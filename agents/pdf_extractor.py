import io
import json
import re
from typing import Optional
from utils.claude_client import call_claude

SYSTEM_PROMPT = """あなたは日本企業の財務書類を読み解く専門家です。
PDFから財務数値を正確に抽出し、指定されたJSONスキーマで返答してください。
数値は全て百万円単位に統一し、不明な項目はnullとしてください。
PDFに明記されていない数値は必ず null にしてください。推測・推定は禁止です。
数値の単位が不明な場合も null にしてください。
会計期間・企業名は必ずPDFから抜き出し、不明なら'不明'としてください。"""

EXTRACTION_PROMPT = """以下のPDFは企業の決算書です。財務数値を抽出し、以下のJSONを完成させてください。
重要: PDFに明記されていない数値は必ず null にしてください。推測・推定は禁止です。数値の単位が不明な場合も null にしてください。会計期間・企業名は必ずPDFから抜き出し、不明なら'不明'としてください。
厳守: 提供されたテキストに数値が存在しない場合、または抽出テキストが空・極端に短い場合は、全ての数値フィールドを null にしてください。「それらしい数値」を想像・推測して埋めることは絶対に禁止です。

```json
{
  "company_name": "企業名",
  "fiscal_year": "2024年3月期",
  "bs": {
    "total_assets": null,
    "current_assets": null,
    "cash": null,
    "receivables": null,
    "inventory": null,
    "non_current_assets": null,
    "total_liabilities": null,
    "current_liabilities": null,
    "long_term_debt": null,
    "total_debt": null,
    "equity": null,
    "retained_earnings": null,
    "working_capital": null
  },
  "pl": {
    "revenue": null,
    "gross_profit": null,
    "cogs": null,
    "operating_profit": null,
    "ordinary_profit": null,
    "ebit": null,
    "net_income": null,
    "depreciation": null,
    "interest_expense": null,
    "labor_cost": null,
    "eps": null,
    "shares_outstanding": null,
    "dividends": null
  },
  "cf": {
    "operating_cf": null,
    "investing_cf": null,
    "financing_cf": null,
    "capex": null,
    "free_cash_flow": null
  },
  "notes": {
    "market_cap": null,
    "nopat": null,
    "invested_capital": null,
    "revenue_3y_ago": null,
    "industry": "業種名"
  }
}
```

JSONのみ返答してください。マークダウンコードブロックは不要です。"""


def _extract_with_pdfplumber(pdf_bytes: bytes) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text:
                text_parts.append(text)
            # 表も抽出
            for table in page.extract_tables():
                if table:
                    for row in table:
                        row_text = " | ".join(str(c) if c else "" for c in row)
                        text_parts.append(row_text)
    return "\n".join(text_parts)


def _extract_with_pymupdf(pdf_bytes: bytes) -> str:
    import fitz
    text_parts = []
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    for page in doc:
        text_parts.append(page.get_text())
    doc.close()
    return "\n".join(text_parts)


def _parse_json_response(text: str) -> dict:
    # コードブロックを除去
    text = re.sub(r"```(?:json)?", "", text).strip()
    return json.loads(text)


async def extract_pdf(pdf_bytes: bytes) -> dict:
    """PDFを解析して財務データを構造化dictで返す"""
    raw_text = None

    # pdfplumber で抽出を試みる
    try:
        raw_text = _extract_with_pdfplumber(pdf_bytes)
    except Exception:
        pass

    # フォールバック: PyMuPDF
    if not raw_text or len(raw_text) < 100:
        try:
            raw_text = _extract_with_pymupdf(pdf_bytes)
        except Exception:
            raw_text = ""

    text_length = len(raw_text) if raw_text else 0

    # スキャンPDF（画像PDF）検出: テキストが100文字未満は解析不能と判定
    if text_length < 100:
        return {
            "company_name": "不明",
            "fiscal_year": "不明",
            "bs": {}, "pl": {}, "cf": {}, "notes": {},
            "_error": (
                "スキャンPDF（画像PDF）のためテキスト抽出に失敗しました。"
                "テキスト形式のPDFをご使用ください。"
                f"（抽出文字数: {text_length}文字）"
            ),
        }

    # テキストが取れた場合はテキスト+プロンプトで呼ぶ（トークン節約）
    # 500文字未満はスキャンPDFの可能性が高く精度低下を警告
    low_quality = text_length < 500

    if raw_text and text_length > 100:
        scan_warning = (
            "\n\n注意: 提供されたテキストは非常に短いです（{} 文字）。"
            "スキャンPDFの可能性があります。"
            "数値が確認できない場合は全フィールドを null にしてください。"
            "絶対に推測で数値を埋めないでください。".format(text_length)
            if low_quality else ""
        )
        prompt = (
            f"{EXTRACTION_PROMPT}{scan_warning}"
            f"\n\n--- 抽出テキスト ---\n{raw_text[:30000]}"
        )
        response = await call_claude(prompt, system=SYSTEM_PROMPT, max_tokens=4096)
    else:
        # PDFバイナリを直接送る
        response = await call_claude(
            EXTRACTION_PROMPT,
            system=SYSTEM_PROMPT,
            pdf_bytes=pdf_bytes,
            max_tokens=4096,
        )

    try:
        data = _parse_json_response(response)
    except json.JSONDecodeError:
        # パースに失敗しても空の構造を返す（後続エージェントがpartial動作）
        data = {
            "company_name": "不明",
            "fiscal_year": "不明",
            "bs": {}, "pl": {}, "cf": {}, "notes": {},
            "_parse_error": response[:500],
        }

    # テキスト品質が低い場合は警告フラグを付与
    if low_quality:
        data["_warning"] = (
            f"スキャンPDFの可能性があります（抽出文字数: {text_length}文字）。"
            "数値の精度が低下している恐れがあります。PDFの各数値を必ず手動で確認してください。"
        )

    return data


def flatten_financials(extracted: dict) -> dict:
    """BS/PL/CFをフラットなdictにまとめる（calculations.py用）"""
    flat = {}
    for section in ("bs", "pl", "cf", "notes"):
        flat.update(extracted.get(section, {}))
    return flat
