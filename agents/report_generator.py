import json
import os
from datetime import datetime
from jinja2 import Environment, FileSystemLoader, select_autoescape

CATEGORY_LABELS = {
    "profitability": "収益性",
    "safety": "安全性",
    "growth": "成長性",
    "efficiency": "効率性",
    "cashflow": "キャッシュフロー",
    "comprehensive": "総合（Piotroski）",
}

RISK_LEVEL_LABELS = {
    "low": "低リスク",
    "medium": "中リスク",
    "high": "高リスク",
    "critical": "要注意",
}


def _prepare_chart_data(metrics: dict) -> dict:
    """Chart.js用JSONデータを準備"""
    # 収益性レーダー
    prof_items = [m for m in metrics.get("profitability", []) if m.get("value") is not None]
    profitability_chart = {
        "labels": [m["name"] for m in prof_items],
        "values": [m["value"] for m in prof_items],
        "avg": [m.get("industry_avg") or 0 for m in prof_items],
    }

    # 安全性バー（値がある項目のみ、Z-Score除外）
    safety_items = [
        m for m in metrics.get("safety", [])
        if m.get("value") is not None and "Z-Score" not in m.get("name", "")
    ]
    color_map = {"good": "#27ae60", "warning": "#f39c12", "danger": "#c0392b"}
    safety_chart = {
        "labels": [m["name"] for m in safety_items],
        "values": [m["value"] for m in safety_items],
        "colors": [color_map.get(m.get("health", ""), "#7f8c8d") for m in safety_items],
    }

    return {"profitability": profitability_chart, "safety": safety_chart}


def generate_report(
    extracted_data: dict,
    financial_analysis: dict,
    web_research: dict,
    risk_evaluation: dict,
) -> str:
    """全エージェント結果を統合してHTMLレポートを生成"""
    templates_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    templates_dir = os.path.normpath(templates_dir)

    env = Environment(
        loader=FileSystemLoader(templates_dir),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html")

    metrics = financial_analysis.get("metrics", {})
    chart_data = _prepare_chart_data(metrics)

    context = {
        "company_name": extracted_data.get("company_name", "企業名不明"),
        "fiscal_year": extracted_data.get("fiscal_year", "不明"),
        "industry": web_research.get("industry", extracted_data.get("notes", {}).get("industry", "一般事業会社")),
        "generated_at": datetime.now().strftime("%Y年%m月%d日 %H:%M"),

        # リスク評価
        "overall_score": risk_evaluation.get("overall_score", 50),
        "risk_level": risk_evaluation.get("risk_level", "medium"),
        "risk_level_label": RISK_LEVEL_LABELS.get(risk_evaluation.get("risk_level", "medium"), "中リスク"),
        "executive_summary": risk_evaluation.get("executive_summary", ""),
        "positive_factors": risk_evaluation.get("positive_factors", []),
        "risks": risk_evaluation.get("risks", []),
        "recommendations": risk_evaluation.get("recommendations", []),

        # 財務指標
        "metrics": metrics,
        "category_labels": CATEGORY_LABELS,

        # BS/PL/CF 分析
        "bs_analysis": financial_analysis.get("bs_analysis", {}),
        "pl_analysis": financial_analysis.get("pl_analysis", {}),
        "cf_analysis": financial_analysis.get("cf_analysis", {}),

        # Web調査
        "news": web_research.get("news", []),
        "industry_avg": web_research.get("industry_avg", {}),
        "competitors": web_research.get("competitors", []),

        # グラフデータ（JSON文字列として埋め込む）
        "chart_data_json": json.dumps(chart_data, ensure_ascii=False),
    }

    return template.render(**context)
