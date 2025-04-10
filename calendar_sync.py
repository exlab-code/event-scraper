#!/usr/bin/env python3
import requests
import caldav
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import dateutil.parser
import logging
import time
import json
import os
import schedule
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/sync.log"), logging.StreamHandler()]
)
logger = logging.getLogger("directus-nextcloud-sync")

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Directus configuration from environment variables
def load_directus_config():
    """Load Directus configuration from environment variables."""
    return {
        "url": os.getenv("DIRECTUS_API_URL"),
        "token": os.getenv("DIRECTUS_API_TOKEN")
    }

# Nextcloud configuration from environment variables
def load_nextcloud_config():
    """Load Nextcloud configuration from environment variables."""
    return {
        "url": os.getenv("NEXTCLOUD_URL"),
        "username": os.getenv("NEXTCLOUD_USERNAME"),
        "password": os.getenv("NEXTCLOUD_PASSWORD"),
        "calendar_name": os.getenv("NEXTCLOUD_CALENDAR_NAME", "nonprofit-events")
    }

# Load configurations
directus_config = load_directus_config()
nextcloud_config = load_nextcloud_config()

# Validate configurations
if not directus_config["url"] or not directus_config["token"]:
    logger.error("Directus configuration is incomplete. Please set DIRECTUS_API_URL and DIRECTUS_API_TOKEN environment variables in the .env file.")
    exit(1)

if not nextcloud_config["url"] or not nextcloud_config["username"] or not nextcloud_config["password"]:
    logger.error("Nextcloud configuration is incomplete. Please set NEXTCLOUD_URL, NEXTCLOUD_USERNAME, and NEXTCLOUD_PASSWORD environment variables in the .env file.")
    exit(1)

def get_directus_events(approved_only=True):
    """Get events from Directus.
    
    Args:
        approved_only (bool): If True, only return approved events
        
    Returns:
        list: List of events from Directus
    """
    headers = {
        "Authorization": f"Bearer {directus_config['token']}"
    }
    
    filter_params = {}
    if approved_only:
        filter_params = {
            "approved": {
                "_eq": True
            }
        }
    
    params = {}
    if filter_params:
        params["filter"] = json.dumps(filter_params)
    
    try:
        response = requests.get(f"{directus_config['url']}/items/events", headers=headers, params=params)
        response.raise_for_status()
        return response.json().get('data', [])
    except Exception as e:
        logger.error(f"Error fetching events from Directus: {str(e)}")
        return []

def create_directus_event(event_data):
    """Create a new event in Directus.
    
    Args:
        event_data (dict): Event data to create
        
    Returns:
        dict: Created event data or None if creation failed
    """
    headers = {
        "Authorization": f"Bearer {directus_config['token']}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(
            f"{directus_config['url']}/items/events", 
            headers=headers, 
            json=event_data
        )
        response.raise_for_status()
        logger.info(f"Created new event in Directus: {event_data.get('title')}")
        return response.json().get('data')
    except Exception as e:
        logger.error(f"Error creating event in Directus: {str(e)}")
        return None

def update_directus_event(event_id, event_data):
    """Update an existing event in Directus.
    
    Args:
        event_id (str): ID of the event to update
        event_data (dict): Updated event data
        
    Returns:
        dict: Updated event data or None if update failed
    """
    headers = {
        "Authorization": f"Bearer {directus_config['token']}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.patch(
            f"{directus_config['url']}/items/events/{event_id}", 
            headers=headers, 
            json=event_data
        )
        response.raise_for_status()
        logger.info(f"Updated event in Directus: {event_data.get('title')}")
        return response.json().get('data')
    except Exception as e:
        logger.error(f"Error updating event in Directus: {str(e)}")
        return None

def get_nextcloud_calendar():
    """Connect to Nextcloud and get the calendar.
    
    Returns:
        tuple: (client, calendar) or (None, None) if connection fails
    """
    try:
        client = caldav.DAVClient(
            url=nextcloud_config["url"],
            username=nextcloud_config["username"],
            password=nextcloud_config["password"]
        )
        
        principal = client.principal()
        calendars = principal.calendars()
        
        # Find or create our calendar
        calendar = None
        for cal in calendars:
            if cal.name == nextcloud_config["calendar_name"]:
                calendar = cal
                logger.info(f"Found existing calendar: {nextcloud_config['calendar_name']}")
                break
        
        if not calendar:
            logger.info(f"Creating new calendar: {nextcloud_config['calendar_name']}")
            calendar = principal.make_calendar(name=nextcloud_config["calendar_name"])
        
        return client, calendar
    except Exception as e:
        logger.error(f"Error connecting to Nextcloud: {str(e)}")
        return None, None

