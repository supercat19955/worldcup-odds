# -*- coding: utf-8 -*-
"""
比分赔率趋势分析器
对比历史快照中的比分赔率，分析每个具体比分的赔率上升/下降趋势
"""
import json
import os
from glob import glob

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "data", "snapshots")


def save_snapshot(data):
    """保存赔率快照"""
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    timestamp = data.get("fetch_time", "").replace(":", "").replace(" ", "_")
    filename = f"crs_odds_{timestamp}.json"
    filepath = os.path.join(SNAPSHOT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[存储] 快照已保存: {filename}")
    return filepath


def _snapshot_files():
    """获取所有比分赔率快照文件列表（按时间排序）"""
    if not os.path.exists(SNAPSHOT_DIR):
        return []
    return sorted(glob(os.path.join(SNAPSHOT_DIR, "crs_odds_*.json")))


def load_best_previous_snapshot(current_data, exclude_current):
    """
    智能加载最佳对比快照：跳过与当前数据内容相同的快照，找到真正有差异的上一期。

    Args:
        current_data: 当前抓取的数据
        exclude_current: 要排除的当前快照文件名

    Returns:
        dict or None: 最佳的对比快照
    """
    files = _snapshot_files()
    if exclude_current:
        files = [f for f in files if os.path.basename(f) != exclude_current]
    if not files:
        return None

    # 从最新开始回溯，找到第一个与当前数据不同的快照
    current_match_scores = {}
    for m in current_data.get("matches", []):
        scores = m.get("score_odds", {}).get("scores", {}) if m.get("score_odds") else {}
        current_match_scores[m["match_id"]] = scores

    for fpath in reversed(files):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 检查是否有任何比赛的比分赔率与当前不同
        has_diff = False
        for m in data.get("matches", []):
            prev_scores = m.get("score_odds", {}).get("scores", {}) if m.get("score_odds") else {}
            cur_scores = current_match_scores.get(m["match_id"], {})
            # 比较所有比分值
            all_scores = set(prev_scores.keys()) | set(cur_scores.keys())
            for score in all_scores:
                pv = prev_scores.get(score)
                cv = cur_scores.get(score)
                if pv != cv:
                    has_diff = True
                    break
            if has_diff:
                break

        if has_diff:
            print(f"[对比] 加载历史快照: {os.path.basename(fpath)} (与当前有差异)")
            return data

    # 所有快照都相同，返回最早的作为对比
    if files:
        with open(files[0], "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[对比] 所有快照与当前相同，使用最早快照: {os.path.basename(files[0])}")
        return data

    return None


def load_all_snapshots():
    """加载所有快照，按时间排序，返回 [(fetch_time, data), ...]"""
    files = _snapshot_files()
    if not files:
        return []
    snapshots = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            snapshots.append((data.get("fetch_time", ""), data))
    return snapshots


def build_score_history(all_snapshots, match_id):
    """
    为指定比赛构建所有比分赔率的时间序列

    Args:
        all_snapshots: [(fetch_time, data), ...]
        match_id: 比赛ID

    Returns:
        dict: {
            score_label: [(time_str, odds_value), ...]  时间升序，第一条=开盘价
        }
    """
    history = {}
    for fetch_time, snap in all_snapshots:
        for m in snap.get("matches", []):
            if m["match_id"] != match_id:
                continue
            scores = m.get("score_odds", {}).get("scores", {}) if m.get("score_odds") else {}
            for score, val in scores.items():
                if score not in history:
                    history[score] = []
                # 避免同一时间重复记录
                if not history[score] or history[score][-1][0] != fetch_time:
                    try:
                        history[score].append((fetch_time, float(val)))
                    except (ValueError, TypeError):
                        history[score].append((fetch_time, val))
    return history


def compare_score_odds(current_scores, previous_scores):
    """
    对比单场比赛的所有比分赔率变化

    Args:
        current_scores: {"0:0": "14.00", "1:0": "7.75", ...}
        previous_scores: 同上

    Returns:
        dict: { 比分: {"current": ..., "previous": ..., "change": ..., "direction": ..., "percent": ...} }
    """
    if not current_scores:
        return {}
    if not previous_scores:
        # 无历史数据, 全部标记为新增
        return {score: {
            "current": val, "previous": "",
            "change": None, "direction": "new", "percent": None,
        } for score, val in current_scores.items()}

    changes = {}
    all_scores = set(current_scores.keys()) | set(previous_scores.keys())

    for score in sorted(all_scores):
        cur = current_scores.get(score, "")
        prev = previous_scores.get(score, "")

        if not prev:
            changes[score] = {
                "current": cur, "previous": "",
                "change": None, "direction": "new", "percent": None,
            }
        elif not cur:
            changes[score] = {
                "current": "", "previous": prev,
                "change": None, "direction": "removed", "percent": None,
            }
        else:
            try:
                cur_f = float(cur)
                prev_f = float(prev)
                diff = round(cur_f - prev_f, 2)
                if abs(diff) < 0.005:
                    changes[score] = {
                        "current": cur, "previous": prev,
                        "change": 0, "direction": "flat", "percent": 0.0,
                    }
                else:
                    pct = round((diff / prev_f) * 100, 1)
                    changes[score] = {
                        "current": cur, "previous": prev,
                        "change": diff,
                        "direction": "up" if diff > 0 else "down",
                        "percent": pct,
                    }
            except (ValueError, TypeError):
                changes[score] = {
                    "current": cur, "previous": prev,
                    "change": None, "direction": "unchanged", "percent": None,
                }

    return changes


def analyze_score_trends(current_data, previous_data, all_snapshots=None):
    """
    分析所有世界杯比赛的比分赔率趋势

    Args:
        current_data: 当前快照
        previous_data: 上一次快照（用于变化对比）
        all_snapshots: 全部快照列表（用于构建完整历史轨迹）

    Returns:
        list: 每场比赛的分析结果
    """
    results = []
    prev_matches = {}
    if previous_data:
        prev_matches = {m["match_id"]: m for m in previous_data.get("matches", [])}

    for match in current_data.get("matches", []):
        prev_match = prev_matches.get(match["match_id"])
        current_scores = match.get("score_odds", {}).get("scores", {}) if match.get("score_odds") else {}
        previous_scores = prev_match.get("score_odds", {}).get("scores", {}) if prev_match and prev_match.get("score_odds") else {}

        score_changes = compare_score_odds(current_scores, previous_scores)

        # 构建完整历史轨迹
        score_history = {}
        if all_snapshots:
            score_history = build_score_history(all_snapshots, match["match_id"])

        # 为每个比分补充历史摘要
        for score, change in score_changes.items():
            trail = score_history.get(score, [])
            if trail:
                # 开盘价（第一项）
                opening = trail[0][1]
                change["opening"] = opening
                # 历史轨迹字符串
                unique_vals = []
                prev_v = None
                for _, v in trail:
                    v_str = f"{v}" if isinstance(v, str) else f"{v:.2f}"
                    if v_str != prev_v:
                        unique_vals.append(v_str)
                        prev_v = v_str
                change["history_trail"] = unique_vals  # 去重后的值列表
                # 开盘到当前总变化
                if isinstance(current_scores.get(score), (int, float)) or (
                    current_scores.get(score) and current_scores[score].replace('.', '', 1).isdigit()
                ):
                    try:
                        cur_f = float(current_scores[score])
                        open_f = float(opening) if not isinstance(opening, str) else float(opening)
                        total_change = round(cur_f - open_f, 2)
                        change["total_change"] = total_change
                        change["total_direction"] = "up" if total_change > 0.005 else ("down" if total_change < -0.005 else "flat")
                    except (ValueError, TypeError):
                        change["total_change"] = None
                        change["total_direction"] = "flat"

        # 统计变化方向
        up_count = sum(1 for v in score_changes.values() if v["direction"] == "up")
        down_count = sum(1 for v in score_changes.values() if v["direction"] == "down")
        flat_count = sum(1 for v in score_changes.values() if v["direction"] == "flat")
        new_count = sum(1 for v in score_changes.values() if v["direction"] == "new")
        has_changes = up_count > 0 or down_count > 0

        results.append({
            **match,
            "score_changes": score_changes,
            "trend_summary": {
                "up": up_count,
                "down": down_count,
                "flat": flat_count,
                "new": new_count,
                "has_changes": has_changes,
                "prev_fetch_time": previous_data.get("fetch_time", "") if previous_data else "",
                "snapshot_count": len(all_snapshots) if all_snapshots else 0,
            },
        })

    print(f"[分析] 完成比分赔率趋势分析, 共 {len(results)} 场比赛")
    return results


def get_significant_changes(results, top_n=20):
    """
    提取变化最大的前 N 个比分赔率

    Returns:
        list: 按变化幅度排序的显著变化列表
    """
    items = []
    for r in results:
        for score, change in r.get("score_changes", {}).items():
            if change["direction"] in ("new", "removed"):
                items.append({
                    "match": f"{r['home_team']} vs {r['away_team']}",
                    "score": score,
                    "current": change["current"],
                    "previous": change["previous"],
                    "change": None,
                    "percent": None,
                    "direction": change["direction"],
                })
            elif change["change"] is not None and abs(change["change"]) >= 0.05:
                items.append({
                    "match": f"{r['home_team']} vs {r['away_team']}",
                    "score": score,
                    "current": change["current"],
                    "previous": change["previous"],
                    "change": change["change"],
                    "percent": change["percent"],
                    "direction": change["direction"],
                })

    items.sort(key=lambda x: abs(x["change"]) if x["change"] is not None else 0, reverse=True)
    return items[:top_n]
