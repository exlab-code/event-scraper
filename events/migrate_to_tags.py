#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Migration Script for Tag-Based Categorization

This script migrates existing events to the new tag-based categorization system.
It fetches all events from the Directus database, processes them through the
LLM extraction to generate tag groups, and updates the events in the database.
"""
import json
import requests
import os
import logging
import argparse
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tag_migration.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tag_migration")

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
    """Client for Directus API interactions"""
    
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_all_events(self, limit=100):
        """Get all events from the events collection"""
        events = []
        page = 1
        
        while True:
            url = f"{self.base_url}/items/events?limit={limit}&page={page}"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            batch = response.json().get('data', [])
            if not batch:
                break
            
            events.extend(batch)
            logger.info(f"Retrieved {len(batch)} events (page {page})")
            
            page += 1
            if page > 10:  # Safety limit
                logger.warning("Reached page limit, some events may not be processed")
                break
        
        logger.info(f"Retrieved a total of {len(events)} events")
        return events
    
    def update_event(self, event_id, data):
        """Update an event in the database"""
        url = f"{self.base_url}/items/events/{event_id}"
        
        # Ensure proper encoding of JSON data with German umlauts
        response = requests.patch(
            url, 
            headers=self.headers, 
            data=json.dumps(data, ensure_ascii=False).encode('utf-8')
        )
        
        if response.status_code in (200, 201, 204):
            logger.info(f"Updated event {event_id}")
            return True
        else:
            logger.error(f"Failed to update event {event_id}: {response.status_code}")
            try:
                error_details = response.json()
                logger.error(f"Error details: {error_details}")
            except:
                logger.error(f"Response text: {response.text}")
            return False

class TagMigrator:
    """Handles migration of events to the new tag-based system"""
    
    def __init__(self, directus_client, openai_api_key):
        self.directus = directus_client
        self.client = OpenAI(api_key=openai_api_key)
    
    def process_event(self, event):
        """Process an event to generate tag groups"""
        # Skip events that already have tag_groups
        if event.get('tag_groups') and isinstance(event.get('tag_groups'), dict):
            logger.info(f"Event {event['id']} already has tag_groups, skipping")
            return None
        
        # Prepare event data for LLM
        event_data = {
            "title": event.get('title', ''),
            "description": event.get('description', ''),
            "category": event.get('category', ''),
            "tags": event.get('tags', []),
            "cost": event.get('cost', '')
        }
        
        # Build prompt for LLM
        prompt = self._build_prompt(event_data)
        
        try:
            # Call GPT-4o Mini
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract and categorize tags for events. Return the result as a JSON object."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse response
            llm_response = response.choices[0].message.content
            structured_data = json.loads(llm_response)
            
            # Extract tags and tag_groups
            tags = structured_data.get('tags', [])
            tag_groups = structured_data.get('tag_groups', {})
            
            # If we don't have tag_groups but have tags, create a simple grouping
            if not tag_groups and tags:
                tag_groups = {
                    "topic": tags
                }
            
            # Add "Kostenlos" tag if the event is free
            if (event.get('cost') == 0 or 
                event.get('cost') == '0' or 
                event.get('cost') == 'kostenlos' or 
                event.get('cost') == 'Kostenlos' or 
                event.get('cost') == 'free' or 
                event.get('cost') == 'Free'):
                
                if "Kostenlos" not in tags:
                    tags.append("Kostenlos")
                
                if "cost" not in tag_groups:
                    tag_groups["cost"] = []
                
                if "Kostenlos" not in tag_groups["cost"]:
                    tag_groups["cost"].append("Kostenlos")
            
            # Add "Online" tag if the event is online
            if (event.get('location', '').lower() == 'online' or
                'online' in event.get('location', '').lower() or
                'virtuell' in event.get('location', '').lower() or
                'webinar' in event.get('title', '').lower() or
                'webinar' in event.get('description', '').lower()):
                
                if "Online" not in tags:
                    tags.append("Online")
                
                if "format" not in tag_groups:
                    tag_groups["format"] = []
                
                if "Online" not in tag_groups["format"]:
                    tag_groups["format"].append("Online")
            
            # Prepare update data
            update_data = {
                "tags": tags,
                "tag_groups": tag_groups
            }
            
            return update_data
            
        except Exception as e:
            logger.error(f"Error processing event {event['id']}: {str(e)}")
            return None
    
    def _build_prompt(self, event_data):
        """Build prompt for LLM"""
        prompt = f"""
Extract and categorize tags for this event:

Title: {event_data['title']}
Description: {event_data['description']}
Category: {event_data['category']}
Existing Tags: {', '.join(event_data['tags']) if event_data['tags'] else 'None'}
Cost: {event_data['cost']}

1. Identify relevant tags in these categories:
   - Topics: Main subjects (KI, Datenschutz, etc.)
   - Format: Event type (Workshop, Webinar, etc.)
   - Audience: Target groups (Vereine, Stiftungen, etc.)
   - Cost: Add "Kostenlos" tag if the event is free

2. For each tag:
   - Use proper capitalization (e.g., "KI" not "ki")
   - Format acronyms correctly (e.g., "NGO", "DSGVO")
   - Use title case for multi-word tags (e.g., "Machine Learning")

3. Return:
   - A flat "tags" array with ALL tags
   - A "tag_groups" object organizing tags by category

Example response format:
{{
  "tags": ["KI", "Workshop", "Vereine", "Kostenlos"],
  "tag_groups": {{
    "topic": ["KI"],
    "format": ["Workshop"],
    "audience": ["Vereine"],
    "cost": ["Kostenlos"]
  }}
}}
"""
        return prompt
    
    def migrate_events(self, batch_size=10, dry_run=False):
        """Migrate all events to the new tag-based system"""
        # Get all events
        events = self.directus.get_all_events()
        
        # Process events in batches
        total_events = len(events)
        updated_events = 0
        skipped_events = 0
        failed_events = 0
        
        for i in range(0, total_events, batch_size):
            batch = events[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} events)")
            
            for event in batch:
                # Process event
                update_data = self.process_event(event)
                
                if update_data is None:
                    skipped_events += 1
                    continue
                
                # Update event in database
                if not dry_run:
                    # Log the data being sent for debugging
                    logger.info(f"Updating event {event['id']} with: {json.dumps(update_data, ensure_ascii=False)}")
                    
                    success = self.directus.update_event(event['id'], update_data)
                    if success:
                        updated_events += 1
                    else:
                        failed_events += 1
                else:
                    logger.info(f"[DRY RUN] Would update event {event['id']} with: {json.dumps(update_data, ensure_ascii=False)}")
                    updated_events += 1
        
        # Print summary
        logger.info("\nMigration Summary:")
        logger.info(f"Total events: {total_events}")
        logger.info(f"Updated events: {updated_events}")
        logger.info(f"Skipped events: {skipped_events}")
        logger.info(f"Failed events: {failed_events}")
        
        return updated_events, skipped_events, failed_events

def main():
    parser = argparse.ArgumentParser(description="Migrate events to tag-based categorization")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size for processing")
    parser.add_argument("--dry-run", action="store_true", help="Dry run (don't update database)")
    
    args = parser.parse_args()
    
    logger.info("Starting tag migration")
    
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    migrator = TagMigrator(directus, OPENAI_API_KEY)
    
    # Run migration
    migrator.migrate_events(batch_size=args.batch_size, dry_run=args.dry_run)
    
    logger.info("Migration complete")

if __name__ == "__main__":
    main()
