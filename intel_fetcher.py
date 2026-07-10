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


def enrich_intel_with_analysis(intel_data, ai_results, analyzed_results):
    """
    将 AI 分析结果 + 赔率趋势反哺到情报数据中，实现赔率与情报的联动更新。

    每次赔率更新后，AI 分析会产生基于最新赔率的新洞察。
    这些洞察应注入情报中，使后续分析能利用不断累积的情报。
    """
    if not ai_results:
        return intel_data

    for match_key, ai_result in ai_results.items():
        if match_key not in intel_data:
            continue

        analysis_text = ai_result.get("analysis", "")
        prediction_text = ai_result.get("prediction", "")
        key_factors = ai_result.get("key_factors", [])
        source = ai_result.get("source", "offline")
        recommendation = ai_result.get("recommendation", "")

        # 注入 AI 分析结果到情报
        if analysis_text:
            intel_data[match_key]["ai_analysis"] = analysis_text
        if prediction_text:
            intel_data[match_key]["ai_prediction"] = prediction_text
        if key_factors:
            intel_data[match_key]["ai_key_factors"] = key_factors
        if recommendation:
            intel_data[match_key]["ai_recommendation"] = recommendation
        intel_data[match_key]["ai_source"] = source

        # 提取赔率趋势摘要注入情报
        for r in analyzed_results:
            r_home = r.get("home_team", "")
            r_away = r.get("away_team", "")
            if f"{r_home} vs {r_away}" == match_key:
                trends = r.get("trend_summary", {})
                up_c = trends.get("up", 0)
                down_c = trends.get("down", 0)
                flat_c = trends.get("flat", 0)
                new_c = trends.get("new", 0)

                # 计算赔率倾向信号
                if down_c > up_c:
                    signal = "机构看好低比分"
                elif up_c > down_c:
                    signal = "市场热度分散"
                else:
                    signal = "市场平稳"

                top5_scores = []
                scores_dict = r.get("score_odds", {}).get("scores", {})
                if scores_dict:
                    try:
                        sorted_s = sorted(scores_dict.items(), key=lambda x: float(x[1]))
                        for i, (s, v) in enumerate(sorted_s[:3]):
                            top5_scores.append(f"{s}@{v}")
                    except (ValueError, TypeError):
                        pass

                intel_data[match_key]["odds_trend"] = (
                    f"▲{up_c}升 ▼{down_c}降 →{flat_c}平 +{new_c}新 | {signal}"
                )
                if top5_scores:
                    intel_data[match_key]["odds_top3"] = ", ".join(top5_scores)
                break

        # 标记情报来源为 AI+赔率联动
        if not intel_data[match_key].get("intel_source"):
            intel_data[match_key]["intel_source"] = "manual"
        # 添加联动标记
        intel_data[match_key]["ai_enriched_at"] = intel_data[match_key].get(
            "intel_updated_at", ""
        )

    print(f"[情报] AI分析结果已反哺到 {len(ai_results)} 场比赛情报中")
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
