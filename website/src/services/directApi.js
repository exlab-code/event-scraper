// Directus API configuration
const DIRECTUS_TOKEN = "APpU898yct7V2VyMFfcJse_7WXktDY-o";

// Use direct Directus API URL for GitHub Pages deployment
const DIRECTUS_URL = "https://calapi.buerofalk.de";
const API_BASE_URL = `${DIRECTUS_URL}`;
const ITEMS_BASE_URL = `${DIRECTUS_URL}/items`;

/**
 * Fetch all approved events from Directus
 * This is specifically for the LinkedIn generator
 * @returns {Promise<Array>} - Array of approved event objects
 */
export async function getAllEvents() {
  try {
    // Build query parameters - only approved events
    const params = new URLSearchParams({
      filter: JSON.stringify({ approved: { _eq: true } }),
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
    return data.data;
  } catch (error) {
    console.error('Error fetching all events:', error);
    throw error;
  }
}
