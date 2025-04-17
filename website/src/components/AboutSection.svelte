<script>
  import Accordion from './Accordion.svelte';
  
  let isAboutOpen = false;
</script>

<div class="bg-white rounded-lg shadow">
  <Accordion 
    title="Über diesen Kalender" 
    defaultOpen={false} 
    mobileOnly={true}
    id="about"
    on:toggle={({ detail }) => isAboutOpen = detail.isOpen}
  >
    <p class="text-sm text-gray-600 mb-3">Dieser Kalender sammelt Digitalisierungsveranstaltungen, die speziell für gemeinnützige Organisationen relevant sind. Die Veranstaltungen decken Themen wie digitales Fundraising, Website-Entwicklung, Datenmanagement und mehr ab.</p>
    <p class="text-sm text-gray-600">Alle Veranstaltungen werden von unserem Team geprüft und freigegeben, um sicherzustellen, dass sie für den gemeinnützigen Sektor wertvoll sind.</p>
  </Accordion>
</div>
