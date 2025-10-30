#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fördermittel (Funding Programs) Analyzer with LLM Extraction

This application processes funding program data from the Directus foerdermittel_scraped_data
collection using OpenAI GPT-4o with Structured Outputs and stores structured results
back to the foerdermittel collection.

Uses JSON Schema for 100% schema adherence and handles German-specific patterns
for amounts, dates, and eligibility criteria.
"""

import json
import re
import os
import logging
import argparse
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
import instructor

# Import shared utilities
from shared.directus_client import DirectusClient

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("foerdermittel_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("foerdermittel-analyzer")

# Configuration
DIRECTUS_URL = os.getenv("DIRECTUS_API_URL", "https://calapi.buerofalk.de")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_API_TOKEN", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Validate required environment variables
if not DIRECTUS_TOKEN:
    raise ValueError("DIRECTUS_API_TOKEN environment variable is required")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class FoerdermittelData(BaseModel):
    """Structured funding program data with validation"""

    title: str = Field(..., min_length=1, max_length=500, description="Title of the funding program in German")
    short_description: str = Field(..., max_length=200, description="Brief description (max 200 characters)")
    description: str = Field(..., min_length=10, description="Detailed description of the funding program")
    funding_organization: str = Field(..., min_length=1, description="Organization providing the funding")

    funding_provider_type: Literal["Bund", "Land", "EU", "Stiftung", "Sonstige"] = Field(
        ..., description="Type of funding provider"
    )

    bundesland: Literal[
        "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen",
        "Hamburg", "Hessen", "Mecklenburg-Vorpommern", "Niedersachsen",
        "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland", "Sachsen",
        "Sachsen-Anhalt", "Schleswig-Holstein", "Thüringen",
        "bundesweit", "EU-weit", "International"
    ] = Field(..., description="Federal state or scope")

    funding_type: Literal["Zuschuss", "Kredit", "Bürgschaft", "Preis", "Sonstige"] = Field(
        ..., description="Type of funding"
    )

    funding_amount_min: Optional[float] = Field(None, description="Minimum funding amount in EUR")
    funding_amount_max: Optional[float] = Field(None, description="Maximum funding amount in EUR")
    funding_amount_text: Optional[str] = Field(None, description="Text description of funding amount if not numeric")
    funding_rate: Optional[str] = Field(None, description="Funding rate (e.g., '100%', 'bis zu 50%')")

    application_deadline: Optional[str] = Field(None, description="Application deadline in ISO format (YYYY-MM-DD)")
    deadline_type: Literal["einmalig", "laufend", "jährlich", "geschlossen"] = Field(
        ..., description="Type of deadline"
    )

    funding_period_start: Optional[str] = Field(None, description="Start of funding period in ISO format (YYYY-MM-DD)")
    funding_period_end: Optional[str] = Field(None, description="End of funding period in ISO format (YYYY-MM-DD)")

    target_group: str = Field(..., min_length=1, description="Target group for the funding")
    eligibility_criteria: str = Field(..., min_length=1, description="Detailed eligibility criteria")

    website: str = Field(..., min_length=1, description="Official website URL for the funding program")
    contact_email: Optional[str] = Field(None, description="Contact email if available")

    is_relevant: bool = Field(..., description="Whether this funding is relevant for NGOs/Wohlfahrtsverbände")
    relevance_reason: str = Field(..., min_length=1, description="Brief explanation of relevance determination")

    # Additional fields added by processor
    source: Optional[str] = Field(None, description="Source name")
    source_url: Optional[str] = Field(None, description="Source URL")
    status: Literal["draft", "published", "archived"] = Field(
        default="draft",
        description="Publication status - new programs start as draft pending review"
    )
    scraped_data_id: Optional[int] = Field(None, description="Link to scraped data item")

    @field_validator('application_deadline', 'funding_period_start', 'funding_period_end')
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

    @field_validator('short_description')
    @classmethod
    def validate_short_description_length(cls, v: str) -> str:
        """Ensure short description is not too long"""
        if len(v) > 200:
            # Truncate and add ellipsis
            return v[:197] + "..."
        return v

    @field_validator('contact_email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """Basic email validation"""
        if v is None:
            return v

        # Simple email pattern check
        if '@' in v and '.' in v.split('@')[-1]:
            return v

        # If invalid, return None instead of raising error
        logger.warning(f"Invalid email format: {v}, setting to None")
        return None

# ============================================================================


class FoerdermittelProcessor:
    """Processes funding program data with GPT-4o and structured outputs"""

    def __init__(self, api_key, directus_client):
        # Patch OpenAI client with Instructor
        self.client = instructor.from_openai(OpenAI(api_key=api_key))
        self.directus = directus_client

    def _extract_amounts_regex(self, text):
        """Extract funding amounts using regex patterns.

        Args:
            text (str): Text to search for amounts

        Returns:
            dict: Dictionary with min_amount, max_amount, amount_text
        """
        result = {
            "min_amount": None,
            "max_amount": None,
            "amount_text": None
        }

        # Patterns for German currency amounts
        patterns = [
            # Exact amount: 10.000 EUR, 10.000€, 10000 Euro
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:EUR|€|Euro)',
            # Range: 1.000 bis 10.000 EUR
            r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*bis\s*(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:EUR|€|Euro)',
            # Up to: bis zu 50.000 EUR
            r'bis\s+zu\s+(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:EUR|€|Euro)',
            # Max/Maximum: max. 25.000 EUR
            r'(?:max\.|maximal|höchstens)\s+(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*(?:EUR|€|Euro)'
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) == 2:
                    # Range found
                    min_str = groups[0].replace('.', '').replace(',', '.')
                    max_str = groups[1].replace('.', '').replace(',', '.')
                    result["min_amount"] = float(min_str)
                    result["max_amount"] = float(max_str)
                    break
                elif len(groups) == 1:
                    # Single amount
                    amount_str = groups[0].replace('.', '').replace(',', '.')
                    amount = float(amount_str)
                    if "bis zu" in match.group(0).lower() or "max" in match.group(0).lower():
                        result["max_amount"] = amount
                    else:
                        result["min_amount"] = amount
                        result["max_amount"] = amount

        return result

    def _extract_dates_regex(self, text):
        """Extract dates using regex patterns for German dates.

        Args:
            text (str): Text to search for dates

        Returns:
            list: List of dates in ISO format
        """
        dates = []

        # Month name mapping
        month_map = {
            'januar': '01', 'jan': '01',
            'februar': '02', 'feb': '02',
            'märz': '03', 'mär': '03',
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

        # Patterns
        patterns = [
            # DD.MM.YYYY
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            # DD. Month YYYY
            (r'(\d{1,2})\.\s*(Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s*(\d{4})',
             lambda m: f"{m.group(3)}-{month_map[m.group(2).lower()]}-{m.group(1).zfill(2)}"),
            # YYYY-MM-DD (ISO)
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}")
        ]

        for pattern, formatter in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    date_str = formatter(match)
                    # Validate date format
                    datetime.strptime(date_str, '%Y-%m-%d')
                    dates.append(date_str)
                except (ValueError, AttributeError):
                    continue

        return dates

    def preprocess_program(self, content):
        """Extract key information using regex before LLM processing.

        Args:
            content (dict): Program content

        Returns:
            dict: Extracted information
        """
        extracted_info = {}

        # Get text content
        title = content.get("title", "") or ""
        text_content = content.get("content", "") or ""
        combined_text = title + " " + text_content

        # Extract amounts
        amounts = self._extract_amounts_regex(combined_text)
        extracted_info.update(amounts)

        # Extract dates
        dates = self._extract_dates_regex(combined_text)
        if dates:
            extracted_info["extracted_dates"] = dates

        return extracted_info

    def _build_prompt(self, content, extracted_info):
        """Build the prompt for GPT-4o.

        Args:
            content (dict): Program content
            extracted_info (dict): Pre-extracted information

        Returns:
            str: Formatted prompt
        """
        title = content.get("title", "Kein Titel")
        text_content = content.get("content", "")
        url = content.get("url", "")
        source_name = content.get("source_name", "")

        prompt = f"""Extrahiere strukturierte Informationen aus der folgenden deutschen Förderprogramm-Beschreibung.

