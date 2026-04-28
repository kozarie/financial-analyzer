#!/usr/bin/env python3
"""決算書PDFを分析してスタンドアロンHTMLを生成するスクリプト"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from agents.pdf_extractor import extract_pdf
from agents.financial_agents import run_financial_agents
from agents.web_researcher import research_company
from agents.risk_evaluator import evaluate_risk
from agents.report_generator import generate_report


async def main(pdf_path: str, output_path: str):
    print(f"📄 PDFを読み込み中: {pdf_path}")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    print("🔍 Step 1/5: PDF解析中...")
    try:
        extracted = await extract_pdf(pdf_bytes)
        print(f"   ✅ 企業名: {extracted.get('company_name')} / 期間: {extracted.get('fiscal_year')}")
    except Exception as e:
        print(f"   ⚠️ PDF解析エラー（続行）: {e}")
        extracted = {"company_name": os.path.basename(pdf_path), "fiscal_year": "不明",
                     "bs": {}, "pl": {}, "cf": {}, "notes": {}}

    print("📊 Step 2/5: 財務分析中（BS/PL/CF 並列）...")
    try:
        financial = await run_financial_agents(extracted)
        print("   ✅ 財務指標計算完了")
    except Exception as e:
        print(f"   ⚠️ 財務分析エラー（続行）: {e}")
        financial = {"bs_analysis": {}, "pl_analysis": {}, "cf_analysis": {}, "metrics": {}}

    print("🌐 Step 3/5: Web調査中...")
    try:
        web = await research_company(extracted)
        print(f"   ✅ ニュース {len(web.get('news', []))}件取得")
    except Exception as e:
        print(f"   ⚠️ Web調査エラー（続行）: {e}")
        web = {"news": [], "industry_avg": {}, "competitors": [], "industry": "一般事業会社"}

    print("⚠️ Step 4/5: リスク評価中...")
    try:
        risk = await evaluate_risk(extracted, financial, web)
        print(f"   ✅ 総合スコア: {risk.get('overall_score')}/100 / リスク: {risk.get('risk_level')}")
    except Exception as e:
        print(f"   ⚠️ リスク評価エラー（続行）: {e}")
        risk = {"overall_score": 50, "risk_level": "medium", "executive_summary": "",
                "risks": [], "recommendations": [], "positive_factors": []}

    print("📝 Step 5/5: HTMLレポート生成中...")
    html = generate_report(extracted, financial, web, risk)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ 完了！ → {output_path}")
    print(f"   ファイルサイズ: {len(html.encode())//1024} KB")


if __name__ == "__main__":
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "nintendo_q2_2025.pdf"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "report_nintendo.html"
    asyncio.run(main(pdf_path, output_path))
