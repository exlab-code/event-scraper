const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 5000;
const PUBLIC_DIR = path.join(__dirname, 'public');

// Create the server
const server = http.createServer((req, res) => {
  console.log(`${req.method} ${req.url}`);
  
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
      'Access-Control-Allow-Headers': 'Origin, X-Requested-With, Content-Type, Accept, Authorization'
    });
    res.end();
    return;
  }
  
  // API proxy for Directus
  if (req.url.startsWith('/api/')) {
    const directusPath = req.url.replace(/^\/api/, '');
    const options = {
      hostname: '162.55.189.163',
      port: 8055,
      path: directusPath,
      method: req.method,
      headers: {
        'Authorization': req.headers.authorization || 'Bearer APpU898yct7V2VyMFfcJse_7WXktDY-o'
      }
    };

    console.log(`Proxying to: http://${options.hostname}:${options.port}${options.path}`);
    
    // Create the proxy request
    const proxyReq = http.request(options, (proxyRes) => {
      res.writeHead(proxyRes.statusCode, {
        'Content-Type': proxyRes.headers['content-type'] || 'application/json',
        'Access-Control-Allow-Origin': '*'
      });
      
      let data = '';
      proxyRes.on('data', (chunk) => {
        data += chunk;
      });
      
      proxyRes.on('end', () => {
        res.end(data);
      });
    });
    
    proxyReq.on('error', (error) => {
      console.error('Proxy error:', error);
      res.writeHead(500, {'Content-Type': 'application/json'});
      res.end(JSON.stringify({error: 'Proxy error: ' + error.message}));
    });
    
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      let requestBody = '';
      req.on('data', (chunk) => {
        requestBody += chunk;
      });
      
      req.on('end', () => {
        proxyReq.end(requestBody);
      });
    } else {
      proxyReq.end();
    }
    
    return;
  }
  
  // Static file handling
  let filePath = req.url;
  
  // Default to index.html for SPA routing
  if (filePath === '/') {
    filePath = '/index.html';
  }
  
  // Get absolute path
  filePath = path.join(PUBLIC_DIR, filePath);
  
  console.log(`Looking for file: ${filePath}`);
  
  // Check if file exists
  fs.access(filePath, fs.constants.F_OK, (err) => {
    if (err) {
      console.log(`File not found: ${filePath}`);
      
      // For SPA, serve index.html for non-api routes
      if (!req.url.startsWith('/api/')) {
        const indexPath = path.join(PUBLIC_DIR, 'index.html');
        fs.readFile(indexPath, (err, data) => {
          if (err) {
            res.writeHead(404);
            res.end('Not found');
            return;
          }
          
          res.writeHead(200, {'Content-Type': 'text/html'});
          res.end(data);
        });
        return;
      }
      
      res.writeHead(404);
      res.end('File not found');
      return;
    }
    
    // Determine content type
    const extname = path.extname(filePath).toLowerCase();
    let contentType = 'text/html';
    
    switch (extname) {
      case '.js':
        contentType = 'text/javascript';
        break;
      case '.css':
        contentType = 'text/css';
        break;
      case '.json':
        contentType = 'application/json';
        break;
      case '.png':
        contentType = 'image/png';
        break;
      case '.jpg':
      case '.jpeg':
        contentType = 'image/jpeg';
        break;
      case '.svg':
        contentType = 'image/svg+xml';
        break;
    }
    
    console.log(`Serving ${filePath} as ${contentType}`);
    
    // Read and serve the file
    fs.readFile(filePath, (err, data) => {
      if (err) {
        res.writeHead(500);
        res.end('Server error');
        return;
      }
      
      res.writeHead(200, {'Content-Type': contentType});
      res.end(data);
    });
  });
});

server.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running at http://0.0.0.0:${PORT}/`);
  
  // List all files in the public/build directory to verify CSS
  const buildDir = path.join(PUBLIC_DIR, 'build');
  console.log('\nChecking build directory contents:');
  try {
    const files = fs.readdirSync(buildDir);
    console.log('Files in build directory:');
    files.forEach(file => {
      console.log(`- ${file}`);
    });
  } catch (error) {
    console.error(`Error reading build directory: ${error.message}`);
  }
});
