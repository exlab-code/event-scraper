<script>
  import { onMount } from 'svelte';
  import Header from './components/Header.svelte';
  import Home from './pages/Home.svelte';
  import About from './pages/About.svelte';
  import LinkedInGenerator from './pages/LinkedInGenerator.svelte';
  import Foerderprogramme from './pages/Foerderprogramme.svelte';
  import { trackPageView } from './services/analytics';

  // Simple routing
  let currentRoute = 'home';

  onMount(() => {
    // Set initial route based on URL
    handleRouteChange();

    // Track initial page view
    trackPageView(window.location.pathname);

    // Listen for URL changes
    window.addEventListener('popstate', () => {
      handleRouteChange();
      trackPageView(window.location.pathname);
    });

    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  });

  // Get base path from the URL (for GitHub Pages subdirectory support)
  const basePath = window.location.pathname.split('/')[1] === 'digikal' ? '/digikal' : '';

  function handleRouteChange() {
    const path = window.location.pathname;
    const pathWithoutBase = path.replace(basePath, '') || '/';

    if (pathWithoutBase === '/about') {
      currentRoute = 'about';
    } else if (pathWithoutBase === '/linkedin-generator') {
      currentRoute = 'linkedin-generator';
    } else if (pathWithoutBase === '/foerderprogramme') {
      currentRoute = 'foerderprogramme';
    } else {
      currentRoute = 'home';
    }
  }

  function navigateTo(route, event) {
    if (event) {
      event.preventDefault();
    }

    const fullRoute = basePath + route;
    window.history.pushState({}, '', fullRoute);
    handleRouteChange();

    // Track page view on navigation
    trackPageView(fullRoute);
  }
</script>

<svelte:head>
  <link rel="stylesheet" href="global.css">
  <link rel="stylesheet" href="custom.css">
</svelte:head>

<Header {navigateTo} {currentRoute} />

<div class="min-h-[calc(100vh-120px)]">
  {#if currentRoute === 'home'}
    <Home />
  {:else if currentRoute === 'about'}
    <About />
  {:else if currentRoute === 'linkedin-generator'}
    <LinkedInGenerator />
  {:else if currentRoute === 'foerderprogramme'}
    <Foerderprogramme />
  {/if}
</div>

<footer class="bg-gray-800 text-white py-6 mt-8">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <p class="text-center text-gray-300 text-sm">
      &copy; {new Date().getFullYear()} Veranstaltungskalender für Non-Profit Digitalisierung
    </p>
  </div>
</footer>
