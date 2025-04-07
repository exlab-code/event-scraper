// Configuration for the Event Moderation Interface

const CONFIG = {
    // Directus API configuration
    api: {
        // Direct API access
        baseUrl: 'https://calapi.buerofalk.de',
        
        // Proxy server (only for local development)
        // baseUrl: 'http://localhost:9090',
        
        token: 'APpU898yct7V2VyMFfcJse_7WXktDY-o',
        eventsCollection: 'events',
        itemsPerPage: 10,
        debug: true,  // Enable debug mode to log API requests and responses
        useProxy: false  // Set to false to connect directly to the API
    },
    
    // Date and time formatting
    formatting: {
        dateFormat: { 
            year: 'numeric', 
            month: 'long', 
            day: 'numeric' 
        },
        timeFormat: { 
            hour: '2-digit', 
            minute: '2-digit', 
            hour12: false 
        }
    },
    
    // Category colors (for category tags)
    categoryColors: {
        'ki_nonprofit': '#3498db',
        'digitale_kommunikation': '#2ecc71',
        'foerderung_finanzierung': '#e74c3c',
        'ehrenamt_engagement': '#f39c12',
        'daten_projektmanagement': '#9b59b6',
        'weiterbildung_qualifizierung': '#1abc9c',
        'digitale_transformation': '#34495e',
        'tools_anwendungen': '#e67e22'
    },
    
    // Refresh interval for stats (in milliseconds)
    statsRefreshInterval: 60000, // 1 minute
    
    // Default filters
    defaultFilters: {
        status: 'pending',
        relevance: 'all',
        feedback: 'all'
    }
};
