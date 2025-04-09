import { writable, derived } from 'svelte/store';
import * as api from '../services/api';

// Create writable stores
export const events = writable([]);
export const categories = writable([]);
export const tags = writable([]);
export const calendarUrls = writable({ nextcloud: '', ical: '' });
export const filters = writable({ 
  category: '',
  tags: [],
  onlineOnly: false,
  timeHorizon: 'all'
});
export const isLoading = writable(false);
export const error = writable(null);

// Helper function to get date ranges based on time horizon
function getDateRangeFromTimeHorizon(timeHorizon) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  
  switch(timeHorizon) {
    case 'today':
      return {
        start: today,
        end: new Date(today.getTime() + 24 * 60 * 60 * 1000) // end of today
      };
      
    case 'thisWeek': {
      // Start of week (Monday)
      const dayOfWeek = today.getDay();
      const startOfWeek = new Date(today);
      const diff = dayOfWeek === 0 ? 6 : dayOfWeek - 1; // Adjust for Sunday
      startOfWeek.setDate(today.getDate() - diff);
      
      // End of week (Sunday)
      const endOfWeek = new Date(startOfWeek);
      endOfWeek.setDate(startOfWeek.getDate() + 6);
      
      return { start: startOfWeek, end: endOfWeek };
    }
    
    case 'nextWeek': {
      // Start of next week (next Monday)
      const dayOfWeek = today.getDay();
      const startOfNextWeek = new Date(today);
      const diff = dayOfWeek === 0 ? 1 : 8 - dayOfWeek; // Adjust for Sunday
      startOfNextWeek.setDate(today.getDate() + diff);
      
      // End of next week (next Sunday)
      const endOfNextWeek = new Date(startOfNextWeek);
      endOfNextWeek.setDate(startOfNextWeek.getDate() + 6);
      
      return { start: startOfNextWeek, end: endOfNextWeek };
    }
    
    case 'thisMonth': {
      // Start of month
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      
      // End of month
      const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      
      return { start: startOfMonth, end: endOfMonth };
    }
    
    case 'nextMonth': {
      // Start of next month
      const startOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 1, 1);
      
      // End of next month
      const endOfNextMonth = new Date(today.getFullYear(), today.getMonth() + 2, 0);
      
      return { start: startOfNextMonth, end: endOfNextMonth };
    }
    
    case 'next3Months': {
      // Start of today
      
      // End of 3 months from today
      const endOf3Months = new Date(today);
      endOf3Months.setMonth(today.getMonth() + 3);
      
      return { start: today, end: endOf3Months };
    }
    
    case 'upcoming': {
      // Next 7 days
      const endDate = new Date(today);
      endDate.setDate(today.getDate() + 7);
      
      return { start: today, end: endDate };
    }
    
    case 'all':
    default:
      // No date filtering
      return { start: null, end: null };
  }
}

// Derived store for filtered events
export const filteredEvents = derived(
  [events, filters],
  ([$events, $filters]) => {
    return $events.filter(event => {
      // Skip events without a start date
      if (!event.start_date) return false;
      const now = new Date();
      const eventDate = new Date(event.start_date);
      if (eventDate < now) return false;
      
      // Filter by category if specified
      if ($filters.category && event.category !== $filters.category) {
        return false;
      }
      
      // Filter by tags if any are selected
      if ($filters.tags && $filters.tags.length > 0) {
        // If event has no tags or none of the selected tags match
        if (!event.tags || !event.tags.some(tag => $filters.tags.includes(tag))) {
          return false;
        }
      }
      
      // Filter by online only if specified
      if ($filters.onlineOnly) {
        // Check if event is online based on location field
        // If location is empty or contains keywords indicating online, consider it online
        const isOnline = !event.location || 
                        event.location.toLowerCase().includes('online') ||
                        event.location.toLowerCase().includes('virtuell') ||
                        event.location.toLowerCase().includes('webinar') ||
                        event.location.toLowerCase().includes('zoom') ||
                        event.location.toLowerCase().includes('teams');
                        
        if (!isOnline) {
          return false;
        }
      }
      
      // Filter by time horizon
      if ($filters.timeHorizon && $filters.timeHorizon !== 'all') {
        try {
          const dateRange = getDateRangeFromTimeHorizon($filters.timeHorizon);
          if (dateRange.start || dateRange.end) {
            const eventDate = new Date(event.start_date);
            
            // Filter out events before the start date
            if (dateRange.start && eventDate < dateRange.start) {
              return false;
            }
            
            // Filter out events after the end date
            if (dateRange.end && eventDate > dateRange.end) {
              return false;
            }
          }
        } catch (err) {
          console.error('Fehler beim Filtern nach Zeitraum:', err, event.start_date);
          // If we can't parse the date, include the event to be safe
        }
      }
      
      return true;
    });
  }
);

// Load all events
export async function loadEvents() {
  isLoading.set(true);
  error.set(null);
  
  try {
    // Only pass the category to the API since it supports this filter
    // Other filters will be applied client-side
    const currentFilters = {};
    filters.subscribe(value => {
      if (value.category) currentFilters.category = value.category;
    })();
    
    const eventData = await api.getEvents(currentFilters);
    events.set(eventData);
  } catch (err) {
    console.error('Fehler beim Laden der Veranstaltungen:', err);
    error.set('Fehler beim Laden der Veranstaltungen. Bitte versuchen Sie es später erneut.');
  } finally {
    isLoading.set(false);
  }
}

// Load all categories
export async function loadCategories() {
  try {
    const categoryData = await api.getCategories();
    categories.set(categoryData);
  } catch (err) {
    console.error('Fehler beim Laden der Kategorien:', err);
  }
}

// Load all tags
export async function loadTags() {
  try {
    const tagData = await api.getTags();
    tags.set(tagData);
  } catch (err) {
    console.error('Fehler beim Laden der Tags:', err);
  }
}

// Load calendar URLs
export async function loadCalendarUrls() {
  try {
    const urlData = await api.getCalendarUrls();
    calendarUrls.set(urlData);
  } catch (err) {
    console.error('Fehler beim Laden der Kalender-URLs:', err);
  }
}

// Update filters and reload events
export function updateFilters(newFilters) {
  filters.update(f => ({ ...f, ...newFilters }));
  loadEvents();
}

// Initialize all data
export async function initializeData() {
  await Promise.all([
    loadEvents(),
    loadCategories(),
    loadTags(),
    loadCalendarUrls()
  ]);
}

export const topTags = derived(events, $events => {
  const tagCounts = {};

  for (const event of $events) {
    if (event.tags && Array.isArray(event.tags)) {
      for (const tag of event.tags) {
        tagCounts[tag] = (tagCounts[tag] || 0) + 1;
      }
    }
  }

  return Object.entries(tagCounts)
    .sort((a, b) => b[1] - a[1])     // sort by count desc
    .slice(0, 9)                     // top 9
    .map(([tag]) => tag);           // return just tag names
});
