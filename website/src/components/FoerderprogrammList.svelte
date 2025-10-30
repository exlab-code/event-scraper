<script>
  import { filteredFoerdermittel, isLoading, error, filters } from '../stores/foerdermittelStore';
  import FoerderprogrammCard from './FoerderprogrammCard.svelte';

  let filterDescription = '';

  // Update filter description when filters change
  $: {
    const parts = [];
    if ($filters.bundesland) parts.push(`Region "${getBundeslandDisplay($filters.bundesland)}"`);
    if ($filters.fundingType) parts.push(`Förderart "${getFundingTypeDisplay($filters.fundingType)}"`);
    if ($filters.providerType) parts.push(`Fördergeber "${getProviderTypeDisplay($filters.providerType)}"`);
    if ($filters.tags && $filters.tags.length > 0) parts.push(`${$filters.tags.length} Tag${$filters.tags.length > 1 ? 's' : ''}`);

    if (parts.length > 0) {
      filterDescription = `Gefiltert nach ${parts.join(', ')}`;
    } else {
      filterDescription = '';
    }
  }

  function getBundeslandDisplay(code) {
    const bundeslandMap = {
      'bundesweit': 'Bundesweit',
      'eu_weit': 'EU-weit',
      'international': 'International',
      'bw': 'Baden-Württemberg',
      'by': 'Bayern',
      'be': 'Berlin',
      'bb': 'Brandenburg',
      'hb': 'Bremen',
      'hh': 'Hamburg',
      'he': 'Hessen',
      'mv': 'Mecklenburg-Vorpommern',
      'ni': 'Niedersachsen',
      'nw': 'Nordrhein-Westfalen',
      'rp': 'Rheinland-Pfalz',
      'sl': 'Saarland',
      'sn': 'Sachsen',
      'st': 'Sachsen-Anhalt',
      'sh': 'Schleswig-Holstein',
      'th': 'Thüringen'
    };
    return bundeslandMap[code] || code;
  }

  function getFundingTypeDisplay(type) {
    const typeMap = {
      'zuschuss': 'Zuschuss',
      'kredit': 'Kredit',
      'buergschaft': 'Bürgschaft',
      'preis': 'Preis',
      'sonstige': 'Sonstige'
    };
    return typeMap[type] || type;
  }

  function getProviderTypeDisplay(type) {
    const providerMap = {
      'bund': 'Bund',
      'land': 'Land',
      'eu': 'EU',
      'stiftung': 'Stiftung',
      'sonstige': 'Sonstige'
    };
    return providerMap[type] || type;
  }
</script>

<div>
  {#if $isLoading}
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <div class="w-10 h-10 border-4 border-gray-200 border-t-primary-600 rounded-full animate-spin mb-4"></div>
      <p class="text-gray-600">Förderprogramme werden geladen...</p>
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
  {:else if $filteredFoerdermittel.length === 0}
    <div class="flex flex-col items-center justify-center py-12 text-center">
      <svg xmlns="http://www.w3.org/2000/svg" class="w-12 h-12 text-gray-300 mb-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"></circle>
        <line x1="8" y1="12" x2="16" y2="12"></line>
      </svg>
      <h3 class="text-xl font-semibold text-gray-800 mb-2">Keine Förderprogramme gefunden</h3>
      {#if filterDescription}
        <p class="text-gray-600">Keine Förderprogramme passen zu deinen Filtern.<br>Probiere andere Filter aus.</p>
      {:else}
        <p class="text-gray-600">Momentan sind keine relevanten Förderprogramme verfügbar.<br>Schau bald wieder vorbei.</p>
      {/if}
    </div>
  {:else}
    <div class="mb-6 space-y-2">
      <h2 class="text-2xl font-bold py-3 text-gray-800">Relevante Förderprogramme</h2>
      {#if filterDescription}
        <div class="inline-block bg-blue-50 px-3 py-1 rounded-full text-sm text-blue-800">
          {filterDescription}
        </div>
      {/if}
      <p class="text-gray-500 text-sm">{$filteredFoerdermittel.length} Förderprogramme gefunden</p>
    </div>

    <div class="space-y-6">
      {#each $filteredFoerdermittel as program (program.id)}
        <FoerderprogrammCard {program} />
      {/each}
    </div>
  {/if}
</div>
