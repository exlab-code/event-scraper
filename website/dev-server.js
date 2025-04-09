const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const path = require('path');

const app = express();
const PORT = 8080; // Change this to 8080 to match npm run dev

// Serve static files from the public directory
app.use(express.static('public'));

// Set up the proxy for API requests
app.use('/api', createProxyMiddleware({
  target: 'https://calapi.buerofalk.de',
  changeOrigin: true,
  pathRewrite: {
    '^/api': '' // Remove the /api prefix when forwarding
  }
}));

// For SPA routing, serve index.html for any other routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start the server
app.listen(PORT, () => {
  console.log(`Development server running at http://localhost:${PORT}`);
});