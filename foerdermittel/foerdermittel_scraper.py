#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fördermittel (Funding Programs) Scraper for German NGOs

This script scrapes German funding databases for funding opportunities targeted at NGOs
and Wohlfahrtsverbände (welfare organizations). It extracts raw funding information
and saves it to a Directus database for further LLM-based analysis.

The scraper supports:
- Static HTML pages with search filters
- URL caching to reduce redundant requests
- Content hashing for deduplication
- Directus database integration

Setup:
1. Ensure shared/directus_client.py is available
2. Configure sources in config/foerdermittel_sources.json
3. Configure Directus credentials in config/directus.json or via environment variables
4. Run: python foerdermittel_scraper.py
"""

import sys
import os
import re
import json
import time
import logging
import argparse
from urllib.parse import urljoin, urlparse
from datetime import datetime
from pathlib import Path

# Check for required dependencies
def check_dependencies():
    """Check if all required dependencies are installed."""
    required_packages = {
        'requests': 'requests',
        'bs4': 'beautifulsoup4',
        'dotenv': 'python-dotenv',
        'lxml': 'lxml'  # For XML/RSS parsing
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
        sys.exit(1)

# Check dependencies
check_dependencies()

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Import shared utilities
from shared.directus_client import DirectusClient, URLCache, ContentHashCache, calculate_content_hash

# Load environment variables
load_dotenv()

# Set up logging
def setup_logging(log_level=logging.INFO, log_dir="logs"):
    """Configure logging with file and console handlers."""
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "foerdermittel_scraper.log"), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("foerdermittel-scraper")

logger = setup_logging()


class FoerdermittelScraper:
    """Main scraper class for collecting German funding programs with Directus integration."""

    def __init__(self, config, directus_config=None, output_dir="data",
                 max_programs_per_source=10, save_html=False, cache_dir=None):
        """Initialize the scraper with configuration.

        Args:
            config (dict): Configuration with sources to scrape
            directus_config (dict): Directus API configuration (optional)
            output_dir (str): Directory to save output files
            max_programs_per_source (int): Maximum programs to scrape per source (-1 for all)
            save_html (bool): Whether to save HTML files to disk
            cache_dir (str): Directory to store cache files
        """
        self.sources = config.get("sources", [])
        self.max_programs = max_programs_per_source
        self.output_dir = output_dir
        self.directus_client = None
        self.collection_name = "foerdermittel_scraped_data"
        self.save_html = save_html

        # Initialize caches
        cache_file = os.path.join(cache_dir, "foerdermittel_url_cache.pkl") if cache_dir else None
        self.url_cache = URLCache(cache_file=cache_file, max_age_hours=168)  # 1 week cache
        self.hash_cache = ContentHashCache()

        # Initialize Directus client if configuration is provided
        if directus_config:
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

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Create cache directory if specified
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

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
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Cache-Control": "max-age=0"
            }

        try:
            # Create a session for better connection handling
            session = requests.Session()

            # Try with verify=True first
            response = session.get(url, headers=headers, timeout=30, verify=True)
            response.raise_for_status()

            # Ensure correct encoding
            if response.encoding == 'ISO-8859-1':
                response.encoding = 'utf-8'

            content = response.text

            # Cache the content if caching is enabled
            if use_cache:
                self.url_cache.set(url, content)

            return content
        except requests.exceptions.SSLError:
            # Retry with verify=False for SSL issues
            try:
                logger.warning(f"SSL verification failed for {url}, retrying without verification")
                response = session.get(url, headers=headers, timeout=30, verify=False)
                response.raise_for_status()
                content = response.text
                if use_cache:
                    self.url_cache.set(url, content)
                return content
            except Exception as e:
                logger.error(f"Error fetching {url} even without SSL verification: {str(e)}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def normalize_text(self, text):
        """Normalize text to handle German umlauts and whitespace.

        Args:
            text (str): Text to normalize

        Returns:
            str: Normalized text
        """
        if not text:
            return ""

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def check_duplicate_content(self, content):
        """Check if content already exists in the database.

        DEPRECATED: Use check_duplicate_or_changed instead for change detection.

        Args:
            content (str): Content to check

        Returns:
            tuple: (is_duplicate, existing_item_id)
        """
        content_hash = calculate_content_hash(content)

        # Check in-memory cache first
        if self.hash_cache.contains(content_hash):
            logger.info("Found duplicate content in memory cache")
            return True, None

        # Check database if available
        if self.directus_client:
            existing_item = self.directus_client.get_item_by_hash(self.collection_name, content_hash)

            if existing_item:
                self.hash_cache.add(content_hash)
                logger.info(f"Found duplicate content with ID: {existing_item['id']}")
                return True, existing_item['id']

        return False, None

    def check_duplicate_or_changed(self, content, url):
        """Check if content is duplicate or has changed.

        Args:
            content (str): Content to check
            url (str): URL of the program

        Returns:
            tuple: (status, existing_item_id, previous_hash)
            status: 'new', 'unchanged', 'changed'
        """
        content_hash = calculate_content_hash(content)

        # Check database for existing entry with this URL
        if self.directus_client:
            existing_item = self.directus_client.get_item_by_url(
                self.collection_name, url
            )

            if existing_item:
                previous_hash = existing_item.get('content_hash')

                if previous_hash == content_hash:
                    logger.debug(f"Content unchanged for: {url}")
                    return ('unchanged', existing_item['id'], previous_hash)
                else:
                    logger.info(f"Content changed for: {url}")
                    return ('changed', existing_item['id'], previous_hash)

        logger.debug(f"New program: {url}")
        return ('new', None, None)

    def save_to_directus(self, program_data, content_hash, status='new',
                         existing_id=None, previous_hash=None, existing_item=None):
        """Save or update funding program data to Directus database.

        Args:
            program_data (dict): Program data
            content_hash (str): Content hash for deduplication
            status (str): 'new', 'unchanged', or 'changed'
            existing_id (int): ID of existing item (for updates)
            previous_hash (str): Previous content hash (for changes)
            existing_item (dict): Full existing item data

        Returns:
            int: ID of created/updated item
        """
        if not self.directus_client:
            return None

        now = datetime.now().isoformat()

        if status == 'new':
            # Create new entry
            directus_data = {
                "url": program_data.get("url"),
                "source_name": program_data.get("source_name"),
                "content_hash": content_hash,
                "raw_content": json.dumps(program_data, ensure_ascii=False),
                "scraped_at": now,
                "last_checked_at": now,
                "last_seen_at": now,
                "processed": False,
                "processing_status": "pending",
                "is_active": True,
                "check_count": 1
            }

            try:
                created_item = self.directus_client.create_item(
                    self.collection_name, directus_data
                )
                logger.info(f"Saved new program to Directus with ID: {created_item['id']}")
                self.hash_cache.add(content_hash)
                return created_item['id']
            except Exception as e:
                logger.error(f"Failed to save program to Directus: {str(e)}")
                return None

        elif status == 'unchanged':
            # Update timestamps only
            update_data = {
                "last_checked_at": now,
                "last_seen_at": now,
                "check_count": existing_item.get('check_count', 0) + 1 if existing_item else 1
            }

            try:
                self.directus_client.update_item(
                    self.collection_name, existing_id, update_data
                )
                logger.debug(f"Updated timestamps for program ID: {existing_id}")
                return existing_id
            except Exception as e:
                logger.error(f"Failed to update timestamps: {str(e)}")
                return existing_id

        elif status == 'changed':
            # Update with new content and flag for reprocessing
            update_data = {
                "previous_content_hash": previous_hash,
                "content_hash": content_hash,
                "raw_content": json.dumps(program_data, ensure_ascii=False),
                "scraped_at": now,
                "last_checked_at": now,
                "last_seen_at": now,
                "change_detected_at": now,
                "processed": False,
                "processing_status": "pending_update",
                "check_count": existing_item.get('check_count', 0) + 1 if existing_item else 1
            }

            try:
                self.directus_client.update_item(
                    self.collection_name, existing_id, update_data
                )
                logger.info(f"Updated changed program ID: {existing_id}")
                self.hash_cache.add(content_hash)
                return existing_id
            except Exception as e:
                logger.error(f"Failed to update changed program: {str(e)}")
                return existing_id

    def mark_removed_programs(self, source_name, seen_urls):
        """Mark programs as inactive if they weren't found in latest scrape.

        Uses a safety buffer - only marks as removed if not seen in 2+ scrapes
        (roughly 1 week for weekly scrapes).

        Args:
            source_name (str): Name of the source
            seen_urls (set): Set of URLs found in current scrape
        """
        if not self.directus_client:
            return

        now = datetime.now().isoformat()

        # Get all active programs from this source
        active_programs = self.directus_client.get_active_programs(
            self.collection_name, source_name
        )

        removed_count = 0

        for program in active_programs:
            if program['url'] not in seen_urls:
                # Program not found in current scrape

                # Calculate days since last seen
                if program.get('last_seen_at'):
                    try:
                        last_seen = datetime.fromisoformat(program['last_seen_at'].replace('Z', '+00:00'))
                        days_since_last_seen = (datetime.now(last_seen.tzinfo) - last_seen).days
                    except Exception:
                        days_since_last_seen = 999  # Error parsing, mark immediately
                else:
                    days_since_last_seen = 999  # Very old, mark immediately

                # Only mark as inactive after safety buffer (7 days ≈ 1-2 scrapes)
                if days_since_last_seen >= 7:
                    try:
                        self.directus_client.update_item(
                            self.collection_name,
                            program['id'],
                            {
                                "is_active": False,
                                "last_checked_at": now,
                                "processing_status": "removed"
                            }
                        )
                        logger.warning(f"Marked as removed: {program['url']}")
                        removed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to mark program as removed: {str(e)}")

        if removed_count > 0:
            logger.info(f"Marked {removed_count} programs from {source_name} as removed")

    def scrape_rss_feed(self, source):
        """Scrape funding programs from an RSS feed.

        Args:
            source (dict): Source configuration with RSS feed URL

        Returns:
            list: List of funding program URLs
        """
        logger.info(f"Scraping RSS feed: {source['name']} - {source['url']}")

        program_urls = []

        # Get the RSS feed
        content = self.get_page_content(source['url'], use_cache=False)  # Don't cache RSS feeds
        if not content:
            return []

        # Parse as XML
        soup = BeautifulSoup(content, 'xml')

        # Find all items
        items = soup.find_all('item')
        logger.info(f"Found {len(items)} items in RSS feed")

        for item in items:
            link_element = item.find('link')
            if link_element:
                url = link_element.get_text().strip()

                # Clean tracking parameters if needed
                url = url.split('?')[0] if '?' in url and 'etcc_cmp' in url else url

                if url not in program_urls:
                    program_urls.append(url)

        # Limit based on max_programs
        if self.max_programs > 0:
            program_urls = program_urls[:self.max_programs]

        logger.info(f"Extracted {len(program_urls)} program URLs from RSS feed")
        return program_urls

    def scrape_dsee_search(self, source):
        """Scrape DSEE funding database search results.

        Args:
            source (dict): Source configuration

        Returns:
            list: List of funding program URLs
        """
        logger.info(f"Scraping {source['name']} - {source['url']}")

        program_urls = []

        # Get the search page
        content = self.get_page_content(source['url'])
        if not content:
            return []

        # Parse the page
        soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')

        # Find all program links based on the configured selector
        link_elements = soup.select(source.get('link_selector', 'a[href*="/foerderung/"]'))

        for link in link_elements:
            if link.has_attr('href'):
                url = urljoin(source['url'], link['href'])

                # Avoid duplicates
                if url not in program_urls:
                    program_urls.append(url)

        # Limit based on max_programs
        if self.max_programs > 0:
            program_urls = program_urls[:self.max_programs]

        logger.info(f"Found {len(program_urls)} program URLs")
        return program_urls

    def scrape_aktion_mensch(self, source):
        """Scrape Aktion Mensch Förderfinder for funding programs.

        Aktion Mensch displays funding programs on a single page with detailed sections.
        Each program has title, description, funding details, and application links.

        Args:
            source (dict): Source configuration

        Returns:
            list: List of program data dictionaries (complete data, not just URLs)
        """
        logger.info(f"Scraping {source['name']} - {source['url']}")

        programs = []

        # Get the Förderfinder page
        content = self.get_page_content(source['url'])
        if not content:
            return []

        # Parse the page
        soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')

        # Find all funding program sections
        # The programs are in list items with headings containing "Förderaktion:", "Pauschalförderung:", etc.
        program_sections = []

        # Look for list items containing program headers
        for li in soup.find_all('li'):
            header = li.find('h3')
            if header and any(keyword in header.get_text() for keyword in ['Förderaktion:', 'Pauschalförderung:', 'Projektförderung:', 'Investitionsförderung:']):
                program_sections.append(li)

        logger.info(f"Found {len(program_sections)} funding programs on page")

        # Limit based on max_programs
        if self.max_programs > 0:
            program_sections = program_sections[:self.max_programs]

        # Extract details from each program section
        for section in program_sections:
            try:
                # Extract program title
                title_elem = section.find('h3')
                if not title_elem:
                    continue

                title = title_elem.get_text().strip()

                # Extract program details
                program_data = {
                    'title': title,
                    'source_url': source['url'],
                    'source_name': source['name'],
                    'scraped_date': datetime.now().isoformat(),
                    'raw_html': str(section),
                    'program_type': 'Aktion Mensch'
                }

                # Try to extract specific funding details if available
                details = {}

                # Look for key-value pairs (Förderprogramm, Zielgruppe, Zuschuss, etc.)
                for p in section.find_all(['p', 'div']):
                    text = p.get_text().strip()
                    if ':' in text and len(text) < 200:  # Likely a detail field
                        key, value = text.split(':', 1)
                        details[key.strip()] = value.strip()

                if details:
                    program_data['extracted_details'] = details

                # Generate stable unique URL from title (all content is on overview page)
                # Use URL fragment with title slug for human-readable, stable tracking
                import hashlib
                from urllib.parse import quote

                # Create URL-safe slug from title
                title_slug = title.lower()
                # Remove common prefixes
                for prefix in ['förderaktion:', 'pauschalförderung:', 'projektförderung:', 'investitionsförderung:']:
                    if title_slug.startswith(prefix):
                        title_slug = title_slug[len(prefix):].strip()
                # Clean up for URL
                title_slug = ''.join(c if c.isalnum() or c in '-_' else '-' for c in title_slug)
                title_slug = '-'.join(filter(None, title_slug.split('-')))[:50]  # Max 50 chars

                # Add hash to ensure uniqueness if titles are similar
                title_hash = hashlib.md5(title.encode()).hexdigest()[:6]
                program_data['url'] = f"{source['url']}#{title_slug}-{title_hash}"

                # Also extract application link for reference
                app_link = section.find('a', href=lambda x: x and 'antrag' in x.lower())
                if app_link and app_link.has_attr('href'):
                    app_url = app_link['href']
                    # Make absolute URL if relative
                    if app_url.startswith('/'):
                        from urllib.parse import urljoin
                        app_url = urljoin(source['url'], app_url)
                    program_data['application_url'] = app_url

                # Check for duplicates before adding
                program_json = json.dumps(program_data, ensure_ascii=False)
                is_duplicate, item_id = self.check_duplicate_content(program_json)

                if is_duplicate:
                    logger.info(f"Skipping duplicate program: {title}")
                    continue

                programs.append(program_data)
                logger.info(f"✓ Extracted: {title}")

            except Exception as e:
                logger.error(f"Error extracting program from section: {e}")
                continue

        return programs

    def scrape_program_detail(self, url, source_name):
        """Scrape a single funding program detail page.

        Args:
            url (str): URL of the program detail page
            source_name (str): Name of the source

        Returns:
            dict: Program data or None if scraping fails
        """
        logger.info(f"Scraping detail page: {url}")

        # Get the detail page
        content = self.get_page_content(url)
        if not content:
            return None

        # Parse the page
        soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')

        # Extract title
        title = None
        title_element = soup.select_one('h1, .title, .heading')
        if title_element:
            title = self.normalize_text(title_element.get_text())

        # Extract main content
        content_text = None
        content_element = soup.select_one('main, .content, .main-content, article')
        if content_element:
            content_text = self.normalize_text(content_element.get_text())
        else:
            # Fallback to body
            content_text = self.normalize_text(soup.body.get_text())

        # Extract meta information
        meta_info = {}

        # Try to find structured data (e.g., tables, lists)
        tables = soup.select('table')
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    key = self.normalize_text(cells[0].get_text())
                    value = self.normalize_text(cells[1].get_text())
                    meta_info[key] = value

        # Find and follow important external links
        external_links = self._find_external_detail_links(soup, url)
        additional_content = []

        for ext_url in external_links:
            logger.info(f"Following external detail link: {ext_url}")
            ext_content = self._scrape_external_page(ext_url)
            if ext_content:
                additional_content.append(f"\n\n=== Content from {ext_url} ===\n{ext_content}")

        # Combine all content
        full_content = content_text
        if additional_content:
            full_content = content_text + "\n".join(additional_content)

        # Build the program data
        program_data = {
            "url": url,
            "source_name": source_name,
            "title": title,
            "content": full_content,
            "meta_info": meta_info,
            "external_urls": external_links,
            "scraped_at": datetime.now().isoformat()
        }

        return program_data

    def _find_external_detail_links(self, soup, base_url):
        """Find relevant external detail links on a program page.

        Args:
            soup (BeautifulSoup): Parsed HTML
            base_url (str): Base URL for resolving relative links

        Returns:
            list: List of external URLs to follow
        """
        external_links = []
        base_domain = urlparse(base_url).netloc

        # Strong keywords that indicate important detail pages (must be in URL path)
        strong_keywords = [
            'richtlinie', 'vergaberichtlinie', 'foerderrichtlinie', 'bewerb',
            'antrag', 'antragsformular', 'guideline', 'application', 'apply',
            'foerderprogramm', 'vorschrift', 'merkblatt'
        ]

        # Weak keywords (can be in link text if URL also looks promising)
        weak_keywords = ['detail', 'mehr', 'info', 'information', 'regel']

        # Find all links
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            text = link.get_text().lower()

            # Skip mailto, tel, javascript, anchors
            if any(href.startswith(prefix) for prefix in ['mailto:', 'tel:', 'javascript:', '#']):
                continue

            # Resolve relative URLs
            full_url = urljoin(base_url, href)
            parsed_url = urlparse(full_url)
            link_domain = parsed_url.netloc
            url_path = parsed_url.path.lower()

            # Skip same-domain links (we already have that content)
            if link_domain == base_domain:
                continue

            # Skip social media and common navigation
            skip_domains = ['facebook.com', 'twitter.com', 'x.com', 'instagram.com',
                          'linkedin.com', 'youtube.com', 'github.com']
            if any(domain in link_domain for domain in skip_domains):
                continue

            # Skip homepage URLs (just domain with no or minimal path)
            if url_path in ['', '/', '/de/', '/en/'] or url_path.endswith('/index.html'):
                continue

            # Skip generic portal/navigation pages
            generic_paths = ['/foerderportal', '/portal', '/startseite', '/home', '/kontakt', '/contact']
            if any(url_path.endswith(generic) for generic in generic_paths):
                continue

            # Check for strong keywords in URL path (highest priority)
            has_strong_keyword = any(keyword in url_path for keyword in strong_keywords)

            # Check for weak keywords with additional URL quality checks
            has_weak_keyword = any(keyword in text for keyword in weak_keywords)
            url_looks_detailed = len(url_path) > 10  # URL has substantial path

            # Accept link if:
            # 1. Has strong keyword in URL path, OR
            # 2. Has weak keyword in text AND URL looks detailed
            if has_strong_keyword or (has_weak_keyword and url_looks_detailed):
                if full_url not in external_links:
                    external_links.append(full_url)
                    # Limit to 5 external pages per program
                    if len(external_links) >= 5:
                        break

        logger.info(f"Found {len(external_links)} external detail links to follow")
        return external_links

    def _scrape_external_page(self, url):
        """Scrape content from an external detail page.

        Args:
            url (str): URL to scrape

        Returns:
            str: Extracted content or None
        """
        try:
            content = self.get_page_content(url)
            if not content:
                return None

            soup = BeautifulSoup(content, 'html.parser', from_encoding='utf-8')

            # Extract main content
            content_element = soup.select_one('main, .content, .main-content, article, .main')
            if content_element:
                return self.normalize_text(content_element.get_text())
            else:
                # Fallback to body but remove nav/footer
                for element in soup.find_all(['nav', 'footer', 'header']):
                    element.decompose()
                return self.normalize_text(soup.body.get_text()) if soup.body else None

        except Exception as e:
            logger.error(f"Error scraping external page {url}: {str(e)}")
            return None

    def scrape_source(self, source):
        """Scrape a single source for funding programs.

        Args:
            source (dict): Source configuration

        Returns:
            list: List of program data dictionaries
        """
        all_programs = []
        seen_urls = set()  # Track URLs found in this scrape

        # Handle Aktion Mensch differently - it returns complete program data
        if source.get('type') == 'aktion_mensch':
            programs = self.scrape_aktion_mensch(source)

            # Save each program
            for program_data in programs:
                url = program_data.get('url', source['url'])
                seen_urls.add(url)

                all_programs.append(program_data)

                # Check for changes and save to Directus
                if self.directus_client:
                    program_json = json.dumps(program_data, ensure_ascii=False)
                    content_hash = calculate_content_hash(program_json)

                    # Check if this is new, unchanged, or changed
                    status, existing_id, previous_hash = self.check_duplicate_or_changed(
                        program_json, url
                    )

                    # Get existing item for check_count if needed
                    existing_item = None
                    if existing_id:
                        existing_item = self.directus_client.get_item_by_url(
                            self.collection_name, url
                        )

                    # Save/update
                    self.save_to_directus(
                        program_data, content_hash,
                        status=status,
                        existing_id=existing_id,
                        previous_hash=previous_hash,
                        existing_item=existing_item
                    )

            # Mark programs that weren't found as removed
            self.mark_removed_programs(source['name'], seen_urls)

            return all_programs

        # Get program URLs from search/listing page
        if source.get('type') == 'rss':
            program_urls = self.scrape_rss_feed(source)
        elif source.get('type') == 'dsee':
            program_urls = self.scrape_dsee_search(source)
        else:
            # Generic handling - look for links
            content = self.get_page_content(source['url'])
            if not content:
                return []

            soup = BeautifulSoup(content, 'html.parser')
            link_elements = soup.select(source.get('link_selector', 'a'))
            program_urls = []

            for link in link_elements:
                if link.has_attr('href'):
                    url = urljoin(source['url'], link['href'])
                    if url not in program_urls:
                        program_urls.append(url)

            if self.max_programs > 0:
                program_urls = program_urls[:self.max_programs]

        # Track URLs found in this scrape
        seen_urls = set()

        # Scrape each program detail page
        for i, url in enumerate(program_urls):
            try:
                # Track this URL
                seen_urls.add(url)

                # Scrape the program detail
                program_data = self.scrape_program_detail(url, source['name'])

                if not program_data:
                    continue

                # Check if this is new, unchanged, or changed
                program_json = json.dumps(program_data, ensure_ascii=False)
                content_hash = calculate_content_hash(program_json)

                status, existing_id, previous_hash = self.check_duplicate_or_changed(
                    program_json, url
                )

                # Get existing item for check_count if needed
                existing_item = None
                if existing_id:
                    existing_item = self.directus_client.get_item_by_url(
                        self.collection_name, url
                    ) if self.directus_client else None

                if status == 'unchanged':
                    logger.debug(f"Skipping unchanged program: {url}")
                    # Still update timestamps
                    if self.directus_client and existing_item:
                        self.save_to_directus(
                            program_data, content_hash,
                            status='unchanged',
                            existing_id=existing_id,
                            existing_item=existing_item
                        )
                    continue

                # Add to results
                all_programs.append(program_data)

                # Save to Directus
                if self.directus_client:
                    self.save_to_directus(
                        program_data, content_hash,
                        status=status,
                        existing_id=existing_id,
                        previous_hash=previous_hash,
                        existing_item=existing_item
                    )

                # Save HTML if requested
                if self.save_html:
                    html_path = os.path.join(
                        self.output_dir,
                        f"{self._safe_filename(source['name'])}_{i+1}.html"
                    )
                    with open(html_path, "w", encoding="utf-8") as f:
                        f.write(self.get_page_content(url, use_cache=True))

                # Be nice to the server
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                continue

        # Mark programs that weren't found as removed
        self.mark_removed_programs(source['name'], seen_urls)

        return all_programs

    def _safe_filename(self, s):
        """Convert a string to a safe filename."""
        return re.sub(r'[^\w\-_]', '_', s.lower())

    def run(self):
        """Run the scraper for all configured sources."""
        logger.info(f"Starting Fördermittel scraper (max {self.max_programs} programs per source)")

        all_programs = []
        new_programs_count = 0

        for source in self.sources:
            try:
                programs = self.scrape_source(source)
                all_programs.extend(programs)
                new_programs_count += len(programs)
            except Exception as e:
                logger.error(f"Error scraping source {source['name']}: {str(e)}")
                logger.exception("Full exception details:")

        # Save all scraped programs to JSON file (as backup)
        output_path = os.path.join(self.output_dir, "scraped_foerdermittel.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_programs, f, indent=2, ensure_ascii=False)

        logger.info(f"Scraping complete. {new_programs_count} new programs scraped.")
        return all_programs


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
                    "name": "DSEE Förderdatenbank",
                    "url": "https://foerderdatenbank.d-s-e-e.de/",
                    "type": "dsee",
                    "link_selector": "a[href*='/foerderung/']"
                }
            ]
        }


def main():
    """Main entry point for the scraper application."""
    parser = argparse.ArgumentParser(
        description="Fördermittel Scraper for German NGO Funding Programs"
    )
    parser.add_argument(
        "--config", "-c",
        default="foerdermittel/config/foerdermittel_sources.json",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--directus-config", "-d",
        default="config/directus.json",
        help="Path to Directus configuration file"
    )
    parser.add_argument(
        "--output", "-o",
        default="data",
        help="Output directory for scraped data"
    )
    parser.add_argument(
        "--max-programs", "-m",
        type=int,
        default=10,
        help="Maximum programs to scrape per source (-1 for all)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--no-directus",
        action="store_true",
        help="Disable Directus database integration"
    )
    parser.add_argument(
        "--save-html",
        action="store_true",
        help="Save HTML files to disk"
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache",
        help="Directory to store cache files"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear URL cache before running"
    )

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
                    "name": "DSEE Förderdatenbank",
                    "url": "https://foerderdatenbank.d-s-e-e.de/",
                    "type": "dsee",
                    "link_selector": "a[href*='/foerderung/']",
                    "description": "Deutsche Stiftung für Engagement und Ehrenamt funding database"
                }
            ]
        }
        with open(args.config, "w", encoding="utf-8") as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)

    # Load configurations
    config = load_config(args.config)
    directus_config = None

    if not args.no_directus:
        try:
            if os.path.exists(args.directus_config):
                with open(args.directus_config, "r", encoding="utf-8") as f:
                    directus_config = json.load(f)
                    logger.info(f"Loaded Directus configuration from {args.directus_config}")
            else:
                logger.warning(f"Directus config not found at {args.directus_config}")
                logger.info("Continuing without Directus integration")
        except Exception as e:
            logger.error(f"Error loading Directus configuration: {str(e)}")
            logger.warning("Continuing without Directus integration")

    # Create cache directory if needed
    if args.cache_dir:
        os.makedirs(args.cache_dir, exist_ok=True)

    # Clear cache if requested
    if args.clear_cache:
        cache_file = os.path.join(args.cache_dir, "foerdermittel_url_cache.pkl")
        if os.path.exists(cache_file):
            os.remove(cache_file)
            logger.info("Cleared URL cache")

    # Run the scraper
    scraper = FoerdermittelScraper(
        config=config,
        directus_config=directus_config,
        output_dir=args.output,
        max_programs_per_source=args.max_programs,
        save_html=args.save_html,
        cache_dir=args.cache_dir
    )
    scraper.run()


if __name__ == "__main__":
    main()
