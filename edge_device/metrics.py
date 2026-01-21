#!/usr/bin/env python3
"""
metrics.py - Evaluation Metrics Collector (Enhanced)
====================================================
Updated for Edge Evaluation (Raspberry Pi)
Key Features:
  - Time-to-Operational (TTO) tracking
  - System Resource Monitoring (CPU, RAM, Temp)
"""

import json
import time
import statistics
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict

# Try to import psutil for resource monitoring
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: 'psutil' module not found. Resource tracking will be limited.")


@dataclass
class ResourceSample:
    """Snapshot of system resources at a specific moment."""
    timestamp: float
    stage: str
    cpu_percent: float      # Overall CPU usage (%)
    memory_mb: float        # RAM usage (MB)
    temperature_c: float    # CPU Temperature (°C)
    power_w: float = 0.0    # Placeholder for power (requires external sensor)


@dataclass
class RunMetrics:
    """Metrics for a single plug-and-play run."""
    
    # --- Identification ---
    run_id: str = ""
    signature: str = ""
    sensor_name: str = ""
    timestamp: str = ""
    edge_id: str = ""
    
    # --- Timestamps (TTO Logic) ---
    t_detected: float = 0.0
    t_lookup_start: float = 0.0
    t_aas_received: float = 0.0
    t_parse_complete: float = 0.0
    t_pull_start: float = 0.0
    t_pull_complete: float = 0.0
    t_container_started: float = 0.0
    t_container_ready: float = 0.0
    t_aas_server_ready: float = 0.0
    t_mdns_advertised: float = 0.0
    
    # --- Durations (ms) ---
    duration_detection_ms: float = 0.0
    duration_lookup_ms: float = 0.0
    duration_parse_ms: float = 0.0
    duration_pull_ms: float = 0.0
    duration_start_ms: float = 0.0
    duration_advertise_ms: float = 0.0
    total_tto_ms: float = 0.0
    
    # --- System Resources ---
    # List of samples taken at each checkpoint
    resource_samples: List[Dict] = field(default_factory=list)
    
    # Peak stats for quick summary
    peak_cpu_percent: float = 0.0
    peak_memory_mb: float = 0.0
    peak_temp_c: float = 0.0
    
    # --- Status ---
    success: bool = False
    error_message: str = ""
    image_cached: bool = False
    container_image: str = ""


class ResourceMonitor:
    """Helper class to fetch Raspberry Pi system metrics."""
    
    @staticmethod
    def get_cpu_temp() -> float:
        """Reads CPU temperature from Raspberry Pi thermal zone."""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                temp_str = f.read()
            return float(temp_str) / 1000.0
        except FileNotFoundError:
            return 0.0  # Not a Pi or file missing

    @staticmethod
    def snapshot(stage_name: str) -> ResourceSample:
        """Captures current system state."""
        cpu = 0.0
        mem = 0.0
        
        if PSUTIL_AVAILABLE:
            # interval=None is non-blocking, returns usage since last call
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().used / (1024 * 1024)  # Convert bytes to MB
            
        temp = ResourceMonitor.get_cpu_temp()
        
        return ResourceSample(
            timestamp=time.time(),
            stage=stage_name,
            cpu_percent=round(cpu, 2),
            memory_mb=round(mem, 2),
            temperature_c=round(temp, 2)
        )


