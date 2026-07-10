# -*- coding: utf-8 -*-
"""
比分赔率 HTML 统计表生成器
为每场世界杯比赛生成比分赔率矩阵，包含趋势箭头
"""
import os

from analytics import generate_analytics_html

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def escape_attr(s):
    """转义 HTML 属性中的特殊字符"""
    return s.replace("&", "&amp;").replace('"', "&quot;").replace("'", "&#39;").replace("<", "&lt;").replace(">", "&gt;")

# 比分矩阵结构: {主队进球: {客队进球: 比分标签}}
# 用于生成矩阵表头
HOME_GOALS = [0, 1, 2, 3, 4, 5]
AWAY_GOALS = [0, 1, 2, 3, 4, 5]


def make_score_label(h, a):
    """生成比分标签, 如 0:1, 4:2"""
    if h == 0 and a == 0:
        return "0:0"
    return f"{h}:{a}"


def trend_arrow(direction):
    if direction == "up":
        return "▲"
    elif direction == "down":
        return "▼"
    elif direction == "new":
        return "●"
    elif direction == "removed":
        return "×"
    return ""


def trend_css_class(direction):
    if direction == "up":
        return "up"
    elif direction == "down":
        return "down"
    elif direction == "new":
        return "new"
    elif direction == "removed":
        return "removed"
    return "flat"


def build_score_cell(score, changes, show_gold=False):
    """生成单个比分赔率单元格HTML — 展示当前赔率、趋势箭头、上次赔率、完整历史轨迹"""
    info = changes.get(score, {"current": "", "direction": "flat"})
    current = info.get("current", "-")
    if not current:
        return '<td class="empty">-</td>'

    direction = info.get("direction", "flat")
    prev = info.get("previous", "")
    change_val = info.get("change")
    history_trail = info.get("history_trail", [])
    opening = info.get("opening")
    total_change = info.get("total_change")
    total_dir = info.get("total_direction", "flat")

    css = trend_css_class(direction)
    arrow = trend_arrow(direction)

    # 色块基于开盘→当前总趋势 (不影响文字箭头)
    total_bg = "total-bg-" + total_dir

    html = f'<td class="score-cell {css} {total_bg}">'
    gold = '<i class="gold-ball"></i>' if show_gold else ''
    html += f'<span class="val">{gold}{current}{arrow}</span>'

    # 显示上次赔率
    if direction == "new":
        html += '<span class="prev-info new">NEW</span>'
    elif direction == "flat":
        if prev:
            html += f'<span class="prev-info flat">前 {prev}</span>'
        else:
            html += '<span class="prev-info flat">-</span>'
    else:
        if prev:
            html += f'<span class="prev-info prev-val">前 {prev}</span>'
        if change_val is not None:
            sign = "+" if change_val > 0 else ""
            html += f'<span class="delta">{sign}{change_val}</span>'

    # 显示完整历史轨迹（点击展开弹窗）
    if history_trail and len(history_trail) >= 2:
        # 开盘到当前总变化趋势
        total_icon = ""
        total_cls = "total-flat"
        if total_dir == "up":
            total_icon = "▲"
            total_cls = "total-up"
        elif total_dir == "down":
            total_icon = "▼"
            total_cls = "total-down"

        # 存储完整轨迹（管道分隔），JS 端构建方向图标
        trail_values = "|".join(history_trail)
        html += (
            f'<span class="history-trail history-clickable {total_cls}" '
            f'onclick="showTrail(event, this)" '
            f'data-trail-values="{escape_attr(trail_values)}" '
            f'data-score="{escape_attr(score)}" '
            f'data-opening="{escape_attr(history_trail[0])}" '
            f'title="点击查看完整赔率轨迹">'
            f'开{history_trail[0]}{total_icon}'
            f'</span>'
        )

    html += '</td>'
    return html


def build_special_cells(changes, gold_scores=None):
    """生成胜其他/平其他/负其他三个特殊单元格"""
    gold_scores = gold_scores or set()
    cells = []
    for label in ["胜其他", "平其他", "负其他"]:
        cells.append(build_score_cell(label, changes, show_gold=(label in gold_scores)))
    return cells


def build_score_matrix(match):
    """
    为单场比赛生成比分赔率矩阵 HTML

    矩阵结构:
           客 0   客 1   客 2   客 3   客 4   客 5   胜/平/负其他
    主 0   [0:0]  [0:1]  ...
    主 1   [1:0]  [1:1]  ...
    主 2   [2:0]  ...
    主 3   [3:0]
    主 4   [4:0]
    主 5   [5:0]
    """
    changes = match.get("score_changes", {})
    current_scores = match.get("score_odds", {}).get("scores", {})

    # 无数据
    if not current_scores and not changes:
        return ""

    # 用 changes 或直接构建
    if not changes:
        # 首次, 无对比
        changes = {score: {"current": val, "direction": "new", "previous": ""}
                   for score, val in current_scores.items()}

    # 最低赔率 TOP5（最可能出现的比分）
    gold_scores = set()
    top5_html = ""
    if current_scores:
        try:
            sorted_scores = sorted(current_scores.items(), key=lambda x: float(x[1]))
            gold_scores = {s for s, _ in sorted_scores[:5]}
            top5_items = []
            for s, v in sorted_scores[:5]:
                top5_items.append(f'<span class="top5-badge"><i class="gold-ball"></i>{s} @{v}</span>')
            top5_html = '<div class="top5-scores">预测比分 TOP5: ' + " ".join(top5_items) + '</div>'
        except (ValueError, TypeError):
            pass

    # 构建矩阵行
    rows = []
    for h in HOME_GOALS:
        cells = [f'<td class="row-label">主 {h}</td>']
        for a in AWAY_GOALS:
            label = make_score_label(h, a)
            cells.append(build_score_cell(label, changes, show_gold=(label in gold_scores)))
        rows.append(f'<tr>{"".join(cells)}</tr>')

    # 胜其他/平其他/负其他 行
    special_cells = build_special_cells(changes, gold_scores=gold_scores)
    special_row = (
        '<tr class="special-row">'
        '<td class="row-label">其他</td>'
        f'{"".join(special_cells)}'
        '</tr>'
    )

    # 统计摘要
    summary = match.get("trend_summary", {})
    up = summary.get("up", 0)
    down = summary.get("down", 0)
    flat = summary.get("flat", 0)
    new = summary.get("new", 0)

    trend_tags = []
    if up > 0:
        trend_tags.append(f'<span class="tag up-tag">▲{up}升</span>')
    if down > 0:
        trend_tags.append(f'<span class="tag down-tag">▼{down}降</span>')
    if new > 0:
        trend_tags.append(f'<span class="tag new-tag">●{new}新</span>')
    if not trend_tags and flat > 0:
        trend_tags.append(f'<span class="tag flat-tag">→持平</span>')

    # 赔率更新时间
    update_date = match.get("score_odds", {}).get("update_date", "")
    update_time = match.get("score_odds", {}).get("update_time", "")

    # ---- 构建横向比分列表（精简版，用于摘要） ----
    # 按主队比分分组展示
    summary_rows_html = ""
    # 只展示有变化的或关键的低赔比分
    changed_scores = {
        s: c for s, c in changes.items()
        if c["direction"] in ("up", "down", "new")
    }
    if changed_scores:
        summary_items = []
        for s, c in sorted(changed_scores.items(), key=lambda x: abs(x[1]["change"] or 0), reverse=True):
            arrow = trend_arrow(c["direction"])
            val = c["current"]
            chg = c.get("change")
            if chg is not None:
                sign = "+" if chg > 0 else ""
                summary_items.append(
                    f'<span class="highlight-score {trend_css_class(c["direction"])}">'
                    f'{s}: {val}{arrow}{sign}{chg}</span>'
                )
        if summary_items:
            summary_rows_html = (
                '<div class="match-summary-row">'
                '<span class="summary-label">赔率变化:</span>'
                + " ".join(summary_items[:12]) +
                '</div>'
            )

    match_header = f"""
    <div class="match-block">
        <div class="match-header">
            <div class="match-info">
                <span class="match-num">{match.get('match_num', '')}</span>
                <span class="match-title">
                    {match.get('home_team_full', '')}{match.get('home_team', '')}
                    <span class="vs-text">VS</span>
                    {match.get('away_team_full', '')}{match.get('away_team', '')}
                </span>
                <span class="match-time">⏰ {match.get('match_date', '')} {match.get('match_time', '')}</span>
                <span class="match-location">📍 {match.get('remark', '')}</span>
            </div>
            <div class="match-stats">
                {"".join(trend_tags)}
                <span class="update-time">快照: {summary.get("snapshot_count", 1)}期 | 更新: {update_date} {update_time}</span>
            </div>
        </div>
        {summary_rows_html}
        {top5_html}
        <div class="matrix-container">
            <table class="score-matrix">
                <thead>
                    <tr>
                        <th class="corner">主队\\客队</th>
                        <th>客 0</th><th>客 1</th><th>客 2</th>
                        <th>客 3</th><th>客 4</th><th>客 5</th>
                        <th>其他</th>
                    </tr>
                </thead>
                <tbody>
                    {chr(10).join(rows)}
                    {special_row}
                </tbody>
            </table>
        </div>
    </div>
    """

    return match_header


