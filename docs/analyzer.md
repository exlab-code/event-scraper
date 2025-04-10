# Event Analyzer Documentation

This document provides information about the Event Analyzer component of the Event Scraper & Management System.

## Overview

The Event Analyzer (`event_analyzer.py`, formerly `data-analysis-save-gpt-v2.py`) is responsible for:

1. Processing unprocessed event data from the Directus database
2. Using GPT-4o Mini to extract structured information from event descriptions
3. Determining event relevance for non-profit organizations
4. Generating tags and tag groups for better categorization
5. Saving the enhanced data back to Directus

## Features

- **Enhanced Extraction**: Improved extraction for dates, times, and registration links
- **Tag-Based Categorization**: Generates normalized, consistent tags grouped by category
- **Feedback Loop**: Incorporates moderator feedback to improve relevance determinations
- **Automatic Exclusion**: Identifies and flags multi-day, high-cost training events
- **Comprehensive Logging**: Detailed logging for better debugging and analysis

## Usage

```bash
python event_analyzer.py [options]
```

### Command-line Options

- `--limit`, `-l`: Maximum number of items to process (default: 10)
- `--batch`, `-b`: Batch size for processing (default: 3)
- `--flag-mismatches`, `-f`: Flag events where LLM determination doesn't match human feedback
- `--only-flag`, `-o`: Only flag mismatches without processing new events
- `--log-file`: Path to log file for LLM extraction results (default: llm_extraction.log)

### Examples

**Process 20 events with a batch size of 5:**
```bash
python event_analyzer.py --limit 20 --batch 5
```

**Flag mismatches and process new events:**
```bash
python event_analyzer.py --flag-mismatches
```

**Only flag mismatches without processing new events:**
```bash
python event_analyzer.py --only-flag
```

## How It Works

1. **Retrieval**: Fetches unprocessed items from the Directus database
2. **Pre-processing**: Uses regex to extract dates, times, and registration links
3. **LLM Processing**: Sends event data to GPT-4o Mini for structured extraction
4. **Post-processing**: Validates and enhances the extracted data
5. **Storage**: Saves the processed data back to Directus

## Feedback System

The analyzer includes a feedback system that:

1. Identifies events where the LLM's relevance determination doesn't match human feedback
2. Flags these events for review
3. Analyzes patterns in the feedback to improve future determinations
4. Incorporates these patterns into the LLM prompt

## Recent Updates (April 2025)

- Removed regex-based date extraction to rely solely on the LLM's extraction capabilities
- Fixed registration link extraction to only match valid URLs
- Added comprehensive logging for better debugging
- Improved override logic to prioritize LLM-extracted dates
- Migrated from categories to a more flexible tag-based approach
- Added tag frequency filtering to show only commonly used tags

## Configuration

The analyzer uses environment variables from a `.env` file:

```
DIRECTUS_API_URL=https://your-directus-api-url
DIRECTUS_API_TOKEN=your-api-token-here
OPENAI_API_KEY=your-openai-api-key
```

## Troubleshooting

If you encounter issues:

1. Check the log file (`llm_extraction.log`) for detailed error messages
2. Verify your API credentials in the `.env` file
3. Ensure the Directus database is accessible
4. Check that you have sufficient OpenAI API credits
