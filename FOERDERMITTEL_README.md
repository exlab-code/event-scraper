# Fördermittel Scraper & Analysis System

Automated system for discovering, monitoring, and analyzing German funding programs (Förderprogramme) relevant to NGOs and nonprofit organizations.

## 🎯 Overview

This system automatically:
- **Scrapes** funding programs from multiple German sources
- **Monitors** for changes, new programs, and removed programs
- **Analyzes** programs using AI to extract structured data
- **Tracks** changes and versions over time
- **Filters** for relevance to NGOs and Wohlfahrtsverbände

## 📁 Components

### 1. `foerdermittel_scraper.py`
Scrapes funding programs from configured sources and stores raw HTML/JSON data.

**Features:**
- Multi-source scraping with source-specific handlers
- Content-based change detection using hashing
- Automatic URL tracking and deduplication
- Marks removed programs after safety buffer
- Fragment URL generation for single-page sources (Aktion Mensch)

**Usage:**
```bash
# Scrape from all sources
python3 foerdermittel/foerdermittel_scraper.py

# Limit number of programs per source
python3 foerdermittel/foerdermittel_scraper.py --max-programs 10

# Scrape unlimited (-1 means all programs)
python3 foerdermittel/foerdermittel_scraper.py --max-programs -1
```

### 2. `foerdermittel_analyzer.py`
Uses LLM (GPT-4o) with Instructor for structured data extraction and relevance filtering.

**Features:**
- Pydantic model-based validation with field validators
- Automatic retries on validation failures
- Change detection for updated programs
- Version tracking with change summaries
- Relevance filtering for NGO/nonprofit sector

**Usage:**
```bash
# Process new and changed programs
python3 foerdermittel/foerdermittel_analyzer.py

# Limit number of programs to process
python3 foerdermittel/foerdermittel_analyzer.py --limit 20

# Dry run (no database writes)
python3 foerdermittel/foerdermittel_analyzer.py --limit 5 --dry-run

# Verbose output
python3 foerdermittel/foerdermittel_analyzer.py --verbose
```

### 3. `foerdermittel_monitor.py`
Orchestration script that runs the complete monitoring workflow.

**Usage:**
```bash
python3 foerdermittel/foerdermittel_monitor.py
```

Workflow:
1. Scrape all sources (checks for new/changed/removed programs)
2. Analyze new/changed programs with LLM
3. Generate summary report

### 4. `foerdermittel_importer.py`
Imports initial program data from Directus to populate the scraper's hash cache.

**Usage:**
```bash
python3 foerdermittel/foerdermittel_importer.py
```

## 🗂️ Data Model

### Database Collections

#### `foerdermittel_scraped_data`
Raw scraped data with change tracking:
- `url` - Program URL (unique identifier)
- `source_name` - Source identifier
- `raw_content` - Raw HTML/JSON
- `content_hash` - Hash for change detection
- `previous_content_hash` - Previous hash when changed
- `scraped_at` - When first scraped
- `last_checked_at` - Last check timestamp
- `last_seen_at` - Last time found on source
- `change_detected_at` - When change was detected
- `check_count` - Number of checks performed
- `is_active` - Still exists on source
- `processing_status` - pending, completed, pending_update, removed, failed
- `foerdermittel_id` - Link to analyzed program

#### `foerdermittel`
Analyzed and structured funding program data:
- `title` - Program title
- `short_description` - Brief description (max 200 chars)
- `description` - Full description
- `funding_organization` - Providing organization
- `funding_provider_type` - Bund, Land, EU, Stiftung, Sonstige
- `bundesland` - State or scope
- `funding_type` - Zuschuss, Kredit, Bürgschaft, Preis, Sonstige
- `funding_amount_min/max` - Funding range in EUR
- `funding_amount_text` - Non-numeric amount description
- `funding_rate` - e.g., "100%", "bis zu 50%"
- `application_deadline` - ISO date format
- `deadline_type` - einmalig, laufend, jährlich, geschlossen
- `funding_period_start/end` - ISO date format
- `target_group` - Target audience
- `eligibility_criteria` - Detailed criteria
- `website` - Official program URL
- `contact_email` - Contact if available
- `is_relevant` - Relevance flag for NGOs
- `relevance_reason` - Explanation of relevance
- `status` - draft, published, archived
- `version` - Version number
- `change_summary` - What changed in this version
- `previous_version_id` - Link to previous version
- `requires_review` - Human review needed flag
- `source` - Source name
- `source_url` - Source URL
- `scraped_data_id` - Link to raw data

## 🔄 Monitoring Workflow

### Change Detection System

The system tracks three types of changes:

#### 1. New Programs
- Program URL not in database
- Status: `pending`
- Full LLM analysis performed
- Starts with `status='draft'`

#### 2. Changed Programs
- URL exists but content hash changed
- Status: `pending_update`
- Full LLM reanalysis performed
- New version created with:
  - Incremented version number
  - `change_summary` describing changes
  - Link to previous version
  - Reset to `status='draft'` for review
  - `requires_review=true` flag

