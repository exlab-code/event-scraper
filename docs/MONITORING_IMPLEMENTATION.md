# Fördermittel Monitoring System Implementation

## Status: IN PROGRESS

This document tracks the implementation of the website change monitoring system for the Fördermittel scraper.

## Completed

### 1. Database Schema Changes ✓
- Added fields to `foerdermittel_scraped_data`:
  - `previous_content_hash` (string) - Hash of previous scrape
  - `last_checked_at` (datetime) - Last check timestamp
  - `change_detected_at` (datetime) - When change was found
  - `check_count` (integer, default: 1) - Number of checks
  - `is_active` (boolean, default: true) - Program exists on source
  - `last_seen_at` (datetime) - Last time found on source

- Added fields to `foerdermittel`:
  - `version` (integer, default: 1) - Version number
  - `change_summary` (text) - What changed
  - `previous_version_id` (uuid) - Link to previous version
  - `requires_review` (boolean, default: false) - Human review flag

- Updated `processing_status` choices to include:
  - `pending_update` - Content changed, needs reanalysis
  - `removed` - Program no longer on source

### 2. DirectusClient Updates ✓
- Added `get_item_by_url(collection, url)` method
- Added `get_active_programs(collection, source_name)` method

### 3. Scraper Updates (PARTIAL)
- Added `check_duplicate_or_changed(content, url)` method ✓

## Remaining Work

### 4. Complete Scraper Updates

#### A. Update `save_to_directus()` method
Replace existing method at line 283 with:

```python
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
            "check_count": existing_item.get('check_count', 0) + 1
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
            "check_count": existing_item.get('check_count', 0) + 1
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
```

#### B. Add `mark_removed_programs()` method
Add after save_to_directus method:

```python
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
                last_seen = datetime.fromisoformat(program['last_seen_at'].replace('Z', '+00:00'))
                days_since_last_seen = (datetime.now().replace(tzinfo=last_seen.tzinfo) - last_seen).days
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
```

#### C. Update `scrape_source()` method
Modify the existing code starting at line ~695 to:

1. Track seen URLs
2. Use `check_duplicate_or_changed()` instead of `check_duplicate_content()`
3. Pass status to `save_to_directus()`
4. Call `mark_removed_programs()` at end

Key changes:
```python
seen_urls = set()  # Track URLs found in this scrape

# ... existing URL collection logic ...

for i, url in enumerate(program_urls):
    seen_urls.add(url)  # Track this URL

    # ... existing scraping logic ...

    # Replace duplicate check:
    # OLD: is_duplicate, item_id = self.check_duplicate_content(program_json)
    # NEW:
    status, existing_id, previous_hash = self.check_duplicate_or_changed(
        program_json, url
    )

    if status == 'unchanged':
        logger.debug(f"Skipping unchanged program: {url}")
        # Still update timestamps
        self.save_to_directus(
            program_data, content_hash,
            status='unchanged',
            existing_id=existing_id,
            existing_item=...  # Need to get full item
        )
        continue

    # ... rest of logic ...

    # Pass status to save_to_directus
    self.save_to_directus(
        program_data, content_hash,
        status=status,
        existing_id=existing_id,
        previous_hash=previous_hash,
        existing_item=...  # Get from check_duplicate_or_changed
    )

# After loop, mark removed programs
self.mark_removed_programs(source['name'], seen_urls)
```

### 5. Analyzer Updates

#### A. Add `detect_changes()` function
Add to foerdermittel_analyzer.py:

```python
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
```

#### B. Add `process_program_update()` function
[See full implementation in plan document - too long for this summary]

#### C. Modify `main()` function
Update to process both pending and pending_update items separately.

### 6. Create Monitoring Script

Create `foerdermittel/foerdermittel_monitor.py`:

```python
#!/usr/bin/env python3
"""
Fördermittel Monitoring Script

Runs the complete monitoring workflow:
1. Scrape all sources (checks for new, changed, removed programs)
2. Analyze new/changed programs with LLM
3. Generate change report
"""

import subprocess
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("foerdermittel-monitor")

def run_command(cmd, description):
    """Run a command and log results."""
    logger.info(f"Starting: {description}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"{description} failed:")
        logger.error(result.stderr)
        return False

    logger.info(f"{description} completed successfully")
    if result.stdout:
        print(result.stdout)
    return True

def main():
    logger.info(f"=== Fördermittel Monitoring Run: {datetime.now()} ===")

    # Step 1: Run scraper
    if not run_command(
        ["python", "foerdermittel/foerdermittel_scraper.py", "--max-programs", "-1"],
        "Scraper (checking for changes)"
    ):
        sys.exit(1)

    # Step 2: Run analyzer
    if not run_command(
        ["python", "foerdermittel/foerdermittel_analyzer.py", "--limit", "50"],
        "Analyzer (processing new/changed programs)"
    ):
        sys.exit(1)

    logger.info("=== Monitoring run completed successfully ===")

if __name__ == "__main__":
    main()
```

### 7. Testing

1. Test new program detection
2. Test change detection
3. Test removal detection
4. Test restoration
5. Test LLM reanalysis of changed programs

## Next Steps

1. Complete scraper updates (save_to_directus, mark_removed_programs, scrape_source modifications)
2. Add analyzer change detection and update processing
3. Create monitoring script
4. Test all scenarios
5. Set up cron job for weekly runs
6. Update documentation

## Cron Schedule

Add to crontab for weekly Monday 6 AM runs:
```bash
0 6 * * 1 cd /path/to/Event-Scraper && PYTHONPATH=. /usr/bin/python3 foerdermittel/foerdermittel_monitor.py >> logs/monitor.log 2>&1
```
