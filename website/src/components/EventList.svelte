<script>
  import { onMount } from 'svelte';
  import { filteredEvents, isLoading, error, filters } from '../stores/eventStore';
  import EventCard from './EventCard.svelte';
  import { getCategoryName } from '../categoryMappings';

  let filterDescription = '';

  // Update filter description when filters change
  $: {
    const parts = [];
    if ($filters.category) parts.push(`Kategorie "${getCategoryName($filters.category)}"`);
    if ($filters.tag) parts.push(`Tag "${$filters.tag}"`);

    if (parts.length > 0) {
      filterDescription = `Gefiltert nach ${parts.join(' und ')}`;
    } else {
      filterDescription = '';
    }
  }
</script>

<div>
  {#if $isLoading}
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <div class="w-10 h-10 border-4 border-gray-200 border-t-primary-600 rounded-full animate-spin mb-4"></div>
      <p class="text-gray-600">⏳ Veranstaltungen werden geladen...</p>
    </div>
  {:else if $error}
    <div class="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md flex items-center gap-3">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-6 h-6 flex-shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="12" y1="8" x2="12" y2="12"></line>
        <line x1="12" y1="16" x2="12.01" y2="16"></line>
      </svg>
      <p>Fehler: {$error}</p>
    </div>
  {:else if $filteredEvents.length === 0}
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-gray-300 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="8" y1="12" x2="16" y2="12"></line>
      </svg>
      <h3 class="text-xl font-semibold text-gray-800 mb-2">🚫 Keine Veranstaltungen gefunden</h3>
      {#if filterDescription}
        <p class="text-gray-600">Keine Veranstaltungen passen zu deinen Filtern.<br>Probiere andere Filter aus.</p>
      {:else}
        <p class="text-gray-600">Momentan sind keine Veranstaltungen geplant.<br>Schau bald wieder vorbei 👀</p>
      {/if}
    </div>
  {:else}
    <div class="mb-6 space-y-2">
      <h2 class="text-2xl font-bold py-3 text-gray-800">📆 Bevorstehende Veranstaltungen</h2>
      {#if filterDescription}
        <div class="inline-block bg-blue-50 px-3 py-1 rounded-full text-sm text-blue-800">
          🔍 {filterDescription}
        </div>
      {/if}
      <p class="text-gray-500 text-sm">{$filteredEvents.length} Veranstaltungen gefunden</p>
    </div>

    <div class="space-y-6">
      {#each $filteredEvents as event (event.id)}
        <EventCard {event} />
      {/each}
    </div>
  {/if}
</div>
