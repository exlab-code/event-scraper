#!/usr/bin/env python3
"""
Simple CORS Proxy Server for the Event Moderation Interface

This script starts a local proxy server that forwards requests to the Directus API
and adds the necessary CORS headers to the response. This allows the interface to
communicate with the API even when running on a different port or domain.

Usage:
  python proxy.py

The proxy will run on port 9090 by default and forward requests to the Directus API.
"""

import http.server
import socketserver
import urllib.request
import urllib.error
import json
import os
import sys
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration
PROXY_PORT = 9090  # Using a less common port to avoid conflicts
TARGET_API = os.getenv("DIRECTUS_API_URL", "https://your-directus-api-url")
API_TOKEN = os.getenv("DIRECTUS_API_TOKEN", "your-api-token-here")  # This should match the token in config-secrets.js

class CORSProxyHandler(http.server.BaseHTTPRequestHandler):
    """Custom request handler that proxies requests to the Directus API"""
    
    def do_OPTIONS(self):
        """Handle preflight requests"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        self.proxy_request("GET")
    
    def do_POST(self):
        """Handle POST requests"""
        self.proxy_request("POST")
    
    def do_PUT(self):
        """Handle PUT requests"""
        self.proxy_request("PUT")
    
    def do_PATCH(self):
        """Handle PATCH requests"""
        self.proxy_request("PATCH")
    
    def do_DELETE(self):
        """Handle DELETE requests"""
        self.proxy_request("DELETE")
    
    def send_cors_headers(self):
        """Send CORS headers to allow cross-origin requests"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")  # 24 hours
    
    def proxy_request(self, method):
        """Proxy the request to the target API"""
        try:
            # Parse the request path
            parsed_path = urlparse(self.path)
            
            # Skip the /proxy prefix if present
            api_path = parsed_path.path
            if api_path.startswith("/proxy"):
                api_path = api_path[6:]
            
            # Build the target URL
            target_url = f"{TARGET_API}{api_path}"
            if parsed_path.query:
                target_url += f"?{parsed_path.query}"
            
            print(f"Proxying {method} request to: {target_url}")
            
            # Create the request
            request = urllib.request.Request(
                target_url,
                method=method
            )
            
            # Add headers from the original request
            for header in self.headers:
                if header.lower() not in ["host", "connection"]:
                    request.add_header(header, self.headers[header])
            
            # Add the Authorization header if not present
            if "Authorization" not in self.headers:
                request.add_header("Authorization", f"Bearer {API_TOKEN}")
            
            # Add request body for POST, PUT, PATCH
            if method in ["POST", "PUT", "PATCH"]:
                content_length = int(self.headers.get("Content-Length", 0))
                request_body = self.rfile.read(content_length)
                request.data = request_body
            
            # Send the request to the target API
            response = urllib.request.urlopen(request)
            
            # Send the response status code
            self.send_response(response.status)
            
            # Send CORS headers
            self.send_cors_headers()
            
            # Send the response headers
            for header in response.headers:
                if header.lower() not in ["transfer-encoding", "connection"]:
                    self.send_header(header, response.headers[header])
            
            self.end_headers()
            
            # Send the response body
            self.wfile.write(response.read())
            
        except urllib.error.HTTPError as e:
            # Handle HTTP errors
            self.send_response(e.code)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            error_message = {
                "error": {
                    "code": e.code,
                    "message": str(e.reason)
                }
            }
            
            self.wfile.write(json.dumps(error_message).encode())
            
        except Exception as e:
            # Handle other errors
            self.send_response(500)
            self.send_cors_headers()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            error_message = {
                "error": {
                    "code": 500,
                    "message": str(e)
                }
            }
            
            self.wfile.write(json.dumps(error_message).encode())

def run_proxy(port=PROXY_PORT):
    """Start the proxy server"""
    try:
        # Create the server
        with socketserver.TCPServer(("", port), CORSProxyHandler) as httpd:
            print(f"CORS Proxy running at http://localhost:{port}")
            print(f"Forwarding requests to {TARGET_API}")
            print("Press Ctrl+C to stop the server")
            
            # Start the server
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nProxy server stopped")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            if port < PROXY_PORT + 10:  # Try up to 10 alternative ports
                print(f"Port {port} is already in use. Trying port {port + 1}...")
                # Try an alternative port
                run_proxy(port + 1)
            else:
                print(f"All ports from {PROXY_PORT} to {PROXY_PORT + 10} are in use.")
                print("Please choose a different port or stop the process using that port.")
                sys.exit(1)
        else:
            raise

if __name__ == "__main__":
    run_proxy()
