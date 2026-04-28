import os
import asyncio
import streamlit as st
import streamlit.components.v1 as components

# ページ設定（最初に呼ぶ）
st.set_page_config(
    page_title="決算書AI分析システム",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

from agents.pdf_extractor import extract_pdf
from agents.financial_agents import run_financial_agents
from agents.web_researcher import research_company
from agents.risk_evaluator import evaluate_risk
from agents.report_generator import generate_report


# ---------------------------------------------------------------------------
# サイドバー: APIキー設定
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("⚙️ 設定")
    st.markdown("---")
    st.success("✅ Claude Code の認証を使用中\n\nAPIキー不要です。")

    tavily_key = st.text_input(
        "TAVILY_API_KEY（任意）",
        value=os.environ.get("TAVILY_API_KEY", ""),
        type="password",
        help="未入力の場合はDuckDuckGoで代替します。",
    )
    if tavily_key:
        os.environ["TAVILY_API_KEY"] = tavily_key

    st.markdown("---")
    st.markdown("""
**使い方**
1. 決算書PDFをアップロード
2. 分析開始ボタンをクリック
3. レポートをダウンロード

**対応PDFの種類**
- 有価証券報告書
- 決算短信
- アニュアルレポート
""")


# ---------------------------------------------------------------------------
# メインUI
# ---------------------------------------------------------------------------

st.title("📊 決算書AI財務分析システム")
st.markdown("企業の決算書PDFをアップロードすると、AIが財務・リスク・Web調査を行いプロ品質のレポートを生成します。")

uploaded_file = st.file_uploader(
    "決算書PDFをアップロード",
    type=["pdf"],
    help="有価証券報告書・決算短信・アニュアルレポートに対応",
)

col1, col2 = st.columns([1, 4])
with col1:
    analyze_btn = st.button("🚀 分析開始", type="primary", disabled=(uploaded_file is None))

if analyze_btn and uploaded_file is not None:
    pdf_bytes = uploaded_file.read()
    html_result = None
    error_occurred = False

    # ---------------------------------------------------------------------------
    # 分析パイプライン
    # ---------------------------------------------------------------------------

    async def run_pipeline(pdf_bytes: bytes) -> str:
        extracted = None
        financial = None
        web = None
        risk = None

        with st.status("分析パイプラインを実行中...", expanded=True) as status:

            # Step 1: PDF解析
            st.write("📄 Step 1: PDF解析 — テキスト・表を抽出中...")
            try:
                extracted = await extract_pdf(pdf_bytes)
                company = extracted.get("company_name", "不明")
                st.write(f"   ✅ 企業名: {company} / 対象期間: {extracted.get('fiscal_year', '不明')}")
            except Exception as e:
                st.error(f"PDF解析エラー: {e}")
                extracted = {
                    "company_name": uploaded_file.name,
                    "fiscal_year": "不明",
                    "bs": {}, "pl": {}, "cf": {}, "notes": {},
                }

            # Step 2: BS/PL/CF 並列分析
            st.write("🔢 Step 2: 財務分析 — BS/PL/CF エージェントを並列実行中...")
            try:
                financial = await run_financial_agents(extracted)
                st.write("   ✅ 収益性・安全性・成長性・効率性指標を計算完了")
            except Exception as e:
                st.error(f"財務分析エラー: {e}")
                financial = {"bs_analysis": {}, "pl_analysis": {}, "cf_analysis": {}, "metrics": {}}

            # Step 3: Web調査
            st.write("🌐 Step 3: Web調査 — EDINET・最新ニュース・業界情報を取得中...")
            try:
                web = await research_company(extracted)
                news_count = len(web.get("news", []))
                st.write(f"   ✅ ニュース {news_count}件 / 業界平均指標を取得")
            except Exception as e:
                st.warning(f"Web調査で一部エラー（続行します）: {e}")
                web = {"news": [], "industry_avg": {}, "competitors": [], "industry": "一般事業会社"}

            # Step 4: リスク評価
            st.write("⚠️ Step 4: リスク評価 — 統合分析中...")
            try:
                risk = await evaluate_risk(extracted, financial, web)
                score = risk.get("overall_score", "N/A")
                level = risk.get("risk_level", "N/A")
                st.write(f"   ✅ 総合スコア: {score}/100 / リスクレベル: {level}")
            except Exception as e:
                st.error(f"リスク評価エラー: {e}")
                risk = {
                    "overall_score": 50, "risk_level": "medium",
                    "executive_summary": "リスク評価に失敗しました",
                    "risks": [], "recommendations": [], "positive_factors": [],
                }

            # Step 5: レポート生成
            st.write("📝 Step 5: レポート生成 — HTMLレポートを作成中...")
            try:
                html = generate_report(extracted, financial, web, risk)
                st.write("   ✅ レポート生成完了")
                status.update(label="✅ 分析完了！", state="complete", expanded=False)
                return html
            except Exception as e:
                st.error(f"レポート生成エラー: {e}")
                status.update(label="❌ レポート生成に失敗しました", state="error")
                raise

    try:
        html_result = asyncio.run(run_pipeline(pdf_bytes))
    except Exception as e:
        st.error(f"パイプラインエラー: {e}")
        error_occurred = True

    # ---------------------------------------------------------------------------
    # 結果表示
    # ---------------------------------------------------------------------------

    if html_result and not error_occurred:
        st.markdown("---")

        # ダウンロードボタン
        company_name = "report"
        dl_col1, dl_col2 = st.columns([1, 5])
        with dl_col1:
            st.download_button(
                label="⬇️ HTMLレポートをダウンロード",
                data=html_result.encode("utf-8"),
                file_name=f"{company_name}_financial_report.html",
                mime="text/html",
            )

        st.markdown("### レポートプレビュー")
        components.html(html_result, height=900, scrolling=True)
