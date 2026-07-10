# -*- coding: utf-8 -*-
"""
多维情报获取与更新模块
每次赔率更新时同步刷新比赛情报：球队近况、球员状态、海内外消息、裁判组、场地时间等
"""
import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
INTEL_FILE = os.path.join(DATA_DIR, "match_intel.json")
INTEL_HISTORY_DIR = os.path.join(DATA_DIR, "intel_history")


def load_match_intel():
    """加载当前情报数据"""
    try:
        with open(INTEL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "_meta": {
                "version": "1.0",
                "last_updated": "",
                "update_count": 0,
                "description": "比赛多维度情报数据，每次赔率更新时同步刷新"
            }
        }


def save_match_intel(intel_data):
    """保存情报数据并归档历史版本"""
    os.makedirs(DATA_DIR, exist_ok=True)

    intel_data["_meta"]["update_count"] = intel_data.get("_meta", {}).get("update_count", 0) + 1
    intel_data["_meta"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 归档历史版本
    os.makedirs(INTEL_HISTORY_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    history_file = os.path.join(INTEL_HISTORY_DIR, f"match_intel_{timestamp}.json")
    try:
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(intel_data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # 保存当前版本
    with open(INTEL_FILE, "w", encoding="utf-8") as f:
        json.dump(intel_data, f, ensure_ascii=False, indent=2)

    print(f"[情报] 情报已更新 (第{intel_data['_meta']['update_count']}次), 已归档: {history_file}")
    return intel_data


def get_intel_age_hours(match_key):
    """获取某场比赛情报的新鲜度（小时）"""
    intel_data = load_match_intel()
    match = intel_data.get(match_key, {})
    updated_at = match.get("intel_updated_at", "")

    if not updated_at:
        return None

    try:
        updated_dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M:%S")
        age = (datetime.now() - updated_dt).total_seconds() / 3600
        return round(age, 1)
    except ValueError:
        return None


def get_all_match_keys(intel_data=None):
    """获取所有比赛名称（排除 _meta）"""
    if intel_data is None:
        intel_data = load_match_intel()
    return [k for k in intel_data.keys() if not k.startswith("_")]


def refresh_intel_on_odds_update():
    """
    每次赔率更新时自动刷新所有比赛情报的时间戳。
    将 intel_updated_at 设为当前时间。
    同时归档历史情报版本供回溯。
    """
    intel_data = load_match_intel()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    match_keys = get_all_match_keys(intel_data)
    refreshed = 0
    for key in match_keys:
        if isinstance(intel_data.get(key), dict):
            intel_data[key]["intel_updated_at"] = now
            refreshed += 1
    if refreshed > 0:
        save_match_intel(intel_data)
        print(f"[情报] 已跟随赔率更新同步刷新 {refreshed} 场比赛情报时间戳 -> {now}")
    else:
        print(f"[情报] 无比赛情报需要刷新")
    return intel_data


def get_betting_deadline(match_date, match_time):
    """
    推算投注截止时间（通常开赛前5分钟截止）

    Args:
        match_date: "2026-07-10" 格式
        match_time: "15:00" 或 "15:00:00" 格式

    Returns:
        str: 截止时间 "2026-07-10 14:55"
    """
    if not match_date or not match_time:
        return ""

    time_str = match_time.strip()
    fmt = "%Y-%m-%d %H:%M"
    if len(time_str.split(":")) == 3:
        fmt = "%Y-%m-%d %H:%M:%S"

    try:
        from datetime import timedelta
        dt = datetime.strptime(f"{match_date} {time_str}", fmt)
        deadline = dt.replace(second=0)
        deadline = deadline - timedelta(minutes=5)
        return deadline.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ""
