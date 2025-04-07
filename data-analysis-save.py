def get_available_models():
    """Get a list of available models from Anthropic API.
    
    Returns:
        list: List of available model names
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    try:
        # Try to get available models
        logger.info("Checking available Claude models...")
        
        # If the anthropic client has a models method, use it
        if hasattr(client, 'models') and hasattr(client.models, 'list'):
            response = client.models.list()
            models = [model.id for model in response.data]
            logger.info(f"Available models: {', '.join(models)}")
            return models
        else:
            # Otherwise try a direct API call to get models
            headers = {
                "x-api-key": ANTHROPIC_API_KEY,
                "content-type": "application/json"
            }
            response = requests.get("https://api.anthropic.com/v1/models", headers=headers)
            response.raise_for_status()
            models = [model['id'] for model in response.json().get('data', [])]
            logger.info(f"Available models: {', '.join(models)}")
            return models
            
    except Exception as e:
        logger.error(f"Error getting available models: {str(e)}")
        # Return a default list of models that might be available
        default_models = ["claude-3", "claude-2", "claude-instant-1"]
        logger.warning(f"Using default model list: {', '.join(default_models)}")
        return default_models#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Processor for Scraped Event Data from Directus Database

This script processes unprocessed event data from a Directus database,
sends it to Claude AI for processing, and saves the structured results
to the 'events' collection in Directus.
"""
import anthropic
import json
import logging
import requests
import os
import re
import argparse
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("processor.log"), logging.StreamHandler()]
)
logger = logging.getLogger("event-processor")

# Anthropic API key for Claude
ANTHROPIC_API_KEY = "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"

# Directus configuration
DIRECTUS_URL = "https://calapi.buerofalk.de"
DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o"

def get_unprocessed_items_from_directus(limit=10):
    """Get unprocessed items from Directus database
    
    Args:
        limit (int): Maximum number of items to retrieve
        
    Returns:
        list: List of unprocessed items
    """
    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        # First check if we can connect to Directus
        logger.info(f"Testing connection to Directus API at {DIRECTUS_URL}")
        test_url = f"{DIRECTUS_URL}/users/me"
        test_response = requests.get(test_url, headers=headers)
        test_response.raise_for_status()
        logger.info("Successfully connected to Directus API and authenticated")
        
        # Get all items with pagination
        all_items = []
        unprocessed_items = []
        page = 1
        page_size = 50  # Fetch in larger batches for efficiency
        
        while True:
            url = f"{DIRECTUS_URL}/items/scraped_data?limit={page_size}&page={page}"
            logger.info(f"Fetching page {page} of items from scraped_data")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            items = response.json().get('data', [])
            if not items:
                break
                
            all_items.extend(items)
            page += 1
            
            # Stop if we have enough items or there are no more
            if len(all_items) >= 200:  # Safety limit to avoid too many API calls
                break
        
        logger.info(f"Retrieved {len(all_items)} total items from scraped_data")
        
        # Filter for truly unprocessed items
        for item in all_items:
            # Check if this item is actually unprocessed
            if not item.get('processed', False) and item.get('processing_status') != 'processed':
                unprocessed_items.append(item)
                
                # Break if we have enough unprocessed items
                if len(unprocessed_items) >= limit:
                    break
        
        logger.info(f"Found {len(unprocessed_items)} unprocessed items out of {len(all_items)} total items")
        return unprocessed_items
        
    except Exception as e:
        logger.error(f"Failed to get items from Directus: {str(e)}")
        return []

def update_item_status(item_id, success=True, processed_content=None):
    """Update item processing status in Directus
    
    Args:
        item_id (str): Item ID
        success (bool): Whether processing was successful
        processed_content (str): JSON string of processed content
    """
    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    update_data = {
        "processed": True,
        "processed_at": datetime.now().isoformat(),
        "processing_status": "processed" if success else "failed"
    }
    
    if processed_content:
        update_data["processed_content"] = processed_content
    
    try:
        url = f"{DIRECTUS_URL}/items/scraped_data/{item_id}"
        response = requests.patch(url, headers=headers, json=update_data)
        response.raise_for_status()
        logger.info(f"Updated status for item {item_id} in Directus (success={success})")
    
    except Exception as e:
        logger.error(f"Failed to update status for item {item_id} in Directus: {str(e)}")

