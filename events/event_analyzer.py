#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event Analysis App with Instructor

A streamlined application that processes event data from a Directus database
using GPT-4o Mini with Instructor for structured extraction and validation.
Processes events with automatic date parsing, validation, and relevance determination.
"""
import json
import requests
import argparse
import re
import os
import logging
from datetime import datetime
from openai import OpenAI
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
import instructor
from dotenv import load_dotenv

# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class TagGroups(BaseModel):
    """Organized tags by category"""
    topic: List[str] = Field(default_factory=list, description="Themen-Tags")
    format: List[str] = Field(default_factory=list, description="Format-Tags (Workshop, Webinar, etc.)")
    audience: List[str] = Field(default_factory=list, description="Zielgruppen-Tags")
    cost: List[str] = Field(default_factory=list, description="Kosten-Tags")


class EventData(BaseModel):
    """Structured event data with validation"""
    title: str = Field(..., min_length=1, max_length=500, description="Titel der Veranstaltung")
    description: str = Field(..., max_length=450, description="Prägnante Beschreibung (max 450 Zeichen)")
    start_date: str = Field(..., description="Startdatum im ISO-Format (YYYY-MM-DD)")
    start_time: Optional[str] = Field(None, description="Startzeit (HH:MM)")
    end_date: Optional[str] = Field(None, description="Enddatum im ISO-Format")
    end_time: Optional[str] = Field(None, description="Endzeit (HH:MM)")
    location: str = Field(..., min_length=1, description="Physischer Ort oder 'Online'")
    organizer: str = Field(..., min_length=1, description="Veranstalter")
    tags: List[str] = Field(default_factory=list, max_length=5, description="Schlagwörter (max 5)")
    tag_groups: Optional[TagGroups] = Field(None, description="Tags nach Kategorien organisiert")
    cost: str = Field(default="Kostenlos", description="Preisinformationen")
    registration_link: Optional[str] = Field(None, description="URL für Anmeldung")
    relevancy_score: int = Field(..., ge=0, le=100, description="Relevanzwert für Non-Profit digitale Transformation (0-100)")

    # Additional fields added by processor
    source: Optional[str] = Field(None, description="Quelle der Veranstaltung")
    approved: Optional[bool] = Field(None, description="Freigabestatus")
    website: Optional[str] = Field(None, description="Event-Website URL")

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate ISO date format (YYYY-MM-DD)"""
        if v is None:
            return v

        # Check if already in ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', v):
            try:
                datetime.strptime(v, '%Y-%m-%d')
                return v
            except ValueError:
                pass

        # Try to parse German date formats
        german_formats = [
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', '%d.%m.%Y'),  # DD.MM.YYYY
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%d/%m/%Y'),    # DD/MM/YYYY
        ]

        for pattern, format_str in german_formats:
            match = re.match(pattern, v)
            if match:
                try:
                    parsed_date = datetime.strptime(v, format_str)
                    return parsed_date.strftime('%Y-%m-%d')
                except ValueError:
                    continue

        # If we can't parse it, raise an error
        raise ValueError(f"Date must be in ISO format (YYYY-MM-DD) or German format (DD.MM.YYYY). Got: {v}")

    @field_validator('start_time', 'end_time')
    @classmethod
    def validate_time_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate time format (HH:MM)"""
        if v is None:
            return v

        # Check if in HH:MM format
        if re.match(r'^\d{1,2}:\d{2}$', v):
            parts = v.split(':')
            hour = int(parts[0])
            minute = int(parts[1])

            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return f"{hour:02d}:{minute:02d}"

        raise ValueError(f"Time must be in HH:MM format. Got: {v}")

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate and clean tags"""
        if len(v) > 5:
            # Truncate to 5 tags if too many
            v = v[:5]

        # Clean and validate each tag
        cleaned_tags = []
        for tag in v:
            tag = tag.strip()
            if tag:  # Only add non-empty tags
                cleaned_tags.append(tag)

        return cleaned_tags

    @model_validator(mode='after')
    def validate_dates_consistency(self):
        """Ensure end_date is not before start_date"""
        if self.start_date and self.end_date:
            try:
                start = datetime.strptime(self.start_date, '%Y-%m-%d')
                end = datetime.strptime(self.end_date, '%Y-%m-%d')

                if end < start:
                    raise ValueError(f"End date ({self.end_date}) cannot be before start date ({self.start_date})")
            except ValueError as e:
                if "End date" in str(e):
                    raise
                # If date parsing fails, it will be caught by field validators
                pass

        return self

