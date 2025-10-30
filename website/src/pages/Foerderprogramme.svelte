<script>
  import { onMount } from 'svelte';
  import FoerderprogrammList from '../components/FoerderprogrammList.svelte';
  import FoerderprogrammFilter from '../components/FoerderprogrammFilter.svelte';
  import AboutSection from '../components/AboutSection.svelte';
  import { initializeData } from '../stores/foerdermittelStore';
  import { activeAccordionId } from '../stores/accordionStore';

  onMount(() => {
    // Initialize all data when component mounts
    initializeData();

    // Set default open accordion on desktop
    if (window.innerWidth >= 768) {
      activeAccordionId.set('filter');
    } else {
      activeAccordionId.set(null);
    }
  });
</script>

<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
    <aside class="lg:col-span-1 space-y-6">
      <FoerderprogrammFilter defaultOpen={true} />

      <AboutSection defaultOpen={false} />
    </aside>

    <div class="lg:col-span-3">
      <FoerderprogrammList />
    </div>
  </div>
</main>
