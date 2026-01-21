"""
AAS HTTP Server Module

This module provides a simple HTTP server that exposes the live AAS instance.
When a sensor is active, other systems can query this endpoint to get
information about the sensor, its capabilities, and its current status.

Endpoints:
- GET /shell         - Returns the complete AAS shell JSON
- GET /submodels     - Returns all submodels
- GET /health        - Returns server health status
- GET /              - Returns API information

This server runs in a background thread and can be started/stopped
as sensors are connected and disconnected.
"""

import json
import logging
import threading
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional, Dict, Any

logger = logging.getLogger('AASServer')

# --- 1. Custom Server Class for Address Reuse ---
class ReusableThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """
    Custom HTTPServer that:
    1. Is multi-threaded (handles multiple requests at once).
    2. Allows immediate address reuse (fixes [Errno 98] Address already in use).
    """
    allow_reuse_address = True  # <--- CRITICAL FIX
    daemon_threads = True


class AASRequestHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for AAS endpoints.
    """
    
    # Reference to the AAS data (set by the server)
    aas_data: Optional[Dict[str, Any]] = None
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"HTTP: {args[0]}")
    
    def _send_json_response(self, data: Any, status: int = 200):
        """Send a JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # Enable CORS
        self.end_headers()
        
        response_body = json.dumps(data, indent=2)
        try:
            self.wfile.write(response_body.encode('utf-8'))
        except BrokenPipeError:
            pass # Client disconnected early
    
    def _send_error_response(self, message: str, status: int = 500):
        """Send an error response."""
        self._send_json_response({'error': message}, status)
    
    def do_GET(self):
        """Handle GET requests."""
        path = self.path.split('?')[0]  # Remove query parameters
        
        try:
            if path == '/' or path == '':
                self._handle_root()
            elif path == '/shell':
                self._handle_shell()
            elif path == '/submodels':
                self._handle_submodels()
            elif path == '/health':
                self._handle_health()
            else:
                self._send_error_response(f"Unknown endpoint: {path}", 404)
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self._send_error_response(str(e), 500)
    
    def _handle_root(self):
        """Handle root endpoint - API information."""
        info = {
            'service': 'AAS Plug-and-Play Edge Server',
            'version': '2.0',
            'endpoints': {
                '/shell': 'Get the complete AAS shell',
                '/submodels': 'Get all submodels',
                '/health': 'Health check',
            },
            'status': 'active' if self.aas_data else 'no_sensor'
        }
        self._send_json_response(info)
    
    def _handle_shell(self):
        """Handle /shell endpoint - return complete AAS."""
        if not self.aas_data:
            self._send_error_response("No sensor active", 503)
            return
        
        self._send_json_response(self.aas_data)
    
    def _handle_submodels(self):
        """Handle /submodels endpoint - return all submodels."""
        if not self.aas_data:
            self._send_error_response("No sensor active", 503)
            return
        
        submodels = self.aas_data.get('submodels', [])
        self._send_json_response({'submodels': submodels, 'count': len(submodels)})
    
    def _handle_health(self):
        """Handle /health endpoint - return health status."""
        health = {
            'status': 'healthy',
            'sensor_active': self.aas_data is not None,
        }
        
        if self.aas_data:
            health['aas_id'] = self.aas_data.get('id', 'unknown')
            health['aas_idshort'] = self.aas_data.get('idShort', 'unknown')
        
        self._send_json_response(health)


class AASServer:
    """
    HTTP server for exposing the live AAS instance.
    """

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.is_running = False

        logger.info(f"AAS Server initialized: {host}:{port}")

    def set_aas_data(self, aas_data: Dict[str, Any]):
        AASRequestHandler.aas_data = aas_data

    def clear_aas_data(self):
        AASRequestHandler.aas_data = None

    def start(self):
        if self.is_running:
            logger.warning("Server already running.")
            return

        try:
            # Use our Custom Reusable Server
            self.server = ReusableThreadingHTTPServer((self.host, self.port), AASRequestHandler)
            self.is_running = True

            self.server_thread = threading.Thread(
                target=self._serve_loop,
                daemon=True,
                name="AASServer"
            )
            self.server_thread.start()

            logger.info(f"AAS Server started on http://{self.host}:{self.port}")

        except OSError as e:
            if e.errno == 98:
                logger.error(f"Port {self.port} is busy. Killing old process might be required.")
            raise
        except Exception as e:
            logger.error(f"Failed to start AAS Server: {e}")
            self.is_running = False
            raise

    def _serve_loop(self):
        """Run the server loop."""
        if self.server:
            self.server.serve_forever()

    def stop(self):
        if not self.is_running:
            return

        logger.info("Stopping AAS Server...")
        self.is_running = False

        if self.server:
            self.server.shutdown() # Stops serve_forever()
            self.server.server_close() # Closes socket

        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)

        self.clear_aas_data()
        logger.info("AAS Server stopped")


# =============================================================================
# STANDALONE TESTING
# =============================================================================

if __name__ == '__main__':
    import time
    
    logging.basicConfig(level=logging.DEBUG)
    
    print("Testing AAS Server")
    print("=" * 40)
    
    # Create sample AAS data
    sample_aas = {
        "id": "urn:test:aas:1",
        "idShort": "TestSensor",
        "submodels": []
    }
    
    # Create and start server
    # Use 0.0.0.0 to listen on all interfaces (including external access)
    server = AASServer("0.0.0.0", 8080) 
    server.set_aas_data(sample_aas)
    
    try:
        server.start()
        print("\nServer is running on http://localhost:8080")
        print("Press Ctrl+C to stop...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        server.stop()
    except Exception as e:
        print(f"Error: {e}")
    
    print("Test complete")