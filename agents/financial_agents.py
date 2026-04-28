import asyncio
import json
from typing import Optional
from utils.claude_client import call_claude_text
from utils.calculations import calculate_all
from agents.pdf_extractor import flatten_financials

# ---------------------------------------------------------------------------
# システムプロンプト（共通）
# ---------------------------------------------------------------------------

ANALYST_SYSTEM = """あなたは日本企業の財務分析の専門家です。
【絶対ルール】
・PDFから抽出されたデータに存在する数値のみを使って分析してください。
・null（データなし）の項目については「このデータはPDFに記載がありませんでした」と明記してください。
・数値の推測・補完・想像は一切禁止です。
・ネット上の情報や他社のデータを使って補完することも禁止です。
・「おそらく」「推定では」「一般的に」などの言葉で推測を混ぜることは禁止です。
・事実として確認できることのみを分析対象としてください。"""


# ---------------------------------------------------------------------------
# BSエージェント（貸借対照表分析）
# ---------------------------------------------------------------------------

async def analyze_bs(extracted_data: dict, metrics: dict) -> dict:
    company = extracted_data.get("company_name", "当社")
    bs = extracted_data.get("bs", {})
    safety_metrics = metrics.get("safety", [])

    prompt = f"""
# {company} 貸借対照表（BS）分析

## 財務データ
{json.dumps(bs, ensure_ascii=False, indent=2)}

## 計算済み安全性指標
{json.dumps(safety_metrics, ensure_ascii=False, indent=2)}

## 分析依頼
以下の形式でJSON回答してください：

{{
  "summary": "BS全体の評価を3-4文で（経営体力・財務健全性の総合評価）",
  "analysis": "詳細分析テキスト（400字以上）。資産構成、負債構造、自己資本の状況を多角的に分析",
  "strengths": ["強み1", "強み2", "強み3"],
  "weaknesses": ["弱み1", "弱み2"],
  "key_metrics_comment": "自己資本比率・流動比率・D/Eレシオへのコメント（200字程度）"
}}

JSONのみ返答してください。"""

    response = await call_claude_text(prompt, system=ANALYST_SYSTEM, max_tokens=2048)
    return _parse_agent_response(response, "bs_analysis")


# ---------------------------------------------------------------------------
# PLエージェント（損益計算書分析）
# ---------------------------------------------------------------------------

async def analyze_pl(extracted_data: dict, metrics: dict) -> dict:
    company = extracted_data.get("company_name", "当社")
    pl = extracted_data.get("pl", {})
    profitability = metrics.get("profitability", [])
    growth = metrics.get("growth", [])

    prompt = f"""
# {company} 損益計算書（PL）分析

## 財務データ
{json.dumps(pl, ensure_ascii=False, indent=2)}

## 計算済み収益性指標
{json.dumps(profitability, ensure_ascii=False, indent=2)}

## 計算済み成長性指標
{json.dumps(growth, ensure_ascii=False, indent=2)}

## 分析依頼
以下の形式でJSON回答してください：

{{
  "summary": "PL全体の評価を3-4文（収益力・成長性の総合評価）",
  "analysis": "詳細分析テキスト（400字以上）。売上構造、利益率の変化、コスト効率を分析",
  "strengths": ["強み1", "強み2", "強み3"],
  "weaknesses": ["弱み1", "弱み2"],
  "key_metrics_comment": "営業利益率・ROE・成長率へのコメント（200字程度）"
}}

JSONのみ返答してください。"""

    response = await call_claude_text(prompt, system=ANALYST_SYSTEM, max_tokens=2048)
    return _parse_agent_response(response, "pl_analysis")


# ---------------------------------------------------------------------------
# CFエージェント（キャッシュフロー分析）
# ---------------------------------------------------------------------------

async def analyze_cf(extracted_data: dict, metrics: dict) -> dict:
    company = extracted_data.get("company_name", "当社")
    cf = extracted_data.get("cf", {})
    cashflow_metrics = metrics.get("cashflow", [])

    prompt = f"""
# {company} キャッシュフロー（CF）分析

## 財務データ
{json.dumps(cf, ensure_ascii=False, indent=2)}

## 計算済みCF指標
{json.dumps(cashflow_metrics, ensure_ascii=False, indent=2)}

## 分析依頼
以下の形式でJSON回答してください：

{{
  "summary": "CF全体の評価を3-4文（現金創出力・資金繰りの総合評価）",
  "analysis": "詳細分析テキスト（400字以上）。営業CF・投資CF・財務CFのパターン分析、FCFの状況",
  "cf_pattern": "営業CF/投資CF/財務CFの符号パターンから読み取れる企業の状況（例：成長投資型、成熟型など）",
  "strengths": ["強み1", "強み2"],
  "weaknesses": ["弱み1", "弱み2"],
  "key_metrics_comment": "FCF・CF充当率・配当性向へのコメント（200字程度）"
}}

JSONのみ返答してください。"""

    response = await call_claude_text(prompt, system=ANALYST_SYSTEM, max_tokens=2048)
    return _parse_agent_response(response, "cf_analysis")


# ---------------------------------------------------------------------------
# 並列実行
# ---------------------------------------------------------------------------

async def run_financial_agents(extracted_data: dict) -> dict:
    """BS/PL/CF 3エージェントを並列実行して結果を返す"""
    flat = flatten_financials(extracted_data) if hasattr(extracted_data, "get") else {}
    metrics = calculate_all(flat)

    bs_result, pl_result, cf_result = await asyncio.gather(
        analyze_bs(extracted_data, metrics),
        analyze_pl(extracted_data, metrics),
        analyze_cf(extracted_data, metrics),
        return_exceptions=True,
    )

    # return_exceptions=True なので例外をフォールバックに置換
    def _safe_result(result, fallback_key: str):
        if isinstance(result, Exception):
            return {
                "summary": "分析中にエラーが発生しました",
                "analysis": str(result),
                "strengths": [],
                "weaknesses": [],
                "_error": True,
            }
        return result

    return {
        "bs_analysis": _safe_result(bs_result, "bs"),
        "pl_analysis": _safe_result(pl_result, "pl"),
        "cf_analysis": _safe_result(cf_result, "cf"),
        "metrics": metrics,
    }


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _parse_agent_response(response: str, fallback_key: str) -> dict:
    import re, json
    text = re.sub(r"```(?:json)?", "", response).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "summary": "レスポンスのパースに失敗しました",
            "analysis": response[:1000],
            "strengths": [],
            "weaknesses": [],
        }
