#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Optimized Event Scraper for Non-Profit Digitalization Events with Directus Database Integration

This script scrapes websites for digitalization events targeted at non-profit organizations,
extracts the raw event information, and saves it to a Directus database.
This version includes optimizations for performance:
- URL and content caching to avoid redundant requests
- Reduced disk I/O by not saving HTML files by default
- More efficient text normalization
- Environment variable support for secure API credentials

Setup Instructions:
1. Run the setup script to create a virtual environment and install dependencies:
   - On macOS/Linux: ./setup.sh
   - On Windows: setup.bat
2. Activate the virtual environment:
   - On macOS/Linux: source venv/bin/activate
   - On Windows: venv\Scripts\activate.bat
3. Run the script: python scraper-directus-optimized.py

For more options, run: python scraper-directus-optimized.py --help
"""
import sys

# Check for required dependencies before importing them
def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = {
        'requests': 'requests',
        'bs4': 'beautifulsoup4',
        'dotenv': 'python-dotenv'
    }
    
    missing_packages = []
    
    for module, package in required_packages.items():
        try:
            __import__(module)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Error: Missing required dependencies.")
        print("Please install the following packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nYou can install them by running:")
        print("  pip install -r requirements.txt")
        print("\nOr use the setup script to create a virtual environment:")
        print("  - On macOS/Linux: ./setup.sh")
        print("  - On Windows: setup.bat")
        sys.exit(1)

# Check dependencies before proceeding
check_dependencies()

# Now import the required modules
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
import pickle
from functools import lru_cache
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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

class URLCache:
    """Simple cache for URL content to avoid redundant requests"""
    
    def __init__(self, cache_file=None, max_age_hours=24):
        """Initialize the URL cache.
        
        Args:
            cache_file (str): Path to the cache file
            max_age_hours (int): Maximum age of cached items in hours
        """
        self.cache = {}
        self.cache_file = cache_file
        self.max_age_seconds = max_age_hours * 3600
        
        # Load cache from file if it exists
        if cache_file and os.path.exists(cache_file):
            try:
                with open(cache_file, 'rb') as f:
                    self.cache = pickle.load(f)
                logger.info(f"Loaded URL cache with {len(self.cache)} entries")
                
                # Clean expired entries
                self._clean_expired()
            except Exception as e:
                logger.error(f"Error loading URL cache: {str(e)}")
                self.cache = {}
    
    def _clean_expired(self):
        """Remove expired entries from the cache"""
        now = datetime.now().timestamp()
        expired_keys = []
        
        for url, entry in self.cache.items():
            if now - entry['timestamp'] > self.max_age_seconds:
                expired_keys.append(url)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"Removed {len(expired_keys)} expired entries from URL cache")
    
    def get(self, url):
        """Get content from cache if available and not expired.
        
        Args:
            url (str): URL to retrieve
            
        Returns:
            str or None: Cached content or None if not in cache or expired
        """
        if url in self.cache:
            entry = self.cache[url]
            now = datetime.now().timestamp()
            
            # Check if entry is expired
            if now - entry['timestamp'] > self.max_age_seconds:
                del self.cache[url]
                return None
            
            return entry['content']
        
        return None
    
    def set(self, url, content):
        """Add or update an entry in the cache.
        
        Args:
            url (str): URL to cache
            content (str): Content to cache
        """
        self.cache[url] = {
            'content': content,
            'timestamp': datetime.now().timestamp()
        }
        
        # Save cache to file if configured
        if self.cache_file:
            try:
                cache_dir = os.path.dirname(self.cache_file)
                if cache_dir:
                    os.makedirs(cache_dir, exist_ok=True)
                    
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.cache, f)
            except Exception as e:
                logger.error(f"Error saving URL cache: {str(e)}")
    
    def clear(self):
        """Clear the cache"""
        self.cache = {}
        
        # Remove cache file if it exists
        if self.cache_file and os.path.exists(self.cache_file):
            try:
                os.remove(self.cache_file)
            except Exception as e:
                logger.error(f"Error removing cache file: {str(e)}")

class ContentHashCache:
    """Cache for content hashes to avoid redundant database queries"""
    
    def __init__(self):
        """Initialize the content hash cache"""
        self.seen_hashes = set()
    
    def add(self, content_hash):
        """Add a hash to the cache.
        
        Args:
            content_hash (str): Hash to add
        """
        self.seen_hashes.add(content_hash)
    
    def contains(self, content_hash):
        """Check if a hash is in the cache.
        
        Args:
            content_hash (str): Hash to check
            
        Returns:
            bool: True if hash is in cache, False otherwise
        """
        return content_hash in self.seen_hashes

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
        
        # Use a session for connection pooling
        self.session = requests.Session()
        
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
            response = self.session.post(auth_url, json=payload)
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
            response = self.session.post(url, headers=self.get_headers(), json=data)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = self.session.post(url, headers=self.get_headers(), json=data)
            
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
            response = self.session.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = self.session.get(url, headers=self.get_headers(), params=params)
            
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
            response = self.session.patch(url, headers=self.get_headers(), json=data)
            
            if response.status_code == 401:  # Token might have expired
                self.login()
                response = self.session.patch(url, headers=self.get_headers(), json=data)
            
            response.raise_for_status()
            return response.json().get('data', {})
        except Exception as e:
            logger.error(f"Failed to update item {item_id} in {collection}: {str(e)}")
            raise


class EventScraper:
    """Main scraper class for collecting non-profit digitalization events with Directus integration."""
    
    def __init__(self, config, directus_config=None, output_dir="data", max_events_per_source=3, save_html=False, cache_dir=None):
        """Initialize the scraper with configuration.
        
        Args:
            config (dict): Configuration with sources to scrape
            directus_config (dict): Directus API configuration (optional)
            output_dir (str): Directory to save output files
            max_events_per_source (int): Maximum events to scrape per source (-1 for all)
            save_html (bool): Whether to save HTML files to disk
            cache_dir (str): Directory to store cache files
        """
        self.sources = config.get("sources", [])
        self.max_events = max_events_per_source
        self.output_dir = output_dir
        self.directus_client = None
        self.collection_name = "scraped_data"
        self.save_html = save_html
        
        # Initialize caches
        cache_file = os.path.join(cache_dir, "url_cache.pkl") if cache_dir else None
        self.url_cache = URLCache(cache_file=cache_file)
        self.hash_cache = ContentHashCache()
        
        # Precompile regex patterns for text normalization
        self._compile_regex_patterns()
        
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
        
        # Create cache directory if specified
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
    
    def _compile_regex_patterns(self):
        """Precompile regex patterns for text normalization"""
        # Pattern for removing extra whitespace
        self.whitespace_pattern = re.compile(r'\s+')
        
        # Create a single regex for HTML entity replacements
        entity_patterns = {
            '&auml;': 'ä', '&ouml;': 'ö', '&uuml;': 'ü',
            '&Auml;': 'Ä', '&Ouml;': 'Ö', '&Uuml;': 'Ü',
            '&szlig;': 'ß', '&euro;': '€', '&nbsp;': ' '
        }
        
        pattern_parts = []
        self.entity_replacements = {}
        
        for entity, char in entity_patterns.items():
            pattern_parts.append(re.escape(entity))
            self.entity_replacements[entity] = char
        
        self.entity_pattern = re.compile('|'.join(pattern_parts))
        
    def calculate_hash(self, content):
        """Calculate MD5 hash of content for deduplication"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
        
    def get_page_content(self, url, headers=None, use_cache=True):
        """Get content from a URL with error handling and caching.
        
        Args:
            url (str): URL to fetch
            headers (dict): Optional HTTP headers
            use_cache (bool): Whether to use the URL cache
            
        Returns:
            str: HTML content or None if fetch fails
        """
        # Check cache first if enabled
        if use_cache:
            cached_content = self.url_cache.get(url)
            if cached_content:
                logger.debug(f"Using cached content for {url}")
                return cached_content
        
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
            
            content = response.text
            
            # Cache the content if caching is enabled
            if use_cache:
                self.url_cache.set(url, content)
            
            return content
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
        
        # Replace HTML entities using regex
        def replace_entity(match):
            entity = match.group(0)
            return self.entity_replacements.get(entity, entity)
        
        text = self.entity_pattern.sub(replace_entity, text)
        
        # Replace Unicode characters
        unicode_replacements = {
            '\u00e4': 'ä', '\u00f6': 'ö', '\u00fc': 'ü',
            '\u00c4': 'Ä', '\u00d6': 'Ö', '\u00dc': 'Ü',
            '\u00df': 'ß'
        }
        
        for char, replacement in unicode_replacements.items():
            text = text.replace(char, replacement)
        
        # Remove extra whitespace using regex
        text = self.whitespace_pattern.sub(' ', text)
        
        return text

    def check_duplicate_content(self, content):
        """Check if content already exists in the database.
        
        Args:
            content (str): Content to check
            
        Returns:
            tuple: (is_duplicate, existing_item_id)
        """
        # Calculate hash of content
        content_hash = self.calculate_hash(content)
        
        # Check in-memory cache first
        if self.hash_cache.contains(content_hash):
            logger.info(f"Found duplicate content in memory cache")
            return True, None
        
        # If not in memory cache, check database if available
        if self.directus_client:
            existing_item = self.directus_client.get_item_by_hash(self.collection_name, content_hash)
            
            if existing_item:
                # Add to memory cache for future checks
                self.hash_cache.add(content_hash)
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
            
            # Add hash to memory cache
            self.hash_cache.add(content_hash)
            
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
        
        # Check if source has pagination configuration
        pagination_config = source.get('pagination', None)
        
        if pagination_config and pagination_config.get('type') == 'url-param':
            # Handle paginated content
            return self._scrape_paginated_source(source, pagination_config)
        else:
            # Handle single page content
            return self._scrape_single_page(source, source['url'])
    
    def _scrape_paginated_source(self, source, pagination_config):
        """Scrape a source with pagination.
        
        Args:
            source (dict): Source configuration
            pagination_config (dict): Pagination configuration
            
        Returns:
            list: List of event details from all pages
        """
        full_event_details = []
        param_name = pagination_config.get('param_name', 'page')
        start_index = pagination_config.get('start_index', 0)
        max_pages = pagination_config.get('max_pages', 20)
        
        # Iterate through pages
        for page_num in range(start_index, start_index + max_pages):
            # Construct the URL with pagination parameter
            if '?' in source['url']:
                page_url = f"{source['url']}&{param_name}={page_num}"
            else:
                page_url = f"{source['url']}?{param_name}={page_num}"
            
            logger.info(f"Scraping page {page_num} - {page_url}")
            
            # Scrape the page
            page_events = self._scrape_single_page(source, page_url)
            
            # Add events to the full list
            full_event_details.extend(page_events)
            
            # If no events found on this page, assume we've reached the end
            if not page_events:
                logger.info(f"No events found on page {page_num}, stopping pagination")
                break
            
            # Be nice to the server - small delay between pages
            time.sleep(2)
        
        return full_event_details
    
    def _scrape_single_page(self, source, url):
        """Scrape a single page for events.
        
        Args:
            source (dict): Source configuration
            url (str): URL to scrape
            
        Returns:
            list: List of event details as dictionaries
        """
        full_event_details = []
        
        # Get the page content
        content = self.get_page_content(url)
        if not content:
            return []
        
        # Check if this page is already in our database
        if self.directus_client:
            is_duplicate, item_id = self.check_duplicate_content(content)
            if is_duplicate:
                logger.info(f"Skipping {url} - content already in database with ID {item_id}")
                return []
        
        # Parse the listing page
        soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')
        event_elements = soup.select(source['event_selector'])
        
        if not event_elements:
            logger.warning(f"No events found on {url} using selector: {source['event_selector']}")
            return []
        
        # Limit events based on max_events
        if self.max_events > 0:
            event_elements = event_elements[:self.max_events]
        
        logger.info(f"Found {len(event_elements)} event listings on {url} (limited to {self.max_events if self.max_events > 0 else 'all'} events)")
        
        # Save raw HTML for debugging if enabled
        if self.save_html:
            raw_html_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_raw.html")
            with open(raw_html_path, "w", encoding="utf-8") as f:
                f.write(content)
        
        # Log file for scraped content
        content_log_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_content.txt")
        
        # Determine if we should append to the log file (for paginated content)
        # Extract the page number from the URL if it's a paginated URL
        page_num = None
        if '?' in url and 'page=' in url:
            page_param = re.search(r'page=(\d+)', url)
            if page_param:
                page_num = int(page_param.group(1))
        
        # Open the log file in append mode if it's not the first page
        mode = "a" if page_num is not None and page_num > 0 else "w"
        
        with open(content_log_path, mode, encoding="utf-8") as content_log:
            # Only write the header if it's a new file or the first page
            if mode == "w":
                content_log.write(f"SCRAPING SOURCE: {source['name']} - {url}\n")
                content_log.write("="*80 + "\n\n")
            else:
                content_log.write(f"\nPAGE {page_num} - {url}\n")
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
                        event_json = json.dumps(event_data, ensure_ascii=False)
                        is_duplicate, item_id = self.check_duplicate_content(event_json)
                        if is_duplicate:
                            content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                            continue
                    
                    # Add to our results
                    full_event_details.append(event_data)
                    
                    # Save to Directus if configured
                    if self.directus_client:
                        event_json = json.dumps(event_data, ensure_ascii=False)
                        content_hash = self.calculate_hash(event_json)
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
                        event_json = json.dumps(event_data, ensure_ascii=False)
                        is_duplicate, item_id = self.check_duplicate_content(event_json)
                        if is_duplicate:
                            content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                            continue
                    
                    # Add to our results
                    full_event_details.append(event_data)
                    
                    # Save to Directus if configured
                    if self.directus_client:
                        event_json = json.dumps(event_data, ensure_ascii=False)
                        content_hash = self.calculate_hash(event_json)
                        self.save_to_directus(event_data, content_hash)
                    
                    continue
                
                # Save detail page HTML for reference if enabled
                if self.save_html:
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
                    event_json = json.dumps(event_data, ensure_ascii=False)
                    is_duplicate, item_id = self.check_duplicate_content(event_json)
                    if is_duplicate:
                        content_log.write(f"DUPLICATE CONTENT - ID: {item_id}\n\n")
                        continue
                
                # Add to our results
                full_event_details.append(event_data)
                
                # Save to Directus if configured
                if self.directus_client:
                    event_json = json.dumps(event_data, ensure_ascii=False)
                    content_hash = self.calculate_hash(event_json)
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
    parser = argparse.ArgumentParser(description="Optimized Event Scraper for Non-Profit Digitalization Events")
    parser.add_argument("--config", "-c", default="config/sources.json", help="Path to configuration file")
    parser.add_argument("--directus-config", "-d", default="config/directus.json", help="Path to Directus configuration file")
    parser.add_argument("--output", "-o", default="data", help="Output directory for scraped data")
    parser.add_argument("--max-events", "-m", type=int, default=-1, 
                        help="Maximum events to scrape per source (-1 for all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--no-directus", action="store_true", help="Disable Directus database integration")
    parser.add_argument("--save-html", action="store_true", help="Save HTML files to disk")
    parser.add_argument("--cache-dir", default=".cache", help="Directory to store cache files")
    parser.add_argument("--clear-cache", action="store_true", help="Clear URL cache before running")
    
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
        
        # Get values from environment variables or use defaults
        default_directus_config = {
            "url": os.getenv("DIRECTUS_API_URL", "https://your-directus-api-url"),
            "token": os.getenv("DIRECTUS_API_TOKEN", "your-api-token-here"),
            "collection": os.getenv("DIRECTUS_COLLECTION", "scraped_data")
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
    
    # Create cache directory if needed
    if args.cache_dir:
        os.makedirs(args.cache_dir, exist_ok=True)
    
    # Initialize URL cache
    url_cache = URLCache(cache_file=os.path.join(args.cache_dir, "url_cache.pkl") if args.cache_dir else None)
    
    # Clear cache if requested
    if args.clear_cache:
        logger.info("Clearing URL cache")
        url_cache.clear()
    
    # Run the scraper
    scraper = EventScraper(
        config=config, 
        directus_config=directus_config,
        output_dir=args.output,
        max_events_per_source=args.max_events,
        save_html=args.save_html,
        cache_dir=args.cache_dir
    )
    scraper.run()

if __name__ == "__main__":
    main()