def get_nextcloud_events(calendar):
    """Get all events from Nextcloud calendar.
    
    Args:
        calendar: Nextcloud calendar object
        
    Returns:
        list: List of calendar events
    """
    try:
        events = calendar.events()
        logger.info(f"Found {len(events)} events in Nextcloud calendar")
        return events
    except Exception as e:
        logger.error(f"Error fetching events from Nextcloud: {str(e)}")
        return []

def parse_ical_event(ical_event):
    """Parse an iCalendar event into a dictionary.
    
    Args:
        ical_event: iCalendar event object
        
    Returns:
        dict: Event data or None if parsing fails
    """
    try:
        # Check if ical_event is a string or an object with a data attribute
        if isinstance(ical_event, str):
            ical_data = ical_event
        elif hasattr(ical_event, 'data'):
            ical_data = ical_event.data
        else:
            logger.error(f"Unexpected ical_event type: {type(ical_event)}")
            return None
            
        cal = Calendar.from_ical(ical_data)
        for component in cal.walk():
            if component.name == "VEVENT":
                # Extract UID and check if it's from Directus
                uid = component.get('uid')
                if uid and isinstance(uid, str) and uid.endswith('@directus'):
                    # This is a Directus event, skip it
                    return None
                
                # Extract event data
                event_data = {
                    'title': str(component.get('summary', 'Untitled Event')),
                    'start_date': component.get('dtstart').dt.isoformat(),
                    'approved': False  # New events from Nextcloud are not approved by default
                }
                
                # Add end date if available
                if component.get('dtend'):
                    event_data['end_date'] = component.get('dtend').dt.isoformat()
                
                # Extract description and parse it
                description = component.get('description')
                if description:
                    event_data['description'] = str(description)
                
                # Extract URL if available
                url = component.get('url')
                if url:
                    event_data['website'] = str(url)
                
                # Extract location if available
                location = component.get('location')
                if location:
                    event_data['location'] = str(location)
                
                # Add source information
                event_data['source'] = 'nextcloud'
                
                return event_data
        return None
    except Exception as e:
        logger.error(f"Error parsing iCalendar event: {str(e)}")
        return None

