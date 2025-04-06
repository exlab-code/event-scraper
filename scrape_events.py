#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
import re
from urllib.parse import urljoin
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger("event-scraper")

# Self-hosted LLM configuration
LLM_API_URL = "http://localhost:11434/api/generate"  # Default Ollama API URL
LLM_MODEL = "mistral"  # Default model, can be changed to any model available on your server

# Directus configuration
DIRECTUS_URL = "https://calapi.buerofalk.de"
DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o"

# Sources to scrape - using just one source for testing
SOURCES = [
    {
        "name": "Stifter-helfen.de",
        "url": "https://www.hausdesstiftens.org/non-profits/wissen/webinare/",
        "type": "html",
        "event_selector": ".eg-webinare-22-wrapper",
        "link_selector": "a",
        "full_page_selector": ".article-content"
    },

    {
        "name": "Aktion Zivilcourage Weiterbildungsforum Ehrenamt",
        "url": "https://eveeno.com/138543290",
        "type": "html",
        "event_selector": ".event",
        "link_selector": "a",
        "full_page_selector": ".article-content"
    }
]

# Maximum number of events to process for testing
MAX_EVENTS = 3

def get_page_content(url, headers=None):
    """Get content from a URL with error handling."""
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching {url}: {str(e)}")
        return None

def scrape_source(source):
    """Scrape a single source for events, following links to get full details."""
    logger.info(f"Scraping {source['name']} - {source['url']}")
    
    full_event_details = []
    
    # Get the main listing page
    content = get_page_content(source['url'])
    if not content:
        return []
    
    # Parse the listing page
    soup = BeautifulSoup(content, 'html.parser')
    event_elements = soup.select(source['event_selector'])
    
    if not event_elements:
        logger.warning(f"No events found on {source['name']} using selector: {source['event_selector']}")
        return []
    
    # Limit to MAX_EVENTS for testing
    event_elements = event_elements[:MAX_EVENTS]
    
    logger.info(f"Found {len(event_elements)} event listings on {source['name']} (limited to {MAX_EVENTS} for testing)")
    
    # Write raw HTML to file for review
    with open("scraped_listing.html", "w", encoding="utf-8") as f:
        f.write(content)
    
    # Create a file to log all scraped content
    with open("scraped_content.txt", "w", encoding="utf-8") as content_log:
        content_log.write(f"SCRAPING SOURCE: {source['name']} - {source['url']}\n")
        content_log.write("="*80 + "\n\n")
        
        # Process each event listing
        for i, element in enumerate(event_elements):
            content_log.write(f"EVENT {i+1}\n")
            content_log.write("-"*50 + "\n")
            
            # Log the listing text
            listing_text = element.get_text(strip=True, separator=' ')
            content_log.write(f"LISTING TEXT:\n{listing_text}\n\n")
            
            # Find the link to the detail page
            link_element = element.select_one(source['link_selector'])
            if not link_element or not link_element.has_attr('href'):
                content_log.write("NO LINK FOUND\n\n")
                
                # If no link found, use the listing text as fallback
                full_event_details.append({
                    "listing_text": listing_text,
                    "detail_text": None,
                    "url": None
                })
                continue
            
            # Get the full URL
            event_url = urljoin(source['url'], link_element['href'])
            content_log.write(f"EVENT URL: {event_url}\n\n")
            
            # Get the detail page
            logger.info(f"Following link to {event_url}")
            detail_content = get_page_content(event_url)
            
            if not detail_content:
                content_log.write("COULD NOT FETCH DETAIL PAGE\n\n")
                
                # If detail page fails, use the listing text as fallback
                full_event_details.append({
                    "listing_text": listing_text,
                    "detail_text": None,
                    "url": event_url
                })
                continue
            
            # Write detail page HTML to file for review (only the last one to avoid overwriting)
            with open(f"scraped_detail_{i+1}.html", "w", encoding="utf-8") as f:
                f.write(detail_content)
            
            # Parse the detail page
            detail_soup = BeautifulSoup(detail_content, 'html.parser')
            detail_element = detail_soup.select_one(source['full_page_selector'])
            
            if not detail_element:
                # If selector doesn't match, use the whole body
                detail_text = detail_soup.body.get_text(strip=True, separator=' ')
                content_log.write(f"SELECTOR NOT FOUND, USING BODY TEXT\n")
            else:
                detail_text = detail_element.get_text(strip=True, separator=' ')
                
            content_log.write(f"DETAIL TEXT:\n{detail_text}\n\n")
            content_log.write("="*80 + "\n\n")
            
            # Add both the listing and detail text
            full_event_details.append({
                "listing_text": listing_text,
                "detail_text": detail_text,
                "url": event_url
            })
            
            # Be nice to the server - small delay between requests
            time.sleep(2)
    
    logger.info(f"Scraped {len(full_event_details)} events with details from {source['name']}")
    return full_event_details

