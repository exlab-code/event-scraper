<script>
  import { getCategoryName } from '../categoryMappings';
  import Tag from './Tag.svelte';
  import { trackEvent } from '../services/analytics';
  
  export let event;
  
  // Format date for display
  function formatDate(dateString) {
    if (!dateString) return 'TBA';
    
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('de-DE', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    }).format(date);
  }
  
  // Format short date for display (just day and month)
  function formatShortDate(dateString) {
    if (!dateString) return 'TBA';
    
    const date = new Date(dateString);
    return new Intl.DateTimeFormat('de-DE', {
      day: '2-digit',
      month: '2-digit'
    }).format(date);
  }
  
  // Truncate description if it's too long
  function truncateText(text, maxLength = 450) {
    if (!text || text.length <= maxLength) return text;
    // Try to find a sensible cutoff point at a space
    const cutoff = text.substring(0, maxLength).lastIndexOf(' ');
    return text.substring(0, cutoff > 0 ? cutoff : maxLength) + '...';
  }
  
  // Find the group ID for a tag
  function findTagGroup(tag) {
    if (!event.tag_groups) return null;
    
    for (const [groupId, tags] of Object.entries(event.tag_groups)) {
      if (tags.includes(tag)) {
        return groupId;
      }
    }
    return null;
  }
</script>

<div class="bg-white rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200 h-full overflow-hidden event-card">
  <div class="flex h-full">
    <!-- Date indicator on the left side -->
    <div class="bg-primary-600 text-white px-3 flex flex-col items-center text-center w-12 flex-shrink-0 date-indicator">
      <div class="text-2xl font-bold">{formatShortDate(event.start_date).split('.')[0]}</div>
      <div class="text-sm">{new Date(event.start_date).toLocaleString('de-DE', {month: 'short'})}</div>
      {#if event.end_date && new Date(event.start_date).toDateString() !== new Date(event.end_date).toDateString()}
        <div class="text-xs mt-1 py-1 bg-white/20 rounded-full">+ {Math.ceil((new Date(event.end_date) - new Date(event.start_date)) / (1000 * 60 * 60 * 24))} Tage</div>
      {/if}
    </div>
    
    <!-- Main content -->
    <div class="p-4 w-full flex-grow main-content">
      <h3 class="text-lg font-semibold text-gray-800 mb-2 line-clamp-2">{event.title}</h3>
      
      <!-- Event metadata -->
      <div class="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
        <!-- Time with end time -->
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
          <span>
            {new Date(event.start_date).toLocaleTimeString('de-DE', {hour: '2-digit', minute:'2-digit'})}
            {#if event.end_date || event.end_time}
              - 
              {#if event.end_date}
                {new Date(event.end_date).toLocaleTimeString('de-DE', {hour: '2-digit', minute:'2-digit'})}
              {:else if event.end_time}
                {event.end_time}
              {/if}
            {/if}
          </span>
        </div>
        
        <!-- Location or Online -->
        <div class="flex items-center gap-2">
          {#if event.location}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
              <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <span>{event.location}</span>
          {:else}
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
              <line x1="8" y1="21" x2="16" y2="21"></line>
              <line x1="12" y1="17" x2="12" y2="21"></line>
            </svg>
            <span class="text-primary-600 font-medium">Online Event</span>
          {/if}
        </div>
        
        <!-- Cost (only if available) -->
        {#if event.cost !== undefined && event.cost !== null && event.cost !== ''}
          <div class="flex items-center gap-2">
            <!-- Simple Euro symbol using text instead of SVG -->
            <span>
              {#if event.cost === 0 || event.cost === '0' || event.cost === 'kostenlos' || event.cost === 'Kostenlos' || event.cost === 'free' || event.cost === 'Free'}
                Kostenlos
              {:else}
                {typeof event.cost === 'number' ? `${event.cost} €` : event.cost}
              {/if}
            </span>
          </div>
        {/if}
        
        <!-- Organizer -->
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
            <circle cx="12" cy="7" r="4"></circle>
          </svg>
          <span>{event.organizer || 'Unknown organizer'}</span>
        </div>
      </div>
      
      <!-- Description -->
      {#if event.description}
        <p class="text-sm text-gray-700 mb-3 line-clamp-2">{truncateText(event.description)}</p>
      {/if}
      
      <!-- Tags -->
      <div class="flex flex-wrap gap-2">
        {#if event.tags && event.tags.length > 0}
          {#each event.tags.slice(0, 5) as tag}
            <Tag {tag} groupId={findTagGroup(tag)} />
          {/each}
          {#if event.tags.length > 5}
            <span class="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-full">+{event.tags.length - 5} more</span>
          {/if}
        {/if}
        
        {#if event.category && (!event.tags || !event.tags.length)}
          <Tag tag={getCategoryName(event.category)} groupId="topic" />
        {/if}
      </div>
    </div>
    
    <!-- Right action bar -->
    <div class="border-l border-gray-100 px-4 py-4 flex flex-col justify-end text-sm w-32 action-bar">
      <!-- Download ICS button -->
      <button 
        class="w-full py-1 transition-colors hover:bg-gray-50 text-primary-600 flex items-center gap-2 mb-1"
        on:click={() => {
          // Track ICS download event
          trackEvent('ics_download', { 
            event_id: event.id,
            event_title: event.title,
            organizer: event.organizer
          });
          
          // Create ICS content
          const startDate = new Date(event.start_date);
          const endDate = event.end_date ? new Date(event.end_date) : new Date(startDate.getTime() + 60*60*1000); // Default 1 hour
          
          const formatICSDate = (date) => {
            return date.toISOString().replace(/-|:|\.\d+/g, '').slice(0, 15) + 'Z';
          };
          
          const icsContent = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//Nonprofit Events//DE',
            'CALSCALE:GREGORIAN',
            'METHOD:PUBLISH',
            'BEGIN:VEVENT',
            `UID:${event.id}@nonprofitevents`,
            `DTSTAMP:${formatICSDate(new Date())}`,
            `DTSTART:${formatICSDate(startDate)}`,
            `DTEND:${formatICSDate(endDate)}`,
            `SUMMARY:${event.title}`,
            `DESCRIPTION:${event.description ? event.description.replace(/\n/g, '\\n') : ''}`,
            `LOCATION:${event.location || 'Online'}`,
            `URL:${event.website || event.register_link || ''}`,
            'END:VEVENT',
            'END:VCALENDAR'
          ].join('\r\n');
          
          // Create and trigger download
          const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
          const url = URL.createObjectURL(blob);
          const link = document.createElement('a');
          link.href = url;
          link.download = `event-${event.id}.ics`;
          document.body.appendChild(link);
          link.click();
          document.body.removeChild(link);
        }}
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
        .ics
      </button>
      
      <!-- Website or Registration link -->
      {#if event.website || event.register_link}
        <div>
          {#if event.website}
            <a href={event.website} target="_blank" rel="noopener noreferrer" class="w-full py-1 transition-colors hover:bg-gray-50 text-primary-600 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="2" y1="12" x2="22" y2="12"></line>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
              </svg>
              Website
            </a>
          {:else if event.register_link}
            <a href={event.register_link} target="_blank" rel="noopener noreferrer" class="w-full py-1 transition-colors hover:bg-gray-50 text-primary-600 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="8.5" cy="7" r="4"></circle>
                <line x1="20" y1="8" x2="20" y2="14"></line>
                <line x1="23" y1="11" x2="17" y2="11"></line>
              </svg>
              Anmeldung
            </a>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
