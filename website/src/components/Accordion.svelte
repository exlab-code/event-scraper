<script>
  import { slide } from 'svelte/transition';
  import { createEventDispatcher } from 'svelte';
  import { activeAccordionId, setActiveAccordion } from '../stores/accordionStore';
  import { onMount } from 'svelte';
  import { writable } from 'svelte/store';
  
  // Props
  export let title = ""; // The header text
  export let defaultOpen = false; // Whether the accordion is open by default
  export let id = ""; // Optional ID for the accordion
  
  // Event dispatcher to notify parent when accordion state changes
  const dispatch = createEventDispatcher();

  // Reactive declaration to compute if this accordion is open
  $: isOpen = $activeAccordionId === id || defaultOpen;

  // Toggle accordion state
  function toggle() {
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

<div class="accordion p-4">
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
