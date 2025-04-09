<script>
  import { onMount } from 'svelte';
  import EventList from '../components/EventList.svelte';
  import EventFilter from '../components/EventFilter.svelte';
  import CalendarSubscription from '../components/CalendarSubscription.svelte';
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
      
      <div class="bg-white rounded-lg shadow p-5">
        <h3 class="text-lg font-semibold text-gray-800 mb-3">Über diesen Kalender</h3>
        <p class="text-gray-600 mb-3">Dieser Kalender sammelt Digitalisierungsveranstaltungen, die speziell für gemeinnützige Organisationen relevant sind. Die Veranstaltungen decken Themen wie digitales Fundraising, Website-Entwicklung, Datenmanagement und mehr ab.</p>
        <p class="text-gray-600">Alle Veranstaltungen werden von unserem Team geprüft und freigegeben, um sicherzustellen, dass sie für den gemeinnützigen Sektor wertvoll sind.</p>
      </div>
    </aside>
    
    <div class="lg:col-span-3">
      <EventList />
    </div>
  </div>
</main>