def clean_json(json_text):
    """Clean and fix common JSON issues from LLM responses."""
    # Step 1: Remove invalid control characters
    json_text = ''.join(c for c in json_text if c >= ' ' or c in '\r\n\t')
    
    # Step 2: Fix escape sequences
    json_text = re.sub(r'(?<!\\)\\n', r'\\n', json_text)
    json_text = re.sub(r'(?<!\\)\\t', r'\\t', json_text)
    
    # Step 3: Normalize all types of quotes
    json_text = json_text.replace('„', '"').replace('"', '"').replace('"', '"')
    json_text = json_text.replace(''', "'").replace(''', "'")
    
    # Step 4: Replace empty string quotes with null
    json_text = re.sub(r':\s*""', r': null', json_text)
    
    # Step 5: Fix trailing commas in arrays and objects (common JSON error)
    json_text = re.sub(r',\s*]', ']', json_text)
    json_text = re.sub(r',\s*}', '}', json_text)
    
    # Step 6: Fix missing commas between array elements or object properties
    # This is more complex and might require a proper JSON parser
    # For now, we'll do a simple fix for common patterns
    json_text = re.sub(r'"\s*"', '", "', json_text)
    json_text = re.sub(r'}\s*{', '}, {', json_text)
    
    # Step 7: Ensure property names are quoted
    def quote_property_names(match):
        prop = match.group(1)
        if prop.startswith('"') and prop.endswith('"'):
            return match.group(0)  # Already quoted
        return f'"{prop}":'
    
    json_text = re.sub(r'([a-zA-Z0-9_]+):', quote_property_names, json_text)
    
    return json_text

