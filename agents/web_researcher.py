import os
import json
import asyncio
import requests
from typing import Optional
from utils.claude_client import call_claude_text

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FinancialAnalyzer/1.0)"}
TIMEOUT = 10

# ---------------------------------------------------------------------------
# EDINET API
# ---------------------------------------------------------------------------

EDINET_BASE = "https://disclosure.edinet-fsa.go.jp/api/v2"


def _search_edinet(company_name: str) -> Optional[dict]:
    """EDINET で有価証券報告書を検索して最新の書類情報を返す"""
    try:
        # 書類一覧（直近30日）
        from datetime import date, timedelta
        target_date = (date.today() - timedelta(days=30)).isoformat()
        url = f"{EDINET_BASE}/documents.json"
        params = {"date": target_date, "type": 2}  # type=2: 有価証券報告書等
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        results = r.json().get("results", [])

        # 企業名でフィルタ（部分一致）
        matched = [
            doc for doc in results
            if company_name[:3] in (doc.get("filerName") or "")
        ]
        if matched:
            return matched[0]
    except Exception:
        pass
    return None


def _fetch_edinet_document(doc_id: str) -> str:
    """EDINETから書類の概要テキストを取得"""
    try:
        url = f"{EDINET_BASE}/documents/{doc_id}"
        params = {"type": 2}  # CSVメタデータ
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text[:5000]
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Web検索（DuckDuckGo / Tavily）
# ---------------------------------------------------------------------------

def _search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo Instant Answer APIで検索"""
    try:
        url = "https://api.duckduckgo.com/"
        params = {"q": query, "format": "json", "no_redirect": 1, "no_html": 1}
        r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        results = []
        for item in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(item, dict) and "Text" in item:
                results.append({
                    "title": item.get("Text", "")[:100],
                    "url": item.get("FirstURL", ""),
                    "snippet": item.get("Text", "")[:300],
                })
        return results
    except Exception:
        return []


def _search_tavily(query: str, max_results: int = 5) -> list[dict]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return []
    try:
        url = "https://api.tavily.com/search"
        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        r = requests.post(url, json=payload, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", "")[:300],
            }
            for item in r.json().get("results", [])
        ]
    except Exception:
        return []


def _web_search(query: str, max_results: int = 5) -> list[dict]:
    """Tavily優先、なければDuckDuckGo"""
    results = _search_tavily(query, max_results)
    if not results:
        results = _search_duckduckgo(query, max_results)
    return results


# ---------------------------------------------------------------------------
# 業界平均指標（Claude推定）
# ---------------------------------------------------------------------------

async def _estimate_industry_avg(company_name: str, industry: str) -> dict:
    prompt = f"""
{company_name}（業種: {industry}）の業界平均財務指標を推定してください。
日本の上場企業の一般的な水準で構いません。

以下のJSONで回答してください：
{{
  "industry": "{industry}",
  "avg_operating_margin": null,
  "avg_roe": null,
  "avg_equity_ratio": null,
  "avg_revenue_growth": null,
  "avg_current_ratio": null,
  "note": "推定根拠の一言メモ"
}}
JSONのみ返答してください。"""
    response = await call_claude_text(prompt, max_tokens=512)
    try:
        import re
        text = re.sub(r"```(?:json)?", "", response).strip()
        return json.loads(text)
    except Exception:
        return {"industry": industry, "note": "推定失敗"}


# ---------------------------------------------------------------------------
# メインエントリポイント
# ---------------------------------------------------------------------------

async def research_company(extracted_data: dict) -> dict:
    company_name = extracted_data.get("company_name", "不明")
    industry = extracted_data.get("notes", {}).get("industry", "一般事業会社")

    # 3タスクを並列実行
    news_task = asyncio.to_thread(_gather_news, company_name)
    industry_task = _estimate_industry_avg(company_name, industry)
    competitor_task = asyncio.to_thread(_gather_competitors, company_name, industry)

    news, industry_avg, competitors = await asyncio.gather(
        news_task, industry_task, competitor_task,
        return_exceptions=True,
    )

    def _safe(r, default):
        return default if isinstance(r, Exception) else r

    # EDINET情報は別途取得（失敗しても続行）
    edinet_info = None
    try:
        edinet_doc = _search_edinet(company_name)
        if edinet_doc:
            edinet_info = {
                "doc_id": edinet_doc.get("docID"),
                "doc_description": edinet_doc.get("docDescription"),
                "filing_date": edinet_doc.get("submitDateTime"),
                "filer_name": edinet_doc.get("filerName"),
            }
    except Exception:
        pass

    return {
        "company_name": company_name,
        "industry": industry,
        "news": _safe(news, []),
        "industry_avg": _safe(industry_avg, {}),
        "competitors": _safe(competitors, []),
        "edinet": edinet_info,
    }


def _gather_news(company_name: str) -> list[dict]:
    results = _web_search(f"{company_name} 最新ニュース 決算", max_results=5)
    if len(results) < 3:
        results += _web_search(f"{company_name} 業績 2024", max_results=3)
    return results[:6]


def _gather_competitors(company_name: str, industry: str) -> list[dict]:
    results = _web_search(f"{industry} 主要企業 競合 売上ランキング", max_results=5)
    return results[:4]