class MetricsCollector:
    """Collects and stores metrics for plug-and-play evaluation."""

    def __init__(self, output_dir: str = "./evaluation_results"):
        self.output_dir = output_dir
        self.current_run: Optional[RunMetrics] = None
        self._run_counter = 0
        
        os.makedirs(output_dir, exist_ok=True)
        self._load_existing()
        
        # Initialize CPU counter for psutil
        if PSUTIL_AVAILABLE:
            psutil.cpu_percent(interval=None)

    def _load_existing(self):
        filepath = os.path.join(self.output_dir, "metrics.json")
        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                    self._run_counter = data.get("run_counter", 0)
            except:
                pass

    def start_run(self, signature: str, edge_id: str = ""):
        """Start tracking a new plug-and-play run."""
        self._run_counter += 1

        self.current_run = RunMetrics(
            run_id=f"run_{self._run_counter:04d}",
            signature=signature,
            edge_id=edge_id,
            timestamp=datetime.now().isoformat(),
            t_detected=time.time()
        )
        
        # Take initial baseline resource sample
        self._record_resource("start")
        return self.current_run.run_id

    def mark(self, checkpoint: str):
        """Mark timestamp for a specific event and sample resources."""
        if not self.current_run:
            return
        
        now = time.time()
        mapping = {
            "detected": "t_detected",
            "lookup_start": "t_lookup_start",
            "aas_received": "t_aas_received",
            "parse_complete": "t_parse_complete",
            "pull_start": "t_pull_start",
            "pull_complete": "t_pull_complete",
            "container_started": "t_container_started",
            "container_ready": "t_container_ready",
            "aas_server_ready": "t_aas_server_ready",
            "mdns_advertised": "t_mdns_advertised",
        }

        if checkpoint in mapping:
            setattr(self.current_run, mapping[checkpoint], now)
        
        # Sample resources at this checkpoint
        self._record_resource(checkpoint)

    def _record_resource(self, stage: str):
        """Internal helper to add a resource sample."""
        if self.current_run:
            sample = ResourceMonitor.snapshot(stage)
            # We convert dataclass to dict for JSON serialization later
            self.current_run.resource_samples.append(asdict(sample))

    def set_info(self, **kwargs):
        if not self.current_run:
            return
        for key, value in kwargs.items():
            if hasattr(self.current_run, key):
                setattr(self.current_run, key, value)

    def end_run(self, success: bool, sensor_name: str = "", error_message: str = ""):
        if not self.current_run:
            return None

        run = self.current_run
        run.success = success
        run.error_message = error_message
        if sensor_name:
            run.sensor_name = sensor_name

        # --- Calculate Durations ---
        def ms(t_end, t_start):
            return (t_end - t_start) * 1000 if (t_end > 0 and t_start > 0) else 0.0

        run.duration_detection_ms = ms(run.t_lookup_start, run.t_detected)
        run.duration_lookup_ms = ms(run.t_aas_received, run.t_lookup_start)
        run.duration_parse_ms = ms(run.t_parse_complete, run.t_aas_received)
        run.duration_pull_ms = ms(run.t_pull_complete, run.t_pull_start)
        run.image_cached = run.duration_pull_ms < 1000
        run.duration_start_ms = ms(run.t_container_ready, run.t_container_started)
        run.duration_advertise_ms = ms(run.t_mdns_advertised, run.t_aas_server_ready)

        end_point = (run.t_mdns_advertised or run.t_aas_server_ready or 
                     run.t_container_ready or run.t_container_started)
        run.total_tto_ms = ms(end_point, run.t_detected)

        # --- Calculate Resource Peaks ---
        if run.resource_samples:
            run.peak_cpu_percent = max(s['cpu_percent'] for s in run.resource_samples)
            run.peak_memory_mb = max(s['memory_mb'] for s in run.resource_samples)
            run.peak_temp_c = max(s['temperature_c'] for s in run.resource_samples)

        self._save_run(run)
        self.current_run = None
        return run

    def abort_run(self, error_message: str = ""):
        return self.end_run(success=False, error_message=error_message)

    def _save_run(self, run: RunMetrics):
        filepath = os.path.join(self.output_dir, "metrics.json")
        data = {"run_counter": self._run_counter, "runs": []}

        if os.path.exists(filepath):
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
            except:
                pass

        data["run_counter"] = self._run_counter
        data["runs"].append(asdict(run))

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def get_summary(self) -> Dict:
        # (Same simple summary logic, could be extended to show resource stats)
        filepath = os.path.join(self.output_dir, "metrics.json")
        if not os.path.exists(filepath): return {"error": "No data"}
        
        with open(filepath, "r") as f:
            data = json.load(f)
        runs = data.get("runs", [])
        ok = [r for r in runs if r.get("success")]
        
        if not ok: return {"error": "No successful runs"}

        # Helper for stats
        def stats(vals):
            if not vals: return {}
            return {
                "mean": round(statistics.mean(vals), 2),
                "max": round(max(vals), 2)
            }

        return {
            "total_runs": len(runs),
            "success_rate": round(len(ok)/len(runs)*100, 1),
            "tto_ms": stats([r["total_tto_ms"] for r in ok]),
            "peak_cpu": stats([r.get("peak_cpu_percent", 0) for r in ok]),
            "peak_mem": stats([r.get("peak_memory_mb", 0) for r in ok]),
            "peak_temp": stats([r.get("peak_temp_c", 0) for r in ok]),
        }

# =============================================================================
# CLI / REPORT
# =============================================================================

def print_summary(output_dir: str = "./evaluation_results"):
    collector = MetricsCollector(output_dir)
    s = collector.get_summary()
    
    if "error" in s:
        print(f"Status: {s['error']}")
        return

    print("\n" + "="*60)
    print(" EDGE PERFORMANCE REPORT (Raspberry Pi)")
    print("="*60)
    print(f" Runs: {s['total_runs']} | Success: {s['success_rate']}%")
    print("-" * 60)
    print(f" Latency (TTO):     Mean: {s['tto_ms']['mean']} ms | Max: {s['tto_ms']['max']} ms")
    print(f" CPU Load (Peak):   Mean: {s['peak_cpu']['mean']}%  | Max: {s['peak_cpu']['max']}%")
    print(f" RAM Usage (Peak):  Mean: {s['peak_mem']['mean']} MB | Max: {s['peak_mem']['max']} MB")
    print(f" Temperature:       Mean: {s['peak_temp']['mean']} °C | Max: {s['peak_temp']['max']} °C")
    print("="*60 + "\n")

if __name__ == "__main__":
    output = sys.argv[1] if len(sys.argv) > 1 else "./evaluation_results"
    print_summary(output)