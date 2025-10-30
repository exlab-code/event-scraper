<script>
  import { calendarUrls } from '../stores/eventStore';
  import Accordion from './Accordion.svelte';
  import { trackEvent } from '../services/analytics';
  
  let copySuccess = false;
  let copyTimeout;
  let isSubscriptionOpen = false;
  
  function copyToClipboard(url) {
    navigator.clipboard.writeText(url)
      .then(() => {
        copySuccess = true;
        
        // Clear any existing timeout
        if (copyTimeout) clearTimeout(copyTimeout);
        
        // Reset after 3 seconds
        copyTimeout = setTimeout(() => {
          copySuccess = false;
        }, 3000);
        
        // Track calendar subscription copy event
        trackEvent('calendar_subscription_copy', { url });
      })
      .catch(err => {
        console.error('Fehler beim Kopieren in die Zwischenablage:', err);
        alert('Fehler beim Kopieren in die Zwischenablage. Bitte manuell kopieren.');
      });
  }
</script>

<div class="bg-white rounded-lg shadow">
  <Accordion 
    title="Kalender abonnieren" 
    defaultOpen={false} 
    mobileOnly={true}
    id="calendar"
    on:toggle={({ detail }) => isSubscriptionOpen = detail.isOpen}
  >
    <p class="text-gray-600 mb-4 text-sm">Füge diese Veranstaltungen zu deinem persönlichen Kalender hinzu:</p>
  
  <div class="flex flex-col gap-3">
    {#if $calendarUrls.nextcloud}
      <button 
        on:click={() => copyToClipboard($calendarUrls.nextcloud)}
        class="flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white font-medium rounded-md hover:bg-blue-700 transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
        {copySuccess ? 'URL kopiert!' : 'CalDAV URL kopieren'}
      </button>
    {/if}
    
    <!-- {#if $calendarUrls.ical}
      <a 
        href={$calendarUrls.ical} 
        download="nonprofit-events.ics"
        class="flex items-center justify-center gap-2 px-4 py-3 bg-green-600 text-white font-medium rounded-md hover:bg-green-700 transition-colors"
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M4 22h14a2 2 0 0 0 2-2V7.5L14.5 2H6a2 2 0 0 0-2 2v4"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <path d="M2 15h10"></path>
          <path d="M9 18l3-3-3-3"></path>
        </svg>
        .ics herunterladen
      </a>
    {/if} -->
  </div>
  </Accordion>
</div>
