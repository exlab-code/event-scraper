import { writable, derived } from 'svelte/store';
import * as api from '../services/api';

// Create writable stores
export const foerdermittel = writable([]);
export const filters = writable({
  tags: [], // Tags from tag_groups (thema, zielgruppe, etc.)
  bundesland: '', // Geographic filter
  fundingType: '', // funding_type filter
  providerType: '', // funding_provider_type filter
  deadlineHorizon: 'all', // Time horizon for deadlines
  fundingAmountRange: '', // Funding amount range filter
  foerdergeber: '', // Fördergeber filter
  source: '' // Source filter
});
export const isLoading = writable(false);
export const error = writable(null);

// Helper function to get date ranges based on deadline horizon
function getDateRangeFromDeadlineHorizon(horizon) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  switch(horizon) {
    case 'thisMonth': {
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0);
      return { start: startOfMonth, end: endOfMonth };
    }

    case 'next3Months': {
      const endOf3Months = new Date(today);
      endOf3Months.setMonth(today.getMonth() + 3);
      return { start: today, end: endOf3Months };
    }

    case 'next6Months': {
      const endOf6Months = new Date(today);
      endOf6Months.setMonth(today.getMonth() + 6);
      return { start: today, end: endOf6Months };
    }

    case 'ongoing': {
      // Programs with deadline_type 'laufend' or 'jaehrlich'
      return { type: 'ongoing' };
    }

    case 'all':
    default:
      return { start: null, end: null };
  }
}

// Derived store for filtered foerdermittel
export const filteredFoerdermittel = derived(
  [foerdermittel, filters],
  ([$foerdermittel, $filters]) => {
    console.log('[FoerdermittelStore] Filtering', $foerdermittel.length, 'programs with filters:', $filters);

    const today = new Date();
    today.setHours(0, 0, 0, 0); // Set to start of day for accurate comparison

    return $foerdermittel.filter(program => {
      // Filter out programs with past deadlines (but keep laufend/jaehrlich programs)
      if (program.application_deadline &&
          program.deadline_type !== 'laufend' &&
          program.deadline_type !== 'jaehrlich') {
        try {
          const deadlineDate = new Date(program.application_deadline);
          deadlineDate.setHours(0, 0, 0, 0);
          if (deadlineDate < today) {
            return false;
          }
        } catch (err) {
          console.error('Error parsing deadline date:', err, program.application_deadline);
        }
      }
      // Filter by tags if any are selected (AND logic)
      if ($filters.tags && $filters.tags.length > 0) {
        // Check if program has tag_groups
        if (!program.tag_groups) {
          return false;
        }

        // Collect all tags from tag_groups
        const programTags = [];
        if (program.tag_groups) {
          const tagGroupsObj = typeof program.tag_groups === 'string'
            ? JSON.parse(program.tag_groups)
            : program.tag_groups;

          Object.values(tagGroupsObj).forEach(tags => {
            if (Array.isArray(tags)) {
              programTags.push(...tags.map(t => t.toLowerCase()));
            }
          });
        }

        // Check if ALL selected tags are present (AND logic)
        for (const filterTag of $filters.tags) {
          if (!programTags.includes(filterTag.toLowerCase())) {
            return false;
          }
        }
      }

      // Filter by Bundesland
      if ($filters.bundesland && $filters.bundesland !== '') {
        if (program.bundesland !== $filters.bundesland) {
          return false;
        }
      }

      // Filter by funding type
      if ($filters.fundingType && $filters.fundingType !== '') {
        if (program.funding_type !== $filters.fundingType) {
          return false;
        }
      }

      // Filter by provider type
      if ($filters.providerType && $filters.providerType !== '') {
        if (program.funding_provider_type !== $filters.providerType) {
          return false;
        }
      }

      // Filter by deadline horizon
      if ($filters.deadlineHorizon && $filters.deadlineHorizon !== 'all') {
        const dateRange = getDateRangeFromDeadlineHorizon($filters.deadlineHorizon);

        // Handle ongoing programs
        if (dateRange.type === 'ongoing') {
          if (program.deadline_type !== 'laufend' && program.deadline_type !== 'jaehrlich') {
            return false;
          }
        } else if (dateRange.start || dateRange.end) {
          // For date range filters, exclude ongoing programs
          if (program.deadline_type === 'laufend' || program.deadline_type === 'jaehrlich') {
            return false;
          }

          // Only filter programs with actual deadlines
          if (program.application_deadline) {
            try {
              const deadlineDate = new Date(program.application_deadline);

              if (dateRange.start && deadlineDate < dateRange.start) {
                return false;
              }

              if (dateRange.end && deadlineDate > dateRange.end) {
                return false;
              }
            } catch (err) {
              console.error('Error parsing deadline date:', err, program.application_deadline);
            }
          } else {
            // Exclude programs without deadlines
            return false;
          }
        }
      }

      // Filter by funding amount range
      if ($filters.fundingAmountRange && $filters.fundingAmountRange !== '') {
        const min = program.funding_amount_min;
        const max = program.funding_amount_max;

        // Skip programs without funding amount info
        if (!min && !max) {
          return true; // Keep programs without amount info
        }

        const avgAmount = max ? (min + max) / 2 : min;

        switch($filters.fundingAmountRange) {
          case 'small': // < 10k
            if (avgAmount && avgAmount >= 10000) return false;
            break;
          case 'medium': // 10k - 50k
            if (!avgAmount || avgAmount < 10000 || avgAmount > 50000) return false;
            break;
          case 'large': // 50k - 100k
            if (!avgAmount || avgAmount < 50000 || avgAmount > 100000) return false;
            break;
          case 'xlarge': // > 100k
            if (!avgAmount || avgAmount < 100000) return false;
            break;
        }
      }

      // Filter by fördergeber
      if ($filters.foerdergeber && $filters.foerdergeber !== '') {
        // Check if program has tag_groups
        if (!program.tag_groups) {
          return false;
        }

        const tagGroupsObj = typeof program.tag_groups === 'string'
          ? JSON.parse(program.tag_groups)
          : program.tag_groups;

        // Check if the selected fördergeber is in the program's foerdergeber array
        if (!tagGroupsObj.foerdergeber || !Array.isArray(tagGroupsObj.foerdergeber)) {
          return false;
        }

        if (!tagGroupsObj.foerdergeber.includes($filters.foerdergeber)) {
          return false;
        }
      }

      // Filter by source
      if ($filters.source && $filters.source !== '') {
        if (program.source !== $filters.source) {
          return false;
        }
      }

      return true;
    });
  }
);

