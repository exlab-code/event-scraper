#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Improved Event Analysis App

A streamlined application that processes event data from a Directus database
using GPT-4o Mini and stores structured results back to Directus, with enhanced
extraction for dates, times, and links.
"""
import json
import requests
import argparse
import re
import os
from datetime import datetime
from openai import OpenAI

# Configuration
DIRECTUS_URL = "https://calapi.buerofalk.de"
DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o"
OPENAI_API_KEY = "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"
CATEGORIES_CONFIG_FILE = "event_categories_config.json"

def load_categories_config(config_file=CATEGORIES_CONFIG_FILE):
    """Load categories configuration from JSON file"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading categories config: {str(e)}")
        # Return a minimal default configuration
        return {
            "categories": [],
            "tagging_rules": {
                "min_keyword_matches": 2,
                "max_categories_per_event": 3,
                "relevance_threshold": 0.7,
                "required_nonprofit_context": True
            }
        }

class DirectusClient:
    """Simple client for Directus API interactions"""
    
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
        
        # Add the event
        response = requests.post(f"{self.base_url}/items/events", headers=self.headers, json=event_data)
        
        if response.status_code in (200, 201, 204):
            return True, "created"
        else:
            return False, f"Error: {response.status_code}"

class CategoryManager:
    """Manages event categorization based on configuration"""
    
    def __init__(self, config=None):
        """Initialize with categories configuration"""
        self.config = config or load_categories_config()
        self.categories = self.config.get("categories", [])
        self.rules = self.config.get("tagging_rules", {})
        
    def categorize_event(self, event_data):
        """Assign categories to an event based on its content"""
        # Combine all text fields for searching
        search_text = " ".join([
            str(event_data.get("title", "")),
            str(event_data.get("description", "")),
            str(event_data.get("event_type", "")),
            " ".join(str(topic) for topic in event_data.get("topics", []) if topic),
            str(event_data.get("target_audience", ""))
        ]).lower()
        
        # Calculate matches for each category
        category_matches = []
        for category in self.categories:
            matches = 0
            for keyword in category.get("keywords", []):
                if keyword.lower() in search_text:
                    matches += 1
            
            if matches >= self.rules.get("min_keyword_matches", 2):
                category_matches.append({
                    "id": category["id"],
                    "name": category["name"],
                    "matches": matches,
                    "score": matches / len(category.get("keywords", [1]))  # Normalize by keyword count
                })
        
        # Sort by score (highest first)
        category_matches.sort(key=lambda x: x["score"], reverse=True)
        
        # Limit to max categories
        max_categories = self.rules.get("max_categories_per_event", 3)
        top_categories = category_matches[:max_categories]
        
        # Check if we have any categories that meet the threshold
        relevance_threshold = self.rules.get("relevance_threshold", 0.7)
        relevant_categories = [c for c in top_categories if c["score"] >= relevance_threshold]
        
        # Format the result
        result = []
        for category in relevant_categories:
            result.append({
                "id": category["id"],
                "name": category["name"]
            })
        
        return result
    
    def is_event_relevant(self, event_data, categories=None):
        """Determine if an event is relevant based on categories and content"""
        # All events are considered relevant
        # Categories are only used for filtering in the database, not for determining relevance
        return True

