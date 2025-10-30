<script>
  import { onMount } from 'svelte';
  
  export let navigateTo;
  export let currentRoute;
  
  let isScrolled = false;
  let isMenuOpen = false;
  
  // Handle scroll event to add shadow to header when scrolled
  onMount(() => {
    const handleScroll = () => {
      isScrolled = window.scrollY > 10;
    };
    
    window.addEventListener('scroll', handleScroll);
    
    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  });
  
  function toggleMenu() {
    isMenuOpen = !isMenuOpen;
  }
</script>

<header class="{isScrolled ? 'shadow-md' : ''} sticky top-0 z-50 bg-white py-3 transition-shadow duration-300">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between">
    <div class="flex items-center">
      <a 
        href="/" 
        on:click|preventDefault={(e) => navigateTo('/', e)}
        class="flex items-center gap-3 text-gray-800 font-semibold text-xl"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="text-primary-600" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
          <line x1="16" y1="2" x2="16" y2="6"></line>
          <line x1="8" y1="2" x2="8" y2="6"></line>
          <line x1="3" y1="10" x2="21" y2="10"></line>
        </svg>
        <span>DigiKal</span>
      </a>
    </div>
    
    <nav class="{isMenuOpen ? 'translate-y-0 opacity-100 visible' : '-translate-y-full opacity-0 invisible md:opacity-100 md:visible md:translate-y-0'} 
              fixed md:relative top-16 md:top-0 left-0 right-0 md:left-auto md:right-auto
              bg-white md:bg-transparent shadow-md md:shadow-none p-4 md:p-0 
              transition-all duration-300 md:transition-none">
      <ul class="flex flex-col md:flex-row gap-4 md:gap-6">
        <li>
          <a
            href="/"
            on:click|preventDefault={(e) => {
              navigateTo('/', e);
              isMenuOpen = false;
            }}
            class="block md:inline-block px-2 py-2 md:py-1 text-gray-700 font-medium hover:text-primary-600 relative
                  {currentRoute === 'home' ? 'text-primary-600' : ''}
                  after:absolute after:bottom-0 after:left-0 after:h-0.5 after:bg-primary-600 after:w-full
                  {currentRoute === 'home' ? 'after:block' : 'after:hidden'}"
          >
            Veranstaltungen
          </a>
        </li>

        <li>
          <a
            href="/foerderprogramme"
            on:click|preventDefault={(e) => {
              navigateTo('/foerderprogramme', e);
              isMenuOpen = false;
            }}
            class="block md:inline-block px-2 py-2 md:py-1 text-gray-700 font-medium hover:text-primary-600 relative
                  {currentRoute === 'foerderprogramme' ? 'text-primary-600' : ''}
                  after:absolute after:bottom-0 after:left-0 after:h-0.5 after:bg-primary-600 after:w-full
                  {currentRoute === 'foerderprogramme' ? 'after:block' : 'after:hidden'}"
          >
            Förderprogramme
          </a>
        </li>

        <!-- <li>
          <a
            href="/about"
            on:click|preventDefault={(e) => {
              navigateTo('/about', e);
              isMenuOpen = false;
            }}
            class="block md:inline-block px-2 py-2 md:py-1 text-gray-700 font-medium hover:text-primary-600
                  {currentRoute === 'about' ? 'text-primary-600' : ''}"
          >
            Über uns
          </a>
        </li> -->
      </ul>
    </nav>
    
    <button class="md:hidden p-2 text-gray-700 hover:text-primary-600" on:click={toggleMenu} aria-label="Toggle menu">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <line x1="3" y1="12" x2="21" y2="12"></line>
        <line x1="3" y1="6" x2="21" y2="6"></line>
        <line x1="3" y1="18" x2="21" y2="18"></line>
      </svg>
    </button>
  </div>
</header>
