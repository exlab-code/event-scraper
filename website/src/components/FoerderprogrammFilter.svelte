<script>
  import { onMount } from 'svelte';
  import { foerdermittel, filteredFoerdermittel, filters, updateFilters, resetFilters } from '../stores/foerdermittelStore';
  import Tag from './Tag.svelte';
  import Accordion from './Accordion.svelte';

  let searchQuery = '';
  let selectedTags = [];
  let selectedBundesland = '';
  let selectedFundingType = '';
  let selectedProviderType = '';
  let selectedDeadlineHorizon = 'all';
  let selectedFundingAmountRange = '';
  let selectedFoerdergeber = '';
  let selectedSource = '';
  let isFilterOpen = false;
  let tagFrequency = {};
  let groupedTags = {
    "thema": [],
    "foerderart": [],
    "zielgruppe": []
  };
  let superKategorien = [];
  let foerdergeberOptions = [];
  let sourceOptions = [];

  // Initialize tag frequency and grouped tags on mount
  onMount(() => {
    superKategorien = getSuperKategorien($foerdermittel);
    tagFrequency = calculateTagFrequency($foerdermittel);
    groupedTags = getGroupedTags($foerdermittel, superKategorien);
  });

  // Deadline horizon options
  const deadlineHorizons = [
    { value: 'all', label: 'Alle Fristen' },
    { value: 'thisMonth', label: 'Diesen Monat' },
    { value: 'next3Months', label: 'Nächste 3 Monate' },
    { value: 'next6Months', label: 'Nächste 6 Monate' },
    { value: 'ongoing', label: 'Laufende Programme' }
  ];

  // Bundesland options (using full state names to match database values)
  const bundeslandOptions = [
    { value: '', label: 'Alle Regionen' },
    { value: 'bundesweit', label: 'Bundesweit' },
    { value: 'eu_weit', label: 'EU-weit' },
    { value: 'international', label: 'International' },
    { value: 'Baden-Württemberg', label: 'Baden-Württemberg' },
    { value: 'Bayern', label: 'Bayern' },
    { value: 'Berlin', label: 'Berlin' },
    { value: 'Brandenburg', label: 'Brandenburg' },
    { value: 'Bremen', label: 'Bremen' },
    { value: 'Hamburg', label: 'Hamburg' },
    { value: 'Hessen', label: 'Hessen' },
    { value: 'Mecklenburg-Vorpommern', label: 'Mecklenburg-Vorpommern' },
    { value: 'Niedersachsen', label: 'Niedersachsen' },
    { value: 'Nordrhein-Westfalen', label: 'Nordrhein-Westfalen' },
    { value: 'Rheinland-Pfalz', label: 'Rheinland-Pfalz' },
    { value: 'Saarland', label: 'Saarland' },
    { value: 'Sachsen', label: 'Sachsen' },
    { value: 'Sachsen-Anhalt', label: 'Sachsen-Anhalt' },
    { value: 'Schleswig-Holstein', label: 'Schleswig-Holstein' },
    { value: 'Thüringen', label: 'Thüringen' }
  ];

  // Funding amount range options
  const fundingAmountRanges = [
    { value: '', label: 'Alle Beträge' },
    { value: 'small', label: 'Bis 10.000 €' },
    { value: 'medium', label: '10.000 - 50.000 €' },
    { value: 'large', label: '50.000 - 100.000 €' },
    { value: 'xlarge', label: 'Über 100.000 €' }
  ];

  // Tag group names (maps to foerdermittel tag_groups structure)
  const tagGroupNames = {
    "thema": "Thema",
    "foerderart": "Förderart",
    "zielgruppe": "Zielgruppe"
  };

  // Subscribe to the filters store to get current filter values
  filters.subscribe(f => {
    searchQuery = f.searchQuery || '';
    selectedTags = f.tags ? [...f.tags] : [];
    selectedBundesland = f.bundesland || '';
    selectedFundingType = f.fundingType || '';
    selectedProviderType = f.providerType || '';
    selectedDeadlineHorizon = f.deadlineHorizon || 'all';
    selectedFundingAmountRange = f.fundingAmountRange || '';
    selectedFoerdergeber = f.foerdergeber || '';
    selectedSource = f.source || '';
  });

  // Calculate minimum tag frequency dynamically based on result count
  function getMinTagFrequency(resultCount) {
    if (resultCount >= 100) return 5;  // Show only tags appearing 5+ times
    if (resultCount >= 50) return 3;   // Show tags appearing 3+ times
    if (resultCount >= 20) return 2;   // Show tags appearing 2+ times
    return 1;                          // Show all tags
  }

  let minTagFrequency = 1;

  // Calculate super kategorien first
  $: if ($filteredFoerdermittel && $filteredFoerdermittel.length > 0) {
    superKategorien = getSuperKategorien($filteredFoerdermittel);
  }

  // Update tag frequency and fördergeber options based on filtered results
  $: if ($filteredFoerdermittel && $filteredFoerdermittel.length > 0) {
    minTagFrequency = getMinTagFrequency($filteredFoerdermittel.length);
    tagFrequency = calculateTagFrequency($filteredFoerdermittel);
    groupedTags = getGroupedTags($filteredFoerdermittel, superKategorien);
    foerdergeberOptions = getFoerdergeberOptions($filteredFoerdermittel);
    sourceOptions = getSourceOptions($filteredFoerdermittel);
  }

  function calculateTagFrequency(programs) {
    const frequency = {};

    programs.forEach(program => {
      if (program.tag_groups) {
        const tagGroupsObj = typeof program.tag_groups === 'string'
          ? JSON.parse(program.tag_groups)
          : program.tag_groups;

        Object.values(tagGroupsObj).forEach(tags => {
          if (Array.isArray(tags)) {
            tags.forEach(tag => {
              frequency[tag] = (frequency[tag] || 0) + 1;
            });
          }
        });
      }
    });

    return frequency;
  }

  function getGroupedTags(programs, superKats) {
    const groups = {
      "thema": new Set(),
      "foerderart": new Set(),
      "zielgruppe": new Set()
    };

    // Get super kategorien to exclude them from regular tag groups
    const superKategorienSet = new Set(superKats || []);

    // Collect tags from programs
    programs.forEach(program => {
      if (program.tag_groups) {
        const tagGroupsObj = typeof program.tag_groups === 'string'
          ? JSON.parse(program.tag_groups)
          : program.tag_groups;

        Object.entries(tagGroupsObj).forEach(([groupId, tags]) => {
          if (groups[groupId] && Array.isArray(tags)) {
            tags.forEach(tag => {
              // Only add tags that meet the frequency threshold AND are not in super kategorien
              if (tagFrequency[tag] >= minTagFrequency && !superKategorienSet.has(tag)) {
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

  function getFoerdergeberOptions(programs) {
    const foerdergeber = new Set();

    programs.forEach(program => {
      if (program.tag_groups) {
        const tagGroupsObj = typeof program.tag_groups === 'string'
          ? JSON.parse(program.tag_groups)
          : program.tag_groups;

        if (tagGroupsObj.foerdergeber && Array.isArray(tagGroupsObj.foerdergeber)) {
          tagGroupsObj.foerdergeber.forEach(fg => foerdergeber.add(fg));
        }
      }
    });

    const options = [{ value: '', label: 'Alle Fördergeber' }];
    Array.from(foerdergeber).sort().forEach(fg => {
      options.push({ value: fg, label: fg });
    });

    return options;
  }

  function getSourceOptions(programs) {
    const sources = new Set();

    programs.forEach(program => {
      if (program.source) {
        sources.add(program.source);
      }
    });

    const options = [{ value: '', label: 'Alle Quellen' }];
    Array.from(sources).sort().forEach(source => {
      options.push({ value: source, label: source });
    });

    return options;
  }

  function getSuperKategorien(programs) {
    const kategorien = new Set();

    programs.forEach(program => {
      if (program.tag_groups) {
        const tagGroupsObj = typeof program.tag_groups === 'string'
          ? JSON.parse(program.tag_groups)
          : program.tag_groups;

        if (tagGroupsObj.super_kategorie && Array.isArray(tagGroupsObj.super_kategorie)) {
          tagGroupsObj.super_kategorie.forEach(sk => kategorien.add(sk));
        }
      }
    });

    return Array.from(kategorien).sort();
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

  function toggleSuperKategorie(kategorie) {
    if (selectedTags.includes(kategorie)) {
      selectedTags = selectedTags.filter(t => t !== kategorie);
    } else {
      selectedTags = [...selectedTags, kategorie];
    }
    applyFilters();
  }

  function selectDeadlineHorizon(horizon) {
    selectedDeadlineHorizon = horizon;
    applyFilters();
  }

  function selectBundesland(event) {
    selectedBundesland = event.target.value;
    applyFilters();
  }

  function selectFundingAmountRange(event) {
    selectedFundingAmountRange = event.target.value;
    applyFilters();
  }

  function selectFoerdergeber(event) {
    selectedFoerdergeber = event.target.value;
    applyFilters();
  }

  function selectSource(event) {
    selectedSource = event.target.value;
    applyFilters();
  }

  function handleSearchInput(event) {
    searchQuery = event.target.value;
    applyFilters();
  }

  function applyFilters() {
    updateFilters({
      searchQuery: searchQuery,
      tags: selectedTags,
      bundesland: selectedBundesland,
      deadlineHorizon: selectedDeadlineHorizon,
      fundingAmountRange: selectedFundingAmountRange,
      foerdergeber: selectedFoerdergeber,
      source: selectedSource
    });
  }

  function clearFilters() {
    searchQuery = '';
    selectedTags = [];
    selectedBundesland = '';
    selectedFundingType = '';
    selectedProviderType = '';
    selectedDeadlineHorizon = 'all';
    selectedFundingAmountRange = '';
    selectedFoerdergeber = '';
    selectedSource = '';
    resetFilters();
  }

  function toggleFilterPanel() {
    isFilterOpen = !isFilterOpen;
  }
</script>

<div class="bg-white rounded-lg shadow mb-6">
  <Accordion
    title="Filter"
    defaultOpen={false}
    mobileOnly={true}
    id="filter"
    on:toggle={({ detail }) => isFilterOpen = detail.isOpen}
  >
    <!-- Search Bar -->
    <div class="mb-6 pb-4 border-b border-gray-200">
      <label for="search" class="block text-sm font-medium text-gray-700 mb-2">Suche</label>
      <input
        type="text"
        id="search"
        class="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        placeholder="Suchbegriff eingeben..."
        bind:value={searchQuery}
        on:input={handleSearchInput}
      />
    </div>

    <!-- Super-Categories (always visible, not subject to frequency threshold) -->
    {#if superKategorien.length > 0}
      <div class="tag-group mb-6 pb-4 border-b border-gray-200">
        <h3 class="tag-group-title font-semibold text-base mb-3">Kategorien</h3>
        <div class="flex flex-wrap gap-1">
          {#each superKategorien as kategorie}
            <button
              class="super-kategorie-tag {selectedTags.includes(kategorie) ? 'selected' : ''}"
              on:click={() => toggleSuperKategorie(kategorie)}
            >
              {kategorie}
            </button>
          {/each}
        </div>
      </div>
    {/if}

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

    <!-- Bundesland dropdown -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Region</h3>
      <select
        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        bind:value={selectedBundesland}
        on:change={selectBundesland}
      >
        {#each bundeslandOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>

    <!-- Funding amount range dropdown -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Fördersumme</h3>
      <select
        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        bind:value={selectedFundingAmountRange}
        on:change={selectFundingAmountRange}
      >
        {#each fundingAmountRanges as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>

    <!-- Fördergeber dropdown -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Fördergeber</h3>
      <select
        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        bind:value={selectedFoerdergeber}
        on:change={selectFoerdergeber}
      >
        {#each foerdergeberOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>

    <!-- Source dropdown -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Quelle</h3>
      <select
        class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
        bind:value={selectedSource}
        on:change={selectSource}
      >
        {#each sourceOptions as option}
          <option value={option.value}>{option.label}</option>
        {/each}
      </select>
    </div>

    <!-- Deadline Horizon Selection -->
    <div class="tag-group mb-4">
      <h3 class="tag-group-title">Frist</h3>
      <div class="flex flex-wrap gap-1">
        {#each deadlineHorizons as horizon}
          <button
            class="tag {selectedDeadlineHorizon === horizon.value ? 'selected' : ''} selectable"
            on:click={() => selectDeadlineHorizon(horizon.value)}
          >
            {horizon.label}
          </button>
        {/each}
      </div>
    </div>

    <!-- Filter Actions -->
    <div class="flex gap-1 flex-wrap">
      <button
        type="button"
        class="flex justify-center items-center px-4 py-2 border border-gray-300 text-sm rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        on:click={clearFilters}
        disabled={searchQuery === '' && selectedTags.length === 0 && selectedBundesland === '' && selectedDeadlineHorizon === 'all' && selectedFundingAmountRange === '' && selectedFoerdergeber === '' && selectedSource === ''}
      >
        Zurücksetzen
      </button>
    </div>
  </Accordion>
</div>
