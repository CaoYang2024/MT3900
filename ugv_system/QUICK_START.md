# PnP Sensor Monitor - Quick Start

## One-Time Setup (5 minutes)

```bash
# 1. Install dependencies
sudo apt install -y docker.io python3-pip
sudo usermod -aG docker $USER
pip3 install docker requests pyyaml
# LOGOUT AND LOGIN AGAIN for docker group to take effect

# 2. Extract package
cd ~/rr100_user_ws/src
unzip pnp_sensor_monitor.zip

# 3. Configure Pi IP address
nano pnp_sensor_monitor/config/config.yaml
# Change pi_address to your Pi's IP (default: 192.168.137.221)

# 4. Build
cd ~/rr100_user_ws
catkin_make
source devel/setup.bash
```

## Running

```bash
# Start the monitor
roslaunch pnp_sensor_monitor monitor.launch

# Or with different Pi IP
roslaunch pnp_sensor_monitor monitor.launch pi_address:=192.168.1.100
```

## What Happens

| Event | Monitor Action |
|-------|---------------|
| Sensor plugged into Pi | Detects AAS → Starts Application container |
| Sensor unplugged from Pi | Stops Application container |

## Useful Commands

```bash
# Check running containers
docker ps | grep pnp-app

# View application logs
docker logs pnp-app-camera

# Test Pi connection (health check)
curl http://192.168.137.221:8080/health

# Test Pi connection (full AAS)
curl http://192.168.137.221:8080/shell

# Stop all pnp containers
docker stop $(docker ps -q --filter "name=pnp-app")
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker permission denied | Logout and login (after usermod) |
| Cannot reach Pi | Check `ping 192.168.137.221` |
| Package not found | Run `source ~/rr100_user_ws/devel/setup.bash` |
| App won't start | Check `docker logs pnp-app-camera` |
| "No sensor active" | Plug USB sensor into Pi first |
