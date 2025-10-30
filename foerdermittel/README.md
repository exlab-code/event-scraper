# Fördermittel Database System

A unified funding opportunity database for German NGOs and Wohlfahrtsverbände (welfare organizations). This system scrapes German funding databases, extracts structured data using LLM analysis, and stores it in Directus for easy filtering and exploration.

## Overview

The Fördermittel system consists of three main components:

1. **Scraper** (`foerdermittel_scraper.py`) - Scrapes funding program websites
2. **Analyzer** (`foerdermittel_analyzer.py`) - Extracts structured data using GPT-4o with Structured Outputs
3. **Shared utilities** (`shared/directus_client.py`) - Reusable Directus and caching components

## Architecture

```
┌─────────────────────┐
│  Funding Websites   │
│  (DSEE, etc.)      │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ foerdermittel_      │
│    scraper.py      │  → Scrapes raw HTML
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Directus CMS     │
│ foerdermittel_      │
│  scraped_data       │  → Raw scraped data
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ foerdermittel_      │
│   analyzer.py      │  → LLM extraction (GPT-4o)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│    Directus CMS     │
│   foerdermittel     │  → Structured funding data
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│  Website Display    │
│ (Future: Svelte)    │  → User-facing interface
└─────────────────────┘
```

## Installation

1. Ensure you have Python 3.8+ installed
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables in `.env`:
   ```
   DIRECTUS_API_URL=https://your-directus-url.com
   DIRECTUS_API_TOKEN=your-api-token
   OPENAI_API_KEY=your-openai-key
   ```

## Directus Collections

### `foerdermittel_scraped_data`
Raw scraped content pipeline collection with the following fields:
- `id` (integer, auto-increment)
- `url` (string)
- `source_name` (string)
- `content_hash` (string) - SHA-256 hash for deduplication
- `raw_content` (text) - JSON-encoded scraped data
- `scraped_at` (datetime)
- `processed` (boolean)
- `processing_status` (dropdown: pending/processing/completed/failed)
- `error_message` (text)
- `foerdermittel_id` (uuid) - Relation to foerdermittel collection

### `foerdermittel`
Structured funding program data with 45 fields including:
- Basic info: title, description, funding_organization
- Financial: funding_amount_min/max, funding_rate, funding_type
- Temporal: application_deadline, funding_period_start/end, deadline_type
- Geographic: bundesland
- Eligibility: target_group, eligibility_criteria
- Status: approved, is_relevant, status
- And more...

## Usage

### 1. Scraping Funding Programs

```bash
# Scrape with default limit (10 programs per source)
python foerdermittel_scraper.py

# Scrape specific number of programs
python foerdermittel_scraper.py --max-programs 5

# Verbose logging
python foerdermittel_scraper.py --verbose

# Save HTML files for debugging
python foerdermittel_scraper.py --save-html

# Clear cache and re-scrape
python foerdermittel_scraper.py --clear-cache
```

**Output:**
- Saves to `foerdermittel_scraped_data` collection in Directus
- Backup JSON file: `data/scraped_foerdermittel.json`
- Log file: `logs/foerdermittel_scraper.log`

### 2. Analyzing with LLM

```bash
# Process pending items (default: 10)
python foerdermittel_analyzer.py

# Process specific number
python foerdermittel_analyzer.py --limit 20

# Dry run (no saving to Directus)
python foerdermittel_analyzer.py --dry-run

# Verbose logging
python foerdermittel_analyzer.py --verbose
```

**Output:**
- Structured data in `foerdermittel` collection
- Log file: `foerdermittel_extraction.log`

## Configuration

### Scraper Configuration (`config/foerdermittel_sources.json`)

The scraper supports two types of sources:

**1. HTML Listing Pages (type: "dsee")**
```json
{
  "name": "DSEE Förderdatenbank",
  "url": "https://foerderdatenbank.d-s-e-e.de/",
  "type": "dsee",
  "link_selector": "a[href*='/foerderprogramme/']",
  "description": "DSEE funding database for NGOs",
  "target_group": "NGOs, Wohlfahrtsverbände",
  "update_frequency": "weekly"
}
```

**2. RSS Feeds (type: "rss")**
```json
{
  "name": "Förderdatenbank des Bundes",
  "url": "https://www.foerderdatenbank.de/FDB/DE/Service/RSS/Functions/foerderprogram_rssnewsfeed.xml",
  "type": "rss",
  "description": "Federal funding database RSS feed",
  "target_group": "Various including NGOs",
  "update_frequency": "daily"
}
```

### External Link Following

The scraper intelligently follows external detail links to gather comprehensive information:

**Followed Links (High Priority):**
- Vergaberichtlinien / Förderrichtlinien (guidelines)
- Antragsformulare (application forms)
- Bewerbungsverfahren (application procedures)
- Legal texts (Vorschriften, Rechtsgrundlagen)

**Filtered Out (Low Quality):**
- Homepage URLs (e.g., `https://example.de/`)
- Generic portals (e.g., `/foerderportal`, `/startseite`)
- Social media links
- Navigation pages

**Result:** 8x more data per program with focused, relevant content.

