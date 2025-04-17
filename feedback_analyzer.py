#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Feedback Analyzer for Event Classification

This script uses a meta-LLM approach to analyze feedback data from events that were
incorrectly classified by the primary LLM but later approved by human moderators.
It generates sophisticated rules and patterns that can be used to improve the
primary LLM's performance.
"""
import json
import requests
import argparse
import os
import logging
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("feedback_analysis.log"),
        logging.StreamHandler()  # Also log to console
    ]
)
logger = logging.getLogger("feedback_analyzer")

# Load environment variables from .env file
load_dotenv()

# Configuration
DIRECTUS_URL = os.getenv("DIRECTUS_API_URL", "https://calapi.buerofalk.de")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Validate required environment variables
if not DIRECTUS_TOKEN:
    raise ValueError("DIRECTUS_API_TOKEN environment variable is required")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

class DirectusClient:
    """Client for Directus API interactions to fetch feedback data"""
    
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_feedback_events(self, limit=20):
        """Get events that were marked as not relevant by LLM but approved by users"""
        url = f"{self.base_url}/items/events?filter[_and][][is_relevant][_eq]=false&filter[_and][][approved][_eq]=true&limit={limit}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            events = response.json().get('data', [])
            logger.info(f"Found {len(events)} false negative events (marked not relevant by LLM but approved)")
            
            return events
        except Exception as e:
            logger.error(f"Error fetching feedback events: {str(e)}")
            return []
    
    def get_events_with_feedback_notes(self, limit=20):
        """Get events with explicit feedback notes from moderators"""
        url = f"{self.base_url}/items/events?filter[feedback_notes][_nnull]=true&limit={limit}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            events = response.json().get('data', [])
            logger.info(f"Found {len(events)} events with explicit feedback notes")
            
            return events
        except Exception as e:
            logger.error(f"Error fetching events with feedback notes: {str(e)}")
            return []

class FeedbackAnalyzer:
    """Analyzes feedback data using LLM to generate improved rules and patterns"""
    
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
    
    def analyze_feedback(self, events):
        """Analyze feedback events using LLM to identify patterns and generate rules"""
        if not events:
            logger.warning("No events provided for analysis")
            return None
        
        # Format events for the prompt
        events_text = ""
        for i, event in enumerate(events):
            events_text += f"EVENT {i+1}:\n"
            events_text += f"Title: {event.get('title', 'Unknown')}\n"
            events_text += f"Description: {event.get('description', 'No description')}\n"
            
            # Add tags if available
            if event.get('tags') and len(event.get('tags', [])) > 0:
                events_text += f"Tags: {', '.join(event.get('tags', []))}\n"
            
            # Add feedback notes if available
            if event.get('feedback_notes'):
                events_text += f"Feedback: {event.get('feedback_notes')}\n"
            
            events_text += "\n"
        
        # Create the meta-LLM prompt
        prompt = f"""
You are an expert in pattern recognition and natural language understanding. Your task is to analyze a set of events that our system incorrectly classified as "not relevant" but were later approved by human moderators.

For each event, you'll see:
- Title
- Description
- Tags (if available)
- Feedback notes (if available)

Based on this data, please:
1. Identify common patterns or themes that might explain why these events were misclassified
2. Generate 5-10 specific rules that would help our system better identify similar events in the future
3. Create a concise set of guidelines that capture the essence of what makes these events relevant
4. Suggest modifications to our relevance criteria to reduce false negatives

Here are the events:
{events_text}

Our current relevance criteria are:
- The event MUST EXPLICITLY mention both non-profit/gemeinnützig context AND digital transformation
- Both aspects must be clear: Non-Profit-Bezug UND Digitalisierungsbezug
- General business, technology, or innovation events without explicit non-profit reference are NOT relevant
- In case of doubt (if the non-profit reference is not clear): mark as NOT relevant