class GPT4MiniProcessor:
    """Processes event data with GPT-4o Mini with enhanced extraction"""
    
    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key)
        self.category_manager = CategoryManager()
        
    def preprocess_event(self, content):
        """Extract key information using regex before GPT processing"""
        extracted_info = {}
        
        # Extract dates and times using regex
        date_pattern = r'(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s*(\d{4})'
        time_pattern = r'(\d{1,2}):(\d{2})(?:\s*-\s*(\d{1,2}):(\d{2}))?'
        
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        combined_text = listing_text + " " + detail_text
        
        # Extract date
        date_matches = re.findall(date_pattern, combined_text, re.IGNORECASE)
        if date_matches:
            # Convert month name to number
            month_map = {
                'januar': '01', 'jan': '01',
                'februar': '02', 'feb': '02',
                'märz': '03', 'mär': '03', 'marz': '03',
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
            
            day, month_name, year = date_matches[0]
            month_num = month_map.get(month_name.lower(), '01')
            
            # Format as YYYY-MM-DD
            extracted_info["start_date"] = f"{year}-{month_num}-{day.zfill(2)}"
        
        # Extract time
        time_matches = re.findall(time_pattern, combined_text)
        if time_matches:
            start_hour, start_min, end_hour, end_min = time_matches[0]
            extracted_info["start_time"] = f"{start_hour.zfill(2)}:{start_min}"
            
            if end_hour and end_min:
                extracted_info["end_time"] = f"{end_hour.zfill(2)}:{end_min}"
        
        # Extract registration link
        reg_link_patterns = [
            r'(?:Anmeldung|Registrierung).*?href=["\']([^"\']+)["\']',
            r'(?:Zur Anmeldung|Zur Registrierung)[^\w]*?([http|https][^\s]+)',
            r'(?:Anmeldung|Registrierung)[^\w]*?([http|https][^\s]+)'
        ]
        
        for pattern in reg_link_patterns:
            link_match = re.search(pattern, combined_text, re.IGNORECASE | re.DOTALL)
            if link_match:
                extracted_info["registration_link"] = link_match.group(1).strip()
                break
        
        # Try to extract event type
        event_types = ["Online-Seminar", "Webinar", "Workshop", "Konferenz", "Tagung", "Forum", "Vortrag", "Schulung"]
        for event_type in event_types:
            if event_type.lower() in combined_text.lower():
                extracted_info["event_type"] = event_type
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
        
        # Build prompt
        prompt = self._build_prompt(content, extracted_info)
        
        try:
            # Call GPT-4o Mini
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Extract structured information from German event descriptions with focus on dates, times, and links. Be VERY strict about relevance criteria - only mark events as relevant if they EXPLICITLY mention both non-profit/gemeinnützig context AND digital transformation."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            # Parse response
            structured_data = json.loads(response.choices[0].message.content)
            
            # Override with direct extraction results if available
            for key, value in extracted_info.items():
                if value and (not structured_data.get(key) or key in ['start_date', 'start_time', 'end_time', 'registration_link']):
                    structured_data[key] = value
            
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
            
            # Assign categories based on content
            categories = self.category_manager.categorize_event(structured_data)
            structured_data["categories"] = categories
            
            # Determine if the event is relevant (using LLM's determination)
            # No post-processing override
            
            # Add metadata
            structured_data["source"] = content.get("source_name", event_data.get("source_name", "Unknown"))
            structured_data["approved"] = False
            
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
    
    def _build_prompt(self, content, extracted_info=None):
        """Build prompt for GPT-4o Mini with extracted information"""
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        url = content.get("url", "")
        
        # Trim long text to reduce tokens
        if len(listing_text) > 2000:
            listing_text = listing_text[:2000]
        if len(detail_text) > 3000:
            detail_text = detail_text[:3000]
        
        # Add pre-extracted information if available
        extracted_info_str = ""
        if extracted_info:
            extracted_info_str = "BEREITS EXTRAHIERTE INFORMATIONEN:\n"
            for key, value in extracted_info.items():
                extracted_info_str += f"- {key}: {value}\n"
            extracted_info_str += "\n"
        
        # Add category information from config
        categories_info = ""
        for category in self.category_manager.categories:
            categories_info += f"- {category['name']}: {category['description']}\n"
        
        prompt = f"""
        Analysiere diese Veranstaltungsinformation und extrahiere strukturierte Daten:
        
        {extracted_info_str}
        LISTING TEXT:
        {listing_text}
        
        DETAIL TEXT:
        {detail_text}
        
        URL: {url}
        
        MÖGLICHE KATEGORIEN:
        {categories_info}
        
        Extrahiere die folgenden Informationen im JSON Format:
        - title: Der Titel der Veranstaltung
        - description: Eine prägnante Beschreibung (max. 5 Sätze)
        - start_date: Startdatum im ISO-Format (YYYY-MM-DD)
        - start_time: Startzeit (HH:MM)
        - end_date: Enddatum falls angegeben
        - end_time: Endzeit falls angegeben
        - location: Physischer Ort oder "Online"
        - organizer: Die Organisation, die die Veranstaltung durchführt
        - event_type: Art der Veranstaltung (Workshop, Webinar, Konferenz, etc.)
        - topics: Hauptthemen (Array von Strings)
        - target_audience: Zielgruppe der Veranstaltung
        - cost: Preisinformationen oder "Kostenlos"
        - registration_link: URL für die Anmeldung falls verfügbar
        - is_relevant: Boolean (true/false) ob die Veranstaltung relevant ist
        
        Wichtig für Datumsformate:
        - Nutze YYYY-MM-DD für Datumsangaben (z.B. 2025-04-08)
        - Nutze HH:MM für Zeitangaben (z.B. 08:00)
        - Achte besonders auf deutsche Datumsformate (z.B. "08. April 2025")
        
        Relevanzkriterien (WICHTIG - STRENG ANWENDEN):
        - Die Veranstaltung MUSS EINDEUTIG für Non-Profit-Organisationen oder den gemeinnützigen Sektor relevant sein
          UND gleichzeitig einen klaren Bezug zu digitaler Transformation haben
        - Beide Aspekte müssen klar erkennbar sein: Non-Profit-Bezug UND Digitalisierungsbezug
        - Veranstaltungen zu Themen wie KI, Social Media, digitale Kommunikation, digitale Strategie, Datenmanagement
          sind NUR relevant, wenn sie EXPLIZIT für Non-Profits oder gemeinnützige Organisationen ausgerichtet sind
        - Allgemeine Business-, Technologie- oder Innovationsveranstaltungen ohne expliziten Non-Profit-Bezug
          sind NICHT relevant, selbst wenn sie digitale Themen behandeln
        - Im Zweifelsfall (wenn der Non-Profit-Bezug nicht eindeutig ist): als NICHT relevant markieren
        
        Liefere nur gültiges JSON zurück. Nutze null für unbekannte Felder.
        """
        
        return prompt

def process_events(limit=10, batch_size=3):
    """Main processing function"""
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    gpt = GPT4MiniProcessor(OPENAI_API_KEY)
    
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
    
    # Process in batches
    for i in range(0, len(items), batch_size):
        batch = items[i:i+batch_size]
        print(f"Processing batch {i//batch_size + 1} ({len(batch)} items)")
        
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
            
            # Print extracted date and time for verification
            print(f"Extracted: {structured_data.get('title')} | Date: {structured_data.get('start_date')} | Time: {structured_data.get('start_time')} | Relevant: {structured_data.get('is_relevant', False)}")
            
            # Print categories
            if structured_data.get('categories'):
                categories_str = ", ".join([cat.get('name', '') for cat in structured_data.get('categories', [])])
                print(f"Categories: {categories_str}")
            
            # Only save relevant events to Directus
            if structured_data.get('is_relevant', False):
                # Save to events collection
                success, status = directus.save_event(structured_data)
                
                if success:
                    processed += 1
                    print(f"Processed: {structured_data.get('title', 'Unknown')} (Relevant)")
                elif status == "duplicate":
                    duplicates += 1
                    print(f"Duplicate: {structured_data.get('title', 'Unknown')}")
                else:
                    errors += 1
                    print(f"Error saving: {status}")
            else:
                print(f"Skipped: {structured_data.get('title', 'Unknown')} (Not relevant to digital transformation in non-profits)")
            
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

def main():
    parser = argparse.ArgumentParser(description="Process events with enhanced extraction")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum number of items to process")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size for processing")
    parser.add_argument("--config", "-c", default=CATEGORIES_CONFIG_FILE, help="Path to categories configuration file")
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        print(f"Warning: Categories configuration file '{args.config}' not found. Using default configuration.")
    
    process_events(limit=args.limit, batch_size=args.batch)

if __name__ == "__main__":
    main()