// Load all foerdermittel
export async function loadFoerdermittel() {
  isLoading.set(true);
  error.set(null);

  try {
    console.log('[FoerdermittelStore] Loading förderprogramme...');
    const data = await api.getFoerderprogramme();
    console.log('[FoerdermittelStore] Loaded', data.length, 'programs from API');
    foerdermittel.set(data);
  } catch (err) {
    console.error('Fehler beim Laden der Förderprogramme:', err);
    error.set('Fehler beim Laden der Förderprogramme. Bitte versuchen Sie es später erneut.');
  } finally {
    isLoading.set(false);
  }
}

// Update filters and reload foerdermittel
export function updateFilters(newFilters) {
  filters.update(f => ({ ...f, ...newFilters }));
}

// Reset all filters
export function resetFilters() {
  filters.set({
    tags: [],
    bundesland: '',
    fundingType: '',
    providerType: '',
    deadlineHorizon: 'all',
    fundingAmountRange: '',
    foerdergeber: '',
    source: ''
  });
}

// Initialize all data
export async function initializeData() {
  await loadFoerdermittel();
}

// Derived store for top tags (from tag_groups)
export const topTags = derived(foerdermittel, $foerdermittel => {
  const tagCounts = {};

  for (const program of $foerdermittel) {
    if (program.tag_groups) {
      const tagGroupsObj = typeof program.tag_groups === 'string'
        ? JSON.parse(program.tag_groups)
        : program.tag_groups;

      Object.values(tagGroupsObj).forEach(tags => {
        if (Array.isArray(tags)) {
          for (const tag of tags) {
            tagCounts[tag] = (tagCounts[tag] || 0) + 1;
          }
        }
      });
    }
  }

  return Object.entries(tagCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 20) // Top 20 tags
    .map(([tag]) => tag);
});
