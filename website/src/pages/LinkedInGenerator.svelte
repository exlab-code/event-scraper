<script>
  import { onMount } from 'svelte';
  import { writable } from 'svelte/store';
  import { getAllEvents } from '../services/directApi';

  // Debug variables to show date ranges
  let nextWeekStart = '';
  let nextWeekEnd = '';
  let loadingStatus = '';
  let eventsCount = 0;
  
  // Store for all events without filtering
  let allEvents = [];
  // Store for filtered events for next week
  let nextWeekEvents = [];
  // Store for the generated post text
  const postText = writable('');
  // Loading state
  let isLoading = true;
  // Error state
  let hasError = false;
  let errorMessage = '';

  // Set filter to upcoming on mount and load all events directly
  onMount(async () => {
    try {
      // Calculate next week date range for debugging and filtering
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const dayOfWeek = today.getDay();
      const diff = dayOfWeek === 0 ? 1 : 8 - dayOfWeek; // Adjust for Sunday
      const startOfNextWeek = new Date(today);
      startOfNextWeek.setDate(today.getDate() + diff);
      const endOfNextWeek = new Date(startOfNextWeek);
      endOfNextWeek.setDate(startOfNextWeek.getDate() + 6);
      
      nextWeekStart = startOfNextWeek.toLocaleDateString('de-DE');
      nextWeekEnd = endOfNextWeek.toLocaleDateString('de-DE');
      
      loadingStatus = 'Lade Veranstaltungen...';
      isLoading = true;
      
      // Load all approved events directly from API
      allEvents = await getAllEvents();
      console.log('Alle geladenen Veranstaltungen:', allEvents);
      
      // Filter events for next week manually
      nextWeekEvents = allEvents.filter(event => {
        if (!event.start_date) return false;
        
        const eventDate = new Date(event.start_date);
        return eventDate >= startOfNextWeek && eventDate <= endOfNextWeek;
      });
      
      eventsCount = nextWeekEvents.length;
      console.log('Veranstaltungen für nächste Woche:', nextWeekEvents);
      
      loadingStatus = 'Veranstaltungen geladen';
      isLoading = false;
      
      // Generate post text with the filtered events
      generatePostText();
    } catch (error) {
      loadingStatus = `Fehler beim Laden: ${error.message}`;
      errorMessage = error.message;
      hasError = true;
      isLoading = false;
      console.error('Fehler beim Laden der Daten:', error);
    }
  });

  // Helper: format date as "Montag, 03.04.2025"
  function formatDateLong(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const options = { weekday: 'long', day: '2-digit', month: '2-digit', year: 'numeric' };
    return date.toLocaleDateString('de-DE', options);
  }

  // Helper: format time as "HH:mm"
  function formatTime(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    return date.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }

  // Emoji for weekdays
  const weekdayEmojis = {
    Montag: '🔵',
    Dienstag: '🟢',
    Mittwoch: '🟠',
    Donnerstag: '🟣',
    Freitag: '🟡',
    Samstag: '⚫',
    Sonntag: '🔴'
  };

  // Group events by weekday
  function groupEventsByWeekday(events) {
    const groups = {};
    for (const event of events) {
      if (!event.start_date) continue;
      const date = new Date(event.start_date);
      const weekday = date.toLocaleDateString('de-DE', { weekday: 'long' });
      if (!groups[weekday]) groups[weekday] = [];
      groups[weekday].push(event);
    }
    // Sort events within each weekday by start time
    for (const day in groups) {
      groups[day].sort((a, b) => new Date(a.start_date) - new Date(b.start_date));
    }
    return groups;
  }

  // Generate the LinkedIn post text
  function generatePostText() {
    if (!nextWeekEvents || nextWeekEvents.length === 0) {
      postText.set('Keine Veranstaltungen für die nächste Woche gefunden.');
      return;
    }

    // Determine date range for title
    const startDates = nextWeekEvents.map(e => new Date(e.start_date));
    const minDate = new Date(Math.min(...startDates));
    const maxDate = new Date(Math.max(...startDates));
    const dateRangeStr = `${minDate.toLocaleDateString('de-DE')} - ${maxDate.toLocaleDateString('de-DE')}`;

    const groups = groupEventsByWeekday(nextWeekEvents);

    let text = `💁‍♂️ Digitalisierungs Service Post \n 📅 Kommende Veranstaltungen zur Digitalisierung im Non-Profit-Bereich\n\n`;
    // text += 'Hier sind die wichtigsten Veranstaltungen für Non-Profit-Digitalisierungsprofis in der nächsten Woche:\n\n';

    // Sort weekdays in calendar order
    const weekdayOrder = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag'];

    for (const day of weekdayOrder) {
      if (!groups[day]) continue;
      const emoji = weekdayEmojis[day] || '';
      const firstEventDate = new Date(groups[day][0].start_date);
      const dateStr = firstEventDate.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
      text += `${emoji} ${day}, ${dateStr}\n`;

      for (const event of groups[day]) {
        const timeStr = formatTime(event.start_date);
        const title = event.title || 'Kein Titel';
        const organizer = event.source || 'Unbekannter Veranstalter';
        const location = event.location ? `📍 ${event.location}` : '💻 Online';
        const link = event.website || event.register_link || '';
        const linkText = link ? `🔗 ${link}` : '🔗 Keine Anmeldelink verfügbar';
        
        // Add cost information
        let costText = '';
        if (event.cost !== undefined && event.cost !== null && event.cost !== '') {
          if (event.cost === 0 || event.cost === '0' || 
              event.cost === 'kostenlos' || event.cost === 'Kostenlos' || 
              event.cost === 'free' || event.cost === 'Free') {
            costText = '💰 Kostenlos';
          } else {
            costText = `💰 ${typeof event.cost === 'number' ? `${event.cost} €` : event.cost}`;
          }
        }

        text += `🔖 ${title}\n    🕒 ${timeStr} \n    👥 ${organizer}\n    ${location}\n    ${costText ? `${costText}\n  ` : ''}  ${linkText}\n\n`;
      }
      text += '———\n\n';
    }

    text += '🌐 Weitere Veranstaltungen findest du auf DigiKal: digikal.org\n';
    text += '#nonprofitdigital #veranstaltungen #digitalisierung\n';

    postText.set(text);
  }

  // Copy post text to clipboard
  async function copyToClipboard() {
    const text = await new Promise(resolve => {
      postText.subscribe(value => resolve(value))();
    });
    try {
      await navigator.clipboard.writeText(text);
      alert('LinkedIn-Post wurde in die Zwischenablage kopiert!');
    } catch (err) {
      alert('Fehler beim Kopieren in die Zwischenablage.');
    }
  }

  // Refresh data
  async function refreshData() {
    try {
      isLoading = true;
      loadingStatus = 'Lade Veranstaltungen...';
      hasError = false;
      
      // Load all approved events directly from API
      allEvents = await getAllEvents();
      
      // Filter events for next week manually
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const dayOfWeek = today.getDay();
      const diff = dayOfWeek === 0 ? 1 : 8 - dayOfWeek; // Adjust for Sunday
      const startOfNextWeek = new Date(today);
      startOfNextWeek.setDate(today.getDate() + diff);
      const endOfNextWeek = new Date(startOfNextWeek);
      endOfNextWeek.setDate(startOfNextWeek.getDate() + 6);
      
      nextWeekEvents = allEvents.filter(event => {
        if (!event.start_date) return false;
        
        const eventDate = new Date(event.start_date);
        return eventDate >= startOfNextWeek && eventDate <= endOfNextWeek;
      });
      
      eventsCount = nextWeekEvents.length;
      loadingStatus = 'Veranstaltungen geladen';
      isLoading = false;
      
      // Generate post text with the filtered events
      generatePostText();
    } catch (error) {
      loadingStatus = `Fehler beim Laden: ${error.message}`;
      errorMessage = error.message;
      hasError = true;
      isLoading = false;
      console.error('Fehler beim Laden der Daten:', error);
    }
  }
