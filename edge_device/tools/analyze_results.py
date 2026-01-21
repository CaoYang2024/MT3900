#!/usr/bin/env python3
"""
analyze_results.py - Evaluation Results Analyzer (Robust & Detailed)
==================================================================

Key Improvements:
1. Robust Path Handling: Accepts file or directory paths.
2. Resource Analysis: Calculates both PEAK and AVERAGE load per run.
3. Reporting: Distinguishes between transient spikes and sustained load.
"""

import json
import os
import sys
import argparse
import statistics
from datetime import datetime
from typing import Dict, List


def load_metrics(path_input: str) -> List[Dict]:
    """Load metrics from JSON file or directory containing metrics.json."""
    if os.path.isfile(path_input):
        filepath = path_input
    else:
        filepath = os.path.join(path_input, "metrics1.json")
    
    if not os.path.exists(filepath):
        print(f"Error: Metrics file not found at {filepath}")
        sys.exit(1)
    
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        return data.get('runs', [])
    except Exception as e:
        print(f"Error reading JSON: {e}")
        sys.exit(1)


def calculate_statistics(values: List[float]) -> Dict:
    """Calculate statistical summary of values."""
    values = [v for v in values if v is not None]
    
    if not values:
        return {"n": 0, "mean": 0, "median": 0, "stdev": 0, "min": 0, "max": 0}
    
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
    }


def get_run_resource_stats(run: Dict) -> Dict:
    """Calculates average resource usage for a single run from samples."""
    samples = run.get('resource_samples', [])
    if not samples:
        return {"cpu_avg": 0, "mem_avg": 0, "temp_avg": 0}
    
    return {
        "cpu_avg": statistics.mean([s['cpu_percent'] for s in samples]),
        "mem_avg": statistics.mean([s['memory_mb'] for s in samples]),
        "temp_avg": statistics.mean([s['temperature_c'] for s in samples])
    }


def analyze(runs: List[Dict]) -> Dict:
    """Perform full analysis of runs."""
    successful = [r for r in runs if r.get('success', False)]
    failed = [r for r in runs if not r.get('success', False)]
    
    cached = [r for r in successful if r.get('image_cached', False)]
    uncached = [r for r in successful if not r.get('image_cached', False)]
    
    # Pre-calculate averages for each successful run
    run_averages = [get_run_resource_stats(r) for r in successful]

    analysis = {
        "summary": {
            "total_runs": len(runs),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate_percent": round(len(successful) / len(runs) * 100, 1) if runs else 0,
        },
        
        # --- Time-to-Operational ---
        "tto_all": calculate_statistics([r.get('total_tto_ms', 0) for r in successful]),
        "tto_cached": calculate_statistics([r.get('total_tto_ms', 0) for r in cached]),
        "tto_uncached": calculate_statistics([r.get('total_tto_ms', 0) for r in uncached]),
        
        # --- System Resources (Detailed) ---
        "resources": {
            # Transient Peaks (Instantaneous max during the process)
            "cpu_peak": calculate_statistics([r.get('peak_cpu_percent', 0) for r in successful]),
            "mem_peak": calculate_statistics([r.get('peak_memory_mb', 0) for r in successful]),
            "temp_peak": calculate_statistics([r.get('peak_temp_c', 0) for r in successful]),
            
            # Process Averages (Mean load during the process)
            "cpu_avg": calculate_statistics([x['cpu_avg'] for x in run_averages]),
            "mem_avg": calculate_statistics([x['mem_avg'] for x in run_averages]),
            "temp_avg": calculate_statistics([x['temp_avg'] for x in run_averages]),
        },

        # --- Phases Breakdown ---
        "phases": {
            "lookup": calculate_statistics([r.get('duration_lookup_ms', 0) for r in successful]),
            "parse": calculate_statistics([r.get('duration_parse_ms', 0) for r in successful]),
            "pull": calculate_statistics([r.get('duration_pull_ms', 0) for r in successful]),
            "pull_uncached": calculate_statistics([r.get('duration_pull_ms', 0) for r in uncached]),
            "start": calculate_statistics([r.get('duration_start_ms', 0) for r in successful]),
            "advertise": calculate_statistics([r.get('duration_advertise_ms', 0) for r in successful]),
        },
        
        "by_sensor": {},
        "errors": [r.get('error_message', '') for r in failed if r.get('error_message')],
    }
    
    # Group by sensor type
    for run in successful:
        sensor = run.get('sensor_name', 'Unknown')
        if sensor not in analysis['by_sensor']:
            analysis['by_sensor'][sensor] = []
        analysis['by_sensor'][sensor].append(run.get('total_tto_ms', 0))
    
    # Calculate stats per sensor
    for sensor, values in analysis['by_sensor'].items():
        analysis['by_sensor'][sensor] = calculate_statistics(values)
    
    return analysis


