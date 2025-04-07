#!/usr/bin/env python3
"""
Simple HTTP server for the Event Moderation Interface

This script starts a local web server to serve the Event Moderation Interface.
It's a convenient way to test the interface without setting up a separate web server.
"""

import http.server
import socketserver
import os
import sys
import webbrowser
from urllib.parse import urlparse

# Configuration
PORT = 9000  # Using a less common port to avoid conflicts
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler that serves from the current directory"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        # Add CORS headers to allow API requests
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, PATCH, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type, Authorization')
        super().end_headers()
    
    def do_OPTIONS(self):
        # Handle preflight requests
        self.send_response(200)
        self.end_headers()

def run_server(port=PORT):
    """Start the HTTP server and open the browser"""
    
    # Change to the directory containing the interface files
    os.chdir(DIRECTORY)
    
    try:
        # Create the server
        with socketserver.TCPServer(("", port), Handler) as httpd:
            url = f"http://localhost:{port}"
            print(f"Serving Event Moderation Interface at {url}")
            print("Press Ctrl+C to stop the server")
            
            # Open the browser
            webbrowser.open(url)
            
            # Start the server
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            if port < PORT + 10:  # Try up to 10 alternative ports
                print(f"Port {port} is already in use. Trying port {port + 1}...")
                # Try an alternative port
                run_server(port + 1)
            else:
                print(f"All ports from {PORT} to {PORT + 10} are in use.")
                print("\nTo fix this issue, you can:")
                print("1. Edit serve.py to use a different port range")
                print("2. Find and stop processes using these ports:")
                print("   On macOS/Linux: lsof -i :<port>")
                print("   On Windows: netstat -ano | findstr :<port>")
                print("3. Use a different web server to host the interface")
                sys.exit(1)
        else:
            raise

if __name__ == "__main__":
    run_server()