</script>

<div class="max-w-4xl mx-auto my-12 p-10 bg-white rounded-xl shadow-lg">
  <div class="flex justify-between items-center mb-8">
    <h1 class="text-3xl font-bold text-gray-800 pb-4 border-b-2 border-gray-100">LinkedIn-Post Generator</h1>
    <div class="bg-gray-100 px-4 py-2 rounded-lg text-sm text-gray-600">
      <span>Zeitraum: {nextWeekStart} bis {nextWeekEnd}</span>
    </div>
  </div>
  
  {#if isLoading}
    <div class="flex flex-col items-center justify-center py-12">
      <div class="w-10 h-10 border-4 border-gray-100 border-t-primary-600 rounded-full animate-spin mb-4"></div>
      <div class="text-primary-600 font-medium">{loadingStatus}</div>
    </div>
  {:else if hasError}
    <div class="bg-red-50 text-red-700 p-6 rounded-lg mb-6">
      <div class="font-semibold mb-2">Fehler beim Laden der Daten</div>
      <div>{errorMessage}</div>
      <button 
        class="mt-4 inline-flex items-center px-6 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition-colors gap-2 border border-gray-200"
        on:click={refreshData}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 2v6h-6"></path>
          <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path>
          <path d="M3 22v-6h6"></path>
          <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path>
        </svg>
        Erneut versuchen
      </button>
    </div>
  {:else}<div class="copyfield w-80 h-80 m-auto">
    <textarea 
       
      bind:value={$postText}
      class="w-full h-96 font-mono text-base p-6 border border-gray-200 rounded-lg resize-y mb-6 shadow-inner bg-gray-50 text-gray-800"
    ></textarea></div>
    
    <div class="flex gap-4 mb-6">
      <button 
        class="inline-flex items-center px-6 py-3 bg-primary-600 text-white rounded-lg font-semibold hover:bg-primary-700 transition-colors gap-2"
        on:click={copyToClipboard}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
        </svg>
        In Zwischenablage kopieren
      </button>
      
      <button 
        class="inline-flex items-center px-6 py-3 bg-gray-100 text-gray-700 rounded-lg font-semibold hover:bg-gray-200 transition-colors gap-2 border border-gray-200"
        on:click={refreshData}
      >
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 2v6h-6"></path>
          <path d="M3 12a9 9 0 0 1 15-6.7L21 8"></path>
          <path d="M3 22v-6h6"></path>
          <path d="M21 12a9 9 0 0 1-15 6.7L3 16"></path>
        </svg>
        Aktualisieren
      </button>
      
      <div class="inline-flex items-center bg-blue-50 text-blue-800 px-4 py-2 rounded-full text-sm font-medium ml-auto">
        {eventsCount} Veranstaltungen gefunden
      </div>
    </div>
  {/if}
  
  <div class="mt-8 p-6 bg-gray-100 rounded-lg text-sm text-gray-600">
    <h2 class="text-xl font-semibold mb-4 text-gray-800">Informationen</h2>
    <p class="my-2 leading-relaxed">Dieser Generator erstellt einen formatierten LinkedIn-Post mit allen genehmigten Veranstaltungen für die nächste Woche.</p>
    <p class="my-2 leading-relaxed">Die Veranstaltungen werden nach Wochentagen gruppiert und chronologisch sortiert.</p>
    <p class="my-2 leading-relaxed">Status: {loadingStatus}</p>
  </div>
</div>
