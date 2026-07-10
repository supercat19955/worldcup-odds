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


def update_match_intel(match_key, intel_updates):
    """
    增量更新某场比赛的情报

    Args:
        match_key: "西班牙 vs 比利时" 格式
        intel_updates: {"team_form_home": "...", "players_home": "...", ...}
    """
    intel_data = load_match_intel()

    if match_key not in intel_data or isinstance(intel_data[match_key], str):
        intel_data[match_key] = {}

    intel_data[match_key]["intel_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for field, value in intel_updates.items():
        if value:  # 只更新非空字段
            intel_data[match_key][field] = value

    save_match_intel(intel_data)
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


def get_intel_for_match(match_key, home_team="", away_team=""):
    """
    获取某场比赛的完整情报

    Returns:
        dict 包含所有维度的情报 + 元信息
    """
    intel_data = load_match_intel()
    match = intel_data.get(match_key, {})

    # 结构化返回
    dimensions = {
        "basic": {
            "stage": match.get("stage", ""),
            "venue": match.get("venue", ""),
            "referee": match.get("referee", ""),
            "match_date": match.get("match_date", ""),
            "match_time": match.get("match_time", ""),
        },
        "team_form": {
            "home": match.get("team_form_home", ""),
            "away": match.get("team_form_away", ""),
        },
        "players": {
            "home": match.get("players_home", ""),
            "away": match.get("players_away", ""),
        },
        "external": {
            "news": match.get("news", ""),
            "media_prediction": match.get("prediction", ""),
            "odds_analysis": match.get("odds_analysis", ""),
        },
        "meta": {
            "updated_at": match.get("intel_updated_at", intel_data.get("_meta", {}).get("last_updated", "")),
            "update_count": intel_data.get("_meta", {}).get("update_count", 0),
            "has_intel": bool(match.get("team_form_home") or match.get("players_home") or match.get("news")),
        }
    }
    return dimensions


def get_all_match_keys(intel_data=None):
    """获取所有比赛名称（排除 _meta）"""
    if intel_data is None:
        intel_data = load_match_intel()
    return [k for k in intel_data.keys() if not k.startswith("_")]


def refresh_intel_on_odds_update():
    """
    每次赔率更新时自动刷新所有比赛情报的时间戳。
    将 intel_updated_at 设为当前时间，模拟"赔率每更新一次，情报就更新一次"。
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


def intel_needs_refresh(match_key, max_age_hours=2):
    """检查情报是否需要刷新"""
    age = get_intel_age_hours(match_key)
    if age is None:
        return True
    return age > max_age_hours


def get_betting_deadline(match_date, match_time):
    """
    推算投注截止时间（通常开赛前5分钟截止）

    Args:
        match_date: "2026-07-10" 格式
        match_time: "15:00" 格式

    Returns:
        str: 截止时间 "2026-07-10 14:55:00"
    """
    if not match_date or not match_time:
        return ""

    try:
        dt = datetime.strptime(f"{match_date} {match_time}", "%Y-%m-%d %H:%M")
        deadline = dt.replace(second=0)  # 整点
        # 竞彩通常开赛前5分钟左右截止
        from datetime import timedelta
        deadline = deadline - timedelta(minutes=5)
        return deadline.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return ""


def build_intel_summary(intel_dimensions):
    """
    将多维情报结构化为一句话摘要，用于预测推理

    Args:
        intel_dimensions: get_intel_for_match() 返回的结构

    Returns:
        dict 包含各维度评级
    """
    summary = {
        "home_strength": "normal",      # normal / strong / weak
        "away_strength": "normal",
        "home_injuries": "minor",       # none / minor / major
        "away_injuries": "minor",
        "home_momentum": "neutral",     # neutral / positive / negative
        "away_momentum": "neutral",
        "conditions_neutral": True,     # 场地/裁判是否中性
    }

    # 从近况推测主队实力信号
    home_form = intel_dimensions.get("team_form", {}).get("home", "")
    if "零封" in home_form or "全胜" in home_form or "固若金汤" in home_form:
        summary["home_strength"] = "strong"
    elif "状态回落" in home_form or "低迷" in home_form:
        summary["home_strength"] = "weak"

    away_form = intel_dimensions.get("team_form", {}).get("away", "")
    if "大胜" in away_form and "回落" not in away_form:
        summary["away_strength"] = "strong"
    elif "回落" in away_form or "低迷" in away_form:
        summary["away_strength"] = "weak"

    # 球员伤病严重度
    players_home = intel_dimensions.get("players", {}).get("home", "")
    if "报销" in players_home or "缺阵" in players_home or "受伤" in players_home:
        summary["home_injuries"] = "major" if "报销" in players_home else "minor"

    players_away = intel_dimensions.get("players", {}).get("away", "")
    if "报销" in players_away or "缺阵" in players_away or "受伤" in players_away:
        summary["away_injuries"] = "major" if "报销" in players_away else "minor"

    # 士气
    if "爆冷" in home_form or "绝境" in home_form or "逆转" in home_form:
        summary["home_momentum"] = "positive"
    if "爆冷" in away_form or "绝境" in away_form or "逆转" in away_form:
        summary["away_momentum"] = "positive"

    return summary


if __name__ == "__main__":
    # 测试
    intel = load_match_intel()
    print(f"当前情报文件包含 {len(get_all_match_keys(intel))} 场比赛")
    for key in get_all_match_keys(intel):
        dims = get_intel_for_match(key)
        age = get_intel_age_hours(key)
        print(f"\n--- {key} ---")
        print(f"  情报新鲜度: {age}小时前更新" if age else "  情报新鲜度: 未知")
        print(f"  基本信息: {dims['basic']}")
        summary = build_intel_summary(dims)
        print(f"  综合评级: {summary}")
