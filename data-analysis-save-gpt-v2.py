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
from datetime import datetime
from openai import OpenAI
from collections import Counter

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
DIRECTUS_URL = os.getenv("DIRECTUS_API_URL", "https://calapi.buerofalk.de")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
CATEGORIES_CONFIG_FILE = "event_categories_config.json"

# Validate required environment variables
if not DIRECTUS_TOKEN:
    raise ValueError("DIRECTUS_API_TOKEN environment variable is required")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

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
            
            # Lower the threshold for matching to ensure we get some categories
            min_matches = self.rules.get("min_keyword_matches", 2)
            if min_matches > 1:
                min_matches = 1  # Reduce to 1 to be more lenient
                
            if matches >= min_matches:
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
        
        # Lower the threshold to ensure we get some categories
        relevance_threshold = self.rules.get("relevance_threshold", 0.7)
        if relevance_threshold > 0.3:
            relevance_threshold = 0.3  # Reduce to 0.3 to be more lenient
            
        relevant_categories = [c for c in top_categories if c["score"] >= relevance_threshold]
        
        # If we still don't have any categories, take the top ones regardless of score
        if not relevant_categories and top_categories:
            relevant_categories = top_categories[:2]  # Take up to 2 top categories
        
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
    """Processes event data with GPT-4o Mini with enhanced extraction and feedback loop"""
    
    def __init__(self, api_key, directus_client, feedback_section=""):
        self.client = OpenAI(api_key=api_key)
        self.category_manager = CategoryManager()
        self.directus = directus_client
        self.feedback_section = feedback_section  # Store the pre-generated feedback section
        
    # Cache for regex patterns to avoid recompiling
    _date_pattern = re.compile(r'(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|Nov|Dez)\s*(\d{4})', re.IGNORECASE)
    _time_pattern = re.compile(r'(\d{1,2}):(\d{2})(?:\s*-\s*(\d{1,2}):(\d{2}))?')
    _reg_link_patterns = [
        re.compile(r'(?:Anmeldung|Registrierung).*?href=["\']([^"\']+)["\']', re.IGNORECASE | re.DOTALL),
        re.compile(r'(?:Zur Anmeldung|Zur Registrierung)[^\w]*?([http|https][^\s]+)', re.IGNORECASE | re.DOTALL),
        re.compile(r'(?:Anmeldung|Registrierung)[^\w]*?([http|https][^\s]+)', re.IGNORECASE | re.DOTALL)
    ]
    
    # Cache for month name mapping
    _month_map = {
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
    
    # Cache for event types
    _event_types = ["Online-Seminar", "Webinar", "Workshop", "Konferenz", "Tagung", "Forum", "Vortrag", "Schulung"]
    
    def preprocess_event(self, content):
        """Extract key information using regex before GPT processing"""
        extracted_info = {}
        
        # Get text content efficiently
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        
        # Only combine texts if needed for searching
        combined_text = listing_text + " " + detail_text
        
        # Extract date using pre-compiled regex
        date_matches = self._date_pattern.findall(combined_text)
        if date_matches:
            day, month_name, year = date_matches[0]
            month_num = self._month_map.get(month_name.lower(), '01')
            
            # Format as YYYY-MM-DD
            extracted_info["start_date"] = f"{year}-{month_num}-{day.zfill(2)}"
        
        # Extract time using pre-compiled regex
        time_matches = self._time_pattern.findall(combined_text)
        if time_matches:
            start_hour, start_min, end_hour, end_min = time_matches[0]
            extracted_info["start_time"] = f"{start_hour.zfill(2)}:{start_min}"
            
            if end_hour and end_min:
                extracted_info["end_time"] = f"{end_hour.zfill(2)}:{end_min}"
        
        # Extract registration link using pre-compiled regex
        for pattern in self._reg_link_patterns:
            link_match = pattern.search(combined_text)
            if link_match:
                extracted_info["registration_link"] = link_match.group(1).strip()
                break
        
        # Try to extract event type using lowercase comparison for efficiency
        combined_text_lower = combined_text.lower()
        for event_type in self._event_types:
            if event_type.lower() in combined_text_lower:
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
        
        # Build prompt with feedback
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
                
                # Store topics as tags
                structured_data["tags"] = topics
            
            # Remove target_audience field if present
            if 'target_audience' in structured_data:
                del structured_data['target_audience']
            
            # Use categories directly from the LLM response
            # If no categories were provided by the LLM, use the CategoryManager as fallback
            if not structured_data.get('categories'):
                categories = self.category_manager.categorize_event(structured_data)
                structured_data["categories"] = categories
            
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
    
    VERFÜGBARE KATEGORIEN:
    {categories_info}
    
    {feedback_section}
    
    Extrahiere die folgenden Informationen im JSON Format:
    - title: Der Titel der Veranstaltung
    - description: Eine prägnante Beschreibung (MAXIMAL 450 Zeichen). Fokussiere auf die wichtigsten Informationen.
    - start_date: Startdatum im ISO-Format (YYYY-MM-DD)
    - start_time: Startzeit (HH:MM)
    - end_date: Enddatum falls angegeben
    - end_time: Endzeit falls angegeben
    - location: Physischer Ort oder "Online"
    - organizer: Die Organisation, die die Veranstaltung durchführt
    - topics: Hauptthemen und Art der Veranstaltung (Array von Strings). Füge die Art der Veranstaltung (Workshop, Webinar, etc.) als eines der Topics hinzu.
    - tags: Schlagwörter für die Veranstaltung (Array von Strings). Verwende die Topics als Basis und füge weitere relevante Schlagwörter hinzu.
    - categories: Wähle passende Kategorien aus der Liste der verfügbaren Kategorien (Array von Objekten mit id und name). Wähle maximal 3 Kategorien.
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
    
    # Cache for category information
    _categories_info_cache = None
    
    def _build_prompt(self, content, extracted_info=None):
        """Build prompt for GPT-4o Mini with extracted information and feedback"""
        # Get text content efficiently
        listing_text = content.get("listing_text", "") or ""
        detail_text = content.get("detail_text", "") or ""
        url = content.get("url", "")
        
        # More aggressive trimming for long texts to reduce tokens
        if len(listing_text) > 1500:
            listing_text = listing_text[:1500] + "..."
        if len(detail_text) > 2000:
            detail_text = detail_text[:2000] + "..."
        
        # Add pre-extracted information if available
        extracted_info_str = ""
        if extracted_info:
            extracted_info_str = "BEREITS EXTRAHIERTE INFORMATIONEN:\n"
            for key, value in extracted_info.items():
                extracted_info_str += f"- {key}: {value}\n"
            extracted_info_str += "\n"
        
        # Build category information only once and cache it
        if self._categories_info_cache is None:
            categories_info = ""
            for category in self.category_manager.categories:
                categories_info += f"- id: {category['id']}, name: {category['name']}, description: {category['description']}\n"
            self._categories_info_cache = categories_info
        else:
            categories_info = self._categories_info_cache
        
        # Use the pre-generated feedback section
        feedback_section = self.feedback_section
        
        # Use the template with format() for better performance than f-strings with large text
        prompt = self._prompt_template.format(
            extracted_info=extracted_info_str,
            listing_text=listing_text,
            detail_text=detail_text,
            url=url,
            categories_info=categories_info,
            feedback_section=feedback_section
        )
        
        return prompt

def process_events(limit=10, batch_size=3):
    """Main processing function with optimized feedback"""
    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, DIRECTUS_TOKEN)
    
    # OPTIMIZATION 1: Fetch all feedback data ONCE at the beginning
    print("\n--- FEEDBACK SYSTEM INITIALIZATION ---")
    
    # Create a cache for API results
    api_cache = {}
    
    # Cache feedback examples
    if 'feedback_examples' not in api_cache:
        api_cache['feedback_examples'] = directus.get_feedback_examples(limit=5)
    feedback_examples = api_cache['feedback_examples']
    
    # Cache feedback patterns
    if 'feedback_patterns' not in api_cache:
        api_cache['feedback_patterns'] = directus.get_feedback_patterns()
    feedback_patterns = api_cache['feedback_patterns']
    
    # Cache feedback stats
    if 'feedback_stats' not in api_cache:
        api_cache['feedback_stats'] = directus.get_feedback_stats()
    feedback_stats = api_cache['feedback_stats']
    
    # Log the feedback information
    print(f"Feedback examples: {len(feedback_examples)} retrieved")
    if feedback_examples:
        print("Example titles:")
        for example in feedback_examples:
            relevance = "Relevant" if example['is_relevant'] else "Not Relevant"
            print(f"- \"{example['title']}\" ({relevance})")
    
    print(f"\nFeedback patterns: {len(feedback_patterns)} extracted")
    if feedback_patterns:
        print("Patterns:")
        for pattern in feedback_patterns:
            print(f"- {pattern}")
    
    if feedback_stats["total"] >= 10:
        accuracy = feedback_stats["accuracy"] * 100
        print(f"\nFeedback statistics: {feedback_stats['total']} events, {accuracy:.1f}% accuracy")
    else:
        print(f"\nFeedback statistics: Insufficient data ({feedback_stats['total']} events)")
    
    print("--- END FEEDBACK INITIALIZATION ---\n")
    
    # OPTIMIZATION 2: Generate the feedback prompt section once
    feedback_section = ""
    
    # Add examples to the prompt if available
    if feedback_examples:
        feedback_section = "BEISPIELE AUS FEEDBACK:\n"
        for example in feedback_examples:
            relevance = "Relevant" if example['is_relevant'] else "Nicht relevant"
            feedback_section += f"- \"{example['title']}\": {relevance}\n"
            if example.get('reason'):
                feedback_section += f"  Grund: {example['reason']}\n"
        feedback_section += "\n"
    
    # Add patterns to the prompt if available
    if feedback_patterns:
        if not feedback_section:
            feedback_section = "HINWEISE AUS FEEDBACK:\n"
        else:
            feedback_section += "HINWEISE AUS FEEDBACK:\n"
            
        for pattern in feedback_patterns:
            feedback_section += f"- {pattern}\n"
        feedback_section += "\n"
    
    # Add stats to the prompt if available and significant
    if feedback_stats["total"] >= 10:
        accuracy = feedback_stats["accuracy"] * 100
        if not feedback_section:
            feedback_section = f"FEEDBACK STATISTIK: Basierend auf {feedback_stats['total']} Bewertungen liegt die Genauigkeit bei {accuracy:.1f}%.\n\n"
        else:
            feedback_section += f"FEEDBACK STATISTIK: Basierend auf {feedback_stats['total']} Bewertungen liegt die Genauigkeit bei {accuracy:.1f}%.\n\n"
    
    # Save the feedback section to a log file for reference
    with open("feedback_prompt_additions.log", "w", encoding="utf-8") as f:
        f.write(f"Timestamp: {datetime.now().isoformat()}\n\n")
        f.write("FEEDBACK PROMPT ADDITIONS:\n")
        f.write(feedback_section if feedback_section else "No feedback data available")
    
    # Initialize processor with pre-generated feedback section
    gpt = GPT4MiniProcessor(OPENAI_API_KEY, directus, feedback_section)
    
    # OPTIMIZATION 3: Cache unprocessed items
    if 'unprocessed_items' not in api_cache:
        api_cache['unprocessed_items'] = directus.get_unprocessed_items(limit)
    items = api_cache['unprocessed_items']
    
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
            
            # Print extracted date and time for verification
            print(f"Extracted: {structured_data.get('title')} | Date: {structured_data.get('start_date')} | Time: {structured_data.get('start_time')} | Relevant: {structured_data.get('is_relevant', False)}")
            
            # Print categories
            if structured_data.get('categories'):
                categories_str = ", ".join([cat.get('name', '') for cat in structured_data.get('categories', [])])
                print(f"Categories: {categories_str}")
            
            # Save all events to Directus, but mark them as pending approval
            structured_data["approved"] = None  # Pending approval
            
            # Add to batch results
            batch_results.append({
                'item_id': item_id,
                'structured_data': structured_data
            })
        
        # OPTIMIZATION 5: Process batch results together
        for result in batch_results:
            item_id = result['item_id']
            structured_data = result['structured_data']
            
            # Save to events collection
            success, status = directus.save_event(structured_data)
            
            if success:
                processed += 1
                relevance_status = "Relevant" if structured_data.get('is_relevant', False) else "Not Relevant"
                print(f"Processed: {structured_data.get('title', 'Unknown')} ({relevance_status}, Pending Approval)")
            elif status == "duplicate":
                duplicates += 1
                print(f"Duplicate: {structured_data.get('title', 'Unknown')}")
            else:
                errors += 1
                print(f"Error saving: {status}")
            
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
    
    # Print feedback stats if available
    if feedback_stats["total"] > 0:
        print("\nFeedback Statistics:")
        print(f"Total feedback: {feedback_stats['total']}")
        print(f"LLM accuracy: {feedback_stats['accuracy'] * 100:.1f}%")
    
    print(f"\nFeedback: Used {len(feedback_examples)} examples and {len(feedback_patterns)} patterns")
    print(f"Feedback log saved to: feedback_prompt_additions.log")

def main():
    parser = argparse.ArgumentParser(description="Process events with enhanced extraction and feedback loop")
    parser.add_argument("--limit", "-l", type=int, default=10, help="Maximum number of items to process")
    parser.add_argument("--batch", "-b", type=int, default=3, help="Batch size for processing")
    parser.add_argument("--config", "-c", default=CATEGORIES_CONFIG_FILE, help="Path to categories configuration file")
    parser.add_argument("--flag-mismatches", "-f", action="store_true", help="Flag events where LLM determination doesn't match human feedback")
    parser.add_argument("--only-flag", "-o", action="store_true", help="Only flag mismatches without processing new events")
    
    args = parser.parse_args()
    
    # Check if config file exists
    if not os.path.exists(args.config):
        print(f"Warning: Categories configuration file '{args.config}' not found. Using default configuration.")
    
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
