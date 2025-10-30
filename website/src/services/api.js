// Directus API configuration
const DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o";

// Use direct Directus API URL for GitHub Pages deployment
const DIRECTUS_URL = "https://calapi.buerofalk.de";
const API_BASE_URL = `${DIRECTUS_URL}`;
const ITEMS_BASE_URL = `${DIRECTUS_URL}/items`;

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
      sort: "start_date",
      limit: "-1"  // Get all events (no limit)
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
      sort: "start_date",
      limit: "-1"  // Get all events (no limit)
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
      sort: "start_date",
      limit: "-1"  // Get all events (no limit)
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

/**
 * Fetch all relevant Förderprogramme from Directus
 * @param {Object} filters - Optional filters
 * @returns {Promise<Array>} - Array of foerdermittel objects
 */
export async function getFoerderprogramme(filters = {}) {
  try {
    // Prepare the filter object for Directus
    // For now, show all programs (draft and published) since relevance scoring hasn't been applied yet
    // TODO: Once relevance_score is populated, filter by: relevance_score >= 60 AND status = published
    let filterObj = {
      _or: [
        {
          // Show published programs with good relevance scores
          _and: [
            {
              relevance_score: {
                _gte: 60
              }
            },
            {
              status: {
                _eq: "published"
              }
            }
          ]
        },
        {
          // Also show draft programs (for development)
          status: {
            _eq: "draft"
          }
        }
      ]
    };

    // Build query parameters
    const params = new URLSearchParams({
      filter: JSON.stringify(filterObj),
      sort: "-application_deadline",  // Sort by deadline descending (upcoming first)
      limit: "-1"  // Get all programs (no limit)
    });

    // Use the Nginx proxy endpoint for items
    const apiUrl = `${ITEMS_BASE_URL}/foerdermittel?${params}`;

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

    return data.data;
  } catch (error) {
    console.error('Error fetching förderprogramme:', error);
    throw error;
  }
}
