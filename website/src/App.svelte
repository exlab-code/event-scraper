<script>
  import { onMount } from 'svelte';
  import Header from './components/Header.svelte';
  import Home from './pages/Home.svelte';
  import About from './pages/About.svelte';
  
  // Simple routing
  let currentRoute = 'home';
  
  onMount(() => {
    // Set initial route based on URL
    handleRouteChange();
    
    // Listen for URL changes
    window.addEventListener('popstate', handleRouteChange);
    
    return () => {
      window.removeEventListener('popstate', handleRouteChange);
    };
  });
  
  function handleRouteChange() {
    const path = window.location.pathname;
    
    if (path === '/about') {
      currentRoute = 'about';
    } else {
      currentRoute = 'home';
    }
  }
  
  function navigateTo(route, event) {
    if (event) {
      event.preventDefault();
    }
    
    window.history.pushState({}, '', route);
    handleRouteChange();
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
  {/if}
</div>

<footer class="bg-gray-800 text-white py-6 mt-8">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <p class="text-center text-gray-300 text-sm">
      &copy; {new Date().getFullYear()} Veranstaltungskalender für Non-Profit Digitalisierung
    </p>
  </div>
</footer>