# ============================================================================

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
    """Client for Directus API interactions - managing scraped data and events"""
    
    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def get_unprocessed_items(self, limit=10):
        """Get unprocessed items from scraped_data collection"""
        # Use Directus filter to get only unprocessed items directly
        url = f"{self.base_url}/items/scraped_data?filter[processed][_eq]=false&limit={limit}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        items = response.json().get('data', [])

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

        # Add the event
        response = requests.post(f"{self.base_url}/items/events", headers=self.headers, json=event_data)
        
        if response.status_code in (200, 201, 204):
            return True, "created"
        else:
            return False, f"Error: {response.status_code}"


class GPT4MiniProcessor:
    """Processes event data with GPT-4o Mini using Instructor for structured extraction"""

    def __init__(self, api_key, directus_client):
        # Wrap OpenAI client with Instructor for structured output with validation
        self.client = instructor.from_openai(OpenAI(api_key=api_key))
        self.directus = directus_client
        
    # Cache for regex patterns to avoid recompiling
    _reg_link_patterns = [
        # Match href attributes in HTML links
        re.compile(r'(?:Anmeldung|Registrierung).*?href=["\']((https?://)[^\s"\']+)["\']', re.IGNORECASE | re.DOTALL),
        # Match URLs following registration phrases - ensure they start with http:// or https://
        re.compile(r'(?:Zur Anmeldung|Zur Registrierung)[^\w]*?(https?://[^\s]+)', re.IGNORECASE | re.DOTALL),
        # Match URLs following registration words - ensure they start with http:// or https://
        re.compile(r'(?:Anmeldung|Registrierung)[^\w]*?(https?://[^\s]+)', re.IGNORECASE | re.DOTALL)
    ]

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

        # Build prompt for LLM extraction
        prompt = self._build_prompt(content, extracted_info)
        
        try:
            # Get item ID for logging
            item_id_str = event_data.get('id', 'unknown')
            
            # Log the prompt being sent to the LLM
            system_prompt = "Extract structured information from German event descriptions with focus on dates, times, and links. Provide a relevancy score (0-100) based on how well the event matches the Non-Profit digital transformation use case."
            
            logger.info(f"\n--- LLM INPUT for item {item_id_str} ---\nSYSTEM PROMPT:\n{system_prompt}\n\nUSER PROMPT:\n{prompt}\n--- END LLM INPUT ---")

            # Call GPT-4o Mini with Instructor for structured output and automatic validation
            event = self.client.chat.completions.create(
                model="gpt-4o-mini",
                response_model=EventData,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_retries=3  # Instructor will automatically retry on validation errors
            )

            # The event is already a validated Pydantic model, convert to dict
            structured_data = event.model_dump(exclude_none=True)

            # Log the validated response
            logger.info(f"\n--- VALIDATED RESPONSE for item {item_id_str} ---\n{json.dumps(structured_data, indent=2, ensure_ascii=False)}\n--- END VALIDATED RESPONSE ---")

            # Log the extracted date information
            date_log = f"""
Date extraction for item {item_id_str}:
Title: {structured_data.get('title', 'Unknown')}

VALIDATED EXTRACTION:
  start_date: {structured_data.get('start_date', 'Not found')}
  end_date: {structured_data.get('end_date', 'Not found')}
  start_time: {structured_data.get('start_time', 'Not found')}
  end_time: {structured_data.get('end_time', 'Not found')}
"""
            logger.info(date_log)
            
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

            # Add metadata
            structured_data["source"] = content.get("source_name", event_data.get("source_name", "Unknown"))
            structured_data["approved"] = None  # Set to pending approval by default
            
            # Add URL if available
            if content.get("url") and not structured_data.get("website"):
                structured_data["website"] = content.get("url")

            # Add token usage info
            # Note: Instructor wraps the response, so we need to access the raw response
            # For now, we'll provide a default token usage since Instructor doesn't expose it directly
            # The token tracking is primarily for monitoring, not critical for functionality
            token_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

            # Try to get token usage from the raw response if available
            try:
                if hasattr(event, '_raw_response') and hasattr(event._raw_response, 'usage'):
                    token_usage = {
                        "prompt_tokens": event._raw_response.usage.prompt_tokens,
                        "completion_tokens": event._raw_response.usage.completion_tokens,
                        "total_tokens": event._raw_response.usage.total_tokens
                    }
            except AttributeError:
                # If we can't access token usage, continue with defaults
                pass

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
      * Format-Tags: Art der Veranstaltung (z.B. Workshop, Webinar, Konferenz, Forbildung)
      * Zielgruppen-Tags: Für wen ist die Veranstaltung gedacht (z.B. Vereine, Stiftungen)
      * Kosten-Tags: Füge "Kostenlos" hinzu, wenn die Veranstaltung kostenlos ist
    - tag_groups: Organisiere die Tags nach Kategorien (Objekt mit Arrays):
      * topic: Themen-Tags
      * format: Format-Tags
      * audience: Zielgruppen-Tags
      * cost: Kosten-Tags
    - cost: Preisinformationen oder "Kostenlos"
    - registration_link: URL für die Anmeldung falls verfügbar
    - relevancy_score: Relevanzwert (0-100) für Non-Profit digitale Transformation

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
    
    Relevanzkriterien für relevancy_score (0-100):

    HOHE RELEVANZ (70-100 Punkte):
    - Expliziter Fokus auf Non-Profit-Organisationen (Vereine, Stiftungen, NGOs, gemeinnützige Organisationen)
    - Klarer Bezug zu digitaler Transformation, Digitalisierung oder IT-Themen
    - Beide Aspekte (Non-Profit + Digital) sind deutlich erkennbar
    - Beispiele: "Digitalisierung für Vereine", "IT-Lösungen für gemeinnützige Organisationen"

    MITTLERE RELEVANZ (40-69 Punkte):
    - Indirekter Non-Profit-Bezug (z.B. soziale Innovation, Engagement, bürgerschaftliches Engagement)
    - Digitale Themen vorhanden, aber Non-Profit-Bezug nicht explizit
    - Oder: Non-Profit-Bezug vorhanden, aber digitaler Aspekt nur teilweise relevant

    NIEDRIGE RELEVANZ (20-39 Punkte):
    - Schwacher Non-Profit-Bezug oder nur allgemein soziale Themen
    - Digitale Themen vorhanden, aber für breite Business-Zielgruppe
    - Kann für Non-Profits interessant sein, aber nicht spezifisch ausgerichtet

    KEINE RELEVANZ (0-19 Punkte):
    - Reine Business/Unternehmens-Veranstaltungen ohne Non-Profit-Bezug
    - Fehlender Digitalisierungsbezug
    - Allgemeine Schulungen ohne spezifischen Non-Profit-Kontext

    WICHTIG:
    - Mehrtägige, teure Schulungen (>500€) sollten in der Regel niedrigere Scores erhalten (max. 20-30 Punkte)
    - Im Zweifelsfall: Eher konservativ bewerten (niedrigerer Score)

    Liefere nur gültiges JSON zurück. Nutze null für unbekannte Felder.
    """
    
    def _build_prompt(self, content, extracted_info=None):
        """Build prompt for GPT-4o Mini with extracted information"""
        # Get text content efficiently
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        url = content.get("url", "")

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

        # Use the template with format() for better performance than f-strings with large text
        prompt = self._prompt_template.format(
            extracted_info=extracted_info_str,
            listing_text=listing_text,
            detail_text=detail_text,
            url=url
        )
        
        return prompt

def process_events(limit=10, batch_size=3):
    """Main processing function for event extraction and analysis"""
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)

    # Initialize processor
    gpt = GPT4MiniProcessor(OPENAI_API_KEY, directus)
    
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
                try:
                    directus.update_item_status(item_id, success=False)
                except requests.exceptions.HTTPError as e:
                    print(f"Warning: Could not update item status in DB: {e}")
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

            # Save all events to Directus, but mark them as pending approval
            structured_data["approved"] = None  # Pending approval
            
            # Save to events collection
            success, status = directus.save_event(structured_data)
            
            # Format event information for console output
            title = structured_data.get('title', 'Unknown')
            date = structured_data.get('start_date', 'No date')
            if date and len(date) > 10:  # Truncate ISO date to just YYYY-MM-DD
                date = date[:10]
            
            relevancy_score = structured_data.get('relevancy_score', 0)

            # Print a single, well-formatted line for each event
            if success:
                processed += 1
                print(f"✓ {title} | {date} | Score: {relevancy_score}/100")
            elif status == "duplicate":
                duplicates += 1
                print(f"↺ Duplicate: {title}")
            else:
                errors += 1
                print(f"✗ Error: {title} - {status}")
            
            # Update item status
            processed_content = json.dumps(structured_data, ensure_ascii=False)
            try:
                directus.update_item_status(item_id, success=True, processed_content=processed_content)
            except requests.exceptions.HTTPError as e:
                print(f"Warning: Could not update item {item_id} status in DB: {e}")
    
    # Calculate cost (approx. $0.15 per 1M tokens)
    cost = (total_tokens / 1_000_000) * 0.15
    
    # Print summary
    print("\nProcessing Summary:")
    print(f"Processed: {processed}")
    print(f"Duplicates: {duplicates}")
    print(f"Errors: {errors}")
    print(f"Total tokens: {total_tokens}")
    print(f"Estimated cost: ${cost:.4f}")

def main():
    parser = argparse.ArgumentParser(description="Process events with structured extraction using Instructor")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum number of items to process")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size for processing")
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

    # Process events
    process_events(limit=args.limit, batch_size=args.batch)

if __name__ == "__main__":
    main()
