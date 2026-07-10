# -*- coding: utf-8 -*-
"""
AI 大模型分析引擎
使用大语言模型综合分析多维情报 + 赔率趋势，产出自然语言预测

支持的 API（OpenAI 兼容接口）:
- DeepSeek:    https://api.deepseek.com/v1
- 硅基流动:    https://api.siliconflow.cn/v1
- 通义千问:    https://dashscope.aliyuncs.com/compatible-mode/v1
- 智谱 GLM:    https://open.bigmodel.cn/api/paas/v4

配置方式: 设置环境变量
- AI_API_KEY:  API 密钥
- AI_API_BASE: API 地址（默认 DeepSeek）
- AI_MODEL:    模型名称（默认 deepseek-chat）

若未配置 API Key，AI 分析功能自动降级为离线规则模式。
"""
import os
import json
import urllib.request
import urllib.error


# ---- 配置 ----
API_KEY = os.environ.get("AI_API_KEY", "")
API_BASE = os.environ.get("AI_API_BASE", "https://api.deepseek.com/v1")
MODEL = os.environ.get("AI_MODEL", "deepseek-chat")
TIMEOUT = int(os.environ.get("AI_TIMEOUT", "30"))


def ai_available():
    """检查 AI API 是否已配置"""
    return bool(API_KEY)


def _call_ai(prompt, max_tokens=1200):
    """调用 AI 大模型，返回文本响应"""
    if not API_KEY:
        return None

    url = f"{API_BASE.rstrip('/')}/chat/completions"
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "你是世界杯足球比赛分析专家，擅长综合多维信息进行比分预测分析。回复简洁专业，使用中文。"},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    })

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"[AI] API 错误 {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"[AI] 请求失败: {e}")
        return None


def analyze_match_with_ai(match_key, home, away, intel_data, odds_data):
    """
    使用 AI 大模型综合分析一场比赛

    Args:
        match_key: "西班牙 vs 比利时"
        home: 主队名
        away: 客队名
        intel_data: 情报字典（team_form_home, players_home, news, prediction 等）
        odds_data: 赔率数据（top5 比分、趋势摘要、overround 等）

    Returns:
        dict: {"prediction", "analysis", "key_factors", "recommendation", "source": "ai"|"offline"}
    """
    if not ai_available():
        return _offline_analysis(match_key, home, away, intel_data, odds_data)

    prompt = _build_ai_prompt(match_key, home, away, intel_data, odds_data)
    result = _call_ai(prompt, max_tokens=1000)

    if not result:
        print(f"[AI] 模型调用失败，降级为离线分析: {match_key}")
        return _offline_analysis(match_key, home, away, intel_data, odds_data)

    # 解析 AI 返回的 JSON
    try:
        # 尝试提取 JSON 块
        if "```json" in result:
            start = result.index("```json") + 7
            end = result.index("```", start)
            parsed = json.loads(result[start:end].strip())
        elif "```" in result:
            start = result.index("```") + 3
            end = result.index("```", start)
            parsed = json.loads(result[start:end].strip())
        else:
            # 尝试直接解析
            parsed = json.loads(result)

        return {
            "prediction": parsed.get("prediction", ""),
            "analysis": parsed.get("analysis", ""),
            "key_factors": parsed.get("key_factors", []),
            "recommendation": parsed.get("recommendation", ""),
            "source": "ai",
        }
    except (json.JSONDecodeError, ValueError):
        # JSON 解析失败，直接使用纯文本结果
        return {
            "prediction": "",
            "analysis": result,
            "key_factors": [],
            "recommendation": "",
            "source": "ai",
        }


def _build_ai_prompt(match_key, home, away, intel_data, odds_data):
    """构建 AI 分析 prompt"""
    # 情报摘要
    intel_summary = []
    for field, label in [
        ("team_form_home", f"{home}近况"), ("team_form_away", f"{away}近况"),
        ("players_home", f"{home}球员"), ("players_away", f"{away}球员"),
        ("news", "海内外消息"), ("history_head2head", "历史交锋"),
        ("prediction", "媒体预测"), ("stage", "比赛阶段"),
        ("venue", "场地"), ("referee", "裁判组"),
        ("match_date", "比赛日期"), ("match_time", "开球时间"),
    ]:
        val = intel_data.get(field, "")
        if val:
            intel_summary.append(f"- {label}: {val}")

    intel_text = "\n".join(intel_summary) or "（暂无情报数据）"

    # 赔率摘要
    top5_text = ""
    if odds_data.get("top5"):
        for i, s in enumerate(odds_data["top5"][:5]):
            marker = "★" if i == 0 else ""
            dir_label = {"up": "↑", "down": "↓", "flat": "→", "new": "新"}.get(s.get("direction", ""), "")
            total_dir = {"up": "（整体上升）", "down": "（整体下降）", "flat": "（整体平稳）"}.get(s.get("total_dir", ""), "")
            top5_text += f"  {marker} {s['score']} @{s['odds']} {dir_label}{total_dir}\n"

    trends = odds_data.get("trends", {})
    odds_summary = f"""
赔率行情:
- 最低赔率比分: {top5_text.split(chr(10))[0] if top5_text else '无'}
- 全部 TOP5:
{top5_text.strip() or '  无数据'}
- 赔率变化: ▲{trends.get('up', 0)}项上升 / ▼{trends.get('down', 0)}项下降 / →{trends.get('flat', 0)}项持平 / 新{trends.get('new', 0)}项
- Overround(庄家抽水): {odds_data.get('overround_pct', 'N/A')}%
"""

    return f"""请综合分析以下世界杯比赛，给出预测建议。回复必须是 JSON 格式。

=== 比赛信息 ===
{match_key}（{home} vs {away}）

=== 多维度情报 ===
{intel_text}

=== 赔率数据 ===
{odds_summary}

=== 输出要求 ===
请以 JSON 格式输出：
{{
    "prediction": "比分预测和理由（一句话，如：看好西班牙2-0小胜，因防守稳固+比利时中场缺核心）",
    "analysis": "300字内的综合分析，涵盖球队状态、关键球员、战术匹配度、赔率信号",
    "key_factors": ["最关键的影响因素1", "因素2", "因素3"],
    "recommendation": "投注方向建议（如：主胜方向，小球，2-0/1-0比分区间）"
}}

注意：analysis 必须结合情报数据和赔率趋势，给出具体推理过程，不能泛泛而谈。
只输出 JSON，不要有其他文字。"""


