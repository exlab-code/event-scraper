#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event Scraper for Non-Profit Digitalization Events with Directus Database Integration

This script scrapes websites for digitalization events targeted at non-profit organizations,
extracts the raw event information, and saves it to a Directus database.
This enables deduplication and efficient processing of events.
"""
import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
import re
import hashlib
from urllib.parse import urljoin
from datetime import datetime
import argparse
from pathlib import Path

# Set up logging
def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """Configure logging with file and console handlers."""
    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "scraper.log"), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("event-scraper")

# Initialize logger
logger = setup_logging()

class DirectusClient:
    """Client for interacting with Directus API"""
    
    def __init__(self, base_url, token=None, email=None, password=None):
        """Initialize the Directus client with credentials.
        
        Args:
            base_url (str): Base URL for the Directus API
            token (str, optional): Static API token for authentication
            email (str, optional): Admin email for authentication
            password (str, optional): Admin password for authentication
        """
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.password = password
        self.static_token = token
        self.token = token  # Use static token if provided
        
        # If no static token is provided, login with email/password
        if not self.static_token and self.email and self.password:
            self.login()
        elif not self.static_token:
            raise ValueError("Either token or email/password must be provided")
        else:
            logger.info("Using static API token for Directus authentication")
    
    def login(self):
        """Authenticate with Directus and get access token"""
        # Skip if using static token
        if self.static_token:
            return
            
        auth_url = f"{self.base_url}/auth/login"
        payload = {
            "email": self.email,
            "password": self.password
        }
        
        try:
            response = requests.post(auth_url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            self.token = data.get('data', {}).get('access_token')
            
            if not self.token:
                raise Exception("Failed to get access token from Directus")
            
            logger.info("Successfully authenticated with Directus")
        except Exception as e:
            logger.error(f"Failed to authenticate with Directus: {str(e)}")
            raise
    
    def get_headers(self):
        """Get request headers with authentication"""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
    
    def create_item(self, collection, data):
        """Create a new item in a collection"""
        url = f"{self.base_url}/items/{collection}"
        
        try:
            response = requests.post(url, headers=self.get_headers(), json=data)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = requests.post(url, headers=self.get_headers(), json=data)
            
            response.raise_for_status()
            return response.json().get('data', {})
        except Exception as e:
            logger.error(f"Failed to create item in {collection}: {str(e)}")
            raise
    
    def get_item_by_hash(self, collection, content_hash):
        """Get an item by its content hash"""
        url = f"{self.base_url}/items/{collection}"
        params = {
            "filter": json.dumps({
                "content_hash": {
                    "_eq": content_hash
                }
            })
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = requests.get(url, headers=self.get_headers(), params=params)
            
            response.raise_for_status()
            
            data = response.json().get('data', [])
            return data[0] if data else None
        except Exception as e:
            logger.error(f"Failed to get item by hash from {collection}: {str(e)}")
            return None
    
    def update_item(self, collection, item_id, data):
        """Update an existing item"""
        url = f"{self.base_url}/items/{collection}/{item_id}"
        
        try:
            response = requests.patch(url, headers=self.get_headers(), json=data)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = requests.patch(url, headers=self.get_headers(), json=data)
            
            response.raise_for_status()
            return response.json().get('data', {})
        except Exception as e:
            logger.error(f"Failed to update item {item_id} in {collection}: {str(e)}")
            raise


class EventScraper:
    """Main scraper class for collecting non-profit digitalization events with Directus integration."""
    
    def __init__(self, config, directus_config=None, output_dir="data", max_events_per_source=3):
        """Initialize the scraper with configuration.
        
        Args:
            config (dict): Configuration with sources to scrape
            directus_config (dict): Directus API configuration (optional)
            output_dir (str): Directory to save output files
            max_events_per_source (int): Maximum events to scrape per source (-1 for all)
        """
        self.sources = config.get("sources", [])
        self.max_events = max_events_per_source
        self.output_dir = output_dir
        self.directus_client = None
        self.collection_name = "scraped_data"
        
        # Initialize Directus client if configuration is provided
        if directus_config:
            # Check if using token or email/password auth
            if directus_config.get("token"):
                self.directus_client = DirectusClient(
                    directus_config.get("url"),
                    token=directus_config.get("token")
                )
            else:
                self.directus_client = DirectusClient(
                    directus_config.get("url"),
                    email=directus_config.get("email"),
                    password=directus_config.get("password")
                )
        
        # Create output directory for file-based outputs
        os.makedirs(self.output_dir, exist_ok=True)
        
    def calculate_hash(self, content):
        """Calculate MD5 hash of content for deduplication"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
        
    def get_page_content(self, url, headers=None):
        """Get content from a URL with error handling.
        
        Args:
            url (str): URL to fetch
            headers (dict): Optional HTTP headers
            
        Returns:
            str: HTML content or None if fetch fails
        """
        if not headers:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept-Charset": "utf-8"
            }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            # Ensure correct encoding detection
            if response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def normalize_text(self, text):
        """Normalize text to handle German umlauts and special characters properly.
        
        Args:
            text (str): Text to normalize
            
        Returns:
            str: Normalized text
        """
        if not text:
            return ""
            
        # Replace common HTML entities for German umlauts
        replacements = {
            '&auml;': 'ä', '&ouml;': 'ö', '&uuml;': 'ü',
            '&Auml;': 'Ä', '&Ouml;': 'Ö', '&Uuml;': 'Ü',
            '&szlig;': 'ß', '&euro;': '€', '&nbsp;': ' ',
            '\u00e4': 'ä', '\u00f6': 'ö', '\u00fc': 'ü',
            '\u00c4': 'Ä', '\u00d6': 'Ö', '\u00dc': 'Ü',
            '\u00df': 'ß'
        }
        
        for entity, char in replacements.items():
            text = text.replace(entity, char)
            
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text

    def check_duplicate_content(self, content):
        """Check if content already exists in the database.
        
        Args:
            content (str): Content to check
            
        Returns:
            tuple: (is_duplicate, existing_item_id)
        """
        if not self.directus_client:
            return False, None
        
        # Calculate hash of content
        content_hash = self.calculate_hash(content)
        
        # Check if content exists in database
        existing_item = self.directus_client.get_item_by_hash(self.collection_name, content_hash)
        
        if existing_item:
            logger.info(f"Found duplicate content with ID: {existing_item['id']}")
            return True, existing_item['id']
        
        return False, None
    
    def save_to_directus(self, event_data, content_hash):
        """Save event data to Directus database.
        
        Args:
            event_data (dict): Event data
            content_hash (str): Content hash for deduplication
            
        Returns:
            str: ID of created item
        """
        if not self.directus_client:
            return None
        
        # Prepare data for Directus
        now = datetime.now().isoformat()
        
        directus_data = {
            "url": event_data.get("url"),
            "source_name": event_data.get("source_name"),
            "content_hash": content_hash,
            "raw_content": json.dumps(event_data, ensure_ascii=False),  # Preserve German characters
            "scraped_at": now,
            "processed": False,
            "processing_status": "pending"
        }
        
        # Save to Directus
        try:
            created_item = self.directus_client.create_item(self.collection_name, directus_data)
            logger.info(f"Saved event to Directus with ID: {created_item['id']}")
            return created_item['id']
        except Exception as e:
            logger.error(f"Failed to save event to Directus: {str(e)}")
            return None
    
    def scrape_source(self, source):
        """Scrape a single source for events, following links to get full details.
        
        Args:
            source (dict): Source configuration
            
        Returns:
            list: List of event details as dictionaries
        """
        logger.info(f"Scraping {source['name']} - {source['url']}")
        
        full_event_details = []
        
        # Get the main listing page
        content = self.get_page_content(source['url'])
        if not content:
            return []
        
        # Check if this page is already in our database
        if self.directus_client:
            is_duplicate, item_id = self.check_duplicate_content(content)
            if is_duplicate:
                logger.info(f"Skipping {source['name']} - content already in database with ID {item_id}")
                return []
        
        # Parse the listing page
        soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')
        event_elements = soup.select(source['event_selector'])
        
        if not event_elements:
            logger.warning(f"No events found on {source['name']} using selector: {source['event_selector']}")
            return []
        
        # Limit events based on max_events
        if self.max_events > 0:
            event_elements = event_elements[:self.max_events]
        
        logger.info(f"Found {len(event_elements)} event listings on {source['name']} (limited to {self.max_events if self.max_events > 0 else 'all'} events)")
        
        # Save raw HTML for debugging
        raw_html_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_raw.html")
        with open(raw_html_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Log file for scraped content
        content_log_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_content.txt")
        with open(content_log_path, "w", encoding="utf-8") as content_log:
            content_log.write(f"SCRAPING SOURCE: {source['name']} - {source['url']}\n")
            content_log.write("="*80 + "\n\n")
            
            # Process each event listing
            for i, element in enumerate(event_elements):
                content_log.write(f"EVENT {i+1}\n")
                content_log.write("-"*50 + "\n\n")
                
                # Log the listing text - with umlaut normalization
                listing_text = self.normalize_text(element.get_text(strip=True, separator=' '))
                content_log.write(f"LISTING TEXT:\n{listing_text}\n\n")
                
                # Find the link to the detail page
                link_element = element.select_one(source['link_selector'])
                if not link_element or not link_element.has_attr('href'):
                    content_log.write("NO LINK FOUND\n\n")
                    
                    # If no link found, use the listing text as fallback
                    event_data = {
                        "listing_text": listing_text,
                        "detail_text": None,
                        "url": None,
                        "source_name": source['name']
                    }
                    
                    # Check for duplicate content
                    if self.directus_client:
                        is_duplicate, item_id = self.check_duplicate_content(json.dumps(event_data, ensure_ascii=False))
                        if is_duplicate:
                            content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                            continue
                    
                    # Add to our results
                    full_event_details.append(event_data)
                    
                    # Save to Directus if configured
                    if self.directus_client:
                        content_hash = self.calculate_hash(json.dumps(event_data, ensure_ascii=False))
                        self.save_to_directus(event_data, content_hash)
                    
                    continue
                
                # Get the full URL
                event_url = urljoin(source['url'], link_element['href'])
                content_log.write(f"EVENT URL: {event_url}\n\n")
                
                # Get the detail page
                logger.info(f"Following link to {event_url}")
                detail_content = self.get_page_content(event_url)
                
                if not detail_content:
                    content_log.write("COULD NOT FETCH DETAIL PAGE\n\n")
                    
                    # If detail page fails, use the listing text as fallback
                    event_data = {
                        "listing_text": listing_text,
                        "detail_text": None,
                        "url": event_url,
                        "source_name": source['name']
                    }
                    
                    # Check for duplicate content
                    if self.directus_client:
                        is_duplicate, item_id = self.check_duplicate_content(json.dumps(event_data, ensure_ascii=False))
                        if is_duplicate:
                            content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                            continue
                    
                    # Add to our results
                    full_event_details.append(event_data)
                    
                    # Save to Directus if configured
                    if self.directus_client:
                        content_hash = self.calculate_hash(json.dumps(event_data, ensure_ascii=False))
                        self.save_to_directus(event_data, content_hash)
                    
                    continue
                
                # Save detail page HTML for reference
                detail_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_detail_{i+1}.html")
                with open(detail_path, "w", encoding="utf-8") as f:
                    f.write(detail_content)
                
                # Parse the detail page
                detail_soup = BeautifulSoup(detail_content, 'html.parser', from_encoding='utf-8')
                detail_element = detail_soup.select_one(source['full_page_selector'])
                
                if not detail_element:
                    # If selector doesn't match, use the whole body
                    detail_text = self.normalize_text(detail_soup.body.get_text(strip=True, separator=' '))
                    content_log.write(f"SELECTOR NOT FOUND, USING BODY TEXT\n")
                else:
                    detail_text = self.normalize_text(detail_element.get_text(strip=True, separator=' '))
                    
                content_log.write(f"DETAIL TEXT:\n{detail_text}\n\n")
                content_log.write("="*80 + "\n\n")
                
                # Add both the listing and detail text
                event_data = {
                    "listing_text": listing_text,
                    "detail_text": detail_text,
                    "url": event_url,
                    "source_name": source['name']
                }
                
                # Check for duplicate content
                if self.directus_client:
                    is_duplicate, item_id = self.check_duplicate_content(json.dumps(event_data, ensure_ascii=False))
                    if is_duplicate:
                        content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                        continue
                
                # Add to our results
                full_event_details.append(event_data)
                
                # Save to Directus if configured
                if self.directus_client:
                    content_hash = self.calculate_hash(json.dumps(event_data, ensure_ascii=False))
                    self.save_to_directus(event_data, content_hash)
                
                # Be nice to the server - small delay between requests
                time.sleep(2)
        
        logger.info(f"Scraped {len(full_event_details)} events with details from {source['name']}")
        return full_event_details
    
    def _safe_filename(self, s):
        """Convert a string to a safe filename."""
        return re.sub(r'[^\w\-_]', '_', s.lower())
    
    def run(self):
        """Run the scraper for all configured sources."""
        logger.info(f"Starting event scraper (max {self.max_events} events per source)")
        
        all_events = []
        new_events_count = 0
        skipped_events_count = 0
        
        # Process each source
        for source in self.sources:
            try:
                events = self.scrape_source(source)
                all_events.extend(events)
                new_events_count += len(events)
            except Exception as e:
                logger.error(f"Error scraping source {source['name']}: {str(e)}")
                logger.exception("Full exception details:")
        
        # Save all scraped events to a single JSON file (as backup)
        output_path = os.path.join(self.output_dir, "scraped_events.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Scraping complete. {new_events_count} new events, {skipped_events_count} skipped (duplicate).")
        return all_events

def load_config(config_path):
    """Load scraper configuration from a JSON file.
    
    Args:
        config_path (str): Path to the configuration file
        
    Returns:
        dict: Configuration dictionary
    """
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading configuration from {config_path}: {str(e)}")
        # Return a minimal default configuration
        return {
            "sources": [
                {
                    "name": "Stifter-helfen.de",
                    "url": "https://www.hausdesstiftens.org/non-profits/wissen/webinare/",
                    "type": "html",
                    "event_selector": ".eg-webinare-22-wrapper",
                    "link_selector": "a",
                    "full_page_selector": ".article-content"
                }
            ]
        }

def main():
    """Main entry point for the scraper application."""
    parser = argparse.ArgumentParser(description="Event Scraper for Non-Profit Digitalization Events")
    parser.add_argument("--config", "-c", default="config/sources.json", help="Path to configuration file")
    parser.add_argument("--directus-config", "-d", default="config/directus.json", help="Path to Directus configuration file")
    parser.add_argument("--output", "-o", default="data", help="Output directory for scraped data")
    parser.add_argument("--max-events", "-m", type=int, default=-1, 
                        help="Maximum events to scrape per source (-1 for all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--no-directus", action="store_true", help="Disable Directus database integration")
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Ensure config directory exists
    config_dir = os.path.dirname(args.config)
    if config_dir and not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    
    # Create default config if it doesn't exist
    if not os.path.exists(args.config):
        logger.info(f"Configuration file not found, creating default at {args.config}")
        default_config = {
            "sources": [
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
        }
        with open(args.config, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
    
    # Create default Directus config if it doesn't exist
    if not args.no_directus and not os.path.exists(args.directus_config):
        logger.info(f"Directus configuration file not found, creating default at {args.directus_config}")
        default_directus_config = {
            "url": "https://calapi.buerofalk.de",
            "token": "APpU898yct7V2VyMFfcJse_7WXktDY-o",
            "collection": "scraped_data"
        }
        
        # Ensure directus config directory exists
        directus_config_dir = os.path.dirname(args.directus_config)
        if directus_config_dir and not os.path.exists(directus_config_dir):
            os.makedirs(directus_config_dir, exist_ok=True)
            
        with open(args.directus_config, "w", encoding="utf-8") as f:
            json.dump(default_directus_config, f, indent=2, ensure_ascii=False)
    
    # Load configurations
    config = load_config(args.config)
    directus_config = None
    
    if not args.no_directus:
        try:
            with open(args.directus_config, "r", encoding="utf-8") as f:
                directus_config = json.load(f)
                logger.info(f"Loaded Directus configuration from {args.directus_config}")
        except Exception as e:
            logger.error(f"Error loading Directus configuration: {str(e)}")
            logger.warning("Continuing without Directus integration")
    
    # Run the scraper
    scraper = EventScraper(
        config=config, 
        directus_config=directus_config,
        output_dir=args.output,
        max_events_per_source=args.max_events
    )
    scraper.run()

if __name__ == "__main__":
    main()