## LLM Extraction

The analyzer uses **OpenAI GPT-4o with Structured Outputs** for 100% schema adherence. Key features:

- **JSON Schema validation** - Guarantees correct data structure
- **German-specific patterns** - Regex extraction for dates and amounts
- **Relevance filtering** - Determines if funding is relevant for NGOs
- **Pre-processing** - Extracts key information with regex before LLM
- **Post-processing** - Validates and formats dates, amounts, etc.

### Relevance Criteria

A funding program is marked as `is_relevant: true` when:
- Explicitly for gemeinnützige Organisationen, NGOs, Vereine, Wohlfahrtsverbände
- OR for Engagement, Ehrenamt, Zivilgesellschaft
- AND förderfähige Kosten or Zuschüsse available

Marked as `is_relevant: false` when:
- Only for Unternehmen/Startups
- Only for Forschungseinrichtungen/Hochschulen
- Only for Privatpersonen
- Only Kredite without Zuschüsse for profit-oriented projects

## Tech Stack

### Scraper
- **BeautifulSoup** - HTML/XML parsing (html.parser for HTML, xml for RSS)
- **lxml** - XML parsing library for RSS feeds
- **Requests** - HTTP client with session support
- **Pickle** - URL caching (1 week TTL)
- **SHA-256** - Content hashing for deduplication
- **Intelligent Link Detection** - Keyword-based external link following

### Analyzer
- **OpenAI GPT-4o** - LLM with Structured Outputs
- **JSON Schema** - 100% schema adherence
- **Regex patterns** - German date/amount extraction
- **Directus API** - Data persistence

### Shared
- **DirectusClient** - Unified API client with authentication
- **URLCache** - Persistent URL content cache
- **ContentHashCache** - In-memory hash deduplication

## Data Flow

1. **Scraping** (weekly)
   - Fetch funding program URLs from source (RSS feed or HTML listing)
   - Scrape detail pages
   - **Follow external detail links** (up to 5 per program)
     - Detect links with keywords: richtlinie, antrag, bewerb, vorschrift
     - Skip homepages and generic portals
     - Combine all content into single comprehensive document
   - Calculate SHA-256 hash for deduplication
   - Save raw content to `foerdermittel_scraped_data`

2. **LLM Analysis** (on-demand)
   - Query pending items from `foerdermittel_scraped_data`
   - Pre-process with regex (dates, amounts)
   - Call GPT-4o with JSON Schema
   - Post-process and validate
   - Save to `foerdermittel` collection
   - Update scraped data status

3. **Approval Workflow** (future)
   - Moderators review extracted data
   - Approve/reject funding programs
   - Provide feedback for LLM improvement

## Caching Strategy

- **URL Cache** - 1 week TTL, stored in `.cache/foerdermittel_url_cache.pkl`
- **Content Hash Cache** - In-memory, session-only
- **Directus Queries** - Check by hash before saving

## Error Handling

- **Network errors** - Logged, continue with next item
- **Parse errors** - Logged, mark as failed in Directus
- **LLM errors** - Logged, mark as failed in Directus
- **Duplicate content** - Skipped, logged as duplicate

## Logging

All operations are logged to:
- `logs/foerdermittel_scraper.log` - Scraping activity
- `foerdermittel_extraction.log` - LLM extraction activity

Log entries include:
- Timestamps
- URLs processed
- Errors and exceptions
- Extracted data summaries
- Relevance determinations

## Future Enhancements

1. **Website Display**
   - Svelte frontend (shared with event scraper)
   - Advanced filtering by Bundesland, funding type, amounts
   - Calendar integration for deadlines
   - Tag-based search

2. **Additional Sources**
   - Förderdatenbank.de (10+ sources planned)
   - Regional funding databases
   - Foundation databases

3. **Feedback Loop**
   - User feedback on relevance
   - LLM fine-tuning based on feedback
   - Pattern extraction from approved programs

4. **Notifications**
   - Email alerts for new relevant programs
   - Deadline reminders
   - RSS feed

## Troubleshooting

### Scraper Issues

**No programs found:**
- Check link selector in `config/foerdermittel_sources.json`
- Verify website structure hasn't changed
- Check robots.txt compliance

**403 Forbidden errors:**
- Verify Directus API token has permissions
- Check collection access rights in Directus
- Ensure token is in `.env` file

**Duplicate detection not working:**
- Clear cache: `--clear-cache`
- Check content hash calculation
- Verify Directus API connectivity

### Analyzer Issues

**OpenAI API errors:**
- Verify API key in `.env`
- Check API quota/billing
- Review rate limits

**Schema validation errors:**
- Check JSON Schema in `foerdermittel_analyzer.py`
- Verify field types match Directus schema
- Review LLM response in logs

## Contributing

When adding new funding sources:

1. Add source configuration to `config/foerdermittel_sources.json`
2. Test with small limit: `--max-programs 2`
3. Verify link selector finds programs
4. Check extracted data quality
5. Update this README

## License

Same as parent project (Event-Scraper).

## Contact

For questions or issues, contact the Event-Scraper project maintainer.
