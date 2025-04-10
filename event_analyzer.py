#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Improved Event Analysis App with Feedback Loop

A streamlined application that processes event data from a Directus database
using GPT-4o Mini and stores structured results back to Directus, with enhanced
extraction for dates, times, and links. Includes a feedback loop to improve
relevance determinations based on moderator feedback.
"""
import json
import requests
import argparse
import re
import os
import logging
from datetime import datetime
from openai import OpenAI
from collections import Counter

import os
from dotenv import load_dotenv

# Set up logging - only log to file, not console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("llm_extraction.log")
    ]
)
logger = logging.getLogger("event_extraction")

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
    """Enhanced client for Directus API interactions with feedback support"""
    
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_unprocessed_items(self, limit=10):
        """Get unprocessed items from scraped_data collection"""
        items = []
        page = 1
        page_size = 50
        
        while len(items) < limit:
            url = f"{self.base_url}/items/scraped_data?limit={page_size}&page={page}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            batch = response.json().get('data', [])
            if not batch:
                break
            
            # Filter for unprocessed items
            for item in batch:
                if not item.get('processed', False):
                    items.append(item)
                    if len(items) >= limit:
                        break
            
            page += 1
            if page > 10:  # Safety limit
                break
        
        print(f"Retrieved {len(items)} unprocessed items")
        return items
    
    def update_item_status(self, item_id, success=True, processed_content=None):
        """Update item status in Directus"""
        update_data = {
            "processed": True,
            "processed_at": datetime.now().isoformat(),
            "processing_status": "processed" if success else "failed"
        }
        
        if processed_content:
            update_data["processed_content"] = processed_content
        
        url = f"{self.base_url}/items/scraped_data/{item_id}"
        response = requests.patch(url, headers=self.headers, json=update_data)
        response.raise_for_status()
    
    def save_event(self, event_data):
        """Save processed event to events collection"""
        # Check if event already exists
        filter_params = {
            "filter": {
                "_and": [
                    {"title": {"_eq": event_data.get("title", "")}},
                    {"start_date": {"_eq": event_data.get("start_date", "")}}
                ]
            }
        }
        
        # Convert filter to query string
        filter_json = json.dumps(filter_params["filter"])
        encoded_filter = f"filter={requests.utils.quote(filter_json)}"
        
        # Check for duplicates
        check_url = f"{self.base_url}/items/events?{encoded_filter}"
        check_response = requests.get(check_url, headers=self.headers)
        
        if check_response.status_code == 200:
            existing = check_response.json().get("data", [])
            if existing:
                return False, "duplicate"
        
        # Set default values for approval and feedback
        if "approved" not in event_data:
            event_data["approved"] = None  # Pending approval
        
        # Add the event
        response = requests.post(f"{self.base_url}/items/events", headers=self.headers, json=event_data)
        
        if response.status_code in (200, 201, 204):
            return True, "created"
        else:
            return False, f"Error: {response.status_code}"
    
    def flag_mismatched_events(self):
        """Flag events where LLM determination doesn't match human feedback"""
        print("\nChecking for mismatched events...")
        
        # Get events with feedback
        url = f"{self.base_url}/items/events?filter[relevance_feedback][_nnull]=true&limit=100"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            print("Error fetching events with feedback")
            return
        
        events = response.json().get('data', [])
        mismatches = []
        
        for event in events:
            # Check if the LLM's determination matched the feedback
            llm_determination = event.get('is_relevant', False)
            human_feedback = event.get('relevance_feedback', False)
            
            # If there's a mismatch, add a flag
            if llm_determination != human_feedback:
                event_id = event.get('id')
                title = event.get('title', 'Unknown')
                
                # Add a flag to the event
                update_data = {
                    "mismatch_flag": True,
                    "mismatch_notes": f"LLM said {'relevant' if llm_determination else 'not relevant'} but human said {'relevant' if human_feedback else 'not relevant'}"
                }
                
                update_url = f"{self.base_url}/items/events/{event_id}"
                update_response = requests.patch(update_url, headers=self.headers, json=update_data)
                
                if update_response.status_code in (200, 201, 204):
                    mismatches.append(title)
                    print(f"Flagged mismatch: {title}")
                else:
                    print(f"Error flagging mismatch for event {event_id}: {update_response.status_code}")
        
        if mismatches:
            print(f"\nFlagged {len(mismatches)} mismatched events")
        else:
            print("No mismatches found")
    
    def get_feedback_examples(self, limit=5):
        """Get events with feedback for few-shot learning, focusing on false negatives"""
        # Focus on events that were marked as not relevant by LLM but approved by user
        url = f"{self.base_url}/items/events?filter[_and][][is_relevant][_eq]=false&filter[_and][][approved][_eq]=true&limit={limit}"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return []
        
        events = response.json().get('data', [])
        print(f"Found {len(events)} false negative events (marked not relevant by LLM but approved)")
        
        # Format examples for the prompt
        examples = []
        for event in events:
            examples.append({
                'title': event.get('title', ''),
                'description': event.get('description', ''),
                'is_relevant': True,  # These should be relevant since they were approved
                'reason': event.get('feedback_notes', '') or "Approved by moderator despite being marked as not relevant by LLM"
            })
        
        return examples
    
    def get_feedback_patterns(self):
        """Extract patterns from feedback to create concise rules, focusing on false negatives"""
        # Get events that were marked as not relevant by LLM but approved by user
        url = f"{self.base_url}/items/events?filter[_and][][is_relevant][_eq]=false&filter[_and][][approved][_eq]=true&limit=100"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return []
        
        false_negatives = response.json().get('data', [])
        print(f"Found {len(false_negatives)} false negative events for pattern extraction")
        
        # Extract common terms from false negatives (incorrectly marked as not relevant)
        fn_terms = self._extract_common_terms([
            (e.get('title', '') + ' ' + e.get('description', '')) for e in false_negatives
        ])
        
        # Create concise rules based on patterns
        rules = []
        
        if fn_terms:
            rules.append(f"WICHTIG: Veranstaltungen mit Begriffen wie {', '.join(fn_terms[:5])} sind oft RELEVANT, auch wenn sie nicht explizit 'Non-Profit' erwähnen.")
            
            # Add more specific rules if we have enough examples
            if len(false_negatives) >= 3:
                # Extract organization types that might be relevant
                org_types = set()
                for event in false_negatives:
                    text = (event.get('title', '') + ' ' + event.get('description', '')).lower()
                    if 'verein' in text:
                        org_types.add('Vereine')
                    if 'stiftung' in text:
                        org_types.add('Stiftungen')
                    if 'ngo' in text or 'non-governmental' in text:
                        org_types.add('NGOs')
                    if 'gemeinnützig' in text:
                        org_types.add('gemeinnützige Organisationen')
                    if 'ehrenamt' in text or 'freiwillig' in text:
                        org_types.add('Ehrenamtsorganisationen')
                
                if org_types:
                    rules.append(f"Veranstaltungen für {', '.join(org_types)} sollten als relevant betrachtet werden, wenn sie digitale Themen behandeln.")
        
        return rules
    
    def _extract_common_terms(self, texts, min_count=2, min_length=5):
        """Extract common terms from a list of texts"""
        if not texts:
            return []
            
        # Simple implementation - in practice, use NLP techniques
        all_words = []
        for text in texts:
            if not text:
                continue
            words = re.findall(r'\b\w+\b', text.lower())
            all_words.extend(words)
        
        # Count occurrences
        word_counts = Counter(all_words)
        
        # Return common terms
        return [word for word, count in word_counts.most_common(10) 
                if count >= min_count and len(word) >= min_length]
    
    def get_feedback_stats(self):
        """Get statistics about feedback and LLM performance"""
        # Get counts of events with feedback
        url = f"{self.base_url}/items/events?filter[relevance_feedback][_nnull]=true&aggregate[count]=*"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return {"total": 0, "accuracy": 0}
        
        total_feedback = response.json().get('data', [{}])[0].get('count', 0)
        
        if total_feedback == 0:
            return {"total": 0, "accuracy": 0}
        
        # Get count of correct determinations
        url = f"{self.base_url}/items/events?filter[_and][][is_relevant][_eq]=$relevance_feedback&aggregate[count]=*"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code != 200:
            return {"total": total_feedback, "accuracy": 0}
        
        correct_count = response.json().get('data', [{}])[0].get('count', 0)
        
        return {
            "total": total_feedback,
            "accuracy": correct_count / total_feedback if total_feedback > 0 else 0
        }

