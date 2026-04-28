import json
import re
from utils.claude_client import call_claude_text
from agents.pdf_extractor import flatten_financials

RISK_SYSTEM = """あなたは企業リスク評価の専門家です。
財務分析・Web調査の結果をもとに、投資家・経営者向けのリスクレポートを作成してください。
客観的かつ具体的な根拠に基づいてリスクを評価してください。
計算できなかった指標（null）はリスク評価に使用しないでください。
根拠のある数値のみでリスクを評価してください。
推定・仮定に基づくリスクは必ず「推定」と明記してください。"""


async def evaluate_risk(
    extracted_data: dict,
    financial_analysis: dict,
    web_research: dict,
) -> dict:
    company = extracted_data.get("company_name", "当社")
    metrics = financial_analysis.get("metrics", {})
    flat = flatten_financials(extracted_data)

    # Altman Z-Scoreを取得（既に計算済みのものを探す）
    z_score_item = None
    for item in metrics.get("safety", []):
        if "Z-Score" in item.get("name", ""):
            z_score_item = item
            break

    # 業界平均との比較サマリーを準備
    industry_avg = web_research.get("industry_avg", {})
    news_snippets = [n.get("snippet", "") for n in web_research.get("news", [])[:3]]

    prompt = f"""
# {company} リスク評価依頼

## 財務指標サマリー
### 収益性
{json.dumps(metrics.get("profitability", []), ensure_ascii=False, indent=2)}

### 安全性
{json.dumps(metrics.get("safety", []), ensure_ascii=False, indent=2)}

### 成長性
{json.dumps(metrics.get("growth", []), ensure_ascii=False, indent=2)}

### Altman Z-Score
{json.dumps(z_score_item, ensure_ascii=False, indent=2) if z_score_item else "計算不可"}

## BS分析サマリー
{financial_analysis.get("bs_analysis", {}).get("summary", "なし")}

## PL分析サマリー
{financial_analysis.get("pl_analysis", {}).get("summary", "なし")}

## CF分析サマリー
{financial_analysis.get("cf_analysis", {}).get("summary", "なし")}

## 業界平均比較
{json.dumps(industry_avg, ensure_ascii=False, indent=2)}

## 最新ニュース（上位3件）
{chr(10).join(news_snippets)}

## 評価依頼
以下の形式でJSONを返してください：

{{
  "overall_score": 72,
  "risk_level": "medium",
  "executive_summary": "200字以内の総合評価コメント",
  "risks": [
    {{
      "category": "財務リスク|市場リスク|事業リスク|外部環境リスク",
      "title": "リスク名称（20字以内）",
      "description": "具体的な説明（100字程度）",
      "severity": "high|medium|low"
    }}
  ],
  "recommendations": [
    {{
      "priority": 1,
      "action": "推奨アクション（50字以内）",
      "reason": "根拠（80字程度）"
    }}
  ],
  "positive_factors": ["ポジティブ要因1", "ポジティブ要因2", "ポジティブ要因3"]
}}

リスクは重要度順に3-6件、推奨事項は3-5件記載してください。
overall_score は 0（最悪）〜100（最良）、risk_level は low/medium/high/critical。
JSONのみ返答してください。"""

    response = await call_claude_text(prompt, system=RISK_SYSTEM, max_tokens=3000)
    result = _parse_risk_response(response)

    # Altman Z-ScoreのHealthをoverall_scoreに反映（補正）
    if z_score_item:
        health = z_score_item.get("health", "unknown")
        if health == "danger":
            result["overall_score"] = min(result.get("overall_score", 50), 40)
            result["risk_level"] = "critical" if result.get("overall_score", 50) < 30 else "high"
        elif health == "good" and result.get("overall_score", 50) < 60:
            result["overall_score"] = max(result.get("overall_score", 50), 60)

    result["altman_z_score"] = z_score_item
    return result


def _parse_risk_response(response: str) -> dict:
    text = re.sub(r"```(?:json)?", "", response).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "overall_score": 50,
            "risk_level": "medium",
            "executive_summary": "リスク評価の解析に失敗しました",
            "risks": [],
            "recommendations": [],
            "positive_factors": [],
            "_parse_error": response[:500],
        }