def _offline_analysis(match_key, home, away, intel_data, odds_data):
    """离线规则分析（AI 不可用时的降级方案）"""
    form_home = intel_data.get("team_form_home", "")
    form_away = intel_data.get("team_form_away", "")
    players_home = intel_data.get("players_home", "")
    players_away = intel_data.get("players_away", "")
    news = intel_data.get("news", "")
    pred = intel_data.get("prediction", "")

    has_intel = bool(form_home or players_home or news)

    # 综合评估
    reasons = []
    if "零封" in form_home or "全胜" in form_home or "不败" in form_home:
        reasons.append(f"{home}防守稳固/状态出色")
    if "报销" in players_away or "缺阵" in players_away or "伤缺" in players_away:
        reasons.append(f"{away}有关键球员缺阵")
    if "报销" in players_home or "缺阵" in players_home:
        reasons.append(f"{home}存在伤病隐患")
    if "高温" in news or "湿度" in news:
        reasons.append("天气条件增加不确定性")

    trends = odds_data.get("trends", {})
    up_c = trends.get("up", 0)
    down_c = trends.get("down", 0)
    if down_c > up_c:
        reasons.append("多数比分赔率下降（机构看好低比分）")
    elif up_c > down_c:
        reasons.append("多数比分赔率上升（市场热度分散）")

    top5 = odds_data.get("top5", [])
    best_score = top5[0]["score"] if top5 else "?"

    if has_intel:
        analysis = f"{match_key}：{'；'.join(reasons)}。赔率最低比分 {best_score}。"
        if pred:
            analysis += f" 媒体预测: {pred[:150]}"
    else:
        down_pct = f"{down_c}/{up_c+down_c+1}" if (up_c + down_c) > 0 else "暂无"
        analysis = f"{match_key}：赔率趋势 {down_pct}项下降，最低赔率比分 {best_score}。（情报数据待补充，以上为纯赔率分析）"

    recommendation = f"参考比分: {best_score}" if top5 else "暂无足够数据"

    return {
        "prediction": f"倾向 {home} 取胜，{best_score}" if top5 else "数据不足",
        "analysis": analysis,
        "key_factors": reasons[:3] if reasons else ["赔率趋势为主"],
        "recommendation": recommendation,
        "source": "offline",
    }


def batch_analyze(analyzed_results, match_intel):
    """
    批量 AI 分析所有比赛

    Args:
        analyzed_results: analyzer.analyze_score_trends() 的输出
        match_intel: intel_fetcher.load_match_intel() 的输出

    Returns:
        dict: {match_key: ai_result, ...}
    """
    results = {}
    for r in analyzed_results:
        home = r.get("home_team", "")
        away = r.get("away_team", "")
        match_key = f"{home} vs {away}"

        # 提取情报
        intel = match_intel.get(match_key, {}) if match_intel else {}

        # 提取赔率摘要
        scores = r.get("score_odds", {}).get("scores", {}) if r.get("score_odds") else {}
        changes = r.get("score_changes", {})

        # 构建 TOP5
        top5 = []
        if scores:
            try:
                sorted_s = sorted(scores.items(), key=lambda x: float(x[1]))
                for s, v in sorted_s[:5]:
                    chg = changes.get(s, {})
                    top5.append({
                        "score": s, "odds": v,
                        "direction": chg.get("direction", "flat"),
                        "total_dir": chg.get("total_direction", "flat"),
                    })
            except (ValueError, TypeError):
                pass

        # 计算 overround
        overround_pct = 0
        if scores:
            try:
                total = sum(1.0 / float(v) for v in scores.values() if float(v) > 0)
                overround_pct = round((total - 1.0) * 100, 2)
            except (ValueError, TypeError):
                pass

        trends = r.get("trend_summary", {})

        odds_data = {
            "top5": top5,
            "trends": {k: trends.get(k, 0) for k in ("up", "down", "flat", "new")},
            "overround_pct": overround_pct,
        }

        print(f"[AI] 分析: {match_key} ...")
        results[match_key] = analyze_match_with_ai(match_key, home, away, intel, odds_data)

    return results