Your analysis will be used to improve our event classification system for non-profit digital transformation events.
Please format your response as JSON with the following structure:
{{
  "patterns": ["pattern1", "pattern2", ...],
  "rules": ["rule1", "rule2", ...],
  "guidelines": ["guideline1", "guideline2", ...],
  "criteria_modifications": ["modification1", "modification2", ...],
  "summary": "A brief summary of your analysis"
}}
"""
        
        try:
            # Call the LLM
            response = self.client.chat.completions.create(
                model="gpt-4o",  # Using a more powerful model for meta-analysis
                messages=[
                    {"role": "system", "content": "You are an expert analyst helping to improve an event classification system."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7  # Slightly higher temperature for more creative insights
            )
            
            # Parse the response
            analysis = json.loads(response.choices[0].message.content)
            
            logger.info("Successfully analyzed feedback data")
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing feedback with LLM: {str(e)}")
            return None
    
    def generate_feedback_prompt_section(self, analysis):
        """Generate a section for the main LLM prompt based on the analysis"""
        if not analysis:
            return "No feedback analysis available."
        
        prompt_section = "FEEDBACK ANALYSIS:\n\n"
        
        # Add patterns
        if analysis.get('patterns'):
            prompt_section += "Common patterns in relevant events:\n"
            for pattern in analysis.get('patterns'):
                prompt_section += f"- {pattern}\n"
            prompt_section += "\n"
        
        # Add rules
        if analysis.get('rules'):
            prompt_section += "Rules for identifying relevant events:\n"
            for rule in analysis.get('rules'):
                prompt_section += f"- {rule}\n"
            prompt_section += "\n"
        
        # Add guidelines
        if analysis.get('guidelines'):
            prompt_section += "Guidelines for relevance assessment:\n"
            for guideline in analysis.get('guidelines'):
                prompt_section += f"- {guideline}\n"
            prompt_section += "\n"
        
        # Add criteria modifications
        if analysis.get('criteria_modifications'):
            prompt_section += "Modified relevance criteria:\n"
            for modification in analysis.get('criteria_modifications'):
                prompt_section += f"- {modification}\n"
            prompt_section += "\n"
        
        # Add summary
        if analysis.get('summary'):
            prompt_section += f"Summary: {analysis.get('summary')}\n"
        
        return prompt_section

def main():
    """Main function to run the feedback analyzer"""
    parser = argparse.ArgumentParser(description="Analyze feedback data to improve event classification")
    parser.add_argument("--limit", "-l", type=int, default=20, help="Maximum number of feedback events to analyze")
    parser.add_argument("--output", "-o", default="feedback_analysis.json", help="Output file for the analysis results")
    parser.add_argument("--prompt-output", "-p", default="feedback_prompt_section.txt", help="Output file for the generated prompt section")
    
    args = parser.parse_args()
    
    logger.info("Starting feedback analysis")
    
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    analyzer = FeedbackAnalyzer(OPENAI_API_KEY)
    
    # Get feedback events
    false_negatives = directus.get_feedback_events(args.limit)
    events_with_notes = directus.get_events_with_feedback_notes(args.limit)
    
    # Combine and deduplicate events
    all_events = {}
    for event in false_negatives + events_with_notes:
        event_id = event.get('id')
        if event_id and event_id not in all_events:
            all_events[event_id] = event
    
    combined_events = list(all_events.values())
    logger.info(f"Combined {len(combined_events)} unique events for analysis")
    
    # Analyze feedback
    analysis = analyzer.analyze_feedback(combined_events)
    
    if analysis:
        # Save analysis to file
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved analysis to {args.output}")
        
        # Generate and save prompt section
        prompt_section = analyzer.generate_feedback_prompt_section(analysis)
        with open(args.prompt_output, 'w', encoding='utf-8') as f:
            f.write(prompt_section)
        logger.info(f"Saved prompt section to {args.prompt_output}")
        
        # Print summary
        print("\nFeedback Analysis Summary:")
        print(f"- Analyzed {len(combined_events)} events")
        print(f"- Identified {len(analysis.get('patterns', []))} patterns")
        print(f"- Generated {len(analysis.get('rules', []))} rules")
        print(f"- Created {len(analysis.get('guidelines', []))} guidelines")
        print(f"- Suggested {len(analysis.get('criteria_modifications', []))} criteria modifications")
        print(f"\nAnalysis saved to: {args.output}")
        print(f"Prompt section saved to: {args.prompt_output}")
        print("\nTo use this analysis in the main LLM, add the content of the prompt section file to the feedback section in event_analyzer.py")
    else:
        logger.error("Failed to generate analysis")
        print("Error: Failed to generate analysis. Check the logs for details.")

if __name__ == "__main__":
    main()
