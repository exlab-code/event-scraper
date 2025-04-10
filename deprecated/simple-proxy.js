const express = require('express');
const http = require('http');
const https = require('https');
const path = require('path');

const app = express();
const PORT = 5000;

// Serve static files from the public directory
app.use(express.static(path.join(__dirname, 'public')));

// Simple proxy function
function proxyRequest(req, res, targetHost, targetPort, targetPath) {
  const options = {
    hostname: targetHost,
    port: targetPort,
    path: targetPath,
    method: req.method,
    headers: {
      ...req.headers,
      host: targetHost
    }
  };

  // Add authorization header if it was in the original request
  if (req.headers.authorization) {
    options.headers.authorization = req.headers.authorization;
  }

  // Create the appropriate request object
  const protocol = targetPort === 443 ? https : http;
  const proxyReq = protocol.request(options, (proxyRes) => {
    // Copy status code
    res.statusCode = proxyRes.statusCode;
    
    // Copy response headers
    const headers = proxyRes.headers;
    
    // Add CORS headers
    headers['Access-Control-Allow-Origin'] = '*';
    headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS';
    headers['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization';
    
    // Copy all headers to the response
    Object.keys(headers).forEach(key => {
      res.setHeader(key, headers[key]);
    });
    
    // Stream the proxy response to the client
    proxyRes.pipe(res);
  });

  // Handle proxy errors
  proxyReq.on('error', (error) => {
    console.error('Proxy error:', error);
    res.status(500).send('Proxy error: ' + error.message);
  });

  // If the request has a body, write it to the proxy request
  if (req.method !== 'GET' && req.method !== 'HEAD' && req.method !== 'OPTIONS') {
    req.pipe(proxyReq);
  } else {
    proxyReq.end();
  }
}

// Proxy API requests to Directus
app.use('/api', (req, res) => {
  // Convert /api/items/events to /items/events
  const targetPath = req.url.replace(/^\/api/, '');
  proxyRequest(req, res, '162.55.189.163', 8055, targetPath);
});

// Handle OPTIONS requests for CORS preflight
app.options('*', (req, res) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  res.sendStatus(200);
});

// For SPA routing - catch all other routes and return the index.html file
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Start the server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on http://0.0.0.0:${PORT}`);
});
