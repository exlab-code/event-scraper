const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const cors = require('cors');
const path = require('path');

const app = express();
const PORT = 5000;

// Enable CORS for all routes
app.use(cors());

// Proxy requests to Directus API
app.use('/api', createProxyMiddleware({
  target: 'http://162.55.189.163:8055',
  changeOrigin: true,
  pathRewrite: {
    '^/api': '' // Remove the /api prefix when forwarding
  },
  onProxyRes: (proxyRes) => {
    // Add CORS headers to the proxied response
    proxyRes.headers['Access-Control-Allow-Origin'] = '*';
    proxyRes.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS';
    proxyRes.headers['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization';
  }
}));

// Serve the Svelte app from the public directory
app.use(express.static(path.join(__dirname, 'public')));

// For SPA routing, send all non-api requests to index.html
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`Proxy server running on http://0.0.0.0:${PORT}`);
});