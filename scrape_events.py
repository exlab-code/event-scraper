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

def extract_event_info_from_text(text, event_url):
    """Extract event information from unstructured text when JSON parsing fails."""
    logger.info("Attempting to extract event information from unstructured text")
    
    # Initialize event with default values
    event = {
        "title": None,
        "description": None,
        "start_date": None,
        "end_date": None,
        "organizer": None,
        "website": event_url,
        "cost": None,
        "category": "Digitale Transformation",  # Default category
        "tags": [],
        "speaker": None,
        "location": "Online",  # Default location
        "register_link": None,
        "videocall_link": None,
        "approved": False
    }
    
    # Based on the log output, we can see the descriptions contain the title at the beginning
    # Extract the first part of the description as the title
    first_line_match = re.match(r'^([^0-9\n]{10,100})', text.strip())
    if first_line_match:
        event["title"] = first_line_match.group(1).strip()
    
    # If we still don't have a title, try other patterns
    if not event["title"]:
        # Look for patterns like "KI-Werkzeuge für Non-Profits"
        title_match = re.search(r'([A-Z][^0-9\n]{10,100}?)(?:\s+[A-Z][a-z]+\s+[A-Z][a-z]+|$)', text)
        if title_match:
            event["title"] = title_match.group(1).strip()
    
    # If we still don't have a title, extract from URL
    if not event["title"] and event_url:
        # Extract from URL path, e.g., "ki-werkzeuge-fuer-non-profits" from URL
        url_title_match = re.search(r'/([^/]+)/?$', event_url)
        if url_title_match:
            url_title = url_title_match.group(1).replace('-', ' ').replace('und', '&')
            # Capitalize first letter of each word
            event["title"] = ' '.join(word.capitalize() for word in url_title.split())
    
    # Extract Unix timestamps - looking at the description, there are Unix timestamps
    timestamp_matches = re.findall(r'\b(\d{10})\b', text)
    if len(timestamp_matches) >= 2:
        try:
            # Convert Unix timestamp to ISO date format
            timestamp = int(timestamp_matches[0])
            event["start_date"] = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            
            # If there's a second timestamp, it might be the end date
            if len(timestamp_matches) > 2:
                end_timestamp = int(timestamp_matches[2])  # The third timestamp might be the end time
                event["end_date"] = datetime.fromtimestamp(end_timestamp).strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Failed to parse Unix timestamp: {str(e)}")
    
    # If we still don't have a date, try other patterns
    if not event["start_date"]:
        # Extract date - look for date patterns
        date_patterns = [
            r'(\d{1,2}\.\d{1,2}\.\d{4})',  # DD.MM.YYYY
            r'(\d{4}-\d{2}-\d{2})',        # YYYY-MM-DD
            r'(\d{1,2}\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*\d{4})'  # DD. Month YYYY
        ]
        
        for pattern in date_patterns:
            date_match = re.search(pattern, text)
            if date_match:
                date_str = date_match.group(1)
                # Try to convert to ISO format
                try:
                    if '.' in date_str and not date_str.endswith('.'):
                        # DD.MM.YYYY format
                        parts = date_str.split('.')
                        if len(parts) == 3:
                            event["start_date"] = f"{parts[2].strip()}-{parts[1].strip().zfill(2)}-{parts[0].strip().zfill(2)}"
                    elif '-' in date_str:
                        # Already in YYYY-MM-DD format
                        event["start_date"] = date_str
                    else:
                        # Try to parse month name
                        month_map = {
                            'Januar': '01', 'Februar': '02', 'März': '03', 'April': '04',
                            'Mai': '05', 'Juni': '06', 'Juli': '07', 'August': '08',
                            'September': '09', 'Oktober': '10', 'November': '11', 'Dezember': '12'
                        }
                        for month_name, month_num in month_map.items():
                            if month_name in date_str:
                                day = re.search(r'(\d{1,2})\.', date_str).group(1).zfill(2)
                                year = re.search(r'(\d{4})', date_str).group(1)
                                event["start_date"] = f"{year}-{month_num}-{day}"
                                break
                except Exception as e:
                    logger.warning(f"Failed to parse date: {date_str} - {str(e)}")
                
                break
    
    # If we still don't have a start date, use today's date as a fallback
    if not event["start_date"]:
        event["start_date"] = datetime.now().strftime('%Y-%m-%d')
        logger.warning(f"Using today's date as fallback for event: {event['title']}")
    
    # Extract speaker - looking at the description, there are names after the title
    speaker_match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?', text)
    if speaker_match:
        event["speaker"] = speaker_match.group(0).strip()
    
    # Extract organizer - look for organization names after speaker names
    org_match = re.search(r'(?:' + (event["speaker"] or '') + r')\s+([A-Z][^\n\.]{3,50})', text)
    if org_match:
        event["organizer"] = org_match.group(1).strip()
    else:
        # Try other patterns
        org_patterns = [
            r'(?:Veranstalter|Anbieter|Organisator):\s*([^\n]+)',
            r'(?:von|durch|präsentiert von)\s+([A-Z][^\n.]+)',
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})'  # Look for capitalized words that might be organization names
        ]
        
        for pattern in org_patterns:
            org_match = re.search(pattern, text, re.IGNORECASE)
            if org_match:
                potential_org = org_match.group(1).strip()
                # Check if it's not just a common word
                if len(potential_org) > 3 and not re.match(r'^(Der|Die|Das|Ein|Eine|Zum|Zur)$', potential_org, re.IGNORECASE):
                    event["organizer"] = potential_org
                    break
    
    # Extract cost information
    cost_match = re.search(r'(?:Kosten|Preis|Gebühr):\s*([^\n]+)', text, re.IGNORECASE)
    if cost_match:
        event["cost"] = cost_match.group(1).strip()
    elif 'kostenlos' in text.lower() or 'kostenfrei' in text.lower():
        event["cost"] = "Kostenlos"
    
    # Clean up the description - take a more focused chunk of text
    # First, try to find a proper description section
    desc_match = re.search(r'(?:Beschreibung|Inhalt|Über):\s*([^\n]+(?:\n[^\n]+){0,5})', text, re.IGNORECASE)
    if desc_match:
        event["description"] = desc_match.group(1).strip()
    else:
        # If no specific description section, take a cleaner portion of the text
        # Skip navigation elements and headers that appear in the scraped content
        clean_text = re.sub(r'Zur Hauptnavigation springen.*?Webseite durchsuchen', '', text, flags=re.DOTALL)
        clean_text = re.sub(r'Stiftungen Philanthropie.*?Engagement', '', clean_text, flags=re.DOTALL)
        
        # Take the first 300 characters of the cleaned text
        if clean_text.strip():
            event["description"] = clean_text.strip()[:300]
        else:
            # Fallback to the first 300 characters of the original text
            event["description"] = text[:300].strip()
    
    # Extract registration link
    reg_match = re.search(r'(?:Anmeldung|Registrierung):\s*(https?://[^\s]+)', text, re.IGNORECASE)
    if reg_match:
        event["register_link"] = reg_match.group(1).strip()
    elif event_url:
        event["register_link"] = event_url
    
    # Extract tags based on keywords
    keywords = [
        "Digital", "Online", "Webinar", "Workshop", "Digitalisierung", "Transformation",
        "Nonprofit", "gemeinnützig", "Wohlfahrt", "Ehrenamt", "Fundraising", "Daten",
        "Website", "Social Media", "Cloud", "Cyber", "KI", "Marketing"
    ]
    
    for keyword in keywords:
        if re.search(r'\b' + keyword + r'\b', text, re.IGNORECASE):
            event["tags"].append(keyword)
    
    # Determine category based on keywords
    category_keywords = {
        "Digital Fundraising": ["Fundraising", "Spenden", "Finanzierung"],
        "Datenmanagement": ["Daten", "Datenbank", "CRM"],
        "Website-Entwicklung": ["Website", "Webseite", "Homepage"],
        "Social Media": ["Social Media", "Facebook", "Instagram", "Twitter"],
        "Digitale Transformation": ["Transformation", "Digitalisierung", "digital"],
        "Cloud-Technologie": ["Cloud", "Server", "Online-Speicher"],
        "Cybersicherheit": ["Sicherheit", "Cyber", "Datenschutz"],
        "Datenanalyse": ["Analyse", "Auswertung", "Statistik"],
        "KI fuer gemeinnuetzige Organisationen": ["KI", "Künstliche Intelligenz", "AI"],
        "Digitales Marketing": ["Marketing", "Werbung", "Kommunikation"]
    }
    
    for category, keywords in category_keywords.items():
        for keyword in keywords:
            if re.search(r'\b' + keyword + r'\b', text, re.IGNORECASE):
                event["category"] = category
                break
        if event["category"] != "Digitale Transformation":  # If we've changed from default
            break
    
    # Log the extracted event for debugging
    logger.info(f"Extracted event: {event['title']} on {event['start_date']}")
    
    return event

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
    
    # Create a JSON template to guide the model
    json_template = """
[
  {
    "title": "Name der Veranstaltung",
    "description": "Beschreibung der Veranstaltung",
    "start_date": "YYYY-MM-DD",
    "end_date": null,
    "organizer": "Name der Organisation",
    "website": "https://example.com",
    "cost": "Kostenlos",
    "category": "Digitale Transformation",
    "tags": ["tag1", "tag2"],
    "speaker": "Name des Referenten",
    "location": "Online",
    "register_link": "https://example.com/register",
    "videocall_link": null
  }
]
"""
    
    prompt = f"""
Du analysierst Texte von deutscher Webseiten, um Digitalisierungsveranstaltungen fuer gemeinnuetzige Organisationen zu identifizieren und zu extrahieren.

Beruecksichtige nur Veranstaltungen, die fuer die Digitalisierung gemeinnuetziger Organisationen relevant sind! Zielgruppe sind Menschen, die sich mit dem digitalen Wandel in Wohlfahrt und gemeinnützigen Organisationen auseinandersetz. Sei hier bitte strikt!

WICHTIG: Deine Antwort MUSS EXAKT dem folgenden JSON-Format entsprechen. Verwende KEINE typografischen Anführungszeichen („ oder ") in Strings. Nutze ausschließlich normale ASCII-Anführungszeichen (").

Hier ist das exakte Format, das du verwenden musst:
{json_template}

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

Gib deine Antwort AUSSCHLIESSLICH als JSON-Array von Veranstaltungsobjekten zurueck, ein Objekt pro Veranstaltung. Schreibe KEINEN zusätzlichen Text vor oder nach dem JSON.

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
                    logger.info("Falling back to manual extraction from text")
                    
                    # Fallback: Extract information manually from the text
                    processed_events = []
                    for event_detail in event_details:
                        combined_text = ""
                        if event_detail.get("listing_text"):
                            combined_text += event_detail["listing_text"] + "\n\n"
                        if event_detail.get("detail_text"):
                            combined_text += event_detail["detail_text"]
                        
                        event = extract_event_info_from_text(combined_text, event_detail.get("url"))
                        event['source'] = source_name
                        processed_events.append(event)
                    
                    logger.info(f"Manually extracted {len(processed_events)} events as fallback")
                    return processed_events
        else:
            logger.warning("No JSON found in LLM response")
            
            # Fallback: Extract information manually from the text
            processed_events = []
            for event_detail in event_details:
                combined_text = ""
                if event_detail.get("listing_text"):
                    combined_text += event_detail["listing_text"] + "\n\n"
                if event_detail.get("detail_text"):
                    combined_text += event_detail["detail_text"]
                
                event = extract_event_info_from_text(combined_text, event_detail.get("url"))
                event['source'] = source_name
                processed_events.append(event)
            
            logger.info(f"Manually extracted {len(processed_events)} events as fallback")
            return processed_events
            
    except Exception as e:
        logger.error(f"Error processing with local LLM: {str(e)}")
        logger.exception("Full exception details:")
        
        # Fallback: Extract information manually from the text
        processed_events = []
        for event_detail in event_details:
            combined_text = ""
            if event_detail.get("listing_text"):
                combined_text += event_detail["listing_text"] + "\n\n"
            if event_detail.get("detail_text"):
                combined_text += event_detail["detail_text"]
            
            event = extract_event_info_from_text(combined_text, event_detail.get("url"))
            event['source'] = source_name
            processed_events.append(event)
        
        logger.info(f"Manually extracted {len(processed_events)} events as fallback")
        return processed_events

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
