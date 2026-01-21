# PnP Sensor Monitor

A ROS package for the UGV that automatically discovers and integrates Plug-and-Play sensors connected to a Raspberry Pi (Intelligent Sensor Hub).

## Overview

This package is the UGV-side component of the AAS-based Plug-and-Play system. It monitors the Raspberry Pi for available sensors and automatically starts Application containers to consume sensor data.

### How It Works

The flow is straightforward. First, the sensor monitor polls the Pi's AAS endpoint every 2 seconds. When the Pi reports an active sensor via AAS, the monitor extracts the Application container information. It then pulls and runs the Application container on the UGV. Finally, when the sensor disconnects, it stops the Application container.

### Architecture

```
Raspberry Pi (Sensor Hub)              UGV (This Package)
┌─────────────────────┐               ┌─────────────────────────────┐
│                     │               │                             │
│  Driver Container   │◄──────────────│  Application Container      │
│  - Reads sensor     │   REST API    │  - Object detection         │
│  - Exposes /data    │               │  - Distance warnings        │
│                     │               │  - ROS/Kuksa publishing     │
│  AAS Server (:8080) │◄──────────────│                             │
│  - /shell endpoint  │   Poll AAS    │  Sensor Monitor (this pkg)  │
│                     │               │  - Polls Pi for AAS         │
└─────────────────────┘               │  - Starts App containers    │
                                      └─────────────────────────────┘
```

## Installation

### Prerequisites

You need to install the Python dependencies on the UGV:

```bash
pip install docker requests pyyaml
```

Also ensure the user has Docker permissions:

```bash
sudo usermod -aG docker $USER
```

### Install Package

Copy or clone this package to your workspace:

```bash
cd ~/rr100_user_ws/src
cp -r /path/to/pnp_sensor_monitor .
```

Build the workspace:

```bash
cd ~/rr100_user_ws
catkin_make
source devel/setup.bash
```

## Configuration

Edit the config file at `config/config.yaml`:

```yaml
pi_address: "192.168.1.50"    # Your Pi's IP address
aas_port: 8080                 # AAS server port on Pi
poll_interval_sec: 2.0         # Polling interval
container_prefix: "pnp-app"    # Prefix for container names
```

## Usage

### Basic Usage

```bash
roslaunch pnp_sensor_monitor monitor.launch
```

### With Custom Pi Address

```bash
roslaunch pnp_sensor_monitor monitor.launch pi_address:=192.168.1.100
```

### What You'll See

When a sensor is connected to the Pi, you'll see output like:

```
[INFO] Sensor detected: HD_Web_Camera
[INFO] Starting Application: st186635/object-detector:v1
[INFO]   Image: st186635/object-detector:v1
[INFO]   Network: host
[INFO]   Env: DRIVER_HOST=192.168.1.50
[INFO]   Env: DRIVER_PORT=8080
[INFO] ==================================================
[INFO] APPLICATION STARTED SUCCESSFULLY
[INFO]   Container: pnp-app-camera
[INFO]   Discovery Time: 45.2 ms
[INFO]   App Start Time: 2340.5 ms
[INFO]   Total Time:     2385.7 ms
[INFO] ==================================================
```

## For Thesis Evaluation

The monitor logs timing metrics that can be used for evaluation. The key metrics are Discovery Time (time to fetch and parse AAS from Pi), App Start Time (time to pull and start Application container), and Total Integration Time (sum of above). These metrics complement the Edge Agent's TTO metrics to give a complete picture of end-to-end integration time.

## Package Structure

```
pnp_sensor_monitor/
├── CMakeLists.txt
├── package.xml
├── setup.py
├── config/
│   └── config.yaml           # Configuration
├── launch/
│   └── monitor.launch        # Launch file
├── scripts/
│   └── sensor_monitor.py     # Main ROS node
└── src/
    └── pnp_sensor_monitor/
        ├── __init__.py
        ├── aas_client.py      # AAS fetching/parsing
        └── container_manager.py  # Docker management
```

## Troubleshooting

If you cannot connect to Pi, verify network connectivity with `ping 192.168.1.50`, check the Pi's edge agent is running, and ensure the AAS server is accessible with `curl http://192.168.1.50:8080/shell`.

If Docker fails, check Docker is running with `docker ps`, verify user permissions with `groups $USER`, and look at Docker logs with `docker logs pnp-app-camera`.

## License

MIT License - IAS Thesis Project 2025
