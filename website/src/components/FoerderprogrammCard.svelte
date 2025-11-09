<script>
  import Tag from './Tag.svelte';

  export let program;

  // Format date for display
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
    const cutoff = text.substring(0, maxLength).lastIndexOf(' ');
    return text.substring(0, cutoff > 0 ? cutoff : maxLength) + '...';
  }

  // Find the group ID for a tag
  function findTagGroup(tag) {
    if (!program.tag_groups) return null;

    const tagGroupsObj = typeof program.tag_groups === 'string'
      ? JSON.parse(program.tag_groups)
      : program.tag_groups;

    for (const [groupId, tags] of Object.entries(tagGroupsObj)) {
      if (tags && Array.isArray(tags) && tags.includes(tag)) {
        return groupId;
      }
    }
    return null;
  }

  // Get all tags from tag_groups
  function getAllTags() {
    if (!program.tag_groups) return [];

    const tagGroupsObj = typeof program.tag_groups === 'string'
      ? JSON.parse(program.tag_groups)
      : program.tag_groups;

    const allTags = [];
    Object.values(tagGroupsObj).forEach(tags => {
      if (Array.isArray(tags)) {
        allTags.push(...tags);
      }
    });
    return allTags;
  }

  // Get selected tags for display: 2 super categories, 2 themes, 1 target group
  function getDisplayTags() {
    if (!program.tag_groups) return [];

    const tagGroupsObj = typeof program.tag_groups === 'string'
      ? JSON.parse(program.tag_groups)
      : program.tag_groups;

    const selectedTags = [];

    // Add up to 2 super categories
    if (tagGroupsObj.super_kategorie && Array.isArray(tagGroupsObj.super_kategorie)) {
      selectedTags.push(...tagGroupsObj.super_kategorie.slice(0, 2));
    }

    // Add up to 2 themes
    if (tagGroupsObj.thema && Array.isArray(tagGroupsObj.thema)) {
      selectedTags.push(...tagGroupsObj.thema.slice(0, 2));
    }

    // Add 1 target group
    if (tagGroupsObj.zielgruppe && Array.isArray(tagGroupsObj.zielgruppe)) {
      selectedTags.push(...tagGroupsObj.zielgruppe.slice(0, 1));
    }

    return selectedTags;
  }

  // Format funding amount for display (min/max only)
  function formatFundingAmount() {
    if (program.funding_amount_min && program.funding_amount_max) {
      return `${formatEuro(program.funding_amount_min)} - ${formatEuro(program.funding_amount_max)}`;
    }

    if (program.funding_amount_min) {
      return `ab ${formatEuro(program.funding_amount_min)}`;
    }

    if (program.funding_amount_max) {
      return `bis ${formatEuro(program.funding_amount_max)}`;
    }

    return 'Betrag variabel';
  }

  function formatEuro(amount) {
    return new Intl.NumberFormat('de-DE', { maximumFractionDigits: 0 }).format(amount) + ' €';
  }

  // Get deadline display text
  function getDeadlineText() {
    if (program.deadline_type === 'laufend') return 'Laufend';
    if (program.deadline_type === 'jaehrlich') return 'Jährlich';
    if (program.deadline_type === 'geschlossen') return 'Geschlossen';
    if (program.application_deadline) {
      return new Intl.DateTimeFormat('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(program.application_deadline));
    }
    return 'Einmalig';
  }

  // Get bundesland display name (now just returns value with underscore replacement)
  function getBundeslandDisplay(bundesland) {
    if (!bundesland) return '';
    // Replace underscores with hyphens for display
    return bundesland.replace(/_/g, '-').replace('eu-weit', 'EU-weit');
  }

  // Get color based on deadline (returns hex color)
  function getDeadlineColor() {
    // Laufend (ongoing) - blue
    if (program.deadline_type === 'laufend' || program.deadline_type === 'jaehrlich') {
      return '#3b82f6'; // blue-500
    }

    // No deadline or closed - gray
    if (!program.application_deadline || program.deadline_type === 'geschlossen') {
      return '#9ca3af'; // gray-400
    }

    // Calculate months until deadline
    const now = new Date();
    const deadline = new Date(program.application_deadline);
    const monthsUntil = (deadline.getFullYear() - now.getFullYear()) * 12 + (deadline.getMonth() - now.getMonth());

    // Next 3 months - pink/red
    if (monthsUntil <= 3) {
      return '#ec4899'; // pink-500
    }

    // Next 10 months - greenish
    if (monthsUntil <= 10) {
      return '#10b981'; // green-500
    }

    // More than 10 months - gray
    return '#9ca3af'; // gray-400
  }
</script>

<div class="bg-white rounded-lg shadow-md hover:shadow-lg transform hover:-translate-y-1 transition-all duration-200 h-full overflow-hidden event-card">
  <div class="flex h-full">
    <!-- Color-coded deadline indicator on the left side -->
    <div class="w-4 flex-shrink-0" style="background-color: {getDeadlineColor()};"></div>

    <!-- Main content -->
    <div class="p-4 w-full flex-grow main-content">
      <h3 class="text-lg font-semibold text-gray-800 mb-2 line-clamp-2">{program.title}</h3>

      <!-- Program metadata (Priority: money, deadline, place, orga) -->
      <div class="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
        <!-- Funding amount -->
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <path d="M15 9.5a3.5 3.5 0 0 0-7 0v2a3.5 3.5 0 0 0 7 0"></path>
            <line x1="8" y1="11" x2="16" y2="11"></line>
            <line x1="8" y1="15" x2="12" y2="15"></line>
          </svg>
          <span>{formatFundingAmount()}</span>
        </div>

        <!-- Deadline -->
        <div class="flex items-center gap-2">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
          <span>{getDeadlineText()}</span>
        </div>

        <!-- Bundesland -->
        {#if program.bundesland}
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"></path>
              <circle cx="12" cy="10" r="3"></circle>
            </svg>
            <span>{getBundeslandDisplay(program.bundesland)}</span>
          </div>
        {/if}

        <!-- Funding organization -->
        {#if program.funding_organization}
          <div class="flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4 text-primary-500" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
              <polyline points="9 22 9 12 15 12 15 22"></polyline>
            </svg>
            <span>{program.funding_organization}</span>
          </div>
        {/if}
      </div>

      <!-- Description -->
      {#if program.description}
        <p class="text-sm text-gray-700 mb-3 line-clamp-3">
          {truncateText(program.description, 350)}
        </p>
      {/if}

      <!-- Funding amount text (if available) -->
      {#if program.funding_amount_text}
        <p class="text-sm text-gray-600 mb-3">
          <span class="font-semibold">Fördersumme:</span> {program.funding_amount_text}
        </p>
      {/if}

      <!-- Tags -->
      <div class="flex flex-wrap gap-2">
        {#each getDisplayTags() as tag}
          <Tag {tag} groupId={findTagGroup(tag)} />
        {/each}
        {#if getAllTags().length > getDisplayTags().length}
          <span class="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded-full">+{getAllTags().length - getDisplayTags().length} mehr</span>
        {/if}
      </div>
    </div>

    <!-- Right action bar -->
    <div class="border-l border-gray-100 px-4 py-4 flex flex-col justify-end text-sm w-32 action-bar">
      <!-- Website or Application portal link -->
      {#if program.website || program.application_portal}
        <div>
          {#if program.application_portal}
            <a href={program.application_portal} target="_blank" rel="noopener noreferrer" class="w-full py-1 transition-colors hover:bg-gray-50 text-primary-600 flex items-center gap-2 mb-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                <circle cx="8.5" cy="7" r="4"></circle>
                <line x1="20" y1="8" x2="20" y2="14"></line>
                <line x1="23" y1="11" x2="17" y2="11"></line>
              </svg>
              Beantragen
            </a>
          {/if}
          {#if program.website}
            <a href={program.website} target="_blank" rel="noopener noreferrer" class="w-full py-1 transition-colors hover:bg-gray-50 text-primary-600 flex items-center gap-2">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="2" y1="12" x2="22" y2="12"></line>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"></path>
              </svg>
              Info
            </a>
          {/if}
        </div>
      {/if}
    </div>
  </div>
</div>
