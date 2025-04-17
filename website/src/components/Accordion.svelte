<script>
  import { slide } from 'svelte/transition';
  import { createEventDispatcher } from 'svelte';
  import { activeAccordionId, setActiveAccordion } from '../stores/accordionStore';
  import { onMount } from 'svelte';
  
  // Props
  export let title = ""; // The header text
  export let defaultOpen = false; // Whether the accordion is open by default
  export let mobileOnly = true; // Whether the accordion behavior only applies to mobile view
  export let id = ""; // Optional ID for the accordion
  
  // Event dispatcher to notify parent when accordion state changes
  const dispatch = createEventDispatcher();
  
  // Check if we're on mobile (client-side only)
  let isMobile = false;
  
  onMount(() => {
    // Check if we're on mobile
    checkMobile();
    
    // Add resize listener to update mobile status
    window.addEventListener('resize', checkMobile);
    
    // Cleanup
    return () => {
      window.removeEventListener('resize', checkMobile);
    };
  });
  
  function checkMobile() {
    isMobile = window.innerWidth < 768;
  }
  
  // Reactive declaration to compute if this accordion is open
  $: isOpen = isMobile 
    ? $activeAccordionId === id 
    : true; // Always open on desktop
  
  // Toggle accordion state (only works on mobile)
  function toggle() {
    if (!isMobile) return; // Do nothing on desktop
    
    if (isOpen) {
      // If already open, close it
      setActiveAccordion(null);
    } else {
      // If closed, open it and close others
      setActiveAccordion(id);
    }
    
    dispatch('toggle', { id, isOpen: !isOpen });
  }
</script>

<div class="accordion {mobileOnly ? 'mobile-only' : ''} p-4">
  <!-- Accordion Header -->
  <button 
    class="accordion-header py-2 {isOpen ? 'active' : ''}" 
    on:click={toggle}
    aria-expanded={isOpen}
    aria-controls="content-{id}"
  >
    <span class="accordion-title text-lg font-bold">{title}</span>
    <span class="accordion-icon">
      <svg 
        xmlns="http://www.w3.org/2000/svg" 
        width="20" 
        height="20" 
        viewBox="0 0 24 24" 
        fill="none" 
        stroke="currentColor" 
        stroke-width="2" 
        stroke-linecap="round" 
        stroke-linejoin="round"
        class="chevron {isOpen ? 'rotate' : ''}"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </span>
  </button>
  
  <!-- Accordion Content -->
  {#if isOpen}
    <div 
      id="content-{id}" 
      class="accordion-content"
      transition:slide={{ duration: 300 }}
    >
      <slot></slot>
    </div>
  {/if}
</div>