def delete_nextcloud_event(calendar, event):
    """Delete an event from Nextcloud calendar.
    
    Args:
        calendar: Nextcloud calendar object
        event: Event to delete
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        event.delete()
        logger.info(f"Deleted event from Nextcloud calendar")
        return True
    except Exception as e:
        logger.error(f"Error deleting event from Nextcloud: {str(e)}")
        return False

def sync_directus_to_nextcloud():
    """Sync approved events from Directus to Nextcloud calendar."""
    # Get approved events from Directus
    events = get_directus_events(approved_only=True)
    if not events:
        logger.info("No approved events in Directus to sync to Nextcloud")
        return
    
    logger.info(f"Found {len(events)} approved events in Directus to sync to Nextcloud")
    
    # Connect to Nextcloud
    client, calendar = get_nextcloud_calendar()
    if not calendar:
        return
    
    # Get existing events from Nextcloud
    nextcloud_events = get_nextcloud_events(calendar)
    
    # Create a map of existing event UIDs for quick lookup
    existing_uids = {}
    for nc_event in nextcloud_events:
        try:
            cal = Calendar.from_ical(nc_event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    uid = component.get('uid')
                    if uid:
                        existing_uids[str(uid)] = nc_event
        except Exception as e:
            logger.error(f"Error parsing Nextcloud event: {str(e)}")
    
    # Add approved events to calendar
    for event in events:
        event_id = event['id']
        title = event['title']
        
        # Create a unique ID for the event
        uid = f"nonprofit-{event_id}@directus"
        
        # Check if event already exists in calendar
        if uid in existing_uids:
            logger.info(f"Event already exists in calendar: {title}")
            # Remove from existing_uids so we don't delete it later
            existing_uids.pop(uid)
            continue
        
        # Parse dates
        try:
            # Check if start_date exists and is not None
            if 'start_date' not in event or event['start_date'] is None:
                logger.error(f"Event {title} has no start_date, skipping")
                continue
                
            start_date = dateutil.parser.parse(event['start_date'])
            
            # For end_date, use start_date as fallback if end_date is None or missing
            end_date_value = event.get('end_date')
            if end_date_value is None:
                # Default to 1 hour event if no end date
                end_date = start_date + timedelta(hours=1)
                logger.info(f"Event {title} has no end_date, defaulting to 1 hour duration")
            else:
                try:
                    end_date = dateutil.parser.parse(end_date_value)
                except (TypeError, ValueError) as e:
                    # If end_date parsing fails, default to 1 hour event
                    logger.warning(f"Could not parse end_date for event {title}: {str(e)}, defaulting to 1 hour duration")
                    end_date = start_date + timedelta(hours=1)
                    
            # Ensure end_date is not None
            if end_date is None:
                end_date = start_date + timedelta(hours=1)
                logger.warning(f"End date is still None for event {title}, defaulting to 1 hour duration")
                
        except (TypeError, ValueError) as e:
            logger.error(f"Error parsing dates for event {title}: {str(e)}, skipping")
            continue
            
        description = event.get('description', '')
        organizer = event.get('organizer', '')
        website = event.get('website', '')
        cost = event.get('cost', '')
        tags = event.get('tags', [])
        tag_groups = event.get('tag_groups', {})
        
        # Extract tags from the event
        event_tags = []
        
        # Handle tags field (array of strings)
        if tags:
            if isinstance(tags, list):
                # Filter out None values and convert all items to strings
                event_tags.extend([str(tag) for tag in tags if tag is not None])
            elif isinstance(tags, str):
                # Handle comma-separated tags
                event_tags.extend([tag.strip() for tag in tags.split(',')])
        
        # Handle tag_groups field (object with arrays)
        if tag_groups:
            if isinstance(tag_groups, dict):
                # Extract tags from each group
                for group_name, group_tags in tag_groups.items():
                    if isinstance(group_tags, list):
                        # Filter out None values and convert all items to strings
                        event_tags.extend([str(tag) for tag in group_tags if tag is not None])
            elif isinstance(tag_groups, str):
                # It might be a JSON string
                try:
                    parsed_groups = json.loads(tag_groups)
                    if isinstance(parsed_groups, dict):
                        for group_name, group_tags in parsed_groups.items():
                            if isinstance(group_tags, list):
                                # Filter out None values and convert all items to strings
                                event_tags.extend([str(tag) for tag in group_tags if tag is not None])
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse tag_groups as JSON: {tag_groups}")
        
        # Remove duplicates and ensure all tags are strings
        event_tags = [str(tag) for tag in set(event_tags) if tag is not None]
        
        # Log the extracted tags
        if event_tags:
            logger.info(f"Extracted tags for event {title}: {', '.join(event_tags)}")
        
        # Create iCalendar event
        cal = Calendar()
        cal.add('prodid', '-//Non-Profit Events Calendar//EN')
        cal.add('version', '2.0')
        
        ical_event = Event()
        ical_event.add('summary', title)
        
        # Create a detailed description with all event info in German
        full_description = f"{description}\n\n"
        if organizer:
            full_description += f"Veranstalter: {organizer}\n"
        if cost:
            full_description += f"Preis: {cost}\n"
        if event_tags:
            full_description += f"Tags: {', '.join(event_tags)}\n"
        if website:
            full_description += f"Webseite: {website}"
            
        ical_event.add('description', full_description)
        ical_event.add('dtstart', start_date)
        ical_event.add('dtend', end_date)
        ical_event.add('uid', uid)
        
        if website:
            ical_event.add('url', website)
            
        cal.add_component(ical_event)
        
        try:
            calendar.add_event(cal.to_ical())
            logger.info(f"Added event to calendar: {title}")
        except Exception as e:
            logger.error(f"Error adding event {title} to calendar: {str(e)}")
    
    # Delete events from Nextcloud that are no longer approved in Directus
    # These are events with UIDs that start with "nonprofit-" and end with "@directus"
    # but weren't in our approved events list
    for uid, nc_event in existing_uids.items():
        if uid.startswith("nonprofit-") and uid.endswith("@directus"):
            logger.info(f"Deleting event from Nextcloud that is no longer approved in Directus: {uid}")
            delete_nextcloud_event(calendar, nc_event)

def sync_nextcloud_to_directus():
    """Sync events from Nextcloud to Directus."""
    # Connect to Nextcloud
    client, calendar = get_nextcloud_calendar()
    if not calendar:
        return
    
    # Get events from Nextcloud
    nextcloud_events = get_nextcloud_events(calendar)
    if not nextcloud_events:
        logger.info("No events in Nextcloud to sync to Directus")
        return
    
    # Get all events from Directus (including unapproved)
    directus_events = get_directus_events(approved_only=False)
    
    # Create a map of existing Directus events by UID
    directus_events_by_uid = {}
    for event in directus_events:
        uid = f"nonprofit-{event['id']}@directus"
        directus_events_by_uid[uid] = event
    
    # Process each Nextcloud event
    for nc_event in nextcloud_events:
        # Parse the event
        event_data = parse_ical_event(nc_event.data)
        
        # Skip if parsing failed or if it's a Directus event
        if not event_data:
            continue
        
        # Check if this event already exists in Directus
        # We can't easily determine this, so we'll use the title and start date as a heuristic
        existing_event = None
        for d_event in directus_events:
            if (d_event.get('title') == event_data.get('title') and 
                d_event.get('start_date') == event_data.get('start_date')):
                existing_event = d_event
                break
        
        if existing_event:
            # Update existing event if needed
            # For now, we'll skip updates to avoid overwriting Directus data
            logger.info(f"Event already exists in Directus: {event_data.get('title')}")
        else:
            # Create new event in Directus
            logger.info(f"Creating new event in Directus from Nextcloud: {event_data.get('title')}")
            create_directus_event(event_data)

def sync_events():
    """Run a complete two-way sync between Directus and Nextcloud."""
    logger.info("Starting two-way sync between Directus and Nextcloud")
    
    # First sync from Nextcloud to Directus
    # This will add any new events from Nextcloud to Directus (as unapproved)
    logger.info("Syncing from Nextcloud to Directus...")
    sync_nextcloud_to_directus()
    
    # Then sync from Directus to Nextcloud
    # This will add approved events to Nextcloud and remove any that are no longer approved
    logger.info("Syncing from Directus to Nextcloud...")
    sync_directus_to_nextcloud()
    
    logger.info("Two-way sync completed")

def clean_nextcloud_calendar():
    """Remove all events from Nextcloud calendar that are not from Directus."""
    logger.info("Cleaning Nextcloud calendar - removing non-Directus events...")
    
    # Connect to Nextcloud
    client, calendar = get_nextcloud_calendar()
    if not calendar:
        return
    
    # Get existing events from Nextcloud
    nextcloud_events = get_nextcloud_events(calendar)
    if not nextcloud_events:
        logger.info("No events in Nextcloud calendar to clean")
        return
    
    # Get all events from Directus (including unapproved)
    directus_events = get_directus_events(approved_only=False)
    
    # Create a set of Directus event IDs
    directus_event_ids = set()
    for event in directus_events:
        directus_event_ids.add(str(event['id']))
    
    # Count of deleted events
    deleted_count = 0
    
    # Process each Nextcloud event
    for nc_event in nextcloud_events:
        try:
            # Parse the event to get the UID
            cal = Calendar.from_ical(nc_event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    uid = component.get('uid')
                    if uid:
                        # Check if this is a Directus event
                        if uid.startswith("nonprofit-") and uid.endswith("@directus"):
                            # Extract the Directus event ID from the UID
                            event_id = uid.replace("nonprofit-", "").replace("@directus", "")
                            
                            # If this event doesn't exist in Directus, delete it
                            if event_id not in directus_event_ids:
                                logger.info(f"Deleting event from Nextcloud that doesn't exist in Directus: {uid}")
                                delete_nextcloud_event(calendar, nc_event)
                                deleted_count += 1
                        else:
                            # This is not a Directus event, delete it
                            summary = "Unknown"
                            for component in cal.walk():
                                if component.name == "VEVENT":
                                    summary = component.get('summary', 'Unknown')
                                    break
                            
                            logger.info(f"Deleting non-Directus event from Nextcloud: {summary}")
                            delete_nextcloud_event(calendar, nc_event)
                            deleted_count += 1
        except Exception as e:
            logger.error(f"Error processing Nextcloud event: {str(e)}")
    
    logger.info(f"Cleaned Nextcloud calendar - deleted {deleted_count} events")

def main():
    """Main function to run the script."""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Sync events between Directus and Nextcloud")
    parser.add_argument("--clean", action="store_true", help="Clean Nextcloud calendar by removing all non-Directus events")
    parser.add_argument("--sync-once", action="store_true", help="Run sync once and exit (default behavior now)")
    parser.add_argument("--schedule", action="store_true", help="Enable hourly scheduling (disabled by default)")
    args = parser.parse_args()
    
    logger.info("Starting Directus-Nextcloud two-way sync service")
    
    # Clean Nextcloud calendar if requested
    if args.clean:
        clean_nextcloud_calendar()
    
    # Initial sync
    sync_events()
    
    # By default, run once and exit (no scheduling)
    if not args.schedule:
        logger.info("Sync completed. Exiting as scheduled hourly sync is disabled by default.")
        return
    
    # Only set up scheduled sync if explicitly requested
    schedule.every(1).hours.do(sync_events)
    
    logger.info("Sync scheduled to run hourly. Press Ctrl+C to exit.")
    
    try:
        # Keep the script running
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt. Exiting gracefully.")

if __name__ == "__main__":
    main()
