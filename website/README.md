# Event Scraper Website

A Svelte-based website for displaying events collected by the Event Scraper system.

## Features

- Display events in a clean, responsive interface
- Filter events by category, date, and other criteria
- View event details including location, date, and description
- Subscribe to events via calendar integration
- Customizable appearance through CSS

## Setup

1. **Install dependencies**:
   ```bash
   cd website
   npm install
   ```

2. **Development mode**:
   ```bash
   npm run dev
   ```
   This will start a development server at http://localhost:5000

3. **Build for production**:
   ```bash
   npm run build
   ```
   This will create optimized files in the `public/build` directory

## Project Structure

- `src/` - Source code
  - `components/` - Svelte components
    - `EventCard.svelte` - Individual event display
    - `EventFilter.svelte` - Filtering interface
    - `EventList.svelte` - List of events
    - `Header.svelte` - Website header
    - `CalendarSubscription.svelte` - Calendar subscription component
  - `pages/` - Page components
    - `Home.svelte` - Home page
    - `About.svelte` - About page
  - `services/` - API services
    - `api.js` - API communication
  - `stores/` - Svelte stores
    - `eventStore.js` - Event data store
  - `App.svelte` - Main application component
  - `main.js` - Application entry point
  - `categoryMappings.js` - Event category definitions
- `public/` - Static assets
  - `custom.css` - Custom CSS for styling (see [custom-css-readme.md](public/custom-css-readme.md))
  - `index.html` - HTML template
- `rollup.config.js` - Rollup configuration
- `tailwind.config.js` - Tailwind CSS configuration

## API Integration

The website connects to the Directus API to fetch event data. The API connection is configured in `src/services/api.js`.

## Customization

### CSS Customization

You can customize the appearance of the website by editing the `public/custom.css` file. See [custom-css-readme.md](public/custom-css-readme.md) for details.

### Adding New Components

To add a new component:

1. Create a new `.svelte` file in the appropriate directory
2. Import and use the component in your pages or other components
3. If needed, add any associated styles or scripts

## Development Proxy

The website includes several proxy server options for development:

- `basic-proxy.js` - Simple proxy for API requests
- `fixed-proxy.js` - Proxy with CORS headers
- `proxy-server.js` - Advanced proxy with additional features
- `dev-server.js` - Development server with proxy integration

To use a proxy during development:
```bash
node dev-server.js
```

## Browser Compatibility

The website is compatible with modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