#### 3. Removed Programs
- Previously active program not found in scrape
- Safety buffer: Only marked after 7+ days
- Status: `removed`
- `is_active=false`

### Status Workflow

Programs follow this lifecycle:

1. **draft** - Newly created or changed, awaiting review
2. **published** - Reviewed and approved for display
3. **archived** - No longer relevant or program ended

Changed programs reset to `draft` status, even if previously published, to ensure human review of changes.

## 🔧 Configuration

### Sources Configuration
Located in `config/foerdermittel_sources.json`:

```json
{
  "sources": [
    {
      "name": "source_name",
      "url": "https://...",
      "type": "custom",
      "extraction_method": "function_name"
    }
  ]
}
```

### Environment Variables
Required in `.env`:
```bash
DIRECTUS_URL=https://your-directus-url.com
DIRECTUS_TOKEN=your-directus-token
OPENAI_API_KEY=your-openai-key
```

## 🚀 Production Setup

### Automated Monitoring

Add to crontab for weekly Monday 6 AM runs:
```bash
0 6 * * 1 cd /path/to/Event-Scraper && PYTHONPATH=. /usr/bin/python3 foerdermittel/foerdermittel_monitor.py >> logs/foerdermittel_monitor.log 2>&1
```

### Manual Testing

Test the complete workflow:
```bash
# 1. Run scraper to check for changes
python3 foerdermittel/foerdermittel_scraper.py --max-programs 5

# 2. Check what was found
# Query foerdermittel_scraped_data for pending/pending_update items

# 3. Run analyzer
python3 foerdermittel/foerdermittel_analyzer.py --limit 5 --verbose

# 4. Verify results in Directus
```

## 📊 Key Features

### Intelligent URL Handling

**Fragment URLs for Single-Page Sources:**
- Aktion Mensch displays all programs on one page
- System generates stable URLs: `base-url#title-slug-hash`
- Example: `https://www.aktion-mensch.de/foerderung/angebote/foerderfinder#bildungsveranstaltungen-f0e38f`
- Ensures unique, human-readable, stable tracking

### LLM Structured Output with Instructor

**Pydantic Models with Validation:**
- Type-safe field definitions
- Automatic field validators (dates, emails, lengths)
- Better error messages
- Automatic retries on validation failures
- Date format conversion (German → ISO)
- Email validation
- Text truncation for length limits

### Change Detection

**Content-Based Tracking:**
- MD5 hash of program content
- Detects significant field changes
- Tracks version history
- Change summary generation
- Requires human review for changes

**Fields Monitored for Changes:**
- Title
- Funding amounts (min/max)
- Application deadline
- Funding period end
- Eligibility criteria
- Funding rate
- Deadline type
- Relevance status

## 🐛 Troubleshooting

### Scraper Issues

**Problem:** Programs not being scraped
- Check `foerdermittel_extraction.log` for errors
- Verify source website is accessible
- Check if source structure has changed

**Problem:** All programs marked as "unchanged"
- Hash cache may be stale
- Run importer to refresh: `python3 foerdermittel/foerdermittel_importer.py`

### Analyzer Issues

**Problem:** LLM extraction fails
- Check OpenAI API key
- Verify credit/quota availability
- Check prompt length (may exceed context window)

**Problem:** Validation errors
- Check field validators in `FoerdermittelData` model
- Verify date formats
- Check text field lengths

## 📈 Monitoring Metrics

The system tracks:
- **Programs scraped** - Total raw programs found
- **New programs** - First time discovered
- **Changed programs** - Content updates detected
- **Removed programs** - No longer on source
- **Programs analyzed** - Successfully processed by LLM
- **Relevant programs** - Filtered for NGO relevance
- **Processing errors** - Failed extractions

Check logs:
- `foerdermittel_extraction.log` - Scraper activity
- `foerdermittel_monitor.log` - Monitoring runs
- Console output during execution

## 🎓 Related Documentation

- [Monitoring Implementation](docs/MONITORING_IMPLEMENTATION.md) - Detailed implementation notes
- [Event Scraper README](README.md) - Main project documentation
- [Directus Schema](docs/DIRECTUS_SCHEMA.md) - Database structure

## 📝 Development Notes

### Recent Improvements (2025-10-30)

1. **Aktion Mensch URL Fix**
   - Replaced login page URLs with stable fragment identifiers
   - Format: `base-url#title-slug-hash`
   - Preserves application URLs in separate field

2. **Instructor Implementation**
   - Replaced JSON Schema with Pydantic models
   - Added comprehensive field validators
   - Improved error handling and retries

3. **Status Field Integration**
   - Using Directus built-in status field
   - Workflow: draft → published → archived
   - Changed programs reset to draft for review

### Future Enhancements

- [ ] Email notifications for changes
- [ ] Web dashboard for review workflow
- [ ] Automatic deadline reminders
- [ ] Export to calendar formats
- [ ] Multi-language support
- [ ] Additional funding sources
