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

## Deployment to Cloudflare Pages

You can deploy the website to Cloudflare Pages for free hosting with a global CDN. Here's how:

### Prerequisites

1. A [Cloudflare account](https://dash.cloudflare.com/sign-up)
2. Your project in a Git repository (GitHub, GitLab, or Bitbucket)

### Step 1: Build the Website for Production

Before deploying, make sure your website builds correctly:

```bash
cd website
npm install
npm run build
```

This will create optimized files in the `public/build` directory.

### Step 2: Set Up Cloudflare Pages

1. Log in to your [Cloudflare dashboard](https://dash.cloudflare.com)
2. Click on "Pages" in the sidebar
3. Click "Create a project" → "Connect to Git"
4. Select your Git provider (GitHub, GitLab, or Bitbucket) and authenticate
5. Select your repository containing the Event Scraper project

### Step 3: Configure Build Settings

Configure the following build settings:

- **Project name**: Choose a name for your project (e.g., "event-scraper-website")
- **Production branch**: `main` (or your default branch)
- **Build command**: `cd website && npm install && npm run build`
- **Build output directory**: `website/public`
- **Root directory**: (leave empty)

### Step 4: Environment Variables

If your website needs to connect to the Directus API, add these environment variables:

- `DIRECTUS_API_URL`: Your Directus API URL
- `DIRECTUS_API_TOKEN`: Your Directus API token (if needed)

### Step 5: Deploy

1. Click "Save and Deploy"
2. Wait for the build and deployment to complete
3. Once deployed, Cloudflare will provide you with a URL (e.g., `https://event-scraper-website.pages.dev`)

### Step 6: Custom Domain (Optional)

To use a custom domain:

1. Go to your Pages project in the Cloudflare dashboard
2. Click on "Custom domains"
3. Click "Set up a custom domain"
4. Enter your domain name and follow the instructions

### Handling API Requests

Since the website makes API requests to Directus, you'll need to handle CORS. There are two approaches:

#### Option 1: Configure Directus CORS Settings

In your Directus instance, add your Cloudflare Pages domain to the allowed origins:

1. Go to your Directus admin panel
2. Navigate to Settings → Security
3. Add your Cloudflare Pages domain to the "Allowed Origins" list

#### Option 2: Use Cloudflare Workers as a Proxy

Create a Cloudflare Worker to proxy API requests:

1. In your Cloudflare dashboard, go to "Workers & Pages"
2. Click "Create a Worker"
3. Use this template:

```js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const url = new URL(request.url)
  
  // Check if the request is for the API
  if (url.pathname.startsWith('/api/')) {
    // Create a new request to your Directus API
    const apiUrl = 'https://your-directus-api-url' + url.pathname.replace('/api', '') + url.search
    
    const modifiedRequest = new Request(apiUrl, {
      method: request.method,
      headers: request.headers,
      body: request.body,
    })
    
    // Forward the request to your API
    const response = await fetch(modifiedRequest)
    
    // Add CORS headers to the response
    const modifiedResponse = new Response(response.body, response)
    modifiedResponse.headers.set('Access-Control-Allow-Origin', '*')
    modifiedResponse.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
    modifiedResponse.headers.set('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    return modifiedResponse
  }
  
  // For non-API requests, pass through to Pages
  return fetch(request)
}
```

4. Update the API URL in your website code to use the relative path `/api/` instead of the absolute Directus URL

### Continuous Deployment

Cloudflare Pages automatically rebuilds and deploys your site when you push changes to your repository. To see build logs and deployment status, go to the "Deployments" tab in your Pages project.
