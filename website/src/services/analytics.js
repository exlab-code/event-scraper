/**
 * Analytics service for tracking user interactions
 * Uses Umami analytics
 */

/**
 * Track a custom event
 * @param {string} eventName - Name of the event
 * @param {object} props - Additional properties to track
 */

const eventQueue = [];
let umamiLoaded = false;

function sendEvent(eventName, props) {
  if (umamiLoaded && typeof umami !== 'undefined') {
    umami.track(eventName, props);
  } else {
    eventQueue.push({ eventName, props });
  }
}

function flushQueue() {
  while (eventQueue.length > 0) {
    const { eventName, props } = eventQueue.shift();
    if (typeof umami !== 'undefined') {
      umami.track(eventName, props);
    }
  }
}

// Wait for Umami script to load
window.addEventListener('umami:loaded', () => {
  umamiLoaded = true;
  flushQueue();
});

export function trackEvent(eventName, props = {}) {
  sendEvent(eventName, props);
}

/**
 * Track a page view
 * @param {string} url - URL to track
 * @param {object} props - Additional properties to track
 */
export function trackPageView(url, props = {}) {
  if (umamiLoaded && typeof umami !== 'undefined') {
    umami.trackView(url, props);
  } else {
    eventQueue.push({ eventName: 'page_view', props: { url, ...props } });
  }
}
