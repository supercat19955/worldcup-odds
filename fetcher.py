# -*- coding: utf-8 -*-
"""
世界杯比分赔率抓取模块
从 m.sporttery.cn (中国体彩网) 获取世界杯比赛 CRS 比分赔率数据
"""
import requests
import json
import time
from datetime import datetime

API_BASE = "https://webapi.sporttery.cn/gateway/jc/football"
MATCH_CALCULATOR_URL = f"{API_BASE}/getMatchCalculatorV1.qry"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.sporttery.cn/",
    "Origin": "https://www.sporttery.cn",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

WORLD_CUP_LEAGUE_CODE = "WCC"

# 比分赔率字段映射: s{home}s{away} -> "主队:客队"
SCORE_FIELDS = [
    ("s00s00", "0:0"), ("s00s01", "0:1"), ("s00s02", "0:2"),
    ("s00s03", "0:3"), ("s00s04", "0:4"), ("s00s05", "0:5"),
    ("s01s00", "1:0"), ("s01s01", "1:1"), ("s01s02", "1:2"),
    ("s01s03", "1:3"), ("s01s04", "1:4"), ("s01s05", "1:5"),
    ("s02s00", "2:0"), ("s02s01", "2:1"), ("s02s02", "2:2"),
    ("s02s03", "2:3"), ("s02s04", "2:4"), ("s02s05", "2:5"),
    ("s03s00", "3:0"), ("s03s01", "3:1"), ("s03s02", "3:2"),
    ("s03s03", "3:3"),
    ("s04s00", "4:0"), ("s04s01", "4:1"), ("s04s02", "4:2"),
    ("s05s00", "5:0"), ("s05s01", "5:1"), ("s05s02", "5:2"),
    ("s1sh",  "胜其他"), ("s1sd", "平其他"), ("s1sa", "负其他"),
]


def fetch_matches(pool_code="crs", page=1, limit=100):
    """从体彩网 API 获取比赛列表"""
    params = {
        "poolCode": pool_code,
        "channel": "c_web",
        "leagueId": "",
        "limit": limit,
        "page": page,
    }
    for attempt in range(3):
        try:
            resp = requests.get(MATCH_CALCULATOR_URL, params=params,
                                headers=HEADERS, timeout=(10, 15))
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"  [重试 {attempt+1}/3] 请求失败: {e}")
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    return None


def parse_score_odds(crs_data):
    """
    将 CRS API 返回的原始数据解析为结构化比分赔率字典

    Args:
        crs_data: 原始 CRS 数据 (dict)

    Returns:
        dict: {"更新日期": ..., "更新时间": ..., "赔率": {"0:0": "14.00", ...}}
    """
    if not crs_data:
        return None

    scores = {}
    for field_key, label in SCORE_FIELDS:
        val = crs_data.get(field_key, "")
        if val:
            scores[label] = val

    if not scores:
        return None

    return {
        "update_date": crs_data.get("updateDate", ""),
        "update_time": crs_data.get("updateTime", ""),
        "scores": scores,
    }


def parse_world_cup_matches(data):
    """从 API 数据中提取世界杯比赛信息及比分赔率"""
    if not data or not data.get("success"):
        return []

    match_info_list = data.get("value", {}).get("matchInfoList", [])
    wc_matches = []
    seen_ids = set()

    for day_info in match_info_list:
        for m in day_info.get("subMatchList", []):
            if m.get("leagueCode") != WORLD_CUP_LEAGUE_CODE:
                continue

            match_id = m.get("matchId")
            if match_id in seen_ids:
                continue
            seen_ids.add(match_id)

            crs = m.get("crs", {})
            score_odds = parse_score_odds(crs)

            match = {
                "match_id": match_id,
                "match_num": m.get("matchNumStr", ""),
                "match_date": m.get("matchDate", ""),
                "match_time": m.get("matchTime", ""),
                "home_team": m.get("homeTeamAbbName", ""),
                "away_team": m.get("awayTeamAbbName", ""),
                "home_team_full": m.get("homeTeamAllName", ""),
                "away_team_full": m.get("awayTeamAllName", ""),
                "league_name": m.get("leagueAbbName", ""),
                "match_status": m.get("matchStatus", ""),
                "remark": m.get("remark", ""),
                "score_odds": score_odds,
            }
            wc_matches.append(match)

    return wc_matches


def fetch_world_cup_score_odds():
    """
    获取世界杯比赛比分赔率数据 (CRS)

    Returns:
        dict: {"fetch_time": ..., "matches": [...]}
    """
    print("[抓取] 正在从 m.sporttery.cn 获取世界杯比分赔率(CRS)...")

    crs_data = fetch_matches(pool_code="crs")
    matches = parse_world_cup_matches(crs_data) if crs_data else []
    print(f"  -> 找到 {len(matches)} 场世界杯比分赔率数据")

    result = {
        "fetch_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "fetch_timestamp": datetime.now().timestamp(),
        "match_count": len(matches),
        "matches": matches,
    }
    print(f"[完成] 共获取 {len(matches)} 场世界杯比分赔率")
    return result
