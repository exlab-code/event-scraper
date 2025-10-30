#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple HumHub ICS Calendar Importer

This script imports events from ICS calendar files defined in config/ics_sources.json
and adds them to the Directus database as unprocessed events.
"""
import os
import json
import requests
import hashlib
import argparse
from datetime import datetime
from icalendar import Calendar
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DIRECTUS_URL = os.getenv("DIRECTUS_API_URL", "https://calapi.buerofalk.de")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_API_TOKEN", "")
CONFIG_PATH = "config/ics_sources.json"

def ensure_config_exists():
    """Create default configuration file if it doesn't exist"""
    config_dir = os.path.dirname(CONFIG_PATH)
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    if not os.path.exists(CONFIG_PATH):
        default_config = {
            "sources": [
                {
                    "name": "HumHub - Civic Data Cafe",
                    "url": "https://community.civic-data.de/ical/humhub-event-3916e1fa-d9ab-44cc-8090-31179a4d/base.ics",
                    "enabled": True
                }
            ]
        }
        
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        print(f"Created default configuration file at {CONFIG_PATH}")

def load_config():
    """Load configuration from file"""
    ensure_config_exists()
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def calculate_hash(content):
    """Calculate MD5 hash of content for deduplication"""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def download_ics(url):
    """Download ICS file from URL"""
    print(f"Downloading ICS file from: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.text

def parse_ics_file(ics_data, source_name, source_url, future_only=True):
    """Parse ICS file and extract events"""
    calendar = Calendar.from_ical(ics_data)
    events = []
    skipped_past_events = 0
    now = datetime.now()
    
    for component in calendar.walk():
        if component.name == "VEVENT":
            # Extract all available event information
            event_data = {}
            
            # Process all properties in the event
            for key, value in component.items():
                # Convert to string or appropriate format
                if key in ['dtstart', 'dtend', 'dtstamp', 'created', 'last-modified']:
                    # Format datetime properly
                    dt = value.dt
                    if isinstance(dt, datetime):
                        try:
                            event_data[key] = dt.isoformat()
                        except:
                            event_data[key] = str(dt)
                    elif hasattr(dt, 'isoformat'):
                        try:
                            event_data[key] = dt.isoformat()
                        except:
                            event_data[key] = str(dt)
                    else:
                        event_data[key] = str(dt)
                else:
                    # Store other properties as strings
                    event_data[key] = str(value)
            
            # Basic required fields with fallbacks
            summary = str(component.get('summary', ''))
            description = str(component.get('description', ''))
            location = str(component.get('location', ''))
            url = str(component.get('url', ''))
            
            # Extract start date/time for filtering
            start_date = component.get('dtstart')
            if start_date and future_only:
                dt = start_date.dt
                # Check if it's a datetime or just a date
                if isinstance(dt, datetime):
                    # Handle timezone-aware vs naive datetime comparison
                    try:
                        # Try direct comparison first
                        is_past = dt < now
                    except TypeError:
                        # If error (comparing offset-naive with offset-aware), convert to UTC
                        if dt.tzinfo is not None:
                            # If dt has timezone but now doesn't, make now timezone-aware
                            from datetime import timezone
                            now_aware = datetime.now(timezone.utc)
                            is_past = dt < now_aware
                        else:
                            # If dt doesn't have timezone but might be in different format
                            is_past = dt.replace(tzinfo=None) < now
                    
                    if is_past:
                        try:
                            time_str = dt.strftime('%Y-%m-%d %H:%M')
                        except:
                            time_str = str(dt)
                        print(f"Skipping past event: {summary} (Start: {time_str})")
                        skipped_past_events += 1
                        continue
                elif hasattr(dt, 'date'):  # For date objects
                    if dt.date() < now.date():
                        print(f"Skipping past event: {summary} (Start: {dt.strftime('%Y-%m-%d')})")
                        skipped_past_events += 1
                        continue
            
            # Create event object with all extracted data
            event = {
                "listing_text": summary,
                "detail_text": description,
                "url": url or source_url,
                "source_name": source_name,
                "location": location,
                "start_date": event_data.get('dtstart', ''),
                "end_date": event_data.get('dtend', ''),
                "uid": event_data.get('uid', ''),
                "ics_data": event_data  # Store all extracted data
            }
            
            # Add to events list
            events.append(event)
            print(f"Found event: {summary}")
    
    return events, skipped_past_events

def save_to_directus(events):
    """Save events to Directus database"""
    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    saved_count = 0
    duplicate_count = 0
    error_count = 0
    
    for event in events:
        # Create content hash for deduplication
        event_json = json.dumps(event, ensure_ascii=False)
        content_hash = calculate_hash(event_json)
        
        # Check if event already exists
        check_url = f"{DIRECTUS_URL}/items/scraped_data"
        params = {
            "filter": json.dumps({
                "content_hash": {
                    "_eq": content_hash
                }
            })
        }
        
        check_response = requests.get(check_url, headers=headers, params=params)
        check_response.raise_for_status()
        
        existing_items = check_response.json().get('data', [])
        if existing_items:
            print(f"Skipping duplicate event: {event['listing_text']}")
            duplicate_count += 1
            continue
        
        # Prepare data for Directus
        now = datetime.now().isoformat()
        
        directus_data = {
            "url": event.get("url"),
            "source_name": event.get("source_name"),
            "content_hash": content_hash,
            "raw_content": json.dumps(event, ensure_ascii=False),
            "scraped_at": now,
            "processed": False,
            "processing_status": "pending"
        }
        
        # Save to Directus
        try:
            response = requests.post(f"{DIRECTUS_URL}/items/scraped_data", headers=headers, json=directus_data)
            response.raise_for_status()
            print(f"Saved event: {event['listing_text']}")
            saved_count += 1
        except Exception as e:
            print(f"Error saving event: {str(e)}")
            error_count += 1
    
    return {
        "saved": saved_count,
        "duplicates": duplicate_count,
        "errors": error_count
    }

def main():
    """Main function"""
    global CONFIG_PATH
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Import events from ICS calendar files")
    parser.add_argument("--config", "-c", default=CONFIG_PATH, help=f"Path to configuration file (default: {CONFIG_PATH})")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Parse events but don't save to database")
    parser.add_argument("--source", "-s", help="Process only the specified source by name")
    parser.add_argument("--file", "-f", help="Import events from a local ICS file instead of using the config")
    parser.add_argument("--future-only", "-F", action="store_true", default=True, 
                        help="Only import future events (default: True)")
    parser.add_argument("--include-past", action="store_false", dest="future_only",
                        help="Include past events in the import")
    parser.add_argument("--source-name", "-n", help="Custom source name for imported events (used with --file)")
    args = parser.parse_args()
    
    # Update config path if specified
    CONFIG_PATH = args.config
    
    print("Starting ICS import...")
    
    # Track overall statistics
    total_saved = 0
    total_duplicates = 0
    total_errors = 0
    total_skipped_past = 0
    
    # Handle local file import if specified
    if args.file:
        try:
            print(f"\nProcessing local file: {args.file}")
            
            # Read ICS file
            with open(args.file, "r", encoding="utf-8") as f:
                ics_data = f.read()
            
            # Use custom source name if provided, otherwise use filename
            if args.source_name:
                source_name = args.source_name
            else:
                source_name = os.path.basename(args.file)
                print(f"No source name provided, using filename: {source_name}")
                print("Tip: Use --source-name to specify a custom source name")
            
            # Parse events
            events, skipped_past = parse_ics_file(ics_data, source_name, f"file://{os.path.abspath(args.file)}", args.future_only)
            print(f"Found {len(events)} events in ICS file")
            total_skipped_past += skipped_past
            
            if not events:
                print(f"No events found in the ICS file")
            else:
                # Save events to Directus (unless dry run)
                if args.dry_run:
                    print(f"Dry run: Would save {len(events)} events to Directus")
                    if args.verbose:
                        for i, event in enumerate(events):
                            print(f"  {i+1}. {event['listing_text']}")
                            if 'start_date' in event and event['start_date']:
                                print(f"      Start: {event['start_date']}")
                            if 'end_date' in event and event['end_date']:
                                print(f"      End: {event['end_date']}")
                            if 'location' in event and event['location']:
                                print(f"      Location: {event['location']}")
                            if 'uid' in event and event['uid']:
                                print(f"      UID: {event['uid']}")
                            if args.verbose and 'ics_data' in event:
                                print(f"      All properties:")
                                for key, value in event['ics_data'].items():
                                    print(f"        {key}: {value}")
                else:
                    print(f"Saving events to Directus...")
                    results = save_to_directus(events)
                    
                    total_saved += results["saved"]
                    total_duplicates += results["duplicates"]
                    total_errors += results["errors"]
        
        except Exception as e:
            print(f"Error processing file '{args.file}': {str(e)}")
            total_errors += 1
        
        # Print summary and exit
        print("\nImport Summary:")
        print(f"Events saved: {total_saved}")
        print(f"Duplicates skipped: {total_duplicates}")
        print(f"Past events skipped: {total_skipped_past}")
        print(f"Errors: {total_errors}")
        print(f"Total events processed: {total_saved + total_duplicates}")
        return
    
    # If no file specified, process sources from config
    config = load_config()
    
    # Process each enabled source
    for source in config.get("sources", []):
        name = source.get("name", "Unknown")
        
        # Skip if source is not enabled
        if not source.get("enabled", True):
            if args.verbose:
                print(f"Skipping disabled source: {name}")
            continue
        
        # Skip if not the specified source (if --source was provided)
        if args.source and args.source.lower() != name.lower():
            if args.verbose:
                print(f"Skipping source {name} (not selected)")
            continue
        
        url = source.get("url")
        if not url:
            print(f"Error: No URL specified for source '{name}'")
            continue
        
        try:
            print(f"\nProcessing source: {name}")
            
            # Download ICS file
            ics_data = download_ics(url)
            
            # Parse events
            events, skipped_past = parse_ics_file(ics_data, name, url, args.future_only)
            print(f"Found {len(events)} events in ICS file for {name}")
            total_skipped_past += skipped_past
            
            if not events:
                print(f"No events found in the ICS file for {name}")
                continue
            
            # Save events to Directus (unless dry run)
            if args.dry_run:
                print(f"Dry run: Would save {len(events)} events from {name} to Directus")
                if args.verbose:
                    for i, event in enumerate(events):
                        print(f"  {i+1}. {event['listing_text']}")
                        if 'start_date' in event and event['start_date']:
                            print(f"      Start: {event['start_date']}")
                        if 'end_date' in event and event['end_date']:
                            print(f"      End: {event['end_date']}")
                        if 'location' in event and event['location']:
                            print(f"      Location: {event['location']}")
                        if 'uid' in event and event['uid']:
                            print(f"      UID: {event['uid']}")
                        if args.verbose and 'ics_data' in event:
                            print(f"      All properties:")
                            for key, value in event['ics_data'].items():
                                print(f"        {key}: {value}")
            else:
                print(f"Saving events from {name} to Directus...")
                results = save_to_directus(events)
                
                total_saved += results["saved"]
                total_duplicates += results["duplicates"]
                total_errors += results["errors"]
            
        except Exception as e:
            print(f"Error processing source '{name}': {str(e)}")
            total_errors += 1
    
    # Print summary
    print("\nImport Summary:")
    print(f"Events saved: {total_saved}")
    print(f"Duplicates skipped: {total_duplicates}")
    print(f"Past events skipped: {total_skipped_past}")
    print(f"Errors: {total_errors}")
    print(f"Total events processed: {total_saved + total_duplicates}")

if __name__ == "__main__":
    main()
