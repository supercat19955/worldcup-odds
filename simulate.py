# -*- coding: utf-8 -*-
"""
模拟生成多期历史快照，展示赔率从开盘到现在的完整变化轨迹。
确保相邻两期之间有真实的赔率差异，使颜色标注可见。
"""
import json
import os
import copy
import random

random.seed(42)

SNAPSHOT_DIR = os.path.join(os.path.dirname(__file__), "data", "snapshots")


def make_dt(offset_hours):
    from datetime import datetime, timedelta
    return datetime.now() - timedelta(hours=offset_hours)


def load_current():
    files = sorted([f for f in os.listdir(SNAPSHOT_DIR) if f.startswith("crs_odds_")])
    if not files:
        return None
    with open(os.path.join(SNAPSHOT_DIR, files[-1]), "r", encoding="utf-8") as f:
        return json.load(f)


def generate_history():
    base = load_current()
    if not base:
        print("无当前快照，请先运行 main.py")
        return

    print(f"基准快照: {len(base['matches'])} 场比赛")

    # 为每个比分设计一条独立的变化路径
    # 路径格式: (方向, 总变化量)  --- 方向: +1=逐步上升, -1=逐步下降, 0=波动
    paths = {}
    for match in base["matches"]:
        scores = match.get("score_odds", {}).get("scores", {})
        for score, val in scores.items():
            try:
                v = float(val)
            except (ValueError, TypeError):
                continue
            h = hash(f"{match['match_id']}_{score}") % 100
            if h < 20:
                paths[(match["match_id"], score)] = (+1, round(v * random.uniform(0.08, 0.20), 2))
            elif h < 40:
                paths[(match["match_id"], score)] = (-1, round(v * random.uniform(0.08, 0.20), 2))
            elif h < 55:
                paths[(match["match_id"], score)] = (2, round(v * random.uniform(0.05, 0.12), 2))  # 先升后降
            elif h < 65:
                paths[(match["match_id"], score)] = (-2, round(v * random.uniform(0.05, 0.12), 2))  # 先降后升
            # else: 不变

    # 生成 8 期快照: T-8h(开盘), T-7h, ..., T-1h
    # 每期间隔约 1 小时，T-1h 的 progress=0.875，留有变化空间
    total_steps = 8
    for step_idx in range(total_steps):
        hour_offset = total_steps - step_idx  # 8, 7, 6, ..., 1
        snap = copy.deepcopy(base)
        t = make_dt(hour_offset)
        snap["fetch_time"] = t.strftime("%Y-%m-%d %H:%M:%S")

        for match in snap["matches"]:
            scores = match.get("score_odds", {}).get("scores", {})
            for score, val in list(scores.items()):
                key = (match["match_id"], score)
                if key not in paths:
                    continue

                direction, total = paths[key]
                base_v = float(val)
                # 进度: 0=开盘(T-8h), 0.875=T-1h(最后模拟), 1.0=当前(不在这里模拟)
                # 使用 step_idx/total_steps 确保最后模拟期与当前值仍有差异
                progress = step_idx / total_steps if total_steps > 0 else 0.0

                if direction == +1:
                    # 线性上升
                    new_v = round(base_v - total + total * progress, 2)
                elif direction == -1:
                    # 线性下降
                    new_v = round(base_v + total - total * progress, 2)
                elif direction == 2:
                    # 先升后降 (sine-like)
                    # progress=0: 起始值, 0.5: 峰值, 1: 回到 base
                    if progress < 0.5:
                        new_v = round(base_v + total * (progress / 0.5), 2)
                    else:
                        new_v = round(base_v + total * ((1 - progress) / 0.5), 2)
                elif direction == -2:
                    # 先降后升
                    if progress < 0.5:
                        new_v = round(base_v - total * (progress / 0.5), 2)
                    else:
                        new_v = round(base_v - total * ((1 - progress) / 0.5), 2)
                else:
                    continue

                new_v = max(1.20, round(new_v, 2))
                scores[score] = f"{new_v:.2f}"

        # 文件名用 T-Nh 的格式方便识别
        ts = t.strftime("%Y-%m-%d_%H%M%S")
        fname = f"crs_odds_{ts}.json"
        fpath = os.path.join(SNAPSHOT_DIR, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(snap, f, ensure_ascii=False, indent=2)
        print(f"  -> 生成快照: {fname} (T-{hour_offset}h, 进度={step_idx}/{total_steps}={progress:.3f})")

    print(f"\n完成! 共生成 8 期历史快照 (T-8h ~ T-1h)")


if __name__ == "__main__":
    generate_history()
