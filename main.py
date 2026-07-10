# -*- coding: utf-8 -*-
"""
世界杯比分赔率监控系统 - 主程序
自动从 m.sporttery.cn 抓取世界杯比分赔率(CRS)
生成比分赔率矩阵表 + 趋势分析 + AI 大模型预测

用法:
    python main.py              # 单次运行
    python main.py --watch      # 持续监控模式
"""
import sys
import time
import os
from datetime import datetime

from fetcher import fetch_world_cup_score_odds
from analyzer import save_snapshot, load_best_previous_snapshot, load_all_snapshots, \
    analyze_score_trends, get_significant_changes, load_latest_valid_snapshot
from generator import generate_html, save_html
from intel_fetcher import load_match_intel, get_all_match_keys, get_intel_age_hours, \
    refresh_intel_on_odds_update, enrich_intel_with_analysis, save_match_intel
from ai_analyzer import batch_analyze, ai_available

# 配置常量
INTEL_STALE_HOURS = 3
SIG_TOP_N = 20


def run_once():
    """执行一次完整的抓取-分析-生成流程"""
    now = datetime.now()
    print(f"\n{'='*60}")
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行比分赔率抓取")
    print(f"{'='*60}")

    # 1. 抓取比分赔率数据 (CRS)
    data = fetch_world_cup_score_odds()
    if not data or not data.get("matches"):
        print("[警告] 未获取到世界杯比分赔率数据")
        fallback = load_latest_valid_snapshot(min_matches=1)
        if fallback:
            data = fallback
            data["fetch_time"] = now.strftime("%Y-%m-%d %H:%M:%S")
            data["fetch_timestamp"] = now.timestamp()
            data["_fallback"] = True
            print(f"[兜底] 已回退到历史快照，仍显示 {data.get('match_count', 0)} 场比赛")
        else:
            data = data or {
                "fetch_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "fetch_timestamp": now.timestamp(),
                "match_count": 0, "matches": [],
            }

    # 2. 保存快照
    snapshot_file = save_snapshot(data)

    # 3. 赔率更新 → 同步刷新情报 + 加载情报（一次性，不再重复读取）
    print(f"[情报] 赔率已更新，同步刷新比赛情报...")
    match_intel = refresh_intel_on_odds_update()

    # 4. 情报新鲜度检查（合并为单次遍历）
    match_keys = get_all_match_keys(match_intel)
    stale_count = 0
    for key in match_keys:
        age = get_intel_age_hours(key)
        if age is None:
            print(f"  - {key}: 首次更新")
        elif age > INTEL_STALE_HOURS:
            stale_count += 1
            print(f"  ⚠ {key}: {age}小时前更新（过期）")
        else:
            print(f"  - {key}: {age}小时前更新")
    if stale_count > 0:
        print(f"  ⚠ {stale_count} 场比赛情报超过{INTEL_STALE_HOURS}小时未更新")

    # 5. 加载历史快照 + 趋势分析（all_snapshots 一次性加载，后续复用）
    all_snapshots = load_all_snapshots()
    previous_data = load_best_previous_snapshot(data, os.path.basename(snapshot_file))
    analyzed = analyze_score_trends(data, previous_data, all_snapshots)

    # 6. 提取显著变化
    significant = get_significant_changes(analyzed, top_n=SIG_TOP_N)

    # 7. AI 大模型分析（始终运行：有 API Key 用大模型，无则离线规则分析）
    if ai_available():
        print(f"[AI] 大模型分析引擎已启用，正在综合分析所有比赛...")
    ai_results = batch_analyze(analyzed, match_intel)

    # 7b. 将 AI 分析结果反哺到情报中（赔率与情报联动）
    match_intel = enrich_intel_with_analysis(match_intel, ai_results, analyzed)
    save_match_intel(match_intel)

    # 8. 生成 HTML 统计表（含 AI 分析 + 联动情报）
    html = generate_html(data, analyzed, significant, match_intel, all_snapshots, ai_results)
    html_path = save_html(html)

    # 9. 打印摘要
    total_up = sum(r["trend_summary"]["up"] for r in analyzed)
    total_down = sum(r["trend_summary"]["down"] for r in analyzed)
    total_new = sum(r["trend_summary"]["new"] for r in analyzed)
    total_flat = sum(r["trend_summary"]["flat"] for r in analyzed)

    print(f"\n{'─'*40}")
    print(f"[摘要] 比分赔率趋势分析:")
    print(f"  总比赛数: {len(analyzed)}")
    print(f"  赔率上升: {total_up} 项")
    print(f"  赔率下降: {total_down} 项")
    print(f"  新增赔率: {total_new} 项")
    print(f"  保持不变: {total_flat} 项")
    ai_mode = "大模型" if ai_available() else "离线规则"
    print(f"  AI 分析: {ai_mode}模式")
    if significant:
        print(f"\n  显著变化 TOP 5:")
        for d in significant[:5]:
            arrow = "▲" if d["direction"] == "up" else ("▼" if d["direction"] == "down" else "●")
            chg = d.get("change")
            if chg is not None:
                sign = "+" if chg > 0 else ""
                print(f"    {d['match']} [{d['score']}] {d['previous']} → {d['current']} {arrow}{sign}{chg}")
            else:
                print(f"    {d['match']} [{d['score']}] {arrow} {d['direction']}")
    print(f"{'─'*40}")
    print(f"[完成] HTML 报告: {html_path}")

    return html_path


def run_watch(interval_minutes=60):
    """持续监控模式"""
    print(f"世界杯比分赔率监控已启动")
    print(f"运行模式: 每 {interval_minutes} 分钟自动抓取一次")
    print(f"按 Ctrl+C 停止监控\n")

    while True:
        try:
            run_once()
            next_str = datetime.fromtimestamp(
                datetime.now().timestamp() + interval_minutes * 60
            ).strftime("%H:%M:%S")
            print(f"\n[等待] 下次抓取时间: {next_str}")

            for _ in range(interval_minutes * 60):
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[停止] 监控已停止")
            break
        except Exception as e:
            print(f"\n[错误] 运行异常: {e}")
            time.sleep(60)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--watch" in args or "--monitor" in args:
        interval = 60
        if "--interval" in args:
            idx = args.index("--interval")
            if idx + 1 < len(args):
                interval = int(args[idx + 1])
        run_watch(interval)
    else:
        html_path = run_once()
        print(f"\n比分赔率报告已生成: {html_path}")
        print(f"持续监控: python main.py --watch")
