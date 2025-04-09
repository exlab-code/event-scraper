<script>
  import { onMount } from 'svelte';
  import { categories, tags, filters, updateFilters } from '../stores/eventStore';
  import { topTags } from '../stores/eventStore';
  import { getCategoryName } from '../categoryMappings';

  let selectedCategory = '';
  let selectedTags = [];
  let onlineOnly = false;
  let selectedTimeHorizon = 'all'; // Default to 'all'
  let isFilterOpen = true; // For mobile toggle
  
  // Time horizon options
  const timeHorizons = [
    { value: 'all', label: 'Alle Termine' },
    // { value: 'upcoming', label: 'Demnächst' },
    { value: 'today', label: 'Heute' },
    { value: 'thisWeek', label: 'Diese Woche' },
    // { value: 'nextWeek', label: 'Nächste Woche' },
    { value: 'thisMonth', label: 'Diesen Monat' },
    { value: 'nextMonth', label: 'Nächsten Monat' },
    { value: 'next3Months', label: 'Nächste 3 Monate' }
  ];

  // Subscribe to the filters store to get current filter values
  filters.subscribe(f => {
    selectedCategory = f.category || '';
    selectedTags = f.tags ? [...f.tags] : [];
    onlineOnly = f.onlineOnly || false;
    selectedTimeHorizon = f.timeHorizon || 'all';
  });

  function selectCategory(cat) {
    selectedCategory = cat;
    applyFilters();
  }

  function toggleTag(tag) {
    if (selectedTags.includes(tag)) {
      selectedTags = selectedTags.filter(t => t !== tag);
    } else {
      selectedTags = [...selectedTags, tag];
    }
    applyFilters();
  }

  function toggleOnlineOnly() {
    onlineOnly = !onlineOnly;
    applyFilters();
  }

  function selectTimeHorizon(horizon) {
    selectedTimeHorizon = horizon;
    applyFilters();
  }

  function applyFilters() {
    updateFilters({
      category: selectedCategory,
      tags: selectedTags,
      onlineOnly: onlineOnly,
      timeHorizon: selectedTimeHorizon
    });
  }

  function clearFilters() {
    selectedCategory = '';
    selectedTags = [];
    onlineOnly = false;
    selectedTimeHorizon = 'all';
    applyFilters();
  }

  function toggleFilterPanel() {
    isFilterOpen = !isFilterOpen;
  }
</script>

<div class="bg-white rounded-lg shadow p-4 mb-6">
  <div class="flex justify-between items-center mb-4 pb-2">
    <h2 class="text-lg font-semibold text-gray-800">Filter</h2>
  
  </div>
  
  <div class={isFilterOpen ? 'block' : 'hidden md:block'}>
    <!-- Category filter as dropdown -->
    <div class="mb-4">
      <h3 class="text-sm font-medium text-gray-700 mb-2">Kategorie</h3>
      <div class="relative">
        <select 
          class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-primary-500 focus:border-primary-500 appearance-none bg-white"
          bind:value={selectedCategory}
          on:change={applyFilters}
        >
          <option value="">Alle Kategorien</option>
          {#each $categories as cat}
            <option value={cat}>{getCategoryName(cat)}</option>
          {/each}
        </select>
      </div>
    </div>

    <!-- Time Horizon Selection -->
    <div class="mb-4">
      <h3 class="text-sm font-medium text-gray-700 mb-2">Zeitraum</h3>
      <div class="flex flex-wrap gap-2">
        {#each timeHorizons as horizon}
          <button
            class="px-3 py-1 rounded-md text-sm border transition-colors
                   {selectedTimeHorizon === horizon.value ? 
                     'bg-primary-600 text-white border-primary-600' : 
                     'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'}"
            on:click={() => selectTimeHorizon(horizon.value)}
          >
            {horizon.label}
          </button>
        {/each}
      </div>
    </div>

    <!-- Online Only Filter -->
    <div class="mb-4">
      <label class="inline-flex items-center cursor-pointer">
        <input 
          type="checkbox" 
          class="form-checkbox h-4 w-4 text-primary-600 rounded" 
          bind:checked={onlineOnly}
          on:change={applyFilters}
        />
        <span class="ml-2 text-sm text-gray-700">Nur Online-Veranstaltungen</span>
      </label>
    </div>

    <!-- Tags Filter as pills -->
    {#if $topTags.length > 0}
  <div class="mb-4">
    <h3 class="text-sm font-medium text-gray-700 mb-2">Tags</h3>
    <div class="flex flex-wrap gap-2">
      {#each $topTags as tag}
        <button
          class="px-3 py-1 rounded-full text-sm border transition-colors
                {selectedTags.includes(tag) ? 'bg-primary-600 text-white' : 'bg-white text-gray-800 border-gray-300 hover:bg-gray-50'}"
          on:click={() => toggleTag(tag)}
        >{tag}</button>
      {/each}
    </div>
  </div>
{/if}

    <!-- Filter Actions -->
    <div class="flex gap-2 flex-wrap">
      <button 
        type="button" 
        class="flex justify-center items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        on:click={applyFilters}
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M3 3a1 1 0 011-1h12a1 1 0 011 1v3a1 1 0 01-.293.707L12 11.414V15a1 1 0 01-.293.707l-2 2A1 1 0 018 17v-5.586L3.293 6.707A1 1 0 013 6V3z" clip-rule="evenodd" />
        </svg>
        Filter anwenden
      </button>
      <button 
        type="button" 
        class="flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        on:click={clearFilters}
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg>
          Zurücksetzen
      </button>
    </div>
  </div>
</div>
