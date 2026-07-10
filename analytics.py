# -*- coding: utf-8 -*-
"""
赔率分析模块：Overround、隐含概率、赔率变化
接收已加载的数据，不再自行读取磁盘，避免重复 I/O
"""
import os
import json
from glob import glob


SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "data", "snapshots")


def compute_overround(scores):
    """计算 overround = sum(1/odds) - 1.0, 表示庄家抽水比例"""
    total = 0.0
    for score, odds_str in scores.items():
        try:
            odds = float(odds_str)
            if odds > 0:
                total += 1.0 / odds
        except (ValueError, TypeError):
            pass
    overround = total - 1.0
    return {
        "sum_implied": total,
        "overround": overround,
        "overround_pct": round(overround * 100, 2),
    }


def compute_implied_probabilities(scores):
    """计算每个比分的真实隐含概率（扣除 overround 后的标准化概率）"""
    total = sum(1.0 / float(v) for v in scores.values() if float(v) > 0)
    probs = {}
    for score, odds_str in scores.items():
        odds = float(odds_str)
        if odds > 0:
            raw_implied = 1.0 / odds
            fair_prob = raw_implied / total
            probs[score] = {
                "odds": odds,
                "raw_implied": round(raw_implied * 100, 2),
                "fair_prob": round(fair_prob * 100, 2),
            }
    return dict(sorted(probs.items(), key=lambda x: -x[1]["fair_prob"]))


def compute_odds_changes(latest, earliest):
    """计算赔率变化：当前 vs 最早"""
    changes = {}
    all_scores = set(latest.keys()) | set(earliest.keys())
    for score in all_scores:
        cur = float(latest.get(score, 0) or 0)
        old = float(earliest.get(score, 0) or 0)
        if cur > 0 and old > 0:
            abs_change = cur - old
            pct_change = (cur - old) / old * 100
            changes[score] = {
                "latest": cur,
                "oldest": old,
                "abs_change": round(abs_change, 2),
                "pct_change": round(pct_change, 2),
                "direction": "up" if abs_change > 0 else ("down" if abs_change < 0 else "flat"),
            }
    return dict(sorted(changes.items(), key=lambda x: -abs(x[1]["pct_change"])))


def _load_snapshot_files():
    """获取所有快照文件（按时间排序）"""
    if not os.path.exists(SNAPSHOT_DIR):
        return []
    return sorted(glob(os.path.join(SNAPSHOT_DIR, "crs_odds_*.json")))


