<script>
  import { getCategoryName } from '../categoryMappings';
  
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
</script>

<div class="bg-white rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200 h-full flex flex-col overflow-hidden">
  <!-- Date indicator on the left side -->
  <div class="flex w-full">
    <div class="bg-primary-600 text-white px-3 flex flex-col items-center justify-center text-center w-12 flex-shrink-0">
      <div class="text-2xl font-bold">{formatShortDate(event.start_date).split('.')[0]}</div>
      <div class="text-sm">{new Date(event.start_date).toLocaleString('de-DE', {month: 'short'})}</div>
      {#if event.end_date && new Date(event.start_date).toDateString() !== new Date(event.end_date).toDateString()}
        <div class="text-xs mt-1 px-2 py-1 bg-white/20 rounded-full">+ {Math.ceil((new Date(event.end_date) - new Date(event.start_date)) / (1000 * 60 * 60 * 24))} days</div>
      {/if}
    </div>
    
    <!-- Main content -->
    <div class="p-4 w-full">
      <h3 class="text-lg font-semibold text-gray-800 mb-2 line-clamp-2">{event.title}</h3>
      
      <!-- Event metadata -->
      <div class="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
        <!-- Time -->
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
          <span>{new Date(event.start_date).toLocaleTimeString('de-DE', {hour: '2-digit', minute:'2-digit'})}</span>
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
        <p class="text-gray-700 mb-3 line-clamp-2">{truncateText(event.description)}</p>
      {/if}
      
      <!-- Tags & Categories -->
      <div class="flex flex-wrap gap-2">
        {#if event.category}
          <span class="px-2 py-1 bg-primary-100 text-primary-700 text-xs font-medium rounded-full">{getCategoryName(event.category)}</span>
        {/if}
        
        {#if event.tags && event.tags.length > 0}
          {#each event.tags.slice(0, 3) as tag}
            <span class="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">{tag}</span>
          {/each}
          {#if event.tags.length > 3}
            <span class="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-full">+{event.tags.length - 3} more</span>
          {/if}
        {/if}
      </div>

     

    </div>
       <!-- Action bar -->
  <div class="mt-auto px-3 pb-3">
    <div class="flex justify-end px-3">
      {#if event.website}
        <a href={event.website} target="_blank" rel="noopener noreferrer" class="flex-1 py-3 text-center transition-colors hover:bg-gray-50 text-primary-600">
          <span class="flex items-center justify-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="2" y1="12" x2="22" y2="12"></line>
              <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
            </svg>
            Website
          </span>
        </a>
      {:else if event.register_link}
        <a href={event.register_link} target="_blank" rel="noopener noreferrer" class="flex-1 py-3 text-center transition-colors hover:bg-gray-50 text-primary-600">
          <span class="flex items-center justify-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
              <circle cx="8.5" cy="7" r="4"></circle>
              <line x1="20" y1="8" x2="20" y2="14"></line>
              <line x1="23" y1="11" x2="17" y2="11"></line>
            </svg>
            Anmeldung
          </span>
        </a>
      {/if}
    
   
    </div>
  </div>
  </div>
  

</div>