def generate_text_report(analysis: Dict, runs: List[Dict]) -> str:
    """Generate text report suitable for thesis appendix."""
    lines = []
    
    lines.append("=" * 70)
    lines.append("PLUG-AND-PLAY SYSTEM EVALUATION REPORT")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 70)
    
    # Summary
    s = analysis['summary']
    lines.append("\n1. SUMMARY")
    lines.append("-" * 40)
    lines.append(f"   Total test runs:     {s['total_runs']}")
    lines.append(f"   Successful:          {s['successful']}")
    lines.append(f"   Failed:              {s['failed']}")
    lines.append(f"   Success rate:        {s['success_rate_percent']}%")
    
    # TTO Results
    lines.append("\n2. TIME-TO-OPERATIONAL (TTO) RESULTS")
    lines.append("-" * 40)
    
    def format_stats(label: str, stats: Dict, unit: str = "ms") -> str:
        if stats['n'] == 0:
            return f"   {label:30s} No data"
        return (f"   {label:30s} "
                f"Mean: {stats['mean']:6.1f} {unit}  "
                f"Median: {stats['median']:6.1f} {unit}  "
                f"Max: {stats['max']:6.1f} {unit}")
    
    lines.append(format_stats("All runs:", analysis['tto_all']))
    lines.append(format_stats("Cached image:", analysis['tto_cached']))
    lines.append(format_stats("Uncached (cold start):", analysis['tto_uncached']))
    
    # System Resources (Improved Section)
    lines.append("\n3. SYSTEM RESOURCE USAGE (Mean values across runs)")
    lines.append("-" * 40)
    lines.append("   (Comparing Process Average vs. Transient Peak)")
    lines.append("")
    res = analysis['resources']
    
    lines.append("   [CPU Load]")
    lines.append(format_stats("Process Average:", res['cpu_avg'], unit="%"))
    lines.append(format_stats("Transient Peak:", res['cpu_peak'], unit="%"))
    
    lines.append("\n   [Memory Usage]")
    lines.append(format_stats("Process Average:", res['mem_avg'], unit="MB"))
    lines.append(format_stats("Transient Peak:", res['mem_peak'], unit="MB"))
    
    lines.append("\n   [Temperature]")
    lines.append(format_stats("Process Average:", res['temp_avg'], unit="°C"))
    lines.append(format_stats("Peak:", res['temp_peak'], unit="°C"))

    # Phase breakdown
    lines.append("\n4. BREAKDOWN BY PHASE")
    lines.append("-" * 40)
    
    phases = [
        ("Cloud Lookup", "lookup"),
        ("AAS Parsing", "parse"),
        ("Image Pull (all)", "pull"),
        ("Container Start", "start"),
        ("mDNS Advertisement", "advertise"),
    ]
    
    for label, key in phases:
        stats = analysis['phases'].get(key, {})
        lines.append(format_stats(label + ":", stats))
    
    # Errors
    if analysis['errors']:
        lines.append("\n5. FAILURE ANALYSIS")
        lines.append("-" * 40)
        error_counts = {}
        for err in analysis['errors']:
            error_counts[err] = error_counts.get(err, 0) + 1
        for err, count in sorted(error_counts.items(), key=lambda x: -x[1]):
            lines.append(f"   [{count}x] {err}")
    
    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def generate_csv(runs: List[Dict]) -> str:
    """Generate CSV for spreadsheet analysis."""
    headers = [
        "run_id", "timestamp", "sensor_name", "success",
        "total_tto_ms", 
        "peak_cpu", "avg_cpu",  # Added Avg
        "peak_mem", "avg_mem", 
        "peak_temp", "avg_temp",
        "duration_lookup_ms", "duration_pull_ms", "duration_start_ms",
        "error_message"
    ]
    
    lines = [",".join(headers)]
    
    for run in runs:
        # Calculate individual run averages on the fly for CSV
        stats = get_run_resource_stats(run)
        
        values = [
            str(run.get("run_id", "")),
            str(run.get("timestamp", "")),
            str(run.get("sensor_name", "")),
            str(run.get("success", "")),
            str(run.get("total_tto_ms", "")),
            
            # Resources
            str(run.get("peak_cpu_percent", "")),
            f"{stats['cpu_avg']:.2f}",
            str(run.get("peak_memory_mb", "")),
            f"{stats['mem_avg']:.2f}",
            str(run.get("peak_temp_c", "")),
            f"{stats['temp_avg']:.2f}",
            
            str(run.get("duration_lookup_ms", "")),
            str(run.get("duration_pull_ms", "")),
            str(run.get("duration_start_ms", "")),
            str(run.get("error_message", ""))
        ]
        
        values = [f'"{v}"' if ',' in v else v for v in values]
        lines.append(",".join(values))
    
    return "\n".join(lines)


def print_quick_summary(analysis: Dict):
    """Print a quick summary to console."""
    print("\n" + "=" * 60)
    print("  EVALUATION SUMMARY")
    print("=" * 60)
    
    s = analysis['summary']
    print(f"\n  Runs: {s['successful']}/{s['total_runs']} successful ({s['success_rate_percent']}%)")
    
    res = analysis['resources']
    if res['cpu_avg']['n'] > 0:
        print(f"\n  System Load (Mean across all runs):")
        print(f"    CPU Load:    {res['cpu_avg']['mean']:.1f}% (Avg)  vs  {res['cpu_peak']['mean']:.1f}% (Peak Spike)")
        print(f"    RAM Usage:   {res['mem_avg']['mean']:.1f} MB")
        print(f"    Temperature: {res['temp_avg']['mean']:.1f} °C")
    
    print("\n" + "=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze PnP evaluation results")
    parser.add_argument('metrics_dir', nargs='?', default='./evaluation_results',
                        help='File or Directory containing metrics.json')
    parser.add_argument('--export', '-e', help='Export text report to file')
    parser.add_argument('--csv', '-c', help='Export CSV to file')
    args = parser.parse_args()
    
    runs = load_metrics(args.metrics_dir)
    if not runs:
        print("No runs found.")
        sys.exit(1)
    
    analysis = analyze(runs)
    
    if args.export:
        with open(args.export, 'w') as f:
            f.write(generate_text_report(analysis, runs))
        print(f"Report exported to: {args.export}")
    
    if args.csv:
        with open(args.csv, 'w') as f:
            f.write(generate_csv(runs))
        print(f"CSV exported to: {args.csv}")
    
    print_quick_summary(analysis)
    
    if not args.export and not args.csv:
        print(generate_text_report(analysis, runs))


if __name__ == "__main__":
    main()