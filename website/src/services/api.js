// Directus API configuration with CORS-friendly endpoint
const DIRECTUS_URL = "https://calapi.buerofalk.de";
const DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o";

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
    
    // Make the API request
    const response = await fetch(`${DIRECTUS_URL}/items/events?${params}`, {
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
    // First get all approved events
    const events = await getEvents();
    
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
    // First get all approved events
    const events = await getEvents();
    
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
  // For now, return hardcoded URLs for the Nextcloud calendar and local iCal download
  return {
    nextcloud: "https://cloud.buerofalk.de/remote.php/dav/public-calendars/AnaLz2YHKjM6EF7k?export",
    ical: "/calendar.ics"
  };
}