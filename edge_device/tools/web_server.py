import subprocess
import os
import sys
import signal
import time
from flask import Flask, render_template_string, request, jsonify

# ================= CONFIG =================
AGENT_SCRIPT = "bootstrap_agent.py"     # Filename of your core agent script
TTYD_PORT = 7681                        # Port where ttyd runs (WebSocket)
WEB_PORT = 9000                         # Port for web access (No sudo needed for > 1024)
# ==========================================

app = Flask(__name__)
ttyd_process = None

def safe_pkill(pattern):
    """
    Helper to run pkill. If permission is denied, it automatically tries again with sudo.
    """
    cmd = f"pkill -f '{pattern}'"
    try:
        # First attempt: Normal kill
        result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE, text=True)
        
        # Check for permission error
        if "Operation not permitted" in result.stderr:
            print(f"⚠️  Permission denied for '{pattern}'. Retrying with sudo...")
            
            # Second attempt: Sudo kill (Works if Pi has passwordless sudo)
            sudo_cmd = f"sudo {cmd}"
            subprocess.run(sudo_cmd, shell=True)
            print(f"[*] Successfully stopped '{pattern}' using sudo.")
            
        elif result.returncode == 0:
            print(f"[*] Successfully stopped processes matching: {pattern}")
            
    except Exception as e:
        print(f"Error during cleanup of {pattern}: {e}")

def force_cleanup():
    """
    Aggressively kills any existing ttyd or agent processes on the system.
    This fixes the issue where processes remain alive after the web server restarts.
    """
    print("[*] Cleaning up stale background processes...")
    
    # 1. Kill any ttyd process running on our specific port
    safe_pkill(f"ttyd -p {TTYD_PORT}")
    
    # 2. Kill any python process running our agent script
    safe_pkill(AGENT_SCRIPT)
    
    # 3. Optional: Kill camera_driver if it tends to get stuck
    safe_pkill("camera_driver.py")
    
    # Wait a moment for the OS to release the ports
    time.sleep(1)

def start_ttyd():
    """
    Starts ttyd and executes `python3 -u agent.py`
    """
    global ttyd_process
    
    # Always force cleanup before starting to ensure a clean slate
    force_cleanup()

    script_path = os.path.abspath(AGENT_SCRIPT)
    
    if not os.path.exists(script_path):
        print(f"Error: Cannot find {script_path}")
        return

    cmd = [
        "/usr/local/bin/ttyd",
        "-p", str(TTYD_PORT),
        "-W",                                     
        "-t", "fontSize=14",                      
        "-t", "theme={'background': '#1e1e1e'}",  
        "python3", "-u", script_path              
    ]

    print(f"[*] Launching Agent via ttyd: {' '.join(cmd)}")
    
    # Start the new session
    ttyd_process = subprocess.Popen(
        cmd, 
        stdout=subprocess.DEVNULL, 
        stderr=subprocess.DEVNULL,
        start_new_session=True 
    )

@app.route('/')
def index():
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>AAS Agent Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body, html {{ height: 100%; background-color: #121212; color: #e0e0e0; }}
            .sidebar {{ height: 100vh; border-right: 1px solid #333; padding: 20px; background: #1e1e1e; }}
            .terminal-container {{ height: 100%; padding: 0; display: flex; flex-direction: column; }}
            iframe {{ flex-grow: 1; width: 100%; border: none; }}
            .status-dot {{ height: 10px; width: 10px; background-color: #28a745; border-radius: 50%; display: inline-block; margin-right: 5px;}}
            .btn-restart {{ width: 100%; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container-fluid h-100">
            <div class="row h-100">
                <div class="col-md-3 col-lg-2 sidebar">
                    <h5 class="mb-4">🤖 AAS Agent</h5>
                    
                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-body p-3">
                            <small class="text-muted">Status</small>
                            <div class="fw-bold mt-1">
                                <span class="status-dot"></span> Active
                            </div>
                        </div>
                    </div>

                    <div class="card bg-dark border-secondary mb-3">
                        <div class="card-body p-3">
                            <small class="text-muted">Edge ID</small>
                            <div class="fw-bold mt-1">pi-01</div>
                        </div>
                    </div>

                    <button id="restartBtn" class="btn btn-danger btn-restart">
                        ⚠️ Restart Agent Service
                    </button>
                    
                    <div class="mt-4 text-muted small">
                        <p>Web Port: {WEB_PORT}</p>
                        <p>TTY Port: {TTYD_PORT}</p>
                    </div>
                </div>

                <div class="col-md-9 col-lg-10 terminal-container">
                    <iframe src="http://{request.host.split(':')[0]}:{TTYD_PORT}" id="termFrame"></iframe>
                </div>
            </div>
        </div>

        <script>
            document.getElementById('restartBtn').addEventListener('click', function() {{
                if(!confirm('Are you sure you want to force restart the Agent? This will interrupt current USB tasks.')) return;
                
                fetch('/restart', {{ method: 'POST' }})
                    .then(response => response.json())
                    .then(data => {{
                        alert('Agent has been restarted');
                        document.getElementById('termFrame').src = document.getElementById('termFrame').src;
                    }});
            }});
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/restart', methods=['POST'])
def restart_service():
    """API: Restarts the backend Agent"""
    print("[!] Restart command received via Web UI")
    start_ttyd()
    return jsonify({"status": "restarted", "timestamp": time.time()})

def cleanup(signum, frame):
    """Shuts down ttyd when the Web Server stops."""
    print("\n[*] Shutting down Dashboard & Agent...")
    force_cleanup()
    sys.exit(0)

if __name__ == '__main__':
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Initial cleanup of any zombie processes from previous runs
    force_cleanup()
    
    # Start fresh
    start_ttyd()

    print(f"[*] Dashboard running at http://0.0.0.0:{WEB_PORT}")
    app.run(host='0.0.0.0', port=WEB_PORT, debug=False)