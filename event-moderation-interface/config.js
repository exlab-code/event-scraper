// Configuration for the Event Moderation Interface
// This file should not contain sensitive information directly
// Values are loaded from config-secrets.js which is not tracked in git

// Default configuration (will be overridden by config-secrets.js if available)
const CONFIG = {
    // Directus API configuration
    api: {
        // Direct API access
        baseUrl: 'https://your-directus-api-url',
        
        // Proxy server (only for local development)
        // baseUrl: 'http://localhost:9090',
        
        token: 'your-api-token-here',
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
        'datenschutz_sicherheit': '#8e44ad', // Purple for security
        'ki_nonprofit': '#3498db',
        'digitale_kommunikation': '#2ecc71',
        'foerderung_finanzierung': '#e74c3c',
        'ehrenamt_engagement': '#f39c12',
        'daten_projektmanagement': '#9b59b6',
        'weiterbildung_qualifizierung': '#1abc9c',
        'digitale_transformation': '#34495e',
        'tools_anwendungen': '#e67e22'
    },
    
    // Category mappings (from ID to human-readable name)
    categoryMappings: {
        'datenschutz_sicherheit': 'Datenschutz & Sicherheit',
        'ki_nonprofit': 'KI für Non-Profits',
        'digitale_kommunikation': 'Digitale Kommunikation & Social Media',
        'foerderung_finanzierung': 'Förderprogramme & Finanzierung',
        'ehrenamt_engagement': 'Ehrenamt & Engagemententwicklung',
        'daten_projektmanagement': 'Daten & Projektmanagement',
        'weiterbildung_qualifizierung': 'Weiterbildung & Qualifizierung',
        'digitale_transformation': 'Digitale Transformation & Strategie',
        'tools_anwendungen': 'Tools & Anwendungen'
    },
    
    // Refresh interval for stats (in milliseconds)
    statsRefreshInterval: 60000, // 1 minute
    
    // Default filters
    defaultFilters: {
        status: 'pending',
        relevance: 'all',
        feedback: 'all'
    },
    
    // Status badge colors
    statusColors: {
        'pending': '#f39c12',  // Orange
        'approved': '#2ecc71', // Green
        'rejected': '#e74c3c', // Red
        'excluded': '#95a5a6'  // Gray
    }
};
