<script>
  import { onMount } from 'svelte';
  import EventList from '../components/EventList.svelte';
  import EventFilter from '../components/EventFilter.svelte';
  import CalendarSubscription from '../components/CalendarSubscription.svelte';
  import AboutSection from '../components/AboutSection.svelte';
  import { initializeData } from '../stores/eventStore';
  
  onMount(() => {
    // Initialize all data when component mounts
    initializeData();
  });
</script>




<main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="grid grid-cols-1 lg:grid-cols-4 gap-8">
    <aside class="lg:col-span-1 space-y-6">
      <EventFilter />
      <CalendarSubscription />
      
      <AboutSection />
    </aside>
    
    <div class="lg:col-span-3">
      <EventList />
    </div>
  </div>
</main>