# No replacement - removing the CategoryManager class entirely

class GPT4MiniProcessor:
    """Processes event data with GPT-4o Mini with enhanced extraction and feedback loop"""
    
    def __init__(self, api_key, directus_client, feedback_section=""):
        self.client = OpenAI(api_key=api_key)
        self.directus = directus_client
        self.feedback_section = feedback_section  # Store the pre-generated feedback section
        
    # Cache for regex patterns to avoid recompiling
    _reg_link_patterns = [
        # Match href attributes in HTML links
        re.compile(r'(?:Anmeldung|Registrierung).*?href=["\']((https?://)[^\s"\']+)["\']', re.IGNORECASE | re.DOTALL),
        # Match URLs following registration phrases - ensure they start with http:// or https://
        re.compile(r'(?:Zur Anmeldung|Zur Registrierung)[^\w]*?(https?://[^\s]+)', re.IGNORECASE | re.DOTALL),
        # Match URLs following registration words - ensure they start with http:// or https://
        re.compile(r'(?:Anmeldung|Registrierung)[^\w]*?(https?://[^\s]+)', re.IGNORECASE | re.DOTALL)
    ]
    
    # Date and time extraction patterns
    _date_patterns = [
        # ISO format: YYYY-MM-DD
        re.compile(r'(\d{4})-(\d{1,2})-(\d{1,2})'),
        # German format with dots: DD.MM.YYYY or D.M.YYYY or DD.MM.YY
        re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{2,4})'),
        # German format with month name: DD. Month YYYY or D. Month YYYY
        re.compile(r'(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*(\d{2,4})', re.IGNORECASE),
        # German format with abbreviated month: DD. Mon YYYY or D. Mon YYYY
        re.compile(r'(\d{1,2})\.\s*(Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\.?\s*(\d{2,4})', re.IGNORECASE),
        # Date ranges with dash: DD.-DD. Month YYYY
        re.compile(r'(\d{1,2})\.[-–](\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*(\d{2,4})', re.IGNORECASE),
        # Date ranges with "bis": vom DD. bis DD. Month YYYY
        re.compile(r'vom\s+(\d{1,2})\.\s+bis\s+(\d{1,2})\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{2,4})', re.IGNORECASE),
        # Date with weekday: Weekday, DD. Month YYYY
        re.compile(r'(Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|Mo|Di|Mi|Do|Fr|Sa|So),?\s+(\d{1,2})\.\s+(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(\d{2,4})', re.IGNORECASE)
    ]
    
    _time_patterns = [
        # Standard time format: HH:MM or H:MM
        re.compile(r'(\d{1,2}):(\d{2})(?:\s*Uhr)?'),
        # German time format with dots: HH.MM or H.MM
        re.compile(r'(\d{1,2})\.(\d{2})(?:\s*Uhr)?'),
        # Time with just hours: HH Uhr or H Uhr
        re.compile(r'(\d{1,2})\s+Uhr'),
        # Time ranges with dash: HH:MM-HH:MM or HH-HH Uhr
        re.compile(r'(\d{1,2}):?(\d{2})?\s*[-–]\s*(\d{1,2}):?(\d{2})?\s*(?:Uhr)?'),
        # Time ranges with "bis": von HH:MM bis HH:MM Uhr
        re.compile(r'von\s+(\d{1,2}):?(\d{2})?\s+bis\s+(\d{1,2}):?(\d{2})?\s+(?:Uhr)?', re.IGNORECASE),
        # Time with context: Beginn: HH:MM Uhr
        re.compile(r'(?:Beginn|Start|Anfang|Einlass):\s*(\d{1,2}):?(\d{2})?\s*(?:Uhr)?', re.IGNORECASE)
    ]
    
    # Month name to number mapping
    _month_map = {
        'januar': '01', 'jan': '01',
        'februar': '02', 'feb': '02',
        'märz': '03', 'mär': '03', 'maerz': '03',
        'april': '04', 'apr': '04',
        'mai': '05',
        'juni': '06', 'jun': '06',
        'juli': '07', 'jul': '07',
        'august': '08', 'aug': '08',
        'september': '09', 'sep': '09',
        'oktober': '10', 'okt': '10',
        'november': '11', 'nov': '11',
        'dezember': '12', 'dez': '12'
    }
    
    
    def preprocess_event(self, content):
        """Extract key information using regex before GPT processing"""
        extracted_info = {}
        
        # Get text content efficiently
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        
        # Only combine texts if needed for searching
        combined_text = listing_text + " " + detail_text
        
        # Extract registration link using pre-compiled regex
        for pattern in self._reg_link_patterns:
            link_match = pattern.search(combined_text)
            if link_match:
                extracted_info["registration_link"] = link_match.group(1).strip()
                break
        
        return extracted_info
    
    
    def process_event(self, event_data):
        """Process a single event with GPT-4o Mini and enhanced extraction"""
        # Extract raw content
        raw_content = event_data.get('raw_content', '{}')
        if isinstance(raw_content, str):
            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = {"text": raw_content}
        else:
            content = raw_content
        
        # Pre-process to extract dates, times, and links with regex
        extracted_info = self.preprocess_event(content)
        
        # Build prompt with feedback
        prompt = self._build_prompt(content, extracted_info)
        
        try:
            # Get item ID for logging
            item_id_str = event_data.get('id', 'unknown')
            
            # Log the prompt being sent to the LLM
            system_prompt = "Extract structured information from German event descriptions with focus on dates, times, and links. Be VERY strict about relevance criteria - only mark events as relevant if they EXPLICITLY mention both non-profit/gemeinnützig context AND digital transformation."
            
            logger.info(f"\n--- LLM INPUT for item {item_id_str} ---\nSYSTEM PROMPT:\n{system_prompt}\n\nUSER PROMPT:\n{prompt}\n--- END LLM INPUT ---")
            
            # Call GPT-4o Mini
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse response
            llm_response = response.choices[0].message.content
            
            # Log the LLM response for debugging
            logger.info(f"\n--- LLM RESPONSE for item {item_id_str} ---\n{llm_response}\n--- END LLM RESPONSE ---")
            
            # Log specifically the date-related parts if present
            try:
                structured_data = json.loads(llm_response)
                
                # Log the extracted date information
                date_log = f"""
Date extraction for item {item_id_str}:
Title: {structured_data.get('title', 'Unknown')}

LLM EXTRACTION:
  start_date: {structured_data.get('start_date', 'Not found')}
  end_date: {structured_data.get('end_date', 'Not found')}
  start_time: {structured_data.get('start_time', 'Not found')}
  end_time: {structured_data.get('end_time', 'Not found')}
"""
                logger.info(date_log)
                
                # Don't print date extraction to console - only log to file
            except json.JSONDecodeError:
                logger.error("Could not parse LLM response as JSON")
                print("Error: Could not parse LLM response as JSON")
                structured_data = {}
            
            # Only override event_type, and registration_link only if it's a valid URL
            for key, value in extracted_info.items():
                # For registration_link, only override if it's a valid URL and LLM didn't provide one
                if key == 'registration_link':
                    # Validate that it's a proper URL starting with http:// or https://
                    if value and re.match(r'^https?://', value):
                        # Only override if LLM didn't provide a registration link
                        if not structured_data.get(key):
                            structured_data[key] = value
                            logger.info(f"Using regex-extracted registration link: {value}")
                            # Don't print to console - only log to file
                # For other fields like event_type, only override if LLM didn't extract them
                elif value and not structured_data.get(key):
                    structured_data[key] = value
                    logger.info(f"Using regex-extracted {key}: {value}")
                    # Don't print to console - only log to file
            
            # Ensure description is limited to 450 characters
            if 'description' in structured_data and structured_data['description']:
                if len(structured_data['description']) > 450:
                    structured_data['description'] = structured_data['description'][:447] + '...'
            
            # Post-process dates and times if needed
            if 'start_date' in structured_data and structured_data['start_date']:
                # Ensure correct date format (YYYY-MM-DDTHH:MM:00)
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', structured_data['start_date'])
                if date_match:
                    year, month, day = date_match.groups()
                    
                    # Use start_time if available, otherwise default to 00:00
                    time_part = "00:00:00"
                    if 'start_time' in structured_data and structured_data['start_time']:
                        time_match = re.search(r'(\d{1,2}):(\d{2})', structured_data['start_time'])
                        if time_match:
                            hour, minute = time_match.groups()
                            time_part = f"{hour.zfill(2)}:{minute}:00"
                    
                    structured_data['start_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}T{time_part}"
            
            # Also handle end_date if present
            if 'end_date' in structured_data and structured_data['end_date']:
                date_match = re.search(r'(\d{4})-(\d{1,2})-(\d{1,2})', structured_data['end_date'])
                if date_match:
                    year, month, day = date_match.groups()
                    
                    # Use end_time if available, otherwise default to 00:00
                    time_part = "00:00:00"
                    if 'end_time' in structured_data and structured_data['end_time']:
                        time_match = re.search(r'(\d{1,2}):(\d{2})', structured_data['end_time'])
                        if time_match:
                            hour, minute = time_match.groups()
                            time_part = f"{hour.zfill(2)}:{minute}:00"
                    
                    structured_data['end_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}T{time_part}"
                    
            # Check if this is a multi-day, high-cost training event that should be excluded
            is_multi_day = False
            is_high_cost = False
            is_training = False
            
            # Check if it's a multi-day event
            if ('start_date' in structured_data and structured_data['start_date'] and
                'end_date' in structured_data and structured_data['end_date']):
                start_date = datetime.fromisoformat(structured_data['start_date'].replace('Z', '+00:00'))
                end_date = datetime.fromisoformat(structured_data['end_date'].replace('Z', '+00:00'))
                
                # If the event spans multiple days (more than 24 hours)
                if (end_date - start_date).days >= 1:
                    is_multi_day = True
                    logger.info(f"Multi-day event detected: {structured_data.get('title', 'Unknown')}")
            
            # Check if it's a high-cost event
            if 'cost' in structured_data and structured_data['cost']:
                cost_text = structured_data['cost'].lower()
                
                # Look for price indicators
                price_match = re.search(r'(\d+[\.,]?\d*)\s*(?:€|euro|eur)', cost_text)
                if price_match:
                    try:
                        # Extract the price and convert to float
                        price_str = price_match.group(1).replace(',', '.')
                        price = float(price_str)
                        
                        # Consider events costing more than 500€ as high-cost
                        if price > 500:
                            is_high_cost = True
                            logger.info(f"High-cost event detected: {structured_data.get('title', 'Unknown')} - {price}€")
                    except ValueError:
                        # If conversion fails, check for keywords indicating high cost
                        pass
                
                # Check for keywords indicating high cost if no price was found
                if not is_high_cost and any(term in cost_text for term in 
                                           ['kostenpflichtig', 'kostenpflichtiges', 'gebührenpflichtig']):
                    is_high_cost = True
                    logger.info(f"Potentially high-cost event detected: {structured_data.get('title', 'Unknown')}")
            
            # Check if it's a training event
            training_keywords = [
                'training', 'schulung', 'seminar', 'workshop', 'kurs', 'weiterbildung', 
                'fortbildung', 'qualifizierung', 'zertifizierung', 'ausbildung'
            ]
            
            # Check title and description for training keywords
            event_text = (structured_data.get('title', '') + ' ' + 
                         structured_data.get('description', '')).lower()
            
            if any(keyword in event_text for keyword in training_keywords):
                is_training = True
                logger.info(f"Training event detected: {structured_data.get('title', 'Unknown')}")
            
            # Mark as excluded if it meets all criteria
            if is_multi_day and is_high_cost and is_training:
                structured_data['excluded'] = True
                # Make sure it's not marked as pending
                structured_data['status'] = 'excluded'
                logger.info(f"Event marked as EXCLUDED: {structured_data.get('title', 'Unknown')}")
                    
            # If we have a start_date but no end_date, and we have an end_time,
            # use the start_date as the end_date as well (for same-day events)
            if ('start_date' in structured_data and structured_data['start_date'] and
                ('end_date' not in structured_data or not structured_data['end_date']) and
                'end_time' in structured_data and structured_data['end_time']):
                
                # Extract the date part from start_date
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', structured_data['start_date'])
                if date_match:
                    date_part = date_match.group(1)
                    
                    # Use end_time to create end_date
                    time_match = re.search(r'(\d{1,2}):(\d{2})', structured_data['end_time'])
                    if time_match:
                        hour, minute = time_match.groups()
                        time_part = f"{hour.zfill(2)}:{minute}:00"
                        
                        structured_data['end_date'] = f"{date_part}T{time_part}"
            
            # If event_type is present, add it to topics
            if 'event_type' in structured_data and structured_data['event_type']:
                event_type = structured_data['event_type']
                
                # Initialize topics if not present
                if 'topics' not in structured_data or not structured_data['topics']:
                    structured_data['topics'] = [event_type]
                # Add event_type to topics if not already there
                elif event_type not in structured_data['topics']:
                    if isinstance(structured_data['topics'], list):
                        structured_data['topics'].append(event_type)
                    else:
                        # If topics is a string, convert to list
                        structured_data['topics'] = [structured_data['topics'], event_type]
                
                # Remove event_type field as it's now included in topics
                del structured_data['event_type']
            
            # Extract topics as tags if available
            if 'topics' in structured_data and structured_data['topics']:
                # Ensure topics is a list
                topics = structured_data['topics']
                if isinstance(topics, str):
                    # If it's a string, try to parse it as JSON array
                    try:
                        topics = json.loads(topics)
                    except json.JSONDecodeError:
                        # If not valid JSON, split by commas
                        topics = [t.strip() for t in topics.split(',')]
                
                # No need to filter out category names anymore
                
                # Store topics as tags
                structured_data["tags"] = topics
            
            # Remove target_audience field if present
            if 'target_audience' in structured_data:
                del structured_data['target_audience']
            
            # Remove legacy category fields if present
            if 'category' in structured_data:
                del structured_data['category']
            if 'categories' in structured_data:
                del structured_data['categories']
            
            # Add metadata
            structured_data["source"] = content.get("source_name", event_data.get("source_name", "Unknown"))
            structured_data["approved"] = None  # Set to pending approval by default
            
            # Add URL if available
            if content.get("url") and not structured_data.get("website"):
                structured_data["website"] = content.get("url")
            
            # Add token usage info
            token_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
            
            return structured_data, token_usage
            
        except Exception as e:
            print(f"Error processing with GPT: {str(e)}")
            return None, {"total_tokens": 0}
    
    # Cache for prompt templates to avoid rebuilding them each time
    _prompt_template = """
    Analysiere diese Veranstaltungsinformation und extrahiere strukturierte Daten:
    
    {extracted_info}
    LISTING TEXT:
    {listing_text}
    
    DETAIL TEXT:
    {detail_text}
    
    URL: {url}
    
    
    
    Extrahiere die folgenden Informationen im JSON Format:
    - title: Der Titel der Veranstaltung
    - description: Eine prägnante Beschreibung (MAXIMAL 450 Zeichen). Fokussiere auf die wichtigsten Informationen.
    - start_date: Startdatum im ISO-Format (YYYY-MM-DD)
    - start_time: Startzeit (HH:MM)
    - end_date: Enddatum falls angegeben
    - end_time: Endzeit falls angegeben
    - location: Physischer Ort oder "Online"
    - organizer: Die Organisation, die die Veranstaltung durchführt
    - tags: Schlagwörter für die Veranstaltung (Array von Strings). Extrahiere relevante Tags in diesen Kategorien:
      * Themen-Tags: ALLGEMEINE Hauptthemen der Veranstaltung (z.B. KI, Datenschutz, Social Media)
      * Format-Tags: Art der Veranstaltung (z.B. Workshop, Webinar, Konferenz)
      * Zielgruppen-Tags: Für wen ist die Veranstaltung gedacht (z.B. Vereine, Stiftungen)
      * Kosten-Tags: Füge "Kostenlos" hinzu, wenn die Veranstaltung kostenlos ist
    - tag_groups: Organisiere die Tags nach Kategorien (Objekt mit Arrays):
      * topic: Themen-Tags
      * format: Format-Tags
      * audience: Zielgruppen-Tags
      * cost: Kosten-Tags
    - cost: Preisinformationen oder "Kostenlos"
    - registration_link: URL für die Anmeldung falls verfügbar
    - is_relevant: Boolean (true/false) ob die Veranstaltung relevant ist
    - status: Leer oder "excluded" (je nach Status der Veranstaltung)
    
    Wichtig für Tags:
    - Verwende ALLGEMEINE, WIEDERVERWENDBARE Tags statt zu spezifischer Begriffe
    - Beschränke dich auf MAXIMAL 5 Tags pro Veranstaltung
    - Verwende KONSISTENTE TERMINOLOGIE für Konzepte:
      * Verwende "KI" statt "Künstliche Intelligenz" oder "Artificial Intelligence"
      * Verwende "DSGVO" statt "Datenschutz-Grundverordnung"
      * Verwende "NGO" statt "Nichtregierungsorganisation"
    - WICHTIG: Füge IMMER den Tag "Online" hinzu, wenn die Veranstaltung virtuell stattfindet
      * Dies gilt für alle Webinare, virtuelle Konferenzen, Online-Workshops, etc.
      * Der "Online" Tag muss ZUSÄTZLICH zum spezifischen Format-Tag (z.B. "Webinar", "Workshop") hinzugefügt werden
    - Verwende korrekte Groß-/Kleinschreibung (z.B. "KI" statt "ki")
    - Formatiere Akronyme korrekt (z.B. "NGO", "DSGVO")
    - Verwende Title Case für mehrere Wörter (z.B. "Machine Learning")
    - Füge "Kostenlos" als Tag hinzu, wenn die Veranstaltung kostenlos ist
    
    Wichtig für Datumsformate:
    - Nutze YYYY-MM-DD für Datumsangaben und HH:MM für Zeitangaben
    - SUCHE INTENSIV nach Datums- und Zeitangaben in allen möglichen deutschen Formaten:
      * Numerische Formate: "08.04.2025", "8.4.25", "08/04/2025"
      * Mit Monatsnamen: "8. April 2025", "8.Apr.2025"
      * Mit Wochentagen: "Montag, 8. April", "Mo, 08.04."
      * Zeiträume: "8.-10. April", "vom 8. bis 10. April", "30.04.-02.05."
      * Unvollständige Angaben: "8. April" (ohne Jahr), "April 2025" (nur Monat)
      * Uhrzeiten: "14:00", "14 Uhr", "14.00 Uhr", "14-16 Uhr", "von 14 bis 16 Uhr"
      * Kontextangaben: "Einlass 18:30, Beginn 19 Uhr", "vormittags", "abends"

    - Standardwerte für ungenaue Zeitangaben:
      * "Vormittag" → 10:00, "Mittag" → 12:00, "Nachmittag" → 14:00, "Abend" → 19:00
      * "Ganztägig" → start_time: 09:00, end_time: 17:00

    - Prioritätsregeln:
      * Bei mehreren Zeitangaben: Priorisiere "Beginn", "Start" über "Einlass", "Türöffnung"
      * Bei widersprüchlichen Daten: Wähle das Datum näher an Zeitangaben
      * Bei fehlenden Jahren: Verwende aktuelles Jahr, wenn Datum in der Zukunft liegt
      * Bei Datumsformaten wie 01.02.2025: Interpretiere als Tag.Monat.Jahr (europäisch)

    - Beispiele:
      * "Workshop am Montag, 8. April 2025, 14-16 Uhr"
        → start_date: "2025-04-08", start_time: "14:00", end_date: "2025-04-08", end_time: "16:00"
      * "Konferenz vom 8. bis 10. April 2025, täglich 9-17 Uhr"
        → start_date: "2025-04-08", start_time: "09:00", end_date: "2025-04-10", end_time: "17:00"
      * "Vortrag am 8.4., Einlass 18:30 Uhr, Beginn 19 Uhr"
        → start_date: "2025-04-08", start_time: "19:00" (nicht Einlasszeit)
    
    Relevanzkriterien (WICHTIG - STRENG ANWENDEN):
    - Die Veranstaltung MUSS EINDEUTIG für Non-Profit-Organisationen oder den gemeinnützigen Sektor relevant sein
      UND gleichzeitig einen klaren Bezug zu digitaler Transformation haben
    - Beide Aspekte müssen klar erkennbar sein: Non-Profit-Bezug UND Digitalisierungsbezug
    - Allgemeine Business-, Technologie- oder Innovationsveranstaltungen ohne expliziten Non-Profit-Bezug
      sind NICHT relevant, selbst wenn sie digitale Themen behandeln
    - Im Zweifelsfall (wenn der Non-Profit-Bezug nicht eindeutig ist): als NICHT relevant markieren
    
    {feedback_section}

    Ausschlusskriterien für "excluded" Status:
    - Markiere Veranstaltungen als "excluded" (Feld "status" auf "excluded" setzen), wenn ALLE diese Kriterien erfüllt sind:
      1. Mehrtägige Veranstaltung (Zeitraum über mehrere Tage)
      2. Hohe Kosten (mehr als 500€)
      3. Schulungs- oder Trainingscharakter (z.B. Workshop, Seminar, Kurs, Zertifizierung, Ausbildung)
    - Diese Veranstaltungen werden automatisch aus dem Moderationsprozess ausgeschlossen

    Liefere nur gültiges JSON zurück. Nutze null für unbekannte Felder.
    """
    
    def _extract_date_time_info(self, text):
        """Extract date and time information from text using regex patterns"""
        extracted_info = {}
        current_year = datetime.now().year
        
        # Extract dates
        start_date = None
        end_date = None
        
        # Try to find dates with ISO format first (YYYY-MM-DD)
        for match in self._date_patterns[0].finditer(text):
            year, month, day = match.groups()
            date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            if not start_date:
                start_date = date_str
            elif not end_date:
                # If we already have a start date, this is an end date
                end_date = date_str
        
        # If no ISO dates found, try German format with dots (DD.MM.YYYY)
        if not start_date:
            for match in self._date_patterns[1].finditer(text):
                day, month, year = match.groups()
                # Handle 2-digit years
                if len(year) == 2:
                    year = f"20{year}"
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                if not start_date:
                    start_date = date_str
                elif not end_date:
                    end_date = date_str
        
        # If still no dates, try German format with month names
        if not start_date:
            for match in self._date_patterns[2].finditer(text):
                day, month_name, year = match.groups()
                month_num = self._month_map.get(month_name.lower(), "01")
                # Handle 2-digit years or missing years
                if not year:
                    year = str(current_year)
                elif len(year) == 2:
                    year = f"20{year}"
                date_str = f"{year}-{month_num}-{day.zfill(2)}"
                if not start_date:
                    start_date = date_str
                elif not end_date:
                    end_date = date_str
        
        # Try abbreviated month names
        if not start_date:
            for match in self._date_patterns[3].finditer(text):
                day, month_abbr, year = match.groups()
                month_num = self._month_map.get(month_abbr.lower(), "01")
                # Handle 2-digit years or missing years
                if not year:
                    year = str(current_year)
                elif len(year) == 2:
                    year = f"20{year}"
                date_str = f"{year}-{month_num}-{day.zfill(2)}"
                if not start_date:
                    start_date = date_str
                elif not end_date:
                    end_date = date_str
        
        # Extract times
        start_time = None
        end_time = None
        
        # Standard time format (HH:MM)
        for match in self._time_patterns[0].finditer(text):
            hour, minute = match.groups()
            time_str = f"{hour.zfill(2)}:{minute}"
            if not start_time:
                start_time = time_str
            elif not end_time:
                end_time = time_str
        
        # German time format with dots (HH.MM)
        if not start_time:
            for match in self._time_patterns[1].finditer(text):
                hour, minute = match.groups()
                time_str = f"{hour.zfill(2)}:{minute}"
                if not start_time:
                    start_time = time_str
                elif not end_time:
                    end_time = time_str
        
        # Time with just hours (HH Uhr)
        if not start_time:
            for match in self._time_patterns[2].finditer(text):
                hour = match.group(1)
                time_str = f"{hour.zfill(2)}:00"
                if not start_time:
                    start_time = time_str
                elif not end_time:
                    end_time = time_str
        
        # Time with context (Beginn: HH:MM)
        if not start_time:
            for match in self._time_patterns[5].finditer(text):
                hour = match.group(1)
                minute = match.group(2) or "00"
                time_str = f"{hour.zfill(2)}:{minute}"
                start_time = time_str
        
        # Add extracted information to result
        if start_date:
            extracted_info["start_date"] = start_date
        if end_date:
            extracted_info["end_date"] = end_date
        if start_time:
            extracted_info["start_time"] = start_time
        if end_time:
            extracted_info["end_time"] = end_time
        
        # Log what we found
        if extracted_info:
            logger.info(f"Pre-extracted date/time info: {extracted_info}")
        
        return extracted_info
    
    def _build_prompt(self, content, extracted_info=None):
        """Build prompt for GPT-4o Mini with extracted information and feedback"""
        # Get text content efficiently
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        url = content.get("url", "")
        
        # Extract date/time information before truncation
        date_time_info = self._extract_date_time_info(listing_text + " " + detail_text)
        if date_time_info and not extracted_info:
            extracted_info = date_time_info
        elif date_time_info and extracted_info:
            extracted_info.update(date_time_info)
        
        # Less aggressive trimming for texts to preserve more content
        # Increase limits to retain more information while still managing token usage
        if len(listing_text) > 3000:
            listing_text = listing_text[:3000] + "..."
        if len(detail_text) > 4000:
            detail_text = detail_text[:4000] + "..."
        
        # Add pre-extracted information if available
        extracted_info_str = ""
        if extracted_info:
            extracted_info_str = "BEREITS EXTRAHIERTE INFORMATIONEN:\n"
            for key, value in extracted_info.items():
                extracted_info_str += f"- {key}: {value}\n"
            extracted_info_str += "\n"
        
        # Use the pre-generated feedback section
        feedback_section = self.feedback_section
        
        # Use the template with format() for better performance than f-strings with large text
        prompt = self._prompt_template.format(
            extracted_info=extracted_info_str,
            listing_text=listing_text,
            detail_text=detail_text,
            url=url,
            categories_info="",  # No longer using categories
            feedback_section=feedback_section
        )
        
        return prompt

def process_events(limit=10, batch_size=3):
    """Main processing function with optimized feedback"""
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    
    print("\n--- LOADING FEEDBACK ANALYSIS ---")
    
    # Load the feedback section from the feedback_analyzer.py output
    try:
        with open("feedback_prompt_section.txt", "r", encoding="utf-8") as f:
            feedback_section = f.read()
        print("Successfully loaded feedback analysis from feedback_prompt_section.txt")
    except FileNotFoundError:
        feedback_section = ""
        print("Warning: feedback_prompt_section.txt not found. Run feedback_analyzer.py first.")
    
    print("--- FEEDBACK ANALYSIS LOADED ---\n")
    
    # Initialize processor with pre-generated feedback section
    gpt = GPT4MiniProcessor(OPENAI_API_KEY, directus, feedback_section)
    
    # Get unprocessed items
    items = directus.get_unprocessed_items(limit)
    
    if not items:
        print("No unprocessed items found")
        return
    
    # Process statistics
    processed = 0
    duplicates = 0
    errors = 0
    total_tokens = 0
    
    # OPTIMIZATION 4: Process in smaller batches for better memory usage
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} items)")
        
        batch_results = []  # Store batch results to reduce API calls
        
        for item in batch:
            item_id = item.get('id')
            
            # Process with GPT
            structured_data, token_usage = gpt.process_event(item)
            total_tokens += token_usage["total_tokens"]
            
            if not structured_data:
                print(f"Failed to process item {item_id}")
                directus.update_item_status(item_id, success=False)
                errors += 1
                continue
            
            # Add to batch results
            batch_results.append({
                'item_id': item_id,
                'structured_data': structured_data
            })
        
        # OPTIMIZATION 5: Process batch results together
        for result in batch_results:
            item_id = result['item_id']
            structured_data = result['structured_data']
            
            # If this is an excluded event, update the status
            if structured_data.get('excluded', False):
                structured_data['status'] = 'excluded'
            
            # Save all events to Directus, but mark them as pending approval
            structured_data["approved"] = None  # Pending approval
            
            # Save to events collection
            success, status = directus.save_event(structured_data)
            
            # Format event information for console output
            title = structured_data.get('title', 'Unknown')
            date = structured_data.get('start_date', 'No date')
            if date and len(date) > 10:  # Truncate ISO date to just YYYY-MM-DD
                date = date[:10]
            
            relevance = "✓ Relevant" if structured_data.get('is_relevant', False) else "✗ Not Relevant"
            event_status = "EXCLUDED" if structured_data.get('status') == 'excluded' else "Pending"
            
            # Print a single, well-formatted line for each event
            if success:
                processed += 1
                print(f"✓ {title} | {date} | {relevance} | Status: {event_status}")
            elif status == "duplicate":
                duplicates += 1
                print(f"↺ Duplicate: {title}")
            else:
                errors += 1
                print(f"✗ Error: {title} - {status}")
            
            # Update item status
            processed_content = json.dumps(structured_data, ensure_ascii=False)
            directus.update_item_status(item_id, success=True, processed_content=processed_content)
    
    # Calculate cost (approx. $0.15 per 1M tokens)
    cost = (total_tokens / 1_000_000) * 0.15
    
    # Print summary
    print("\nProcessing Summary:")
    print(f"Processed: {processed}")
    print(f"Duplicates: {duplicates}")
    print(f"Errors: {errors}")
    print(f"Total tokens: {total_tokens}")
    print(f"Estimated cost: ${cost:.4f}")
    
    # Print feedback information
    print("\nFeedback: Using analysis from feedback_analyzer.py")

def main():
    parser = argparse.ArgumentParser(description="Process events with enhanced extraction and feedback loop")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum number of items to process")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size for processing")
    parser.add_argument("--flag-mismatches", "-f", action="store_true", help="Flag events where LLM determination doesn't match human feedback")
    parser.add_argument("--only-flag", "-o", action="store_true", help="Only flag mismatches without processing new events")
    parser.add_argument("--log-file", default="llm_extraction.log", help="Path to log file for LLM extraction results")
    
    args = parser.parse_args()
    
    # Configure log file if specified
    if args.log_file != "llm_extraction.log":
        for handler in logger.handlers:
            if isinstance(handler, logging.FileHandler):
                handler.close()
                logger.removeHandler(handler)
        
        file_handler = logging.FileHandler(args.log_file)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
    logger.info(f"Starting event processing with limit={args.limit}, batch_size={args.batch}")
    
    # Initialize Directus client
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    
    # If only flagging mismatches, skip processing
    if args.only_flag:
        directus.flag_mismatched_events()
        return
    
    # Process events
    process_events(limit=args.limit, batch_size=args.batch)
    
    # Flag mismatches if requested
    if args.flag_mismatches:
        directus.flag_mismatched_events()

if __name__ == "__main__":
    main()
