#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared utilities for Directus API integration and caching.

This module provides reusable components for interacting with Directus CMS:
- DirectusClient: Client for Directus API operations
- URLCache: Persistent cache for URL content to reduce redundant requests
- ContentHashCache: In-memory cache for content hash deduplication
"""

import requests
import json
import logging
import os
import pickle
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


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

    def get_pending_items(self, collection, processing_status="pending", limit=10):
        """Get pending items from a collection for processing.

        Args:
            collection (str): Collection name
            processing_status (str): Status to filter by (default: "pending")
            limit (int): Maximum number of items to retrieve

        Returns:
            list: List of pending items
        """
        url = f"{self.base_url}/items/{collection}"
        params = {
            "filter": json.dumps({
                "processing_status": {
                    "_eq": processing_status
                }
            }),
            "limit": limit,
            "sort": "scraped_at"  # Oldest first
        }

        try:
            response = self.session.get(url, headers=self.get_headers(), params=params)

            if response.status_code == 401:  # Token might have expired
                self.login()
                response = self.session.get(url, headers=self.get_headers(), params=params)

            response.raise_for_status()

            return response.json().get('data', [])
        except Exception as e:
            logger.error(f"Failed to get pending items from {collection}: {str(e)}")
            return []


def calculate_content_hash(content):
    """Calculate SHA-256 hash of content for deduplication.

    Args:
        content (str): Content to hash

    Returns:
        str: Hexadecimal hash string
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