def process_with_local_llm(event_details, source_name):
    """Process all event details with a self-hosted language model, optimized for German content."""
    if not event_details:
        return []
    
    # Prepare all events for a single API call
    events_text = ""
    for i, event in enumerate(event_details):
        events_text += f"EVENT {i+1}:\n"
        events_text += f"LISTING PAGE TEXT:\n{event['listing_text']}\n\n"
        
        if event['detail_text']:
            events_text += f"DETAIL PAGE TEXT:\n{event['detail_text']}\n\n"
        
        events_text += f"EVENT URL: {event['url']}\n"
        events_text += "="*50 + "\n\n"
    
    # Log the combined text we're sending to the LLM
    with open("llm_input.txt", "w", encoding="utf-8") as f:
        f.write(events_text)
    
    prompt = """
    Du analysierst Texte von deutscher Webseiten, um Digitalisierungsveranstaltungen fuer gemeinnuetzige Organisationen zu identifizieren und zu extrahieren.
    
    Beruecksichtige nur Veranstaltungen, die fuer die Digitalisierung gemeinnuetziger Organisationen relevant sind! Zielgruppe sind Menschen, die sich mit dem digitalen Wandel in Wohlfahrt und gemeinnützigen Organisationen auseinandersetz. Sei hier bitte strikt!

    Sorge dafür, dass Umlaute richtig formatiert sind. 
    
    WICHTIG: Deine Antwort MUSS valides JSON sein. Verwende KEINE typografischen Anführungszeichen („ oder ") in Strings. Nutze ausschließlich normale ASCII-Anführungszeichen ("). Achte auf korrekte Kommasetzung zwischen Array-Elementen und Objekteigenschaften.


    Extrahiere fuer jede Veranstaltung die folgenden Informationen:
    - title: Der Name der Veranstaltung
    - description: Umfassende Beschreibung (300 Zeichen)
    - start_date: Im ISO-Format (JJJJ-MM-TT) oder JJJJ-MM-TTTHH:MM:SS, wenn die Uhrzeit verfuegbar ist
    - end_date: Im ISO-Format (leer lassen, wenn nicht angegeben)
    - organizer: Die Organisation, die die Veranstaltung durchfuehrt
    - website: Die URL der Veranstaltung
    - cost: Kostenlos, kostenpflichtig oder der spezifische Preis
    - category: Waehle die passendste aus - Digital Fundraising, Datenmanagement, Website-Entwicklung, Social Media, Digitale Transformation, Cloud-Technologie, Cybersicherheit, Datenanalyse, KI fuer gemeinnuetzige Organisationen, Digitales Marketing
    - tags: Relevante Schlagwoerter zur Veranstaltung (als Array von Strings)
    - speaker: Name(n) der Referent(en), falls vorhanden
    - location: Veranstaltungsort (falls physisch) oder "Online" fuer virtuelle Veranstaltungen
    - register_link: Link zur Anmeldung fuer die Veranstaltung (falls verfuegbar)
    - videocall_link: Link zum Videoanruf oder Webinar (falls verfuegbar)
    
    Wenn du ein Feld nicht mit Sicherheit extrahieren kannst, setze es auf null, anstatt zu raten oder leere Strings zu verwenden.
    
    
    Gib deine Antwort als JSON-Array von Veranstaltungsobjekten zurueck, ein Objekt pro Veranstaltung. Achte darauf, dass das JSON syntaktisch korrekt ist.

    Hier sind die zu analysierenden Veranstaltungen:

    """
    
    full_prompt = prompt + events_text
    
    try:
        # Prepare the request for Ollama API
        payload = {
            "model": LLM_MODEL,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 4000
            }
        }
        
        logger.info(f"Sending request to local LLM ({LLM_MODEL}) at {LLM_API_URL}")
        
        # Make the API request
        response = requests.post(LLM_API_URL, json=payload)
        response.raise_for_status()
        
        # Parse the response
        response_data = response.json()
        
        # Log the full response
        with open("llm_response.txt", "w", encoding="utf-8") as f:
            f.write(response_data.get("response", ""))
        
        # Extract content from the response
        content = response_data.get("response", "")
        
        # Find JSON array using regex
        json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
            
            # Apply comprehensive JSON cleaning
            cleaned_json = clean_json(json_text)
            
            # Log the cleaned JSON for debugging
            with open("cleaned_json.txt", "w", encoding="utf-8") as f:
                f.write(cleaned_json)
            
            try:
                # Try to parse the JSON
                processed_events = json.loads(cleaned_json)
                
                # Add source to each event
                for event in processed_events:
                    event['source'] = source_name
                    event['approved'] = False
                
                logger.info(f"Local LLM extracted {len(processed_events)} valid events from {source_name}")
                return processed_events
                    
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON from LLM response: {str(e)}")
                
                # Log the problematic JSON text
                with open("problematic_json.txt", "w", encoding="utf-8") as f:
                    f.write(cleaned_json)
                
                # Try a more aggressive approach - use a JSON repair library or manual fix
                try:
                    # Manual line-by-line approach to find the problematic line
                    lines = cleaned_json.split('\n')
                    for i, line in enumerate(lines):
                        try:
                            # Try to parse each line to identify issues
                            if '{' in line or '[' in line or '}' in line or ']' in line:
                                logger.debug(f"Checking line {i+1}: {line}")
                                # Look for common issues in this line
                                if line.strip().endswith(',') and (lines[i+1].strip().startswith('}') or lines[i+1].strip().startswith(']')):
                                    lines[i] = line.rstrip(',')
                                    logger.debug(f"Fixed trailing comma in line {i+1}")
                        except Exception as line_e:
                            logger.debug(f"Error checking line {i+1}: {str(line_e)}")
                    
                    # Try again with manually fixed JSON
                    fixed_json = '\n'.join(lines)
                    with open("manually_fixed_json.txt", "w", encoding="utf-8") as f:
                        f.write(fixed_json)
                    
                    processed_events = json.loads(fixed_json)
                    
                    # Add source to each event
                    for event in processed_events:
                        event['source'] = source_name
                        event['approved'] = False
                    
                    logger.info(f"Local LLM extracted {len(processed_events)} valid events after manual JSON repair")
                    return processed_events
                    
                except Exception as repair_e:
                    logger.error(f"Failed to repair JSON: {str(repair_e)}")
                    # Return empty list as fallback
                    return []
        else:
            logger.warning("No JSON found in LLM response")
            
    except Exception as e:
        logger.error(f"Error processing with local LLM: {str(e)}")
        logger.exception("Full exception details:")
    
    return []

