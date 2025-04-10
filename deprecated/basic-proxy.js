const http = require('http');
const fs = require('fs');
const path = require('path');
const url = require('url');

const PORT = 5000;
const PUBLIC_DIR = path.join(__dirname, 'public');
const DIRECTUS_HOST = '162.55.189.163';
const DIRECTUS_PORT = 8055;

// Content type mapping based on file extensions
const CONTENT_TYPES = {
  '.html': 'text/html',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

// Create the server
const server = http.createServer((req, res) => {
  const parsedUrl = url.parse(req.url);
  let pathname = parsedUrl.pathname;
  
  console.log(`${req.method} ${pathname}`);
  
  // Handle CORS preflight requests
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Origin, X-Requested-With, Content-Type, Accept, Authorization',
      'Access-Control-Max-Age': '86400' // 24 hours
    });
    res.end();
    return;
  }
  
  // Proxy API requests to Directus
  if (pathname.startsWith('/api/')) {
    // Forward the request to Directus
    const directusPath = pathname.replace(/^\/api/, '');
    const directusUrl = url.parse(parsedUrl.href);
    
    const options = {
      hostname: DIRECTUS_HOST,
      port: DIRECTUS_PORT,
      path: directusPath + (directusUrl.search || ''),
      method: req.method,
      headers: {
        ...req.headers,
        host: DIRECTUS_HOST
      }
    };
    
    const proxyReq = http.request(options, (proxyRes) => {
      // Add CORS headers
      proxyRes.headers['access-control-allow-origin'] = '*';
      
      // Forward the response status and headers
      res.writeHead(proxyRes.statusCode, proxyRes.headers);
      
      // Pipe the response data
      proxyRes.pipe(res);
    });
    
    // Handle errors
    proxyReq.on('error', (error) => {
      console.error('Proxy error:', error);
      res.writeHead(500);
      res.end('Proxy Error: ' + error.message);
    });
    
    // Forward the request body if any
    req.pipe(proxyReq);
    return;
  }
  
  // Handle static files
  // If path is '/', serve index.html
  if (pathname === '/') {
    pathname = '/index.html';
  }
  
  // Get the absolute file path
  const filePath = path.join(PUBLIC_DIR, pathname);
  
  // Check if file exists
  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      // For SPA routing, serve index.html for non-existing files
      const indexPath = path.join(PUBLIC_DIR, 'index.html');
      
      fs.readFile(indexPath, (err, data) => {
        if (err) {
          res.writeHead(404);
          res.end('File not found');
          return;
        }
        
        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end(data);
      });
      return;
    }
    
    // Get the file extension and content type
    const ext = path.extname(filePath);
    const contentType = CONTENT_TYPES[ext] || 'application/octet-stream';
    
    // Read and serve the file
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(500);
        res.end('Server Error');
        return;
      }
      
      res.writeHead(200, { 'Content-Type': contentType });
      res.end(data);
    });
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running at http://0.0.0.0:${PORT}/`);
});
