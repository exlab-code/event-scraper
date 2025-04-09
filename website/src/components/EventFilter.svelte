<script>
  import { onMount } from 'svelte';
  import { events, categories, tags, filters, updateFilters } from '../stores/eventStore';
  import { topTags } from '../stores/eventStore';
  import { getCategoryName } from '../categoryMappings';
  import Tag from './Tag.svelte';

  let selectedTags = [];
  let onlineOnly = false;
  let selectedTimeHorizon = 'all'; // Default to 'all'
  let isFilterOpen = true; // For mobile toggle
  let tagFrequency = {};
  let groupedTags = {
    "topic": [],
    "format": [],
    "audience": [],
    "cost": []
  };
  
  // Initialize tag frequency and grouped tags on mount
  onMount(() => {
    calculateTagFrequency($events);
    groupedTags = getGroupedTags($events);
  });
  
  // Time horizon options
  const timeHorizons = [
    { value: 'all', label: 'Alle Termine' },
    { value: 'today', label: 'Heute' },
    { value: 'thisWeek', label: 'Diese Woche' },
    { value: 'thisMonth', label: 'Diesen Monat' },
    { value: 'nextMonth', label: 'Nächsten Monat' },
    { value: 'next3Months', label: 'Nächste 3 Monate' }
  ];

  // Tag group names
  const tagGroupNames = {
    "topic": "Thema",
    "format": "Format",
    "audience": "Zielgruppe",
    "cost": "Kosten"
  };

  // Subscribe to the filters store to get current filter values
  filters.subscribe(f => {
    selectedTags = f.tags ? [...f.tags] : [];
    onlineOnly = f.onlineOnly || false;
    selectedTimeHorizon = f.timeHorizon || 'all';
  });

  // Set minimum tag frequency
  const minTagFrequency = 3; // Only show tags that appear in at least 3 events
  
  // Update tag frequency and grouped tags when events change
  $: if ($events && $events.length > 0) {
    tagFrequency = calculateTagFrequency($events);
    groupedTags = getGroupedTags($events);
  }
  
  function calculateTagFrequency(events) {
    const frequency = {};
    
    events.forEach(event => {
      if (event.tags && Array.isArray(event.tags)) {
        event.tags.forEach(tag => {
          frequency[tag] = (frequency[tag] || 0) + 1;
        });
      }
    });
    
    return frequency;
  }
  
  function getGroupedTags(events) {
    const groups = {
      "topic": new Set(),
      "format": new Set(),
      "audience": new Set(),
      "cost": new Set()
    };
    
    // Collect tags from events
    events.forEach(event => {
      if (event.tag_groups) {
        Object.entries(event.tag_groups).forEach(([groupId, tags]) => {
          if (groups[groupId]) {
            tags.forEach(tag => {
              // Only add tags that meet the frequency threshold
              if (tagFrequency[tag] >= minTagFrequency) {
                groups[groupId].add(tag);
              }
            });
          }
        });
      }
    });
    
    // Convert Sets to sorted Arrays
    Object.keys(groups).forEach(groupId => {
      groups[groupId] = Array.from(groups[groupId]).sort();
    });
    
    return groups;
  }

  // Find the group ID for a tag
  function findTagGroup(tag) {
    for (const [groupId, tags] of Object.entries(groupedTags)) {
      if (tags.includes(tag)) {
        return groupId;
      }
    }
    return null;
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
      tags: selectedTags,
      onlineOnly: onlineOnly,
      timeHorizon: selectedTimeHorizon
    });
  }

  function clearFilters() {
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
    <!-- Tag filters by group -->
    {#each Object.entries(groupedTags) as [groupId, tags]}
      {#if tags.length > 0}
        <div class="tag-group mb-4">
          <h3 class="tag-group-title">{tagGroupNames[groupId] || groupId}</h3>
          <div class="flex flex-wrap gap-1">
            {#each tags as tag}
              <Tag 
                {tag} 
                {groupId}
                selectable={true}
                selected={selectedTags.includes(tag)}
                count={tagFrequency[tag]}
                onClick={() => toggleTag(tag)}
              />
            {/each}
          </div>
        </div>
      {/if}
    {/each}
    
    <!-- {#if selectedTags.length > 0}
      <div class="mt-2 mb-4 text-sm text-gray-500">
        Zeige Events mit ALLEN ausgewählten Tags (AND-Logik)
      </div>
    {/if} -->

    <!-- Time Horizon Selection -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Zeitraum</h3>
      <div class="flex flex-wrap gap-1">
        {#each timeHorizons as horizon}
          <button
            class="tag {selectedTimeHorizon === horizon.value ? 'selected' : ''} selectable"
            on:click={() => selectTimeHorizon(horizon.value)}
          >
            {horizon.label}
          </button>
        {/each}
      </div>
    </div>

    <!-- Online Only Filter -->
    <!-- <div class="mb-4">
      <label class="inline-flex items-center cursor-pointer">
        <input 
          type="checkbox" 
          class="form-checkbox h-4 w-4 text-primary-600 rounded" 
          bind:checked={onlineOnly}
          on:change={applyFilters}
        />
        <span class="ml-2 text-sm text-gray-700">Nur Online-Veranstaltungen</span>
      </label>
    </div> -->

    <!-- Filter Actions -->
    <div class="flex gap-1 flex-wrap">
      <button 
        type="button" 
        class="flex justify-center items-center px-4 py-2 border border-gray-300 text-sm rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        on:click={clearFilters}
        disabled={selectedTags.length === 0 && !onlineOnly && selectedTimeHorizon === 'all'}
      >
        <!-- <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 mr-1" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd" />
        </svg> -->
          Zurücksetzen
      </button>
    </div>
  </div>
</div>