def generate_analytics_html(latest_data=None, all_snapshots=None):
    """
    生成分析报告 HTML。
    接受预加载的数据，避免重复读取磁盘。

    Args:
        latest_data: 当前快照 dict（必填）
        all_snapshots: [(fetch_time, data), ...] 全部快照（可选，用于找最早）
    """
    if not latest_data:
        return "<p>无快照数据</p>"

    # 找最早快照
    earliest_data = None
    if all_snapshots and len(all_snapshots) > 0:
        earliest_data = all_snapshots[0][1]  # 第一个就是最早的

    rows_html = ""
    for match in latest_data.get("matches", []):
        home = match["home_team"]
        away = match["away_team"]
        match_num = match.get("match_num", "")
        match_date = match.get("match_date", "")
        match_time = match.get("match_time", "")
        scores = match["score_odds"]["scores"]

        # 找最早快照中对应比赛的数据
        earliest_scores = {}
        for em in (earliest_data or {}).get("matches", []):
            if em["match_id"] == match["match_id"]:
                earliest_scores = em["score_odds"]["scores"]
                break

        # 1. Overround
        or_data = compute_overround(scores)

        # 2. 隐含概率 TOP 10
        probs = compute_implied_probabilities(scores)
        top_probs = list(probs.items())[:10]

        # 3. 赔率变化 TOP 15
        changes = compute_odds_changes(scores, earliest_scores) if earliest_scores else {}
        top_changes_up = [(k, v) for k, v in list(changes.items())[:15] if v["direction"] == "up"][:8]
        top_changes_down = [(k, v) for k, v in list(changes.items())[:15] if v["direction"] == "down"][:8]

        # 构建概率表行
        prob_rows = ""
        for score, info in top_probs:
            bar_w = min(info["fair_prob"] * 3, 100)
            prob_rows += f'''
            <tr>
                <td class="score-cell"><strong>{score}</strong></td>
                <td class="odds-cell">@{info["odds"]}</td>
                <td class="prob-cell">
                    <div class="prob-bar-wrap">
                        <div class="prob-bar" style="width:{bar_w}%"></div>
                        <span class="prob-val">{info["fair_prob"]}%</span>
                    </div>
                </td>
                <td class="raw-cell">{info["raw_implied"]}%</td>
            </tr>'''

        # 构建赔率变化表行
        change_rows_up = ""
        for score, info in top_changes_up:
            change_rows_up += f'''
            <tr>
                <td class="score-cell">{score}</td>
                <td class="odds-cell">@{info["oldest"]} → @{info["latest"]}</td>
                <td class="change-cell up">▲ {info["pct_change"]:+.1f}%</td>
            </tr>'''

        change_rows_down = ""
        for score, info in top_changes_down:
            change_rows_down += f'''
            <tr>
                <td class="score-cell">{score}</td>
                <td class="odds-cell">@{info["oldest"]} → @{info["latest"]}</td>
                <td class="change-cell down">▼ {info["pct_change"]:+.1f}%</td>
            </tr>'''

        # 时间跨度
        if earliest_data:
            hours_span = round(
                (latest_data["fetch_timestamp"] - earliest_data["fetch_timestamp"]) / 3600, 1
            )
            time_span_text = f"跨度 {hours_span} 小时"
        else:
            time_span_text = ""

        rows_html += f'''
        <div class="match-analytics">
            <div class="ma-header">
                <span class="ma-match">{match_num} {home} vs {away}</span>
                <span class="ma-time">{match_date} {match_time}</span>
            </div>
            <div class="ma-overround">
                <div class="ma-section-title">📊 庄家抽水 (Overround)</div>
                <div class="or-cards">
                    <div class="or-card">
                        <div class="or-label">隐含概率总和</div>
                        <div class="or-value">{or_data["sum_implied"]*100:.2f}%</div>
                    </div>
                    <div class="or-card highlight">
                        <div class="or-label">庄家抽水率</div>
                        <div class="or-value">{or_data["overround_pct"]}%</div>
                    </div>
                    <div class="or-card">
                        <div class="or-label">返还率</div>
                        <div class="or-value">{(1/(or_data["sum_implied"])*100):.1f}%</div>
                    </div>
                </div>
                <div class="or-note">💡 庄家抽水 {or_data["overround_pct"]}% 意味着：你每投注 100 元，理论预期回收约 {(1/(or_data["sum_implied"])*100):.0f} 元</div>
            </div>
            <div class="ma-two-col">
                <div class="ma-col">
                    <div class="ma-section-title">🎯 隐含概率 TOP10</div>
                    <table class="prob-table">
                        <thead><tr><th>比分</th><th>赔率</th><th>真实概率</th><th>原始</th></tr></thead>
                        <tbody>{prob_rows}</tbody>
                    </table>
                </div>
                <div class="ma-col">
                    <div class="ma-section-title">📈 赔率变化分析 ({time_span_text})</div>
                    <div class="change-subtitle">▲ 赔率升高（热度减退）</div>
                    <table class="change-table">
                        <thead><tr><th>比分</th><th>赔率变化</th><th>变化率</th></tr></thead>
                        <tbody>{change_rows_up or '<tr><td colspan="3" class="no-data">无升高项</td></tr>'}</tbody>
                    </table>
                    <div class="change-subtitle">▼ 赔率降低（热度上升）</div>
                    <table class="change-table">
                        <thead><tr><th>比分</th><th>赔率变化</th><th>变化率</th></tr></thead>
                        <tbody>{change_rows_down or '<tr><td colspan="3" class="no-data">无降低项</td></tr>'}</tbody>
                    </table>
                </div>
            </div>
        </div>'''

    return rows_html
