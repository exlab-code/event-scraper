// Directus API configuration
const DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o";

// Use the server's proxy endpoints instead of direct API access
// This avoids CORS issues by using the Nginx proxy
const API_BASE_URL = "/api"; // Uses the /api/ location in Nginx config
const ITEMS_BASE_URL = "/items"; // Uses the /items/ location in Nginx config

/**
 * Fetch all approved events from Directus
 * @param {Object} filters - Optional filters (category, tag)
 * @returns {Promise<Array>} - Array of event objects
 */
export async function getEvents(filters = {}) {
  try {
    // Prepare the filter object for Directus
    let filterObj = {
      approved: {
        _eq: true
      }
    };
    
    // Add category filter if specified
    if (filters.category) {
      filterObj.category = {
        _eq: filters.category
      };
    }
    
    // Note: Filtering by tags is more complex with Directus and will be handled client-side
    // since tags are stored as an array
    
    // Build query parameters
    const params = new URLSearchParams({
      filter: JSON.stringify(filterObj),
      sort: "start_date"
    });
    
    // Use the Nginx proxy endpoint for items
    const apiUrl = `${ITEMS_BASE_URL}/events?${params}`;
    
    // Make the API request with authorization header
    const response = await fetch(apiUrl, {
      headers: {
        Authorization: `Bearer ${DIRECTUS_TOKEN}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    
    // If tag filter is specified, filter the results client-side
    if (filters.tag && filters.tag.trim() !== '') {
      return data.data.filter(event => 
        event.tags && Array.isArray(event.tags) && event.tags.includes(filters.tag)
      );
    }
    
    return data.data;
  } catch (error) {
    console.error('Error fetching events:', error);
    throw error;
  }
}

/**
 * Fetch all unique categories from approved events
 * @returns {Promise<Array>} - Array of category strings
 */
export async function getCategories() {
  try {
    // Use the Nginx proxy endpoint for items
    const filterParams = new URLSearchParams({
      filter: JSON.stringify({approved:{_eq:true}}),
      sort: "start_date"
    });
    
    const apiUrl = `${ITEMS_BASE_URL}/events?${filterParams}`;
    
    // Make the API request with authorization header
    const response = await fetch(apiUrl, {
      headers: {
        Authorization: `Bearer ${DIRECTUS_TOKEN}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    const events = data.data;
    
    // Extract unique categories
    const uniqueCategories = [...new Set(
      events
        .map(event => event.category)
        .filter(Boolean) // Remove null/undefined values
    )];
    
    return uniqueCategories.sort();
  } catch (error) {
    console.error('Error fetching categories:', error);
    throw error;
  }
}

/**
 * Fetch all unique tags from approved events
 * @returns {Promise<Array>} - Array of tag strings
 */
export async function getTags() {
  try {
    // Use the Nginx proxy endpoint for items
    const filterParams = new URLSearchParams({
      filter: JSON.stringify({approved:{_eq:true}}),
      sort: "start_date"
    });
    
    const apiUrl = `${ITEMS_BASE_URL}/events?${filterParams}`;
    
    // Make the API request with authorization header
    const response = await fetch(apiUrl, {
      headers: {
        Authorization: `Bearer ${DIRECTUS_TOKEN}`
      }
    });
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    
    const data = await response.json();
    const events = data.data;
    
    // Extract all tags and flatten the array
    const allTags = events
      .map(event => event.tags || [])
      .flat();
    
    // Get unique tags
    const uniqueTags = [...new Set(allTags)];
    
    return uniqueTags.sort();
  } catch (error) {
    console.error('Error fetching tags:', error);
    throw error;
  }
}

/**
 * Get calendar subscription URLs
 * @returns {Promise<Object>} - Object with calendar URLs
 */
export async function getCalendarUrls() {
  // Return hardcoded URLs for the Nextcloud calendar and local iCal download
  return {
    nextcloud: "https://cloud.buerofalk.de/remote.php/dav/public-calendars/AnaLz2YHKjM6EF7k?export",
    ical: "/calendar.ics"
  };
}
