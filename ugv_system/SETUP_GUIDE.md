# PnP Sensor Monitor - Setup Guide

Complete setup guide for installing and configuring the PnP Sensor Monitor package on the UGV (RR100).

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Network Setup](#2-network-setup)
3. [Install the Package](#3-install-the-package)
4. [Configure the Package](#4-configure-the-package)
5. [Build the Workspace](#5-build-the-workspace)
6. [Test the Setup](#6-test-the-setup)
7. [Run the Monitor](#7-run-the-monitor)
8. [Verify End-to-End](#8-verify-end-to-end)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

### 1.1 System Requirements

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Ubuntu | 20.04 | `lsb_release -a` |
| ROS | Noetic | `rosversion -d` |
| Python | 3.8+ | `python3 --version` |
| Docker | 20.10+ | `docker --version` |

### 1.2 Install Docker (if not already installed)

```bash
# Update package list
sudo apt update

# Install Docker
sudo apt install -y docker.io

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add your user to docker group (IMPORTANT!)
sudo usermod -aG docker $USER

# Apply group changes (or logout/login)
newgrp docker

# Verify Docker works without sudo
docker ps
```

### 1.3 Install Python Dependencies

```bash
# Install pip if needed
sudo apt install -y python3-pip

# Install required Python packages
pip3 install docker requests pyyaml

# Verify installation
python3 -c "import docker; import requests; import yaml; print('All dependencies OK')"
```

### 1.4 Verify ROS Environment

```bash
# Source ROS
source /opt/ros/noetic/setup.bash

# Verify ROS is working
roscore &
sleep 2
rosnode list
killall roscore
```

---

## 2. Network Setup

### 2.1 Network Architecture

The student's setup uses the 192.168.137.x network:

```
┌─────────────────────────────────────────────────────────────┐
│                       Network                                │
│                                                              │
│   ┌─────────────────┐         ┌─────────────────┐           │
│   │    UGV / PC     │         │  Raspberry Pi   │           │
│   │   (Monitor)     │◄───────►│  (Edge Agent)   │           │
│   │ 192.168.137.1   │ Network │ 192.168.137.221 │           │
│   └─────────────────┘         └─────────────────┘           │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Cloud Proxy: http://192.168.137.1:5000 (runs on Host PC)
AAS Server:  http://192.168.137.221:8080 (runs on Pi)
```

### 2.2 Verify Network Connectivity

```bash
# Find your Pi's IP address (run this on Pi)
# hostname -I

# On UGV/PC, verify you can reach the Pi
ping 192.168.137.221 -c 3

# Expected output:
# PING 192.168.137.221 (192.168.137.221) 56(84) bytes of data.
# 64 bytes from 192.168.137.221: icmp_seq=1 ttl=64 time=0.5 ms
```

### 2.3 Test AAS Endpoint (when Pi Edge Agent is running)

```bash
# Health check (lightweight)
curl http://192.168.137.221:8080/health

# Full AAS (when sensor is active)
curl http://192.168.137.221:8080/shell

# If no sensor active, expect:
# {"error": "No sensor active"}  (HTTP 503)
# If sensor active, expect JSON response with AAS data
```

---

## 3. Install the Package

### 3.1 Navigate to Your Workspace

```bash
# Go to your user workspace
cd ~/rr100_user_ws/src

# Verify you're in the right place
ls -la
# Should see: CMakeLists.txt, rr100_user_base/, etc.
```

### 3.2 Download and Extract the Package

**Option A: If you have the zip file locally**
```bash
# Copy zip to workspace (adjust path as needed)
cp /path/to/pnp_sensor_monitor.zip ~/rr100_user_ws/src/

# Extract
cd ~/rr100_user_ws/src
unzip pnp_sensor_monitor.zip

# Verify extraction
ls pnp_sensor_monitor/
# Should see: CMakeLists.txt, package.xml, config/, launch/, scripts/, src/
```

**Option B: If transferring from another machine**
```bash
# On source machine (e.g., your laptop)
scp pnp_sensor_monitor.zip user@192.168.1.102:~/rr100_user_ws/src/

# On UGV
cd ~/rr100_user_ws/src
unzip pnp_sensor_monitor.zip
```

### 3.3 Verify Package Structure

```bash
cd ~/rr100_user_ws/src
tree pnp_sensor_monitor/
```

Expected output:
```
pnp_sensor_monitor/
├── CMakeLists.txt
├── package.xml
├── setup.py
├── README.md
├── config/
│   └── config.yaml
├── launch/
│   └── monitor.launch
├── scripts/
│   └── sensor_monitor.py
└── src/
    └── pnp_sensor_monitor/
        ├── __init__.py
        ├── aas_client.py
        └── container_manager.py
```

### 3.4 Make Scripts Executable

```bash
chmod +x ~/rr100_user_ws/src/pnp_sensor_monitor/scripts/sensor_monitor.py
```

---

## 4. Configure the Package

### 4.1 Edit Configuration File

```bash
# Open config file
nano ~/rr100_user_ws/src/pnp_sensor_monitor/config/config.yaml
```

### 4.2 Configuration Options

```yaml
# PnP Sensor Monitor Configuration
# =================================

# Raspberry Pi (Intelligent Sensor Hub) settings
pi_address: "192.168.1.50"    # <-- CHANGE THIS to your Pi's IP
aas_port: 8080                 # Port where Pi serves AAS

# Polling settings
poll_interval_sec: 2.0         # How often to check for sensors

# Container settings
container_prefix: "pnp-app"    # Prefix for Application container names

# Logging
log_level: "INFO"              # DEBUG, INFO, WARN, ERROR
```

### 4.3 Key Settings to Verify

| Setting | Description | How to Find |
|---------|-------------|-------------|
| `pi_address` | IP of Raspberry Pi | Run `hostname -I` on Pi |
| `aas_port` | AAS server port | Default 8080, check Pi edge agent config |
| `poll_interval_sec` | How often to check | 2.0 is good for demo |

Save and exit (`Ctrl+X`, then `Y`, then `Enter` in nano).

---

## 5. Build the Workspace

### 5.1 Build

```bash
# Go to workspace root
cd ~/rr100_user_ws

# Build the workspace
catkin_make

# Expected output (last lines):
# [100%] Built target pnp_sensor_monitor_...
# [100%] Built target ...
```

### 5.2 Source the Workspace

```bash
# Source the setup file
source ~/rr100_user_ws/devel/setup.bash

# TIP: Add to .bashrc for persistence
echo "source ~/rr100_user_ws/devel/setup.bash" >> ~/.bashrc
```

### 5.3 Verify Package is Recognized

```bash
# Check if ROS can find the package
rospack find pnp_sensor_monitor

# Expected output:
# /home/<user>/rr100_user_ws/src/pnp_sensor_monitor

# List available launch files
roslaunch pnp_sensor_monitor <TAB><TAB>
# Should show: monitor.launch
```

---

## 6. Test the Setup

### 6.1 Test Python Imports

```bash
# Test that modules can be imported
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/$USER/rr100_user_ws/src/pnp_sensor_monitor/src')
from pnp_sensor_monitor import AASClient, ContainerManager
print("✓ AASClient imported successfully")
print("✓ ContainerManager imported successfully")
EOF
```

### 6.2 Test Docker Connection

```bash
# Verify Docker SDK works
python3 << 'EOF'
import docker
client = docker.from_env()
client.ping()
print("✓ Docker connection OK")
print(f"  Docker version: {client.version()['Version']}")
EOF
```

### 6.3 Test AAS Client (without Pi)

```bash
# This will fail to connect (expected), but verifies code works
python3 << 'EOF'
import sys
sys.path.insert(0, '/home/$USER/rr100_user_ws/src/pnp_sensor_monitor/src')
from pnp_sensor_monitor import AASClient

client = AASClient(pi_address="192.168.1.50", aas_port=8080)
result = client.get_aas()
if result is None:
    print("✓ AASClient works (no sensor active or Pi not reachable)")
else:
    print(f"✓ AASClient works - found sensor: {result.get('idShort')}")
EOF
```

### 6.4 Test ROS Node Launch (dry run)

```bash
# Start roscore in background
roscore &
sleep 2

# Try launching (will work but won't find sensor)
timeout 5 roslaunch pnp_sensor_monitor monitor.launch || true

# Kill roscore
killall roscore
```

---

## 7. Run the Monitor

### 7.1 Start ROS Master (if not already running)

```bash
# Option A: Start roscore manually
roscore &

# Option B: If using RR100's existing ROS setup, it may already be running
rostopic list  # Check if ROS is up
```

### 7.2 Launch the Sensor Monitor

```bash
# Basic launch
roslaunch pnp_sensor_monitor monitor.launch
```

### 7.3 Launch with Custom Pi Address

```bash
# If Pi has different IP than config file
roslaunch pnp_sensor_monitor monitor.launch pi_address:=192.168.1.100
```

### 7.4 Expected Output (No Sensor Connected)

```
... logging to /home/user/.ros/log/...
SUMMARY
========

PARAMETERS
 * /pnp_sensor_monitor/config_file: /home/user/rr100...
 * /rosdistro: noetic
 * /rosversion: 1.15.14

NODES
  /
    pnp_sensor_monitor (pnp_sensor_monitor/sensor_monitor.py)

auto-starting new master
process[master]: started with pid [12345]
...

[INFO] ==================================================
[INFO] PnP Sensor Monitor initialized
[INFO]   Pi Address: 192.168.1.50
[INFO]   AAS Port:   8080
[INFO]   Poll Rate:  2.0s
[INFO] ==================================================
[INFO] Connected to Docker daemon
[INFO] Sensor Monitor running. Polling for sensors...
```

### 7.5 Expected Output (When Sensor Connects on Pi)

```
[INFO] Sensor detected: HD_Web_Camera
[INFO] Starting Application: st186635/object-detector:v1
[INFO]   Image: st186635/object-detector:v1
[INFO]   Network: host
[INFO]   Env: DRIVER_HOST=192.168.1.50
[INFO]   Env: DRIVER_PORT=8080
[INFO]   Env: SENSOR_TYPE=camera
[INFO]   Env: SENSOR_NAME=HD_Web_Camera
[INFO] Pulling image: st186635/object-detector:v1
[INFO] Image pulled successfully: st186635/object-detector:v1
[INFO] Container started: pnp-app-camera (a1b2c3d4)
[INFO] ==================================================
[INFO] APPLICATION STARTED SUCCESSFULLY
[INFO]   Container: pnp-app-camera
[INFO]   Discovery Time: 45.2 ms
[INFO]   App Start Time: 8340.5 ms
[INFO]   Total Time:     8385.7 ms
[INFO] ==================================================
```

---

## 8. Verify End-to-End

### 8.1 Complete Test Sequence

**Terminal 1 (Pi): Start Edge Agent**
```bash
cd ~/edge-agent-simplified
python3 bootstrap_agent.py
```

**Terminal 2 (UGV): Start Sensor Monitor**
```bash
roslaunch pnp_sensor_monitor monitor.launch
```

**Terminal 3 (UGV): Watch Docker containers**
```bash
watch -n 1 'docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"'
```

**Action: Plug USB sensor into Pi**

**Expected Sequence:**
1. Pi Edge Agent detects sensor, starts driver (Terminal 1)
2. UGV Sensor Monitor detects AAS, starts application (Terminal 2)
3. Docker shows new container running (Terminal 3)

### 8.2 Verify Application is Running

```bash
# Check container is running
docker ps | grep pnp-app

# Check container logs
docker logs pnp-app-camera

# Check container details
docker inspect pnp-app-camera
```

### 8.3 Unplug Test

**Action: Unplug USB sensor from Pi**

**Expected:**
1. Pi Edge Agent stops driver
2. UGV Sensor Monitor detects disconnect, stops application
3. Docker shows container stopped

---

## 9. Troubleshooting

### Problem: "Cannot connect to Docker"

```bash
# Check Docker is running
sudo systemctl status docker

# Check user is in docker group
groups $USER | grep docker

# If not in group, add and relogin
sudo usermod -aG docker $USER
# Then logout and login again!
```

### Problem: "Cannot reach Pi"

```bash
# Check network
ping 192.168.1.50

# Check route
ip route

# Check if Pi's AAS server is running
curl http://192.168.1.50:8080/shell
```

### Problem: "Package not found"

```bash
# Rebuild workspace
cd ~/rr100_user_ws
catkin_make --force-cmake

# Re-source
source devel/setup.bash

# Verify
rospack find pnp_sensor_monitor
```

### Problem: "Module not found" (Python imports)

```bash
# Check PYTHONPATH
echo $PYTHONPATH

# Should include:
# /home/user/rr100_user_ws/devel/lib/python3/dist-packages

# If not, source workspace again
source ~/rr100_user_ws/devel/setup.bash
```

### Problem: "Permission denied" on script

```bash
chmod +x ~/rr100_user_ws/src/pnp_sensor_monitor/scripts/sensor_monitor.py
```

### Problem: Application container fails to start

```bash
# Check if image exists
docker images | grep <image-name>

# Try pulling manually
docker pull st186635/object-detector:v1

# Check Docker logs for errors
docker logs pnp-app-camera
```

### Problem: Application can't connect to driver on Pi

```bash
# From UGV, test driver endpoint directly
curl http://192.168.1.50:8080/data

# Check firewall on Pi
sudo ufw status

# If firewall is blocking, allow port
sudo ufw allow 8080
```

---

## Quick Reference

### Common Commands

| Action | Command |
|--------|---------|
| Start monitor | `roslaunch pnp_sensor_monitor monitor.launch` |
| Check containers | `docker ps` |
| View app logs | `docker logs pnp-app-camera` |
| Stop app manually | `docker stop pnp-app-camera` |
| Test Pi connection | `curl http://192.168.1.50:8080/shell` |
| Rebuild workspace | `cd ~/rr100_user_ws && catkin_make` |

### File Locations

| File | Path |
|------|------|
| Config | `~/rr100_user_ws/src/pnp_sensor_monitor/config/config.yaml` |
| Main script | `~/rr100_user_ws/src/pnp_sensor_monitor/scripts/sensor_monitor.py` |
| Launch file | `~/rr100_user_ws/src/pnp_sensor_monitor/launch/monitor.launch` |
| ROS logs | `~/.ros/log/latest/` |

---

## Next Steps

Once setup is complete:

1. **Update AAS** with your Application container image in the `Application` submodel
2. **Test end-to-end** with both camera and ultrasonic sensors
3. **Collect metrics** for thesis evaluation
4. **Prepare demo** for presentation

---

*Setup Guide - PnP Sensor Monitor v1.0*
*IAS Thesis Project 2025*