QUELLE: {source_name}
URL: {url}
TITEL: {title}

INHALT:
{text_content}

WICHTIGE HINWEISE:
1. Die Zielgruppe muss NGOs, Wohlfahrtsverbände, gemeinnützige Organisationen oder Ehrenamtsorganisationen umfassen
2. Extrahiere präzise Fördersummen in EUR (min/max)
3. Extrahiere Fristen im Format YYYY-MM-DD
4. Bestimme den Bundesland-Bezug oder "bundesweit"
5. Identifiziere die Art des Fördergebers (Bund, Land, EU, Stiftung, Sonstige)
6. Bewerte die Relevanz für NGOs/Wohlfahrtsverbände

RELEVANZ-KRITERIEN (is_relevant=true wenn):
- Explizit für gemeinnützige Organisationen, NGOs, Vereine, Wohlfahrtsverbände
- Oder für Engagement, Ehrenamt, Zivilgesellschaft
- Und: Förderfähige Kosten oder Zuschüsse verfügbar

RELEVANZ-KRITERIEN (is_relevant=false wenn):
- Nur für Unternehmen/Startups
- Nur für Forschungseinrichtungen/Hochschulen
- Nur für Privatpersonen
- Kredite ohne Zuschüsse für gewinnorientierte Projekte
"""

        # Add extracted info hints
        if extracted_info.get("min_amount") or extracted_info.get("max_amount"):
            prompt += f"\n\nVORAB EXTRAHIERTE BETRÄGE (als Hinweis):\n"
            if extracted_info.get("min_amount"):
                prompt += f"Min: {extracted_info['min_amount']} EUR\n"
            if extracted_info.get("max_amount"):
                prompt += f"Max: {extracted_info['max_amount']} EUR\n"

        if extracted_info.get("extracted_dates"):
            prompt += f"\n\nVORAB EXTRAHIERTE DATEN (als Hinweis):\n{', '.join(extracted_info['extracted_dates'])}\n"

        return prompt

    def process_program(self, program_data):
        """Process a single funding program with GPT-4o.

        Args:
            program_data (dict): Program data from Directus

        Returns:
            dict: Structured program data or None if processing fails
        """
        # Extract raw content
        raw_content = program_data.get('raw_content', '{}')
        if isinstance(raw_content, str):
            try:
                content = json.loads(raw_content)
            except json.JSONDecodeError:
                content = {"text": raw_content}
        else:
            content = raw_content

        # Pre-process to extract amounts and dates
        extracted_info = self.preprocess_program(content)

        # Build prompt
        prompt = self._build_prompt(content, extracted_info)

        try:
            item_id_str = program_data.get('id', 'unknown')

            logger.info(f"\n--- Processing program {item_id_str} ---")
            logger.info(f"Title: {content.get('title', 'Unknown')}")

            # Call GPT-4o with Instructor for structured output
            structured_data = self.client.chat.completions.create(
                model="gpt-4o",
                response_model=FoerdermittelData,
                messages=[
                    {
                        "role": "system",
                        "content": "Du bist ein Experte für die Analyse deutscher Förderprogramme für NGOs und gemeinnützige Organisationen. Extrahiere strukturierte Informationen aus Förderprogramm-Beschreibungen."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.1
            )

            logger.info(f"Extracted title: {structured_data.title}")
            logger.info(f"Relevance: {structured_data.is_relevant} - {structured_data.relevance_reason}")

            # Add source information
            structured_data.source = content.get('source_name', '')
            structured_data.source_url = content.get('url', '')

            # New programs start as draft, requiring review before publishing
            structured_data.status = 'draft'

            # Link to scraped data item
            structured_data.scraped_data_id = program_data.get('id')

            # Convert to dict for Directus
            return structured_data.model_dump()

        except Exception as e:
            logger.error(f"Error processing program {item_id_str}: {str(e)}")
            return None


def detect_changes(old_data, new_data):
    """Compare old and new program data to identify significant changes.

    Args:
        old_data (dict): Previous program data
        new_data (dict): New program data

    Returns:
        str: Summary of changes, or None if no significant changes
    """
    significant_fields = {
        'title': 'Title',
        'funding_amount_min': 'Min funding amount',
        'funding_amount_max': 'Max funding amount',
        'application_deadline': 'Application deadline',
        'funding_period_end': 'Funding period end',
        'eligibility_criteria': 'Eligibility criteria',
        'funding_rate': 'Funding rate',
        'deadline_type': 'Deadline type',
        'is_relevant': 'Relevance status'
    }

    changes = []

    for field, label in significant_fields.items():
        old_val = old_data.get(field)
        new_val = new_data.get(field)

        # Skip if both are None/null
        if old_val is None and new_val is None:
            continue

        # Detect change
        if old_val != new_val:
            changes.append(f"{label} changed")
            logger.debug(f"{label}: {old_val} → {new_val}")

    if not changes:
        return None

    return "; ".join(changes)


def process_program_update(processor, directus, item, dry_run=False):
    """Process a program that has changed content.

    Args:
        processor (FoerdermittelProcessor): Processor instance
        directus (DirectusClient): Directus client
        item (dict): Scraped data item with status 'pending_update'
        dry_run (bool): If True, don't save to database

    Returns:
        bool: True if processed successfully, False otherwise
    """
    try:
        # Process the updated program
        new_structured_data = processor.process_program(item)

        if not new_structured_data:
            logger.error(f"Failed to extract structured data for updated program {item['id']}")
            if not dry_run:
                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processing_status": "failed",
                        "error_message": "Failed to extract structured data"
                    }
                )
            return False

        # Get the existing foerdermittel entry to compare
        existing_foerdermittel_id = item.get('foerdermittel_id')

        if not existing_foerdermittel_id:
            # No existing entry - treat as new
            logger.warning(f"No foerdermittel_id found for item {item['id']}, treating as new")
            if not dry_run:
                created_item = directus.create_item("foerdermittel", new_structured_data)

                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processed": True,
                        "processing_status": "completed",
                        "foerdermittel_id": created_item.get('id')
                    }
                )
                print(f"✓ Created new: {new_structured_data.get('title', 'Unknown')}")
            else:
                print(f"[DRY-RUN] Would create new: {new_structured_data.get('title', 'Unknown')}")
            return True

        # Get existing foerdermittel entry
        try:
            response = directus.session.get(
                f"{directus.base_url}/items/foerdermittel/{existing_foerdermittel_id}",
                headers=directus.get_headers()
            )
            response.raise_for_status()
            old_data = response.json().get('data', {})
        except Exception as e:
            logger.error(f"Failed to get existing foerdermittel entry: {str(e)}")
            # Treat as new if we can't find the old entry
            if not dry_run:
                created_item = directus.create_item("foerdermittel", new_structured_data)

                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processed": True,
                        "processing_status": "completed",
                        "foerdermittel_id": created_item.get('id')
                    }
                )
                print(f"✓ Created new (old not found): {new_structured_data.get('title', 'Unknown')}")
            else:
                print(f"[DRY-RUN] Would create new (old not found): {new_structured_data.get('title', 'Unknown')}")
            return True

        # Detect changes
        change_summary = detect_changes(old_data, new_structured_data)

        if not change_summary:
            # No significant changes detected
            logger.info(f"No significant changes detected for {item['id']}")
            if not dry_run:
                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processed": True,
                        "processing_status": "completed"
                    }
                )
            return True

        # Significant changes detected - create new version
        logger.info(f"Changes detected: {change_summary}")

        if not dry_run:
            # Get current version number and status
            current_version = old_data.get('version', 1)
            current_status = old_data.get('status', 'draft')

            # Prepare new version data
            new_version_data = new_structured_data.copy()
            new_version_data['version'] = current_version + 1
            new_version_data['change_summary'] = change_summary
            new_version_data['previous_version_id'] = existing_foerdermittel_id
            new_version_data['requires_review'] = True  # Flag for human review

            # Changed programs go back to draft status for review
            # (even if the old version was published)
            new_version_data['status'] = 'draft'

            # Create new version
            created_item = directus.create_item("foerdermittel", new_version_data)

            # Update scraped data status
            directus.update_item(
                "foerdermittel_scraped_data",
                item['id'],
                {
                    "processed": True,
                    "processing_status": "completed",
                    "foerdermittel_id": created_item.get('id')
                }
            )

            print(f"✓ Updated (v{new_version_data['version']}): {new_structured_data.get('title', 'Unknown')}")
            print(f"  Changes: {change_summary}")
        else:
            print(f"[DRY-RUN] Would create version update: {new_structured_data.get('title', 'Unknown')}")
            print(f"[DRY-RUN] Changes: {change_summary}")

        return True

    except Exception as e:
        logger.error(f"Error processing program update {item.get('id', 'unknown')}: {str(e)}")

        if not dry_run:
            try:
                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processing_status": "failed",
                        "error_message": str(e)
                    }
                )
            except Exception as update_error:
                logger.error(f"Failed to update error status: {str(update_error)}")

        return False


def main():
    """Main entry point for the analyzer application."""
    parser = argparse.ArgumentParser(
        description="Fördermittel Analyzer with LLM Extraction"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=10,
        help="Maximum number of items to process"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Process without saving to Directus"
    )

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Initialize clients
    directus = DirectusClient(DIRECTUS_URL, token=DIRECTUS_TOKEN)
    processor = FoerdermittelProcessor(OPENAI_API_KEY, directus)

    print(f"Starting Fördermittel analyzer (limit: {args.limit})")

    # Get pending items
    pending_items = directus.get_pending_items(
        collection="foerdermittel_scraped_data",
        processing_status="pending",
        limit=args.limit
    )

    print(f"Found {len(pending_items)} pending items to process")

    # Process each item
    processed_count = 0
    relevant_count = 0
    error_count = 0

    for item in pending_items:
        try:
            # Process the program
            structured_data = processor.process_program(item)

            if not structured_data:
                error_count += 1
                if not args.dry_run:
                    directus.update_item(
                        "foerdermittel_scraped_data",
                        item['id'],
                        {
                            "processing_status": "failed",
                            "error_message": "Failed to extract structured data"
                        }
                    )
                continue

            # Count relevant programs
            if structured_data.get('is_relevant', False):
                relevant_count += 1

            # Save to Directus if not dry-run
            if not args.dry_run:
                # Check for duplicates
                existing = directus.session.get(
                    f"{directus.base_url}/items/foerdermittel",
                    headers=directus.get_headers(),
                    params={
                        "filter": json.dumps({
                            "title": {"_eq": structured_data.get("title", "")},
                            "funding_organization": {"_eq": structured_data.get("funding_organization", "")}
                        })
                    }
                )

                if existing.status_code == 200 and existing.json().get('data'):
                    print(f"Skipping duplicate: {structured_data.get('title', 'Unknown')}")
                    directus.update_item(
                        "foerdermittel_scraped_data",
                        item['id'],
                        {
                            "processed": True,
                            "processing_status": "completed",
                            "error_message": "Duplicate - already exists"
                        }
                    )
                    continue

                # Save to foerdermittel collection
                created_item = directus.create_item("foerdermittel", structured_data)

                # Update scraped data status
                directus.update_item(
                    "foerdermittel_scraped_data",
                    item['id'],
                    {
                        "processed": True,
                        "processing_status": "completed",
                        "foerdermittel_id": created_item.get('id')
                    }
                )

                print(f"✓ Saved: {structured_data.get('title', 'Unknown')} (Relevant: {structured_data.get('is_relevant', False)})")
            else:
                print(f"[DRY-RUN] Would save: {structured_data.get('title', 'Unknown')} (Relevant: {structured_data.get('is_relevant', False)})")

            processed_count += 1

        except Exception as e:
            logger.error(f"Error processing item {item.get('id', 'unknown')}: {str(e)}")
            error_count += 1

            if not args.dry_run:
                try:
                    directus.update_item(
                        "foerdermittel_scraped_data",
                        item['id'],
                        {
                            "processing_status": "failed",
                            "error_message": str(e)
                        }
                    )
                except Exception as update_error:
                    logger.error(f"Failed to update error status: {str(update_error)}")

    # Process pending_update items (changed programs)
    print(f"\nProcessing changed programs...")
    pending_updates = directus.get_pending_items(
        collection="foerdermittel_scraped_data",
        processing_status="pending_update",
        limit=args.limit
    )

    print(f"Found {len(pending_updates)} changed programs to process")

    updated_count = 0
    update_error_count = 0

    for item in pending_updates:
        success = process_program_update(processor, directus, item, args.dry_run)
        if success:
            updated_count += 1
        else:
            update_error_count += 1

    # Print summary
    print("\n" + "="*60)
    print("PROCESSING SUMMARY")
    print("="*60)
    print(f"New programs processed: {processed_count}")
    print(f"New programs relevant: {relevant_count}")
    print(f"New programs errors: {error_count}")
    print(f"Changed programs updated: {updated_count}")
    print(f"Changed programs errors: {update_error_count}")
    print(f"Total processed: {processed_count + updated_count}")
    print(f"Total errors: {error_count + update_error_count}")
    print("="*60)


if __name__ == "__main__":
    main()
