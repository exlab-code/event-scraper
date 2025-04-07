#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event Scraper for Non-Profit Digitalization Events

This script scrapes websites for digitalization events targeted at non-profit organizations,
extracts the raw event information, and saves it to a structured format for further processing.
"""
import requests
from bs4 import BeautifulSoup
import json
import logging
import time
import os
import re
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
            logging.FileHandler(os.path.join(log_dir, "scraper.log")),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("event-scraper")

# Initialize logger
logger = setup_logging()

class EventScraper:
    """Main scraper class for collecting non-profit digitalization events."""
    
    def __init__(self, config, output_dir="data", max_events_per_source=3):
        """Initialize the scraper with configuration.
        
        Args:
            config (dict): Configuration with sources to scrape
            output_dir (str): Directory to save output files
            max_events_per_source (int): Maximum events to scrape per source (-1 for all)
        """
        self.sources = config.get("sources", [])
        self.max_events = max_events_per_source
        self.output_dir = output_dir
        
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
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
        
        # Parse the listing page
        soup = BeautifulSoup(content, 'html.parser')
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
                        "url": None,
                        "source_name": source['name']
                    })
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
                    full_event_details.append({
                        "listing_text": listing_text,
                        "detail_text": None,
                        "url": event_url,
                        "source_name": source['name']
                    })
                    continue
                
                # Save detail page HTML for reference
                detail_path = os.path.join(self.output_dir, f"{self._safe_filename(source['name'])}_detail_{i+1}.html")
                with open(detail_path, "w", encoding="utf-8") as f:
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
                    "url": event_url,
                    "source_name": source['name']
                })
                
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
        
        # Process each source
        for source in self.sources:
            try:
                events = self.scrape_source(source)
                all_events.extend(events)
            except Exception as e:
                logger.error(f"Error scraping source {source['name']}: {str(e)}")
                logger.exception("Full exception details:")
        
        # Save all scraped events to a single JSON file
        output_path = os.path.join(self.output_dir, "scraped_events.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(all_events, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Scraping complete. {len(all_events)} events saved to {output_path}")
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
    parser.add_argument("--output", "-o", default="data", help="Output directory for scraped data")
    parser.add_argument("--max-events", "-m", type=int, default=3, 
                        help="Maximum events to scrape per source (-1 for all)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
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
    
    # Load configuration
    config = load_config(args.config)
    
    # Run the scraper
    scraper = EventScraper(
        config=config, 
        output_dir=args.output,
        max_events_per_source=args.max_events
    )
    scraper.run()

if __name__ == "__main__":
    main()