def save_to_directus(events):
    """Save processed events to Directus."""
    if not events:
        return
        
    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    for event in events:
        # Skip events without title or start_date as they're required for duplicate checking
        if not event.get("title") or not event.get("start_date"):
            logger.warning(f"Skipping event with missing title or start_date: {event}")
            continue
            
        # Check if event already exists
        try:
            # Create a filter to check for duplicate events
            # Convert filter to JSON string for proper URL encoding
            filter_json = json.dumps({
                "_and": [
                    {"title": {"_eq": event.get("title")}},
                    {"start_date": {"_eq": event.get("start_date")}}
                ]
            })
            
            # Use params properly for requests
            check_params = {
                "filter": filter_json
            }
            
            # Log the check request for debugging
            logger.info(f"Checking for duplicate event: {event.get('title')} on {event.get('start_date')}")
            logger.debug(f"Check URL: {DIRECTUS_URL}/items/events with params: {check_params}")
            
            check_url = f"{DIRECTUS_URL}/items/events"
            check_response = requests.get(check_url, headers=headers, params=check_params)
            
            # Log the response for debugging
            logger.debug(f"Check response status: {check_response.status_code}")
            
            if check_response.status_code == 200:
                response_data = check_response.json()
                logger.debug(f"Check response data: {json.dumps(response_data)}")
                
                existing_events = response_data.get("data", [])
                if existing_events and len(existing_events) > 0:
                    logger.info(f"Event already exists: {event.get('title')} on {event.get('start_date')}")
                    continue
                else:
                    logger.info(f"No duplicate found, proceeding to add event")
            else:
                logger.warning(f"Duplicate check failed with status {check_response.status_code}: {check_response.text}")
                # Continue with adding the event even if the check failed
            
            # Add the event to Directus
            response = requests.post(f"{DIRECTUS_URL}/items/events", headers=headers, json=event)
            
            if response.status_code in (200, 201, 204):
                logger.info(f"Added event to Directus: {event.get('title')}")
            else:
                logger.error(f"Error adding event: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Exception saving to Directus: {str(e)}")
            logger.exception("Full exception details:")

def run_scraper():
    """Main function to run the scraper."""
    logger.info("Starting event scraper - TEST MODE (max 3 events)")
    
    for source in SOURCES:
        event_details = scrape_source(source)
        processed_events = process_with_local_llm(event_details, source['name'])
        
        # Log the processed events
        with open("processed_events.json", "w", encoding="utf-8") as f:
            json.dump(processed_events, f, indent=2, ensure_ascii=False)
        
        save_to_directus(processed_events)
    
    logger.info("Test scraping complete")

if __name__ == "__main__":
    run_scraper()