def process_with_claude(event_details, source_name, batch_size=3):
    """Process event details with Claude AI in batches to optimize cost and performance.
    
    Args:
        event_details (list): List of event data to process
        source_name (str): Name of the source
        batch_size (int): Number of events to process in each API call
        
    Returns:
        list: Processed events
    """
    if not event_details:
        return []
    
    # Initialize cost tracking
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0
    
    # Token and cost rates (as of April 2025)
    # Claude 3 pricing estimates
    INPUT_TOKEN_RATE = 15 / 1_000_000  # $15 per million tokens
    OUTPUT_TOKEN_RATE = 75 / 1_000_000  # $75 per million tokens
    
    # Use the correct model
    model_name = globals().get('CLAUDE_MODEL', "claude-3-sonnet-20240307")
    trim_text = globals().get('TRIM_TEXT', False)
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    all_processed_events = []
    
    # Process in batches to reduce costs
    for i in range(0, len(event_details), batch_size):
        batch = event_details[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} events")
        
        # Prepare events for this batch
        events_text = ""
        for j, event in enumerate(batch):
            events_text += f"EVENT {j+1}:\n"
            
            # Parse raw_content if it's a JSON string
            event_data = event
            if 'raw_content' in event and isinstance(event['raw_content'], str):
                try:
                    parsed_content = json.loads(event['raw_content'])
                    event_data = parsed_content
                except json.JSONDecodeError:
                    pass
            
            # Include only essential text to reduce token usage if trim_text is enabled
            if 'listing_text' in event_data:
                listing_text = event_data['listing_text']
                if trim_text:
                    # Trim listing text to reduce tokens
                    events_text += f"LISTING PAGE TEXT:\n{listing_text[:2000]}\n\n"
                else:
                    events_text += f"LISTING PAGE TEXT:\n{listing_text}\n\n"
            
            if 'detail_text' in event_data and event_data['detail_text']:
                detail_text = event_data['detail_text']
                if trim_text:
                    # Only include first 3000 chars of detail text to save tokens
                    events_text += f"DETAIL PAGE TEXT:\n{detail_text[:3000]}\n\n"
                else:
                    events_text += f"DETAIL PAGE TEXT:\n{detail_text}\n\n"
            
            if 'url' in event_data and event_data['url']:
                events_text += f"EVENT URL: {event_data['url']}\n"
                
            events_text += "="*50 + "\n\n"
        
        # Log the batch's input text
        batch_log_file = f"claude_input_batch_{i//batch_size + 1}.txt"
        with open(batch_log_file, "w", encoding="utf-8") as f:
            f.write(events_text)
        
        # Streamlined prompt to reduce tokens
        prompt = """
        Extrahiere von deutschen Webseiten Digitalisierungsveranstaltungen fuer gemeinnuetzige Organisationen.
        
        Extrahiere fuer jede relevante Veranstaltung:
        - title: Veranstaltungsname
        - description: Kurze Beschreibung (max. 5 Saetze)
        - start_date: JJJJ-MM-TT oder JJJJ-MM-TTTHH:MM:SS
        - end_date: ISO-Format falls vorhanden
        - organizer: Veranstalter
        - website: URL
        - cost: Preisinformation
        - category: Eine aus: Digital Fundraising, Datenmanagement, Website-Entwicklung, Social Media, Digitale Transformation, Cloud-Technologie, Cybersicherheit, Datenanalyse, KI fuer NPOs, Digitales Marketing
        - tags: Relevante Schlagwoerter
        - speaker: Referent(en)
        - location: Ort oder "Online"
        - register_link: Anmeldelink
        - videocall_link: Webinar-Link
        
        Leere Felder bei Unsicherheit. Nur Veranstaltungen zur Digitalisierung fuer NPOs betrachten.
        Antwort nur als JSON-Array. Ein Objekt pro Veranstaltung.
        """
        
        try:
            # Make API call with the model specified in globals()
            logger.info(f"Using Claude model: {model_name}")
            response = client.messages.create(
                model=model_name,
                max_tokens=4000,
                temperature=0,
                messages=[
                    {"role": "user", "content": prompt + "\n\nHier sind die zu analysierenden Veranstaltungen:\n\n" + events_text}
                ]
            )
            
            # Get token usage for cost calculation
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            
            # Calculate cost for this batch
            batch_input_cost = input_tokens * INPUT_TOKEN_RATE
            batch_output_cost = output_tokens * OUTPUT_TOKEN_RATE
            batch_total_cost = batch_input_cost + batch_output_cost
            
            # Add to totals
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_cost += batch_total_cost
            
            # Log token usage and costs
            logger.info(f"Batch {i//batch_size + 1} token usage: {input_tokens} input, {output_tokens} output")
            logger.info(f"Batch {i//batch_size + 1} cost: ${batch_total_cost:.4f} (${batch_input_cost:.4f} input + ${batch_output_cost:.4f} output)")
            
            # Log Claude's response
            batch_response_file = f"claude_response_batch_{i//batch_size + 1}.txt"
            with open(batch_response_file, "w", encoding="utf-8") as f:
                f.write(response.content[0].text)
            
            # Extract JSON from response
            content = response.content[0].text
            
            # Find JSON array using regex
            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                try:
                    batch_processed_events = json.loads(json_text)
                    
                    # Add source to each event
                    for event in batch_processed_events:
                        event['source'] = source_name
                        event['approved'] = False
                    
                    # Add to our overall results
                    all_processed_events.extend(batch_processed_events)
                    logger.info(f"Batch {i//batch_size + 1}: Extracted {len(batch_processed_events)} events")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON from Claude response in batch {i//batch_size + 1}: {str(e)}")
                    with open(f"problematic_json_batch_{i//batch_size + 1}.txt", "w", encoding="utf-8") as f:
                        f.write(json_text)
            else:
                logger.warning(f"No JSON found in Claude response for batch {i//batch_size + 1}")
                
        except Exception as e:
            logger.error(f"Error processing batch {i//batch_size + 1} with Claude: {str(e)}")
    
    # Log overall token usage and cost
    logger.info(f"TOTAL TOKEN USAGE: {total_input_tokens} input, {total_output_tokens} output")
    logger.info(f"TOTAL API COST: ${total_cost:.4f}")
    
    # Save cost information to a file for tracking
    cost_log = {
        "date": datetime.now().isoformat(),
        "source": source_name,
        "num_events": len(event_details),
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "cost": total_cost,
        "model": model_name
    }
    
    with open("api_cost_log.json", "a") as f:
        f.write(json.dumps(cost_log) + "\n")
    
    logger.info(f"Claude extracted {len(all_processed_events)} valid events total from {source_name}")
    return all_processed_events

def save_to_directus(events):
    """Save processed events to Directus."""
    if not events:
        return 0, 0, 0
        
    headers = {
        "Authorization": f"Bearer {DIRECTUS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    successful_count = 0
    duplicate_count = 0
    error_count = 0
    
    for event in events:
        # Check if event already exists
        try:
            # Create a filter to check for duplicate events
            filter_params = {
                "filter": {
                    "_and": [
                        {"title": {"_eq": event.get("title", "")}},
                        {"start_date": {"_eq": event.get("start_date", "")}}
                    ]
                }
            }
            
            # Convert filter to query string params manually
            filter_json = json.dumps(filter_params["filter"])
            encoded_filter = f"filter={requests.utils.quote(filter_json)}"
            
            check_url = f"{DIRECTUS_URL}/items/events?{encoded_filter}"
            check_response = requests.get(check_url, headers=headers)
            
            if check_response.status_code == 200:
                existing_events = check_response.json().get("data", [])
                if existing_events:
                    logger.info(f"Event already exists: {event.get('title', 'Unknown event')}")
                    duplicate_count += 1
                    continue
            
            # Add the event to Directus
            response = requests.post(f"{DIRECTUS_URL}/items/events", headers=headers, json=event)
            
            if response.status_code in (200, 201, 204):
                logger.info(f"Added event to Directus: {event.get('title', 'Unknown event')}")
                successful_count += 1
            else:
                logger.error(f"Error adding event: {response.status_code} - {response.text}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"Exception saving to Directus: {str(e)}")
            error_count += 1
    
    logger.info(f"Summary: {successful_count} events added, {duplicate_count} duplicates skipped, {error_count} errors")
    return successful_count, duplicate_count, error_count

def process_directus_data(limit=10, batch_size=3):
    """Process unprocessed items from Directus database
    
    Args:
        limit (int): Maximum number of items to process
        batch_size (int): Number of events to process in each Claude API call
        
    Returns:
        tuple: (successful, duplicates, errors)
    """
    # Validate batch size
    if batch_size < 1:
        logger.warning(f"Invalid batch size: {batch_size}. Setting to 3.")
        batch_size = 3

    # Get unprocessed items from Directus
    unprocessed_items = get_unprocessed_items_from_directus(limit)
    
    if not unprocessed_items:
        logger.warning("No unprocessed items found in Directus")
        return 0, 0, 0
    
    logger.info(f"Found {len(unprocessed_items)} items to process with batch size {batch_size}")
    
    total_successful = 0
    total_duplicates = 0
    total_errors = 0
    
    # Group items by source_name for more efficient processing
    items_by_source = {}
    for item in unprocessed_items:
        source_name = item.get('source_name', 'Unknown Source')
        if source_name not in items_by_source:
            items_by_source[source_name] = []
        items_by_source[source_name].append(item)
    
    # Process each group of items
    for source_name, items in items_by_source.items():
        logger.info(f"Processing {len(items)} items from source: {source_name}")
        
        # Process with Claude in optimized batches
        processed_events = process_with_claude(items, source_name, batch_size)
        
        # Save processed events to a file for review
        if processed_events:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f"processed_events_{source_name.replace(' ', '_')}_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(processed_events, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(processed_events)} processed events to {output_file}")
            
            # Upload to Directus events collection
            successful, duplicates, errors = save_to_directus(processed_events)
            total_successful += successful
            total_duplicates += duplicates
            total_errors += errors
            
            # Update processing status for all items in this batch
            processed_content_json = json.dumps(processed_events)
            for item in items:
                update_item_status(item.get('id'), True, processed_content_json)
        else:
            logger.warning(f"No events were processed successfully from source: {source_name}")
            # Mark all items as failed
            for item in items:
                update_item_status(item.get('id'), False)
    
    return total_successful, total_duplicates, total_errors

if __name__ == "__main__":
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Process unprocessed events from Directus through Claude AI')
    parser.add_argument('--limit', type=int, default=10, help='Maximum number of items to process')
    parser.add_argument('--batch-size', type=int, default=3, help='Number of events to process in each Claude API call')
    parser.add_argument('--model', type=str, default='', help='Specific Claude model to use')
    parser.add_argument('--list-models', action='store_true', help='List available Claude models and exit')
    parser.add_argument('--trim-text', action='store_true', help='Trim text to reduce token usage')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Check available models if requested
    if args.list_models:
        available_models = get_available_models()
        print("Available Claude models:")
        for model in available_models:
            print(f"  - {model}")
        sys.exit(0)
    
    # Get available models
    available_models = get_available_models()
    
    # Choose a model
    if args.model and args.model in available_models:
        # Use specified model if available
        globals()['CLAUDE_MODEL'] = args.model
        logger.info(f"Using specified model: {args.model}")
    elif args.model:
        # Specified model not available
        logger.warning(f"Specified model '{args.model}' not available. Using default model.")
        if available_models:
            globals()['CLAUDE_MODEL'] = available_models[0]
            logger.info(f"Using default model: {available_models[0]}")
        else:
            globals()['CLAUDE_MODEL'] = "claude-3"
            logger.warning("No models available. Using 'claude-3' as fallback.")
    else:
        # No model specified, use first available
        if available_models:
            globals()['CLAUDE_MODEL'] = available_models[0]
            logger.info(f"Using default model: {available_models[0]}")
        else:
            globals()['CLAUDE_MODEL'] = "claude-3"
            logger.warning("No models available. Using 'claude-3' as fallback.")
    
    # Update trim settings
    globals()['TRIM_TEXT'] = args.trim_text
    if args.trim_text:
        logger.info("Text trimming enabled to reduce token usage.")
    
    logger.info(f"Starting event processor with limit: {args.limit}, batch size: {args.batch_size}")
    
    # Initialize cost tracking file if it doesn't exist
    if not os.path.exists("api_cost_log.json"):
        with open("api_cost_log.json", "w") as f:
            f.write("")
    
    # Process data
    successful, duplicates, errors = process_directus_data(args.limit, args.batch_size)
    logger.info(f"Event processing complete: {successful} added, {duplicates} duplicates, {errors} errors")
    
    # Cost summary if any processing happened
    if successful > 0 or duplicates > 0 or errors > 0:
        try:
            # Read the last line of the cost log
            with open("api_cost_log.json", "r") as f:
                lines = f.readlines()
                if lines:
                    last_cost = json.loads(lines[-1])
                    logger.info(f"API Cost Summary:")
                    logger.info(f"  Model: {last_cost['model']}")
                    logger.info(f"  Items processed: {last_cost['num_events']}")
                    logger.info(f"  Total tokens: {last_cost['input_tokens'] + last_cost['output_tokens']}")
                    logger.info(f"  Cost: ${last_cost['cost']:.4f}")
                    logger.info(f"  Average cost per item: ${last_cost['cost']/last_cost['num_events']:.4f}")
        except Exception as e:
            logger.error(f"Error summarizing costs: {str(e)}")