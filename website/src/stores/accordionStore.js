import { writable } from 'svelte/store';

// Store for tracking which accordion is currently open on mobile
export const activeAccordionId = writable(null);

// Function to set the active accordion
export function setActiveAccordion(id) {
  activeAccordionId.set(id);
}

export function closeAllAccordions() {
  activeAccordionId.set(null);
}
