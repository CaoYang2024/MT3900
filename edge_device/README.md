# AAS Plug-and-Play Edge Agent (Simplified Version)

This is a simplified, efficient implementation of the AAS Plug-and-Play Bootstrap Agent. It runs directly on the Raspberry Pi host system (not in a container), which eliminates the complexity of udev-to-IPC communication chains while maintaining all the core functionality.

## Architecture Overview

The system follows a clean separation of concerns:

```
┌─────────────────────────────────────────────────────────────────┐
│                         HOST PC                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │    BaSyx     │  │    BaSyx     │  │    Cloud Proxy       │  │
│  │   Registry   │  │  Repository  │  │    (FastAPI)         │  │
│  │   :8082      │  │    :8081     │  │      :5000           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      RASPBERRY PI                                │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │              Bootstrap Agent (Python)                       │ │
│  │                 runs directly on host                       │ │
│  │                                                             │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │ │
│  │  │  pyudev     │  │   Cloud     │  │   Container         │ │ │
│  │  │  Monitor    │→ │   Client    │→ │   Manager           │ │ │
│  │  │  (USB)      │  │   (HTTP)    │  │   (Docker SDK)      │ │ │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │ │
│  │         │                                    │              │ │
│  │         │              ┌─────────────────────┘              │ │
│  │         ▼              ▼                                    │ │
│  │  ┌─────────────┐  ┌─────────────────────────────────────┐  │ │
│  │  │  AAS HTTP   │  │      Driver Container               │  │ │
│  │  │  Server     │  │      (e.g., camera-driver:latest)   │  │ │
│  │  │  :8080      │  │                                     │  │ │
│  │  └─────────────┘  └─────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌──────────────────┐                                           │
│  │   USB Sensor     │ ◄── Physical connection                   │
│  │   (Camera etc.)  │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

**Agent Runs on Host**: The bootstrap agent runs directly on the Raspberry Pi's host OS, not inside a Docker container. This provides direct access to USB events via pyudev, eliminating the need for udev rules, shell scripts, and IPC sockets.

**Drivers Run in Containers**: Only the sensor drivers run inside Docker containers. This provides isolation, portability, and easy lifecycle management for drivers.

**Single-Sensor Mode**: The system supports one active sensor at a time. This simplifies resource management and avoids conflicts.

**AAS-Driven Configuration**: All sensor configuration comes from the Asset Administration Shell (AAS) retrieved from the cloud. No local configuration is needed per sensor type.

## Prerequisites

Before installing, ensure you have:

1. **Raspberry Pi** with Raspberry Pi OS (Bullseye or later)
2. **Python 3.7+** with pip
3. **Docker** installed and running
4. **Network connectivity** to your Host PC

Install system dependencies:

```bash
sudo apt update
sudo apt install python3-pip python3-dev docker.io avahi-daemon
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER  # Allow non-root Docker access (logout/login required)
```

## Installation

### Option 1: Quick Install (Recommended)

```bash
# Clone or copy the edge-agent directory to your Pi
cd edge-agent-simplified

# Run the installation script
sudo ./install.sh
```

This installs the agent as a systemd service that starts automatically on boot.

### Option 2: Manual Installation

```bash
# Install Python dependencies
pip3 install -r requirements.txt

# Edit configuration
cp config.yaml.example config.yaml
nano config.yaml  # Set your Host PC's IP address

# Run manually (for testing)
python3 bootstrap_agent.py
```

## Configuration

The agent can be configured in three ways (in order of precedence):

1. **Environment variables** (highest priority)
2. **config.yaml file**
3. **Default values** (lowest priority)

### Key Configuration Options

| Setting | Environment Variable | Description |
|---------|---------------------|-------------|
| Cloud URL | `CLOUD_REPO_URL` | URL of the OEM cloud proxy (e.g., `http://192.168.137.1:5000`) |
| Edge ID | `EDGE_ID` | Unique identifier for this edge device (e.g., `pi-01`) |
| AAS Port | `AAS_SERVER_PORT` | Port for the local AAS HTTP server (default: `8080`) |
| Log Level | `LOG_LEVEL` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Editing Configuration

If installed as a service, edit `/etc/default/aas-pnp-agent`:

