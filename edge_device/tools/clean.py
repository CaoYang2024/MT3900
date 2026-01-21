#!/usr/bin/env python3
"""
clean_metrics.py
清理 metrics.json 中由系统设备（如内部 USB Hub）产生的无效记录
"""
import json
import os

# 定义要删除的无效设备签名片段
IGNORED_SIGNATURES = ["vid_2109", "vid_1d6b", "vid_0424"]
FILE_PATH = "metrics.json"

def clean():
    if not os.path.exists(FILE_PATH):
        print("未找到 metrics.json")
        return

    with open(FILE_PATH, 'r') as f:
        data = json.load(f)

    original_count = len(data.get("runs", []))
    
    # 过滤掉包含黑名单签名的运行记录
    cleaned_runs = [
        run for run in data.get("runs", [])
        if not any(ig in run.get("signature", "") for ig in IGNORED_SIGNATURES)
    ]

    data["runs"] = cleaned_runs
    
    # 可选：重置 run_counter 或者保持原样
    # data["run_counter"] = len(cleaned_runs) 

    with open(FILE_PATH, 'w') as f:
        json.dump(data, f, indent=2)

    print(f"清理完成。")
    print(f"原始记录数: {original_count}")
    print(f"当前记录数: {len(cleaned_runs)}")
    print(f"已删除: {original_count - len(cleaned_runs)} 条系统干扰数据")

if __name__ == "__main__":
    clean()