def generate_html(data, analyzed_results, significant_changes, match_intel=None):
    """生成完整的比分赔率 HTML 统计表（含多维度智能预测）"""
    fetch_time = data.get("fetch_time", "")
    match_count = data.get("match_count", 0)
    is_fallback = data.get("_fallback", False)

    # 各比赛矩阵
    matrices = [build_score_matrix(r) for r in analyzed_results]
    matrices_html = "\n".join(m for m in matrices if m)

    # 构建预测数据 JSON（供前端搜索和预测）
    import json as _json
    from intel_fetcher import get_betting_deadline
    if match_intel is None:
        match_intel = {}

    prediction_data = []
    intel_meta = match_intel.get("_meta", {}) if isinstance(match_intel, dict) else {}
    for r in analyzed_results:
        scores = r.get("score_odds", {}).get("scores", {}) or {}
        changes = r.get("score_changes", {})
        summary = r.get("trend_summary", {})
        match_key = f"{r.get('home_team','')} vs {r.get('away_team','')}"
        intel = match_intel.get(match_key, {})
        top5 = []
        if scores:
            try:
                sorted_s = sorted(scores.items(), key=lambda x: float(x[1]))
                for s, v in sorted_s[:5]:
                    chg = changes.get(s, {})
                    top5.append({
                        "score": s,
                        "odds": v,
                        "prev": chg.get("previous", ""),
                        "direction": chg.get("direction", "flat"),
                        "change": chg.get("change"),
                        "total_dir": chg.get("total_direction", "flat"),
                    })
            except (ValueError, TypeError):
                pass
        prediction_data.append({
            "match": match_key,
            "home": r.get("home_team", ""),
            "away": r.get("away_team", ""),
            "date": r.get("match_date", ""),
            "time": r.get("match_time", ""),
            "betting_deadline": get_betting_deadline(
                r.get("match_date", ""), r.get("match_time", "")
            ),
            "top5": top5,
            "trends": {
                "up": summary.get("up", 0),
                "down": summary.get("down", 0),
                "flat": summary.get("flat", 0),
                "new": summary.get("new", 0),
            },
            "total_scores": len(scores),
            "intel": {
                "updated_at": intel.get("intel_updated_at", intel_meta.get("last_updated", "")),
                "stage": intel.get("stage", ""),
                "venue": intel.get("venue", ""),
                "weather": intel.get("weather", ""),
                "referee": intel.get("referee", ""),
                "match_date": intel.get("match_date", ""),
                "match_time": intel.get("match_time", ""),
                "team_form_home": intel.get("team_form_home", ""),
                "team_form_away": intel.get("team_form_away", ""),
                "players_home": intel.get("players_home", ""),
                "players_away": intel.get("players_away", ""),
                "news": intel.get("news", ""),
                "history_head2head": intel.get("history_head2head", ""),
                "prediction": intel.get("prediction", ""),
            },
        })
    prediction_json = _json.dumps(prediction_data, ensure_ascii=False)

    # 变化排行榜：按比赛日期/时间分组，同场比赛内按变化幅度排序
    sig_html = ""
    if significant_changes:
        # 建立比赛名称 -> 信息(顺序、日期、时间)
        match_info = {}
        for idx, r in enumerate(analyzed_results):
            key = f"{r['home_team']} vs {r['away_team']}"
            match_info[key] = {
                "order": idx,
                "date": r.get('match_date', ''),
                "time": r.get('match_time', ''),
            }

        # 按比赛分组
        groups = {}
        for d in significant_changes:
            key = d["match"]
            groups.setdefault(key, []).append(d)

        # 按比赛日期/时间排序，无日期则按出场顺序
        def _match_sort_key(key):
            info = match_info.get(key, {})
            return (info.get("date") or "", info.get("time") or "", info.get("order", 9999))

        sorted_match_keys = sorted(groups.keys(), key=_match_sort_key)

        # 构建每个比赛的子区域
        group_sections = []
        for key in sorted_match_keys:
            items = groups[key]
            # 同场比赛内：先赔率升高 → 再赔率降低 → 其他，各自按百分比排序
            def _sort_key(x):
                dr = x.get("direction", "")
                if dr == "up":
                    priority = 0
                elif dr == "down":
                    priority = 1
                else:
                    priority = 2
                pct = abs(x["percent"]) if x.get("percent") is not None else 0
                return (priority, -pct)
            items.sort(key=_sort_key)
            total_in_group = len(items)
            # 每场比赛最多展示 10 项变化最显著的赔率
            items = items[:10]

            info = match_info.get(key, {})
            date_str = info.get("date", "")
            time_str = info.get("time", "")
            date_time = f"{date_str} {time_str}".strip()

            item_html = []
            for d in items:
                arrow = trend_arrow(d["direction"])
                css = trend_css_class(d["direction"])
                cur = d["current"]
                prev = d["previous"]
                chg = d.get("change")
                if chg is not None and chg != 0:
                    sign = "+" if chg > 0 else ""
                    chg_str = f'{arrow} {sign}{chg} ({sign}{d["percent"]}%)'
                elif d["direction"] == "new":
                    chg_str = f'● 新增'
                elif d["direction"] == "removed":
                    chg_str = f'× 移除'
                else:
                    chg_str = '→ 不变'

                item_html.append(f"""
                    <div class="sig-item {css}">
                        <span class="sig-score">{d['score']}</span>
                        <span class="sig-change">{chg_str}</span>
                        <span class="sig-odds">{prev or '-'} → {cur or '-'}</span>
                    </div>
                """)

            group_sections.append(f"""
                <div class="sig-group">
                    <div class="sig-group-header">
                        <span class="sig-group-time">{date_time}</span>
                        <span class="sig-group-match">{key}</span>
                        <span class="sig-group-count">{len(items)}/{total_in_group}项</span>
                    </div>
                    <div class="sig-group-items">{''.join(item_html)}</div>
                </div>
            """)

        sig_html = f"""
        <div class="significant-section">
            <h2>📊 比分赔率变化</h2>
            <div class="sig-groups">{''.join(group_sections)}</div>
        </div>
        """

    # 空状态
    if not matrices_html:
        matrices_html = """
        <div class="empty-state">
            <p>暂无在售世界杯比赛比分赔率</p>
            <p>请等待下一轮比赛开售</p>
        </div>
        """

    # 赔率分析：Overround、隐含概率、赔率变化
    analytics_html = generate_analytics_html()

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>世界杯比分赔率统计表 - {fetch_time}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, "Microsoft YaHei", "Segoe UI", sans-serif;
            background: #f5f5f5;
            color: #333;
            padding: 16px;
        }}

        .header {{
            background: linear-gradient(135deg, #0d47a1 0%, #1565c0 50%, #1e88e5 100%);
            color: white;
            padding: 20px 28px;
            border-radius: 10px;
            margin-bottom: 16px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.1);
        }}
        .header h1 {{ font-size: 22px; margin-bottom: 6px; }}
        .header .meta {{ font-size: 13px; opacity: 0.9; display: flex; gap: 20px; flex-wrap: wrap; }}
        .header .meta span {{ display: flex; align-items: center; gap: 4px; }}

        .legend-bar {{
            padding: 16px 20px;
            background: white;
            border-radius: 8px;
            margin-bottom: 16px;
            font-size: 12px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        .legend-title {{
            font-weight: bold;
            font-size: 13px;
            color: #333;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid #eee;
        }}
        .legend-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
            gap: 6px 24px;
        }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .legend-item .arrow-sample {{ font-weight: bold; font-size: 14px; }}
        .legend-item .arrow-sample.up {{ color: #c62828; }}
        .legend-item .arrow-sample.down {{ color: #2e7d32; }}
        .legend-item .arrow-sample.new {{ color: #0d47a1; font-size: 11px; }}

        /* ===== 赔率分析面板 ===== */
        .analytics-section {{
            margin-bottom: 16px;
            padding: 16px 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        .match-analytics {{
            margin-bottom: 24px;
            padding: 16px;
            background: #fafafa;
            border-radius: 8px;
            border: 1px solid #e0e0e0;
        }}
        .match-analytics:last-child {{ margin-bottom: 0; }}
        .ma-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 14px;
            padding-bottom: 10px;
            border-bottom: 2px solid #1565c0;
        }}
        .ma-match {{ font-size: 15px; font-weight: 700; color: #333; }}
        .ma-time {{ font-size: 12px; color: #888; }}
        .ma-section-title {{
            font-size: 13px;
            font-weight: 700;
            color: #1565c0;
            margin-bottom: 8px;
        }}
        .ma-overround {{
            margin-bottom: 14px;
            padding: 12px;
            background: #e3f2fd;
            border-radius: 8px;
        }}
        .or-cards {{
            display: flex;
            gap: 12px;
            margin-bottom: 8px;
        }}
        .or-card {{
            flex: 1;
            text-align: center;
            padding: 10px 8px;
            background: white;
            border-radius: 6px;
        }}
        .or-card.highlight {{
            background: #fff3e0;
            border: 1px solid #ff8f00;
        }}
        .or-label {{ font-size: 11px; color: #888; margin-bottom: 4px; }}
        .or-value {{ font-size: 22px; font-weight: 800; color: #333; }}
        .or-card.highlight .or-value {{ color: #e65100; }}
        .or-note {{
            font-size: 11px;
            color: #666;
            line-height: 1.5;
        }}
        .ma-two-col {{
            display: flex;
            gap: 16px;
        }}
        .ma-col {{
            flex: 1;
            min-width: 0;
        }}
        .prob-table, .change-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        .prob-table th, .change-table th {{
            text-align: left;
            padding: 5px 8px;
            background: #f5f5f5;
            border-bottom: 1px solid #ddd;
            color: #666;
            font-weight: 600;
        }}
        .prob-table td, .change-table td {{
            padding: 4px 8px;
            border-bottom: 1px solid #f0f0f0;
        }}
        .score-cell {{ font-weight: 600; color: #333; }}
        .odds-cell {{ color: #e65100; font-weight: 600; }}
        .prob-cell {{ position: relative; }}
        .prob-bar-wrap {{
            position: relative;
            height: 20px;
            background: #eee;
            border-radius: 3px;
            overflow: hidden;
        }}
        .prob-bar {{
            height: 100%;
            background: linear-gradient(90deg, #42a5f5, #1565c0);
            border-radius: 3px;
            transition: width 0.5s;
        }}
        .prob-val {{
            position: absolute;
            left: 6px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 11px;
            font-weight: 700;
            color: #333;
        }}
        .raw-cell {{ color: #999; font-size: 11px; }}
        .change-cell {{ font-weight: 700; }}
        .change-cell.up {{ color: #c62828; }}
        .change-cell.down {{ color: #2e7d32; }}
        .no-data {{ text-align: center; color: #bbb; padding: 8px; }}
        .change-subtitle {{
            font-size: 11px;
            color: #888;
            margin: 8px 0 4px;
            font-weight: 600;
        }}

        .predict-section {{
            margin-bottom: 16px;
            padding: 16px 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        .predict-status-bar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 14px;
            margin-bottom: 12px;
            background: linear-gradient(135deg, #e8f5e9, #f1f8e9);
            border: 1px solid #c8e6c9;
            border-radius: 8px;
            font-size: 12px;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .predict-status-bar .status-left {{
            display: flex;
            align-items: center;
            gap: 12px;
            flex-wrap: wrap;
        }}
        .predict-status-bar .status-label {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-weight: 700;
            color: #2e7d32;
        }}
        .predict-status-bar .status-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #4caf50;
            animation: pulse-dot 1.5s ease-in-out infinite;
        }}
        @keyframes pulse-dot {{
            0%, 100% {{ opacity: 1; transform: scale(1); }}
            50% {{ opacity: 0.4; transform: scale(1.5); }}
        }}
        .predict-status-bar .deadline-info {{
            color: #555;
            font-weight: 600;
        }}
        .predict-status-bar .deadline-countdown-live {{
            font-weight: 800;
            color: #c62828;
            font-size: 14px;
            min-width: 80px;
        }}
        .predict-status-bar .deadline-countdown-live.urgent {{
            animation: blink-red 0.8s ease-in-out infinite;
        }}
        @keyframes blink-red {{
            0%, 100% {{ color: #c62828; }}
            50% {{ color: #ff1744; }}
        }}
        .predict-status-bar .deadline-countdown-live.expired {{
            color: #999;
        }}
        .predict-status-bar .status-right {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .predict-status-bar .auto-refresh-info {{
            color: #888;
            font-size: 11px;
        }}
        .predict-status-bar .auto-refresh-info .next-refresh {{
            font-weight: 600;
            color: #1565c0;
        }}
        .predict-status-bar .refresh-btn {{
            padding: 5px 12px;
            background: #1565c0;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 11px;
            cursor: pointer;
            font-weight: 600;
        }}
        .predict-status-bar .refresh-btn:hover {{
            background: #0d47a1;
        }}
        .predict-search {{
            display: flex;
            gap: 10px;
            align-items: center;
            margin-bottom: 14px;
        }}
        .predict-search input {{
            flex: 1;
            padding: 10px 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: border-color 0.2s;
        }}
        .predict-search input:focus {{
            border-color: #1565c0;
        }}
        .predict-search input::placeholder {{
            color: #bbb;
        }}
        .predict-search .predict-btn {{
            padding: 10px 20px;
            background: linear-gradient(135deg, #ff8f00, #f9a825);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            white-space: nowrap;
            transition: opacity 0.2s;
        }}
        .predict-search .predict-btn:hover {{
            opacity: 0.9;
        }}

        .predict-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
            gap: 12px;
        }}
        .predict-card {{
            background: linear-gradient(135deg, #fafafa 0%, #f5f5f5 100%);
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 16px;
            transition: all 0.2s;
        }}
        .predict-card.highlight {{
            border-color: #f9a825;
            box-shadow: 0 0 0 2px rgba(249, 168, 37, 0.25);
            background: linear-gradient(135deg, #fffde7 0%, #fff8e1 100%);
        }}
        .predict-card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: wrap;
            gap: 6px;
        }}
        .predict-card-match {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
        }}
        .predict-card-time {{
            font-size: 11px;
            color: #888;
            background: #eee;
            padding: 2px 8px;
            border-radius: 4px;
        }}
        .predict-score {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 22px;
            font-weight: 800;
            color: #0d47a1;
            background: #e3f2fd;
            padding: 4px 16px;
            border-radius: 8px;
            margin-bottom: 8px;
        }}
        .predict-score .gold-ball {{
            width: 14px;
            height: 14px;
        }}
        .predict-reason {{
            font-size: 12px;
            color: #666;
            line-height: 1.6;
        }}
        .predict-reason strong {{
            color: #333;
        }}
        .predict-trend-tags {{
            display: flex;
            gap: 6px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}
        .predict-trend-tag {{
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .predict-trend-tag.up {{ background: #ffebee; color: #c62828; }}
        .predict-trend-tag.down {{ background: #e8f5e9; color: #2e7d32; }}
        .predict-trend-tag.flat {{ background: #f5f5f5; color: #888; }}
        .predict-card .top5-mini {{
            display: flex;
            gap: 8px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}
        .predict-card .top5-mini-item {{
            font-size: 12px;
            padding: 3px 10px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-weight: 600;
        }}
        .predict-card .top5-mini-item.gold {{
            border-color: #f9a825;
            background: #fffde7;
        }}
        .predict-deadline {{
            margin-top: 6px;
            padding: 6px 10px;
            background: #e8eaf6;
            border-radius: 6px;
            font-size: 11px;
            color: #3949ab;
            display: flex;
            align-items: center;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .predict-deadline .deadline-countdown {{
            font-weight: 800;
            color: #c62828;
            font-size: 13px;
        }}
        .predict-deadline.expired {{
            background: #ffebee;
            color: #c62828;
        }}
        .predict-deadline.expired .deadline-countdown {{
            color: #c62828;
        }}
        .intel-freshness {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 10px;
            color: #888;
            padding: 2px 6px;
            background: #f5f5f5;
            border-radius: 4px;
            vertical-align: middle;
            margin-left: 6px;
        }}
        .intel-freshness.fresh {{
            color: #2e7d32;
            background: #e8f5e9;
        }}
        .intel-freshness.stale {{
            color: #e65100;
            background: #fff3e0;
        }}
        .intel-freshness.expired {{
            color: #c62828;
            background: #ffebee;
        }}
        .scoring-breakdown {{
            margin-top: 8px;
            font-size: 10px;
            color: #999;
            display: flex;
            flex-wrap: wrap;
            gap: 4px 10px;
        }}
        .scoring-breakdown .dim {{
            white-space: nowrap;
        }}
        .scoring-breakdown .dim-bar {{
            display: inline-block;
            height: 4px;
            border-radius: 2px;
            vertical-align: middle;
            margin-right: 2px;
        }}
        .intel-section {{
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px dashed #ddd;
        }}
        .intel-title {{
            font-size: 12px;
            font-weight: bold;
            color: #1565c0;
            margin-bottom: 6px;
        }}
        .intel-row {{
            display: flex;
            gap: 8px;
            margin-bottom: 5px;
            font-size: 11px;
            line-height: 1.5;
        }}
        .intel-label {{
            min-width: 64px;
            font-weight: 600;
            color: #666;
            flex-shrink: 0;
        }}
        .intel-content {{
            color: #444;
            flex: 1;
        }}
        .intel-meta {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 6px;
        }}
        .intel-meta-tag {{
            font-size: 10px;
            padding: 1px 6px;
            border-radius: 3px;
            background: #e3f2fd;
            color: #1565c0;
        }}
        .intel-prediction {{
            margin-top: 6px;
            padding: 6px 10px;
            background: #fff3e0;
            border-left: 3px solid #ff8f00;
            border-radius: 4px;
            font-size: 11px;
            color: #555;
            line-height: 1.5;
        }}
        .predict-no-result {{
            text-align: center;
            color: #999;
            padding: 20px;
            font-size: 14px;
        }}

        .significant-section {{
            margin-bottom: 16px;
            padding: 16px 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
        .significant-section h2 {{
            font-size: 15px;
            margin-bottom: 10px;
            color: #333;
        }}
        .sig-list {{ display: flex; flex-wrap: wrap; gap: 8px; }}
        .sig-groups {{
            display: flex;
            flex-direction: column;
            gap: 14px;
        }}
        .sig-group {{
            background: #fafafa;
            border-radius: 8px;
            padding: 12px 16px;
            border: 1px solid #eee;
        }}
        .sig-group-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid #e0e0e0;
            flex-wrap: wrap;
        }}
        .sig-group-time {{
            font-size: 12px;
            color: #666;
            background: #e3f2fd;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .sig-group-match {{
            font-weight: bold;
            font-size: 14px;
            color: #333;
        }}
        .sig-group-count {{
            font-size: 11px;
            color: #999;
            margin-left: auto;
        }}
        .sig-group-items {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}
        .sig-item {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 12px;
            background: white;
            border: 1px solid #eee;
        }}
        .sig-item.up {{ background: #fff5f5; border-color: #ffcdd2; }}
        .sig-item.down {{ background: #f1f8e9; border-color: #c8e6c9; }}
        .sig-item.new {{ background: #e3f2fd; border-color: #90caf9; }}
        .sig-score {{
            font-weight: bold;
            font-size: 14px;
            min-width: 50px;
            padding: 2px 8px;
            background: #eee;
            border-radius: 4px;
        }}
        .sig-change {{ font-weight: bold; min-width: 100px; }}
        .sig-item.up .sig-change {{ color: #c62828; }}
        .sig-item.down .sig-change {{ color: #2e7d32; }}
        .sig-item.new .sig-change {{ color: #0d47a1; }}
        .sig-odds {{ color: #999; font-size: 11px; }}

        .match-block {{
            background: white;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
            overflow: hidden;
        }}
        .match-header {{
            padding: 16px 20px 12px;
            border-bottom: 1px solid #eee;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .match-info {{ display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }}
        .match-num {{
            background: #0d47a1;
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .match-title {{
            font-size: 18px;
            font-weight: bold;
        }}
        .vs-text {{
            color: #e53935;
            margin: 0 8px;
            font-size: 14px;
        }}
        .match-time {{ font-size: 13px; color: #666; }}
        .match-location {{ font-size: 12px; color: #999; max-width: 300px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }}

        .match-stats {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
        .tag {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .up-tag {{ background: #ffebee; color: #c62828; }}
        .down-tag {{ background: #e8f5e9; color: #2e7d32; }}
        .new-tag {{ background: #e3f2fd; color: #0d47a1; }}
        .flat-tag {{ background: #f5f5f5; color: #888; }}
        .update-time {{ font-size: 11px; color: #aaa; }}

        .match-summary-row {{
            padding: 8px 20px;
            background: #fafafa;
            font-size: 12px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
            border-bottom: 1px solid #eee;
        }}
        .summary-label {{ font-weight: bold; color: #555; margin-right: 4px; }}
        .highlight-score {{
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 600;
            font-size: 12px;
        }}
        .highlight-score.up {{ background: #ffebee; color: #c62828; }}
        .highlight-score.down {{ background: #e8f5e9; color: #2e7d32; }}
        .highlight-score.new {{ background: #e3f2fd; color: #0d47a1; }}

        .top5-scores {{
            padding: 8px 20px;
            background: #fffde7;
            font-size: 12px;
            border-bottom: 1px solid #fff9c4;
        }}
        .top5-badge {{
            display: inline-flex;
            align-items: center;
            gap: 2px;
            padding: 2px 10px;
            background: #fff;
            border: 1px solid #f9a825;
            border-radius: 12px;
            font-weight: 600;
            margin-right: 8px;
            font-size: 13px;
        }}
        .gold-ball {{
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: radial-gradient(circle at 35% 30%, #fff176, #f9a825 70%, #e65100);
            vertical-align: middle;
            box-shadow: 0 1px 3px rgba(249, 168, 37, 0.5);
            position: relative;
            top: -1px;
        }}

        .matrix-container {{
            padding: 12px 20px 20px;
            overflow-x: auto;
        }}
        .score-matrix {{
            border-collapse: collapse;
            font-size: 12px;
            min-width: 700px;
        }}
        .score-matrix th {{
            background: #e8eaf6;
            padding: 8px 6px;
            text-align: center;
            font-weight: 600;
            color: #333;
            font-size: 11px;
        }}
        .score-matrix th.corner {{
            background: #283593;
            color: white;
            text-align: left;
            padding-left: 12px;
        }}
        .score-matrix td {{
            padding: 6px 4px;
            text-align: center;
            border: 1px solid #e0e0e0;
        }}
        .score-matrix .row-label {{
            font-weight: 600;
            background: #e8eaf6;
            color: #283593;
            text-align: left;
            padding-left: 12px;
            font-size: 12px;
            white-space: nowrap;
        }}
        .score-matrix .special-row .row-label {{
            color: #e65100;
        }}

        .score-cell {{
            min-width: 72px;
            position: relative;
            cursor: default;
            vertical-align: middle;
        }}
        .score-cell .val {{
            font-weight: bold;
            font-size: 13px;
            display: block;
            line-height: 1.3;
        }}
        .score-cell .prev-info {{
            display: block;
            font-size: 10px;
            margin-top: 2px;
            color: #999;
        }}
        .score-cell .prev-info.flat {{ color: #aaa; }}
        .score-cell .prev-info.new {{
            color: #0d47a1;
            font-weight: 600;
            font-size: 11px;
        }}
        .score-cell .delta {{
            display: block;
            font-size: 10px;
            margin-top: 1px;
            font-weight: 600;
        }}
        .score-cell.up {{
        }}
        .score-cell.up .val {{ color: #c62828; }}
        .score-cell.up .delta {{ color: #c62828; }}
        .score-cell.up .prev-val {{ color: #999; }}
        .score-cell.down {{
        }}
        .score-cell.down .val {{ color: #2e7d32; }}
        .score-cell.down .delta {{ color: #2e7d32; }}
        .score-cell.down .prev-val {{ color: #999; }}
        .score-cell.new {{
        }}
        .score-cell.removed {{
            color: #bbb;
            text-decoration: line-through;
        }}
        .score-cell.flat .val {{ color: #000; }}
        .score-cell.new .val {{ color: #000; }}
        .score-cell.empty {{ color: #ddd; font-style: italic; }}

        /* 开盘→当前总趋势色块 */
        .score-cell.total-bg-down {{ /* 赔率降低=被看好=红色 */
            background: #ffcdd2;
            border: 1px solid #ef9a9a;
        }}
        .score-cell.total-bg-up {{ /* 赔率升高=不被看好=绿色 */
            background: #c8e6c9;
            border: 1px solid #a5d6a7;
        }}

        .score-cell .history-trail {{
            display: block;
            font-size: 10px;
            color: #777;
            margin-top: 2px;
            font-weight: 600;
        }}
        .score-cell .history-clickable {{
            cursor: pointer;
            text-decoration: underline;
            text-decoration-style: dotted;
            text-underline-offset: 3px;
            transition: all 0.15s;
        }}
        .score-cell .history-clickable:hover {{
            outline: 2px solid #0d47a1;
            outline-offset: 1px;
            border-radius: 3px;
        }}
        /* 开盘→当前总趋势颜色 */
        .score-cell .history-trail.total-up {{
            color: #c62828;
        }}
        .score-cell .history-trail.total-down {{
            color: #2e7d32;
        }}
        .score-cell .history-trail.total-flat {{
            color: #777;
        }}
        /* === 轨迹弹窗 === */
        .trail-overlay {{
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0,0,0,0.55);
            z-index: 9999;
            justify-content: center;
            align-items: center;
        }}
        .trail-overlay.active {{ display: flex; }}
        .trail-popup {{
            background: white;
            border-radius: 12px;
            max-width: 480px;
            width: 90%;
            padding: 0;
            box-shadow: 0 8px 40px rgba(0,0,0,0.25);
            animation: trailFadeIn 0.2s ease;
            overflow: hidden;
        }}
        @keyframes trailFadeIn {{
            from {{ opacity: 0; transform: scale(0.95) translateY(-10px); }}
            to {{ opacity: 1; transform: scale(1) translateY(0); }}
        }}
        .trail-popup-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background: linear-gradient(135deg, #0d47a1, #1565c0);
            color: white;
        }}
        .trail-popup-header h3 {{
            font-size: 15px;
            margin: 0;
        }}
        .trail-popup-header .close-btn {{
            background: rgba(255,255,255,0.2);
            color: white;
            border: none;
            width: 30px; height: 30px;
            border-radius: 50%;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            line-height: 1;
            transition: background 0.15s;
        }}
        .trail-popup-header .close-btn:hover {{
            background: rgba(255,255,255,0.4);
        }}
        .trail-popup-body {{
            padding: 20px;
            max-height: 420px;
            overflow-y: auto;
        }}
        .trail-chain {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 6px;
            font-size: 14px;
            line-height: 1.8;
        }}
        .trail-step {{
            font-weight: 700;
            padding: 2px 6px;
            border-radius: 4px;
            background: #f5f5f5;
            color: #333;
        }}
        .trail-step.trail-open {{
            background: #e3f2fd;
            color: #0d47a1;
            border: 2px solid #90caf9;
        }}
        .trail-step.trail-up {{
            background: #ffcdd2;
            color: #c62828;
        }}
        .trail-step.trail-down {{
            background: #c8e6c9;
            color: #2e7d32;
        }}
        .trail-step.trail-flat {{
            background: #f5f5f5;
            color: #777;
        }}
        .trail-arrow {{
            font-size: 13px;
            font-weight: bold;
        }}
        .trail-arrow.trail-up {{ color: #c62828; }}
        .trail-arrow.trail-down {{ color: #2e7d32; }}
        .trail-arrow.trail-flat {{ color: #bbb; }}
        .trail-popup-footer {{
            padding: 12px 20px;
            background: #fafafa;
            border-top: 1px solid #eee;
            font-size: 11px;
            color: #999;
            display: flex;
            justify-content: space-between;
        }}

        .score-matrix tbody tr:hover td {{
            background: #f5f5f5 !important;
        }}
        .score-matrix tbody tr:hover td.row-label {{
            background: #c5cae9 !important;
        }}

        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #999;
            font-size: 16px;
        }}

        .footer {{
            margin-top: 16px;
            padding: 12px 20px;
            background: white;
            border-radius: 8px;
            font-size: 12px;
            color: #888;
            text-align: center;
            box-shadow: 0 1px 4px rgba(0,0,0,0.05);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚽ 2026 世界杯比分赔率统计表</h1>
        <div class="meta">
            <span>📡 数据来源: m.sporttery.cn {'⚠️ [回退快照]' if is_fallback else ''}</span>
            <span>🕐 抓取时间: {fetch_time}</span>
            <span>📊 比赛数量: {match_count}</span>
        </div>
    </div>

    <div class="legend-bar">
        <div class="legend-title">赔率升高降低标注颜色</div>
        <div class="legend-grid">
            <span class="legend-item"><span class="arrow-sample up">▲</span> 赔率上升 (主队赔率升高 = 不被看好)</span>
            <span class="legend-item"><span class="arrow-sample down">▼</span> 赔率下降 (主队赔率降低 = 被看好)</span>
            <span class="legend-item"><span class="arrow-sample new">NEW</span> 新增赔率</span>
            <span class="legend-item"><span>→</span> 赔率不变</span>
            <span class="legend-item">开XX▲/▼ = 开盘赔率 + 开盘至今总趋势</span>
        </div>
    </div>

    <div class="analytics-section">
        <h2 style="font-size: 16px; font-weight: 700; color: #1565c0; margin-bottom: 12px;">
            📊 赔率深度分析：Overround · 隐含概率 · 赔率变化
        </h2>
        {analytics_html}
    </div>

    <div class="predict-section">
        <div class="predict-status-bar" id="predictStatusBar">
            <div class="status-left">
                <span class="status-label"><span class="status-dot"></span> 智能预测持续中</span>
                <span class="deadline-info">最近投注截止: <span class="deadline-countdown-live" id="liveDeadline">--</span></span>
            </div>
            <div class="status-right">
                <span class="auto-refresh-info">自动刷新 <span class="next-refresh" id="nextRefresh">5:00</span></span>
                <button class="refresh-btn" onclick="renderPredictions()">立即刷新</button>
            </div>
        </div>
        <div class="predict-search">
            <input type="text" id="predictInput" placeholder="搜索比赛（如 西班牙、阿根廷）或直接点「预测」查看全部..." onkeyup="handleSearch(event)">
            <button class="predict-btn" onclick="renderPredictions()">🔮 智能预测</button>
        </div>
        <div class="predict-cards" id="predictCards"></div>
    </div>

    {sig_html}

    {matrices_html}

    <div class="footer">
        数据来源: 中国体育彩票竞彩网 (m.sporttery.cn) | 每小时自动更新 | 仅供数据分析参考，不构成投注建议
    </div>

    <!-- 赔率轨迹弹窗 -->
    <div class="trail-overlay" id="trailOverlay" onclick="closeTrail(event)">
        <div class="trail-popup" onclick="event.stopPropagation()">
            <div class="trail-popup-header">
                <h3 id="trailTitle">赔率完整轨迹</h3>
                <button class="close-btn" onclick="closeTrail()">&times;</button>
            </div>
            <div class="trail-popup-body">
                <div class="trail-chain" id="trailContent"></div>
            </div>
            <div class="trail-popup-footer">
                <span id="trailLabel">点击外部区域关闭</span>
                <span id="trailSummary"></span>
            </div>
        </div>
    </div>

    <!-- 预测数据 -->
    <script id="predictData" type="application/json">{prediction_json}</script>

    <script>
    var PREDICT_DATA = JSON.parse(document.getElementById('predictData').textContent);
    var REFRESH_INTERVAL = 5 * 60; // 5分钟自动刷新预测
    var countdownTimer = null;
    var refreshTimer = null;
    var refreshSecondsLeft = REFRESH_INTERVAL;

    // ========== 多维度综合评分引擎 ==========
    function predictScore(match) {{
        var top5 = match.top5;
        if (!top5.length) return null;

        var best = top5[0];
        var intel = match.intel || {{}};
        var hasIntel = !!(intel.team_form_home || intel.players_home || intel.news);

        // 维度1: 赔率趋势分析 (权重25%)
        var upCount = match.trends.up;
        var downCount = match.trends.down;
        var total = upCount + downCount;
        var marketSignal = total > 0 ? ((downCount - upCount) / total) : 0;
        var oddsScore = 12.5 + marketSignal * 12.5;
        oddsScore = Math.max(2, Math.min(25, oddsScore));

        // 维度2: 球队近况 (权重25%)
        var formScore = 12.5;
        var formHome = (intel.team_form_home || '').toLowerCase();
        var formAway = (intel.team_form_away || '').toLowerCase();
        if (hasIntel) {{
            var homeStrong = /零封|全胜|固若金汤|逆转|绝杀|卫冕|顶级/.test(formHome);
            var homeWeak = /回落|低迷|差距/.test(formHome);
            var awayStrong = /大胜|爆冷/.test(formAway) && !/回落/.test(formAway);
            var awayWeak = /回落|低迷|差距|报销|缺阵/.test(formAway);
            if (homeStrong && awayWeak) formScore = 22;
            else if (homeStrong && !awayStrong) formScore = 18;
            else if (homeStrong && awayStrong) formScore = 14;
            else if (!homeStrong && awayWeak) formScore = 15;
            else if (awayStrong && (homeWeak || !homeStrong)) formScore = 8;
            else if (homeWeak) formScore = 6;
        }}

        // 维度3: 球员状态/伤病 (权重25%)
        var playerScore = 12.5;
        var playersHome = (intel.players_home || '').toLowerCase();
        var playersAway = (intel.players_away || '').toLowerCase();
        if (hasIntel) {{
            var homeMajorInjury = /报销|缺阵|受伤|出战成疑/.test(playersHome);
            var homeNoInjury = /无重大|完整/.test(playersHome);
            var awayMajorInjury = /报销|十字韧带|缺阵|退出赛事/.test(playersAway);
            var awayNoInjury = /无重大|完整/.test(playersAway);
            if (homeNoInjury && awayMajorInjury) playerScore = 22;
            else if (!homeMajorInjury && awayMajorInjury) playerScore = 19;
            else if (homeNoInjury && !awayMajorInjury) playerScore = 16;
            else if (homeMajorInjury && awayMajorInjury) playerScore = 10;
            else if (homeMajorInjury) playerScore = 7;
            else playerScore = 14;
        }}

        // 维度4: 消息面/历史交锋 (权重15%)
        var newsScore = 7.5;
        var news = (intel.news || '').toLowerCase();
        var h2h = (intel.history_head2head || '').toLowerCase();
        if (hasIntel && (news || h2h)) {{
            var homeAdv = /占优|全胜|不败/.test(h2h) || /克制|拿不到球/.test(news);
            var awayAdv = /劣势/.test(h2h);
            if (homeAdv) newsScore = 13;
            else if (awayAdv) newsScore = 4;
            else newsScore = 8;
        }}

        // 维度5: 场地/天气/裁判 (权重10%)
        var condScore = 5;
        var venue = (intel.venue || '').toLowerCase();
        var weather = (intel.weather || '').toLowerCase();
        var highHumidity = false;
        if (hasIntel && (venue || weather)) {{
            highHumidity = /湿度/.test(weather) && /[789]\\d%/.test(weather);
            var neutral = /洛杉矶|迈阿密|堪萨斯/.test(venue);
            if (neutral && !highHumidity) condScore = 6;
            else if (highHumidity) condScore = 3;
            else condScore = 5;
        }}

        // 综合评分
        var totalScore = oddsScore + formScore + playerScore + newsScore + condScore;

        // 信心度映射
        var confidence, confLabel;
        if (totalScore >= 72) {{ confidence = "高"; confLabel = "多方信号共振，信心度高"; }}
        else if (totalScore >= 55) {{ confidence = "中高"; confLabel = "多数维度支持，可参考"; }}
        else if (totalScore >= 40) {{ confidence = "中"; confLabel = "部分维度有分歧，需谨慎"; }}
        else if (totalScore >= 25) {{ confidence = "低"; confLabel = "多维度交叉矛盾，不确定性大"; }}
        else {{ confidence = "极低"; confLabel = "建议观望，等待更多信息"; }}

        // 推理说明
        var reasons = [];
        if (hasIntel) {{
            if (formScore >= 18) reasons.push("主队近况占优");
            else if (formScore <= 8) reasons.push("客队近况更佳");
            if (playerScore >= 18) reasons.push("主队阵容完整，客队有关键球员缺阵");
            else if (playerScore <= 8) reasons.push("主队存在伤病隐患");
            if (newsScore >= 12) reasons.push("历史交锋和消息面支持主队");
            if (marketSignal > 0.2) reasons.push("赔率趋势积极(机构看好)");
            else if (marketSignal > 0) reasons.push("赔率趋势偏积极");
            else if (marketSignal < -0.15) reasons.push("赔率趋势偏消极");
            if (highHumidity) reasons.push("高温高湿增加比赛不确定性");
        }} else {{
            if (marketSignal > 0.2) reasons.push("赔率趋势积极(无多维情报辅助)");
            else reasons.push("赔率趋势参考(无多维情报辅助)");
        }}
        var reason = reasons.join("；") || "无显著信号";

        // TOP1 比分自身趋势
        var totalDir = best.total_dir || "flat";
        if (totalDir === "down") {{
            reason += "。该比分从开盘至今持续下降，热度上升";
            if (confidence === "低") confidence = "中";
        }} else if (totalDir === "up") {{
            reason += "。该比分从开盘至今持续上升，热度减退";
            if (confidence === "高") confidence = "中高";
        }}

        var scoringDetail = [];
        scoringDetail.push({{label: "赔率趋势", score: oddsScore, max: 25}});
        scoringDetail.push({{label: "球队近况", score: formScore, max: 25}});
        scoringDetail.push({{label: "球员状态", score: playerScore, max: 25}});
        scoringDetail.push({{label: "消息面", score: newsScore, max: 15}});
        scoringDetail.push({{label: "场地条件", score: condScore, max: 10}});

        return {{
            best: best, top5: top5, reason: reason, confLabel: confLabel,
            confidence: confidence, totalScore: totalScore, maxScore: 100,
            scoringDetail: scoringDetail, marketSignal: marketSignal,
            upCount: upCount, downCount: downCount, hasIntel: hasIntel
        }};
    }}

    // ========== 获取全局最早投注截止时间 ==========
    function getEarliestDeadline() {{
        var earliest = null;
        for (var i = 0; i < PREDICT_DATA.length; i++) {{
            var dl = PREDICT_DATA[i].betting_deadline;
            if (!dl) continue;
            var dt = new Date(dl.replace(/-/g, '/'));
            if (!earliest || dt < earliest) earliest = dt;
        }}
        return earliest;
    }}

    // ========== 实时倒计时 ==========
    function updateLiveCountdown() {{
        var el = document.getElementById('liveDeadline');
        if (!el) return;
        var earliest = getEarliestDeadline();
        if (!earliest) {{
            el.textContent = '--';
            el.className = 'deadline-countdown-live';
            return;
        }}
        var now = new Date();
        var remainSec = Math.floor((earliest - now) / 1000);
        if (remainSec <= 0) {{
            el.textContent = '已截止';
            el.className = 'deadline-countdown-live expired';
            // 所有比赛都截止了，停止刷新
            if (refreshTimer) {{
                clearInterval(refreshTimer);
                refreshTimer = null;
                document.getElementById('nextRefresh').textContent = '已停止';
            }}
            return;
        }}
        var days = Math.floor(remainSec / 86400);
        var hours = Math.floor((remainSec % 86400) / 3600);
        var mins = Math.floor((remainSec % 3600) / 60);
        var secs = remainSec % 60;
        var str = '';
        if (days > 0) str = days + '天' + hours + '时' + mins + '分' + secs + '秒';
        else if (hours > 0) str = hours + '时' + mins + '分' + secs + '秒';
        else str = mins + '分' + secs + '秒';
        el.textContent = str;
        el.className = 'deadline-countdown-live' + (remainSec < 3600 ? ' urgent' : '');
    }}

    // ========== 自动刷新倒计时 ==========
    function updateRefreshCountdown() {{
        var el = document.getElementById('nextRefresh');
        if (!el) return;
        if (refreshSecondsLeft <= 0) {{
            refreshSecondsLeft = REFRESH_INTERVAL;
            renderPredictions();
        }}
        var mins = Math.floor(refreshSecondsLeft / 60);
        var secs = refreshSecondsLeft % 60;
        el.textContent = mins + ':' + (secs < 10 ? '0' : '') + secs;
        refreshSecondsLeft--;
    }}

    // ========== 卡片渲染 ==========
    function renderPredictions() {{
        var input = document.getElementById('predictInput');
        var container = document.getElementById('predictCards');
        var keyword = (input.value || '').toLowerCase().trim();

        var filtered = PREDICT_DATA;
        if (keyword) {{
            filtered = PREDICT_DATA.filter(function(m) {{
                return m.match.toLowerCase().indexOf(keyword) >= 0
                    || m.home.toLowerCase().indexOf(keyword) >= 0
                    || m.away.toLowerCase().indexOf(keyword) >= 0;
            }});
        }}

        if (!filtered.length) {{
            container.innerHTML = '<div class="predict-no-result">未找到匹配的比赛，换个关键词试试</div>';
            return;
        }}

        var html = '';
        var now = new Date();
        for (var i = 0; i < filtered.length; i++) {{
            var m = filtered[i];
            var p = predictScore(m);
            var dateTime = (m.date + ' ' + m.time).trim();

            var trendTags = '';
            if (m.trends.up > 0) trendTags += '<span class="predict-trend-tag up">▲' + m.trends.up + '升</span>';
            if (m.trends.down > 0) trendTags += '<span class="predict-trend-tag down">▼' + m.trends.down + '降</span>';
            if (m.trends.flat > 0) trendTags += '<span class="predict-trend-tag flat">→' + m.trends.flat + '平</span>';

            var top5mini = '';
            if (p && p.top5.length) {{
                for (var j = 0; j < p.top5.length; j++) {{
                    var cls = (j === 0) ? 'top5-mini-item gold' : 'top5-mini-item';
                    top5mini += '<span class="' + cls + '">' + p.top5[j].score + ' @' + p.top5[j].odds + '</span>';
                }}
            }}

            // 投注截止倒计时（每张卡独立计算）
            var deadlineHtml = '';
            if (m.betting_deadline) {{
                var deadlineDate = new Date(m.betting_deadline.replace(/-/g, '/'));
                var remainSec = Math.floor((deadlineDate - now) / 1000);
                var remainMin = Math.floor(remainSec / 60);
                var remainDay = Math.floor(remainMin / 1440); remainMin = remainMin % 1440;
                var remainHour = Math.floor(remainMin / 60); remainMin = remainMin % 60;
                var countdownStr = '', deadlineCls = '';
                if (remainSec <= 0) {{
                    deadlineCls = 'expired';
                    countdownStr = '已截止';
                }} else if (remainDay > 0) {{
                    countdownStr = remainDay + '天' + remainHour + '时' + remainMin + '分';
                }} else if (remainHour > 0) {{
                    countdownStr = remainHour + '时' + remainMin + '分';
                }} else {{
                    countdownStr = remainMin + '分';
                }}
                deadlineHtml = '<div class="predict-deadline ' + deadlineCls + '" data-deadline="' + m.betting_deadline + '">'
                    + '<span>⏰ 投注截止</span>'
                    + '<span class="deadline-countdown">' + countdownStr + '</span>'
                    + '<span>(截止: ' + m.betting_deadline + ')</span>'
                    + '</div>';
            }}

            // 情报新鲜度指示
            var freshnessHtml = '';
            if (p && p.hasIntel) {{
                var updatedAt = m.intel.updated_at || '';
                if (updatedAt) {{
                    var updatedDate = new Date(updatedAt.replace(/-/g, '/'));
                    var ageMin = Math.floor((now - updatedDate) / 60000);
                    var ageStr, freshnessCls;
                    if (ageMin < 60) {{
                        ageStr = ageMin + '分钟前';
                        freshnessCls = 'fresh';
                    }} else if (ageMin < 180) {{
                        ageStr = Math.floor(ageMin / 60) + '小时前';
                        freshnessCls = 'fresh';
                    }} else if (ageMin < 360) {{
                        ageStr = Math.floor(ageMin / 60) + '小时前';
                        freshnessCls = 'stale';
                    }} else {{
                        ageStr = Math.floor(ageMin / 60) + '小时前';
                        freshnessCls = 'expired';
                    }}
                    freshnessHtml = '<span class="intel-freshness ' + freshnessCls + '">📡 情报 ' + ageStr + ' (赔率更新即刷新)</span>';
                }}
            }}

            // 评分明细条
            var scoringHtml = '';
            if (p && p.scoringDetail) {{
                var bars = [];
                for (var d = 0; d < p.scoringDetail.length; d++) {{
                    var dim = p.scoringDetail[d];
                    var pct = Math.round(dim.score / dim.max * 100);
                    var barColor = pct >= 70 ? '#2e7d32' : (pct >= 50 ? '#f9a825' : '#c62828');
                    bars.push(
                        '<span class="dim">'
                        + '<span class="dim-bar" style="width: ' + (pct / 2.5) + 'px; background: ' + barColor + ';"></span>'
                        + dim.label + ' ' + Math.round(dim.score) + '/' + dim.max
                        + '</span>'
                    );
                }}
                scoringHtml = '<div class="scoring-breakdown">' + bars.join(' ') + '</div>';
            }}

            // 多维情报面板
            var intel = m.intel || {{}};
            var intelHtml = '';
            var hasIntelPanel = intel.team_form_home || intel.team_form_away || intel.players_home || intel.news;
            if (hasIntelPanel) {{
                var metaTags = '';
                if (intel.stage) metaTags += '<span class="intel-meta-tag">' + intel.stage + '</span>';
                if (intel.venue) metaTags += '<span class="intel-meta-tag">📍 ' + intel.venue + '</span>';
                if (intel.weather) metaTags += '<span class="intel-meta-tag">🌤 ' + intel.weather + '</span>';
                if (intel.referee && intel.referee !== '待公布') metaTags += '<span class="intel-meta-tag">⚖️ ' + intel.referee + '</span>';

                var rows = '';
                if (intel.team_form_home) rows += '<div class="intel-row"><span class="intel-label">主队近况</span><span class="intel-content">' + intel.team_form_home + '</span></div>';
                if (intel.team_form_away) rows += '<div class="intel-row"><span class="intel-label">客队近况</span><span class="intel-content">' + intel.team_form_away + '</span></div>';
                if (intel.players_home) rows += '<div class="intel-row"><span class="intel-label">主队球员</span><span class="intel-content">' + intel.players_home + '</span></div>';
                if (intel.players_away) rows += '<div class="intel-row"><span class="intel-label">客队球员</span><span class="intel-content">' + intel.players_away + '</span></div>';
                if (intel.news) rows += '<div class="intel-row"><span class="intel-label">消息面</span><span class="intel-content">' + intel.news + '</span></div>';

                // 情报更新时间提示
                var intelNote = '';
                if (intel.updated_at) {{
                    intelNote = '<div style="font-size:10px;color:#aaa;margin-top:6px;">情报随赔率同步更新，最近刷新: ' + intel.updated_at + '</div>';
                }}

                intelHtml = '<div class="intel-section">'
                    + '<div class="intel-title">📋 多维度综合分析（赔率更新即刷新情报）</div>'
                    + (metaTags ? '<div class="intel-meta">' + metaTags + '</div>' : '')
                    + rows;
                if (intel.prediction) {{
                    intelHtml += '<div class="intel-prediction"><strong>媒体预测：</strong>' + intel.prediction + '</div>';
                }}
                intelHtml += intelNote + '</div>';
            }}

            // 卡片渲染
            if (p) {{
                html += '<div class="predict-card">'
                    + '<div class="predict-card-header">'
                    + '<span class="predict-card-match">' + m.match + '</span>'
                    + '<span class="predict-card-time">' + dateTime + '</span>'
                    + freshnessHtml
                    + '</div>'
                    + '<div class="predict-score"><i class="gold-ball"></i>' + p.best.score + '（赔率 ' + p.best.odds + '）</div>'
                    + '<div class="predict-reason"><strong>评分: ' + Math.round(p.totalScore) + '/100 (' + p.confidence + ')</strong> | ' + p.reason + '</div>'
                    + scoringHtml
                    + '<div class="predict-trend-tags">' + trendTags + '</div>'
                    + '<div class="top5-mini">' + top5mini + '</div>'
                    + deadlineHtml
                    + intelHtml
                    + '</div>';
            }} else {{
                html += '<div class="predict-card">'
                    + '<div class="predict-card-header">'
                    + '<span class="predict-card-match">' + m.match + '</span>'
                    + '<span class="predict-card-time">' + dateTime + '</span>'
                    + '</div>'
                    + '<div class="predict-reason">暂无赔率数据，请等待开售</div>'
                    + deadlineHtml
                    + intelHtml
                    + '</div>';
            }}
        }}

        container.innerHTML = html;
        // 重置自动刷新倒计时
        refreshSecondsLeft = REFRESH_INTERVAL;
    }}

    function handleSearch(e) {{
        if (e.key === 'Enter') renderPredictions();
    }}

    // ========== 定时器管理 ==========
    function startTimers() {{
        // 实时倒计时每秒更新
        if (countdownTimer) clearInterval(countdownTimer);
        countdownTimer = setInterval(function() {{
            updateLiveCountdown();
            // 同步更新所有卡片的截止倒计时
            updateCardDeadlines();
        }}, 1000);
        updateLiveCountdown();

        // 预测自动刷新每5分钟
        if (refreshTimer) clearInterval(refreshTimer);
        refreshTimer = setInterval(function() {{
            updateRefreshCountdown();
        }}, 1000);
        refreshSecondsLeft = REFRESH_INTERVAL;
    }}

    function updateCardDeadlines() {{
        var cards = document.querySelectorAll('.predict-deadline');
        if (!cards.length) return;
        var now = new Date();
        for (var i = 0; i < cards.length; i++) {{
            var card = cards[i];
            var deadlineStr = card.getAttribute('data-deadline');
            if (!deadlineStr) continue;
            var deadlineDate = new Date(deadlineStr.replace(/-/g, '/'));
            var remainSec = Math.floor((deadlineDate - now) / 1000);
            var countdownEl = card.querySelector('.deadline-countdown');
            if (!countdownEl) continue;
            if (remainSec <= 0) {{
                countdownEl.textContent = '已截止';
                card.classList.add('expired');
            }} else {{
                var days = Math.floor(remainSec / 86400);
                var hours = Math.floor((remainSec % 86400) / 3600);
                var mins = Math.floor((remainSec % 3600) / 60);
                if (days > 0) countdownEl.textContent = days + '天' + hours + '时' + mins + '分';
                else if (hours > 0) countdownEl.textContent = hours + '时' + mins + '分';
                else countdownEl.textContent = mins + '分';
            }}
        }}
    }}

    // 页面加载：渲染预测 + 启动定时器
    renderPredictions();
    startTimers();
    </script>
    function showTrail(event, el) {{
        event.stopPropagation();
        var overlay = document.getElementById('trailOverlay');
        var content = document.getElementById('trailContent');
        var title = document.getElementById('trailTitle');
        var summary = document.getElementById('trailSummary');
        var label = document.getElementById('trailLabel');

        var rawValues = el.getAttribute('data-trail-values');
        var score = el.getAttribute('data-score');
        var opening = el.getAttribute('data-opening');
        var values = rawValues.split('|');

        title.textContent = '比分 ' + score + ' 赔率完整轨迹';
        label.textContent = '开盘: ' + opening;

        // 构建带方向图标的轨迹 HTML
        var upCount = 0, downCount = 0;
        var parts = [];
        for (var i = 0; i < values.length; i++) {{
            var val = values[i];
            if (i === 0) {{
                parts.push('<span class="trail-step trail-open">' + val + '</span>');
            }} else {{
                var prevV = parseFloat(values[i - 1]);
                var currV = parseFloat(val);
                var cls, icon;
                if (currV > prevV) {{
                    cls = 'trail-up'; icon = '&#9650;'; upCount++;
                }} else if (currV < prevV) {{
                    cls = 'trail-down'; icon = '&#9660;'; downCount++;
                }} else {{
                    cls = 'trail-flat'; icon = '&#8594;';
                }}
                parts.push(
                    '<span class="trail-arrow ' + cls + '">' + icon + '</span> ' +
                    '<span class="trail-step ' + cls + '">' + val + '</span>'
                );
            }}
        }}
        content.innerHTML = parts.join(' ');

        var totalSteps = upCount + downCount;
        summary.textContent = '共 ' + totalSteps + ' 步变化 | &#9650;' + upCount + '升 &#9660;' + downCount + '降';

        overlay.classList.add('active');
    }}

    function closeTrail(event) {{
        if (event && event.target !== document.getElementById('trailOverlay')) return;
        document.getElementById('trailOverlay').classList.remove('active');
    }}

    // ESC 关闭
    document.addEventListener('keydown', function(e) {{
        if (e.key === 'Escape') {{
            document.getElementById('trailOverlay').classList.remove('active');
        }}
    }});
    </script>
</body>
</html>"""

    return html


def save_html(html_content):
    """保存 HTML 文件"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, "worldcup_score_odds.html")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"[输出] HTML 比分赔率统计表已生成: {filepath}")
    return filepath