```bash
sudo nano /etc/default/aas-pnp-agent
```

Then restart the service:

```bash
sudo systemctl restart aas-pnp-agent
```

## Usage

### Viewing Logs

```bash
# If running as a service
journalctl -u aas-pnp-agent -f

# If running manually
python3 bootstrap_agent.py  # Logs appear in terminal
```

### Service Management

```bash
# Check status
systemctl status aas-pnp-agent

# Start/Stop/Restart
sudo systemctl start aas-pnp-agent
sudo systemctl stop aas-pnp-agent
sudo systemctl restart aas-pnp-agent

# View recent logs
journalctl -u aas-pnp-agent -n 50
```

### Testing USB Detection

You can test USB detection without the full agent:

```bash
cd edge-agent
python3 -m core.hw_detector
```

This will scan for connected devices and monitor for plug/unplug events.

## Workflow

When you plug in a USB sensor:

1. **Detection**: pyudev detects the USB add event and extracts VID/PID
2. **Signature Generation**: Creates signature like `usb_vid_05a3_pid_9331`
3. **Cloud Lookup**: Queries the cloud proxy for an AAS matching the signature
4. **Driver Extraction**: Parses the AAS to find the container image URL
5. **Container Deployment**: Pulls and starts the driver container
6. **AAS Server Start**: Exposes the live AAS instance on port 8080
7. **mDNS Advertisement**: Advertises the service for discovery

When you unplug the sensor:

1. **Detection**: pyudev detects the USB remove event
2. **mDNS Stop**: Stops advertising the service
3. **AAS Server Stop**: Shuts down the HTTP server
4. **Container Stop**: Stops and removes the driver container
5. **System Unlock**: Ready for a new sensor

## Project Structure

```
edge-agent/
├── bootstrap_agent.py      # Main entry point
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
├── install.sh              # Installation script
│
├── core/                   # Core modules
│   ├── __init__.py
│   ├── hw_detector.py      # USB detection with pyudev
│   ├── cloud_client.py     # HTTP client for cloud proxy
│   ├── container_mgr.py    # Docker container management
│   └── aas_processor.py    # AAS JSON parsing
│
└── live_server/            # Runtime server modules
    ├── __init__.py
    ├── aas_server.py       # HTTP server for AAS
    └── mdns_advertiser.py  # mDNS service discovery
```

## Troubleshooting

### "No AAS found for signature"

This means the cloud proxy doesn't have an AAS registered for your sensor. You need to:

1. Create an AAS JSON file for your sensor
2. Register it with BaSyx using the registration script
3. Use the correct hardware signature (check with `lsusb`)

### "Cannot connect to cloud"

Check that:

1. The `CLOUD_REPO_URL` is set to your Host PC's actual IP address
2. The cloud proxy is running on the Host PC
3. There's no firewall blocking port 5000
4. The Pi and Host PC are on the same network

Test connectivity:

```bash
curl http://YOUR_HOST_IP:5000/health
```

### "Permission denied" for Docker

Either run the agent as root (via systemd service) or add your user to the docker group:

```bash
sudo usermod -aG docker $USER
# Then logout and login again
```

### USB device not detected

Check that pyudev can see the device:

```bash
python3 -c "import pyudev; c = pyudev.Context(); print([d.get('ID_MODEL') for d in c.list_devices(subsystem='usb') if d.device_type == 'usb_device'])"
```

Also verify with `lsusb`:

```bash
lsusb
```

### Service won't start

Check the journal for errors:

```bash
journalctl -u aas-pnp-agent -n 100 --no-pager
```

Common issues:
- Missing Python dependencies
- Invalid configuration
- Docker not running

## Comparison with Containerized Version

| Aspect | Simplified (This Version) | Containerized (Original) |
|--------|---------------------------|--------------------------|
| Agent Location | Host system | Docker container |
| USB Detection | Direct pyudev | udev → shell → IPC → container |
| Complexity | Lower | Higher |
| Debugging | Easier | Harder |
| Portability | Requires pyudev (Linux) | Theoretically portable |
| Reproducibility | Depends on host | Container provides isolation |

For a thesis prototype where the goal is to demonstrate the concept, this simplified version is recommended because it's easier to understand, debug, and explain.

## License

MIT License - See LICENSE file for details.
