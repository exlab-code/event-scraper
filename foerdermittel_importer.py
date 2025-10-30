#!/usr/bin/env python3
"""
Fördermittel Importer - Downloads and imports funding programs from CorrelAid's dataset

This script:
1. Downloads the latest Förderdatenbank dataset from CorrelAid (Parquet format)
2. Filters for programs eligible for NGOs/Verbände/Vereine
3. Loads them into the foerdermittel_scraped_data collection in Directus
4. Ready for LLM analysis by foerdermittel_analyzer.py

Data source: https://github.com/CorrelAid/cdl_funding_scraper
License: CC BY-ND 3.0 DE (as per source website)
"""

import os
import sys
import json
import logging
import argparse
import requests
import zipfile
from datetime import datetime
from io import BytesIO

# Check dependencies
def check_dependencies():
    """Check if required packages are installed."""
    required = {
        'pandas': 'pandas',
        'pyarrow': 'pyarrow',
    }

    missing = []
    for package, import_name in required.items():
        try:
            __import__(import_name)
        except ImportError:
            missing.append(package)

    if missing:
        print(f"Missing required packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        sys.exit(1)

check_dependencies()

import pandas as pd
from dotenv import load_dotenv

# Import shared utilities
from shared.directus_client import DirectusClient, calculate_content_hash

# Load environment variables
load_dotenv()

# Set up logging
def setup_logging(log_level=logging.INFO):
    """Configure logging with file and console handlers."""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("logs/foerdermittel_importer.log", encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("foerdermittel-importer")

logger = setup_logging()


class FoerdermittelImporter:
    """Import funding programs from CorrelAid's public dataset."""

    # Data source
    PARQUET_URL = "https://foerderdatenbankdump.fra1.cdn.digitaloceanspaces.com/data/parquet_data.zip"

    # Keywords for NGO/Verbände eligibility - must contain one of these
    REQUIRED_KEYWORDS = ['verband', 'verbände', 'vereinigung']

    def __init__(self, directus_config=None, output_dir="data"):
        """Initialize the importer.

        Args:
            directus_config (dict): Directus configuration
            output_dir (str): Directory for local data files
        """
        self.output_dir = output_dir
        self.collection_name = "foerdermittel_scraped_data"

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs("logs", exist_ok=True)

        # Initialize Directus client
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
        else:
            self.directus_client = None
            logger.warning("No Directus configuration provided")

    def download_dataset(self):
        """Download the latest Parquet dataset from CorrelAid.

        Returns:
            pd.DataFrame: Loaded dataset
        """
        logger.info(f"Downloading dataset from {self.PARQUET_URL}")

        try:
            # Download the zip file
            response = requests.get(self.PARQUET_URL, timeout=60)
            response.raise_for_status()

            # Extract and load parquet file
            with zipfile.ZipFile(BytesIO(response.content)) as zf:
                # Find the parquet file (should be data.parquet)
                parquet_files = [f for f in zf.namelist() if f.endswith('.parquet')]

                if not parquet_files:
                    raise ValueError("No parquet file found in zip archive")

                logger.info(f"Extracting {parquet_files[0]}")
                with zf.open(parquet_files[0]) as f:
                    df = pd.read_parquet(f)

            logger.info(f"Loaded {len(df)} funding programs from dataset")
            logger.info(f"Columns: {', '.join(df.columns)}")

            return df

        except Exception as e:
            logger.error(f"Error downloading dataset: {str(e)}")
            return None

    def filter_for_ngos(self, df):
        """Filter dataset for programs eligible for NGOs/Verbände.

        Args:
            df (pd.DataFrame): Full dataset

        Returns:
            pd.DataFrame: Filtered dataset
        """
        logger.info("Filtering for NGO/Verbände eligibility")

        if 'eligible_applicants' not in df.columns:
            logger.warning("'eligible_applicants' column not found, cannot filter")
            return df

        # Convert list columns to strings for searching
        df_filtered = df.copy()

        # Handle list-type eligible_applicants (stored as numpy arrays)
        import numpy as np

        def convert_to_str(x):
            if x is None or (isinstance(x, float) and pd.isna(x)):
                return ''
            if isinstance(x, (list, tuple, np.ndarray)):
                return ' '.join(str(item) for item in x).lower()
            return str(x).lower()

        df_filtered['eligible_applicants_str'] = df_filtered['eligible_applicants'].apply(convert_to_str)

        # Filter for required keywords (verband/verbände/vereinigung)
        mask = df_filtered['eligible_applicants_str'].apply(
            lambda x: any(keyword in x for keyword in self.REQUIRED_KEYWORDS)
        )

        filtered_df = df_filtered[mask].drop(columns=['eligible_applicants_str'])

        logger.info(f"Filtered to {len(filtered_df)} programs eligible for NGOs/Verbände ({len(filtered_df)/len(df)*100:.1f}%)")

        return filtered_df

    def transform_to_our_format(self, row):
        """Transform CorrelAid format to our format.

        Args:
            row (pd.Series): Row from CorrelAid dataset

        Returns:
            dict: Program data in our format
        """
        import numpy as np

        def is_not_empty(val):
            """Check if value is not None/NaN/empty."""
            if val is None:
                return False
            if isinstance(val, float) and pd.isna(val):
                return False
            if isinstance(val, str) and val.strip() == '':
                return False
            return True

        # Combine all text fields into content
        content_parts = []

        if is_not_empty(row.get('title')):
            content_parts.append(f"Title: {row['title']}")

        if is_not_empty(row.get('description')):
            content_parts.append(f"\nDescription:\n{row['description']}")

        if is_not_empty(row.get('more_info')):
            content_parts.append(f"\nAdditional Information:\n{row['more_info']}")

        if is_not_empty(row.get('legal_basis')):
            content_parts.append(f"\nLegal Basis:\n{row['legal_basis']}")

        # Add structured metadata
        metadata = {}

        for field in ['funding_type', 'funding_area', 'funding_location', 'eligible_applicants', 'funding_body']:
            if field in row and is_not_empty(row[field]):
                value = row[field]
                if isinstance(value, (list, np.ndarray)):
                    metadata[field] = value.tolist() if isinstance(value, np.ndarray) else value
                else:
                    metadata[field] = str(value)

        # Add contact information
        contact_fields = ['contact_info_institution', 'contact_info_street', 'contact_info_city',
                         'contact_info_phone', 'contact_info_fax', 'contact_info_email', 'contact_info_website']

        contact_info = {}
        for field in contact_fields:
            if field in row and is_not_empty(row[field]):
                contact_info[field.replace('contact_info_', '')] = str(row[field])

        if contact_info:
            contact_parts = [f"{k.title()}: {v}" for k, v in contact_info.items()]
            content_parts.append(f"\nContact Information:\n" + "\n".join(contact_parts))

        # Add further links
        if 'further_links' in row and is_not_empty(row['further_links']):
            links_value = row['further_links']
            if isinstance(links_value, (list, np.ndarray)):
                links = links_value.tolist() if isinstance(links_value, np.ndarray) else links_value
            else:
                links = [str(links_value)]
            content_parts.append(f"\nFurther Links:\n" + "\n".join(str(link) for link in links))

        full_content = "\n".join(content_parts)

        # Build program data
        # Handle external URLs
        links_value = row.get('further_links')
        if isinstance(links_value, (list, np.ndarray)):
            external_urls = links_value.tolist() if isinstance(links_value, np.ndarray) else links_value
        elif links_value:
            external_urls = [str(links_value)]
        else:
            external_urls = []

        program_data = {
            "url": row.get('url', ''),
            "source_name": "Förderdatenbank (CorrelAid Dataset)",
            "title": row.get('title', ''),
            "content": full_content,
            "meta_info": metadata,
            "external_urls": external_urls,
            "scraped_at": datetime.now().isoformat(),
            "correlaid_id": row.get('id_hash', ''),
            "correlaid_checksum": row.get('checksum', '')
        }

        return program_data

    def import_to_directus(self, df, dry_run=False):
        """Import filtered programs to Directus.

        Args:
            df (pd.DataFrame): Filtered dataset
            dry_run (bool): If True, don't actually save to Directus

        Returns:
            int: Number of programs imported
        """
        if not self.directus_client and not dry_run:
            logger.error("No Directus client available")
            return 0

        imported_count = 0
        skipped_count = 0

        for idx, row in df.iterrows():
            try:
                # Transform to our format
                program_data = self.transform_to_our_format(row)

                # Calculate content hash for deduplication
                content_hash = calculate_content_hash(program_data['content'])

                if dry_run:
                    logger.info(f"[DRY RUN] Would import: {program_data['title']}")
                    imported_count += 1
                    continue

                # Check if already exists
                existing = self.directus_client.get_item_by_hash(self.collection_name, content_hash)
                if existing:
                    logger.debug(f"Skipping duplicate: {program_data['title']}")
                    skipped_count += 1
                    continue

                # Save to Directus
                directus_data = {
                    "url": program_data["url"],
                    "source_name": program_data["source_name"],
                    "content_hash": content_hash,
                    "raw_content": json.dumps(program_data, ensure_ascii=False),
                    "scraped_at": program_data["scraped_at"],
                    "processed": False,
                    "processing_status": "pending"
                }

                created_item = self.directus_client.create_item(self.collection_name, directus_data)
                logger.info(f"Imported: {program_data['title']} (ID: {created_item['id']})")
                imported_count += 1

            except Exception as e:
                logger.error(f"Error importing program {row.get('title', 'unknown')}: {str(e)}")
                continue

        logger.info(f"Import complete: {imported_count} imported, {skipped_count} skipped (duplicates)")
        return imported_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Import funding programs from CorrelAid dataset")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually save to Directus")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of programs to import (0 = no limit)")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Load Directus configuration
    directus_config_path = "config/directus.json"
    if os.path.exists(directus_config_path):
        with open(directus_config_path) as f:
            directus_config = json.load(f)
        logger.info(f"Loaded Directus configuration from {directus_config_path}")
    else:
        logger.error(f"Directus configuration file not found: {directus_config_path}")
        return

    # Initialize importer
    importer = FoerdermittelImporter(directus_config=directus_config)

    # Download dataset
    df = importer.download_dataset()
    if df is None:
        logger.error("Failed to download dataset")
        return

    # Filter for NGOs
    filtered_df = importer.filter_for_ngos(df)

    # Apply limit if specified
    if args.limit > 0:
        filtered_df = filtered_df.head(args.limit)
        logger.info(f"Limited to first {args.limit} programs")

    # Import to Directus
    imported_count = importer.import_to_directus(filtered_df, dry_run=args.dry_run)

    logger.info(f"Done! {imported_count} programs imported")


if __name__ == "__main__":
    main()
