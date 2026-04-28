from typing import Optional
import math

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def _safe(value, default=None):
    """None / 0除算ガード付き値取得"""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    return value


def _pct(num, den) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return round(num / den * 100, 2)


def _ratio(num, den) -> Optional[float]:
    if num is None or den is None or den == 0:
        return None
    return round(num / den, 4)


def _yoy(current, previous) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _grade(value: Optional[float], good_thresh: float, warn_thresh: float, higher_is_better: bool = True) -> str:
    if value is None:
        return "unknown"
    if higher_is_better:
        if value >= good_thresh:
            return "good"
        if value >= warn_thresh:
            return "warning"
        return "danger"
    else:
        if value <= good_thresh:
            return "good"
        if value <= warn_thresh:
            return "warning"
        return "danger"


# ---------------------------------------------------------------------------
# 収益性指標
# ---------------------------------------------------------------------------

def gross_profit_margin(revenue, gross_profit) -> dict:
    val = _pct(gross_profit, revenue)
    return {
        "name": "売上高総利益率",
        "value": val,
        "unit": "%",
        "industry_avg": 25.0,
        "health": _grade(val, 30, 15),
    }


def operating_profit_margin(revenue, operating_profit) -> dict:
    val = _pct(operating_profit, revenue)
    return {
        "name": "営業利益率",
        "value": val,
        "unit": "%",
        "industry_avg": 7.0,
        "health": _grade(val, 10, 5),
    }


def ordinary_profit_margin(revenue, ordinary_profit) -> dict:
    val = _pct(ordinary_profit, revenue)
    return {
        "name": "経常利益率",
        "value": val,
        "unit": "%",
        "industry_avg": 6.0,
        "health": _grade(val, 8, 3),
    }


def ebitda_margin(revenue, operating_profit, depreciation) -> dict:
    if operating_profit is None or depreciation is None:
        val = None
    else:
        val = _pct(operating_profit + depreciation, revenue)
    return {
        "name": "EBITDA率",
        "value": val,
        "unit": "%",
        "industry_avg": 12.0,
        "health": _grade(val, 15, 8),
    }


def roe(net_income, equity) -> dict:
    val = _pct(net_income, equity)
    return {
        "name": "ROE",
        "value": val,
        "unit": "%",
        "industry_avg": 8.0,
        "health": _grade(val, 10, 5),
    }


def roa(net_income, total_assets) -> dict:
    val = _pct(net_income, total_assets)
    return {
        "name": "ROA",
        "value": val,
        "unit": "%",
        "industry_avg": 4.0,
        "health": _grade(val, 5, 2),
    }


def roic(nopat, invested_capital) -> dict:
    val = _pct(nopat, invested_capital)
    return {
        "name": "ROIC",
        "value": val,
        "unit": "%",
        "industry_avg": 6.0,
        "health": _grade(val, 8, 4),
    }


# ---------------------------------------------------------------------------
# 安全性指標
# ---------------------------------------------------------------------------

def equity_ratio(equity, total_assets) -> dict:
    val = _pct(equity, total_assets)
    return {
        "name": "自己資本比率",
        "value": val,
        "unit": "%",
        "industry_avg": 40.0,
        "health": _grade(val, 40, 20),
    }


def current_ratio(current_assets, current_liabilities) -> dict:
    val = _ratio(current_assets, current_liabilities)
    if val is not None:
        val = round(val * 100, 2)
    return {
        "name": "流動比率",
        "value": val,
        "unit": "%",
        "industry_avg": 150.0,
        "health": _grade(val, 150, 100),
    }


def quick_ratio(cash, receivables, current_liabilities) -> dict:
    if cash is None or receivables is None:
        val = None
    else:
        val = _ratio((cash + receivables), current_liabilities)
        if val is not None:
            val = round(val * 100, 2)
    return {
        "name": "当座比率",
        "value": val,
        "unit": "%",
        "industry_avg": 100.0,
        "health": _grade(val, 100, 70),
    }


def de_ratio(total_debt, equity) -> dict:
    val = _ratio(total_debt, equity)
    return {
        "name": "D/Eレシオ",
        "value": val,
        "unit": "倍",
        "industry_avg": 1.0,
        "health": _grade(val, 0.5, 1.5, higher_is_better=False),
    }


def interest_coverage_ratio(operating_profit, interest_expense) -> dict:
    val = _ratio(operating_profit, interest_expense)
    return {
        "name": "ICR（利息カバレッジ比率）",
        "value": val,
        "unit": "倍",
        "industry_avg": 10.0,
        "health": _grade(val, 10, 3),
    }


def altman_z_score(
    working_capital, total_assets, retained_earnings,
    ebit, market_cap, total_liabilities, revenue
) -> dict:
    """Altman Z-score（上場製造業版）"""
    try:
        x1 = _ratio(working_capital, total_assets) or 0
        x2 = _ratio(retained_earnings, total_assets) or 0
        x3 = _ratio(ebit, total_assets) or 0
        x4 = _ratio(market_cap, total_liabilities) or 0
        x5 = _ratio(revenue, total_assets) or 0
        z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        z = round(z, 3)
    except Exception:
        z = None

    if z is None:
        health = "unknown"
    elif z > 2.99:
        health = "good"
    elif z > 1.81:
        health = "warning"
    else:
        health = "danger"

    return {
        "name": "Altman Z-Score",
        "value": z,
        "unit": "",
        "industry_avg": 3.0,
        "health": health,
    }


# ---------------------------------------------------------------------------
# 成長性指標
# ---------------------------------------------------------------------------

def revenue_yoy(current, previous) -> dict:
    val = _yoy(current, previous)
    return {
        "name": "売上高成長率YoY",
        "value": val,
        "unit": "%",
        "industry_avg": 3.0,
        "health": _grade(val, 5, 0),
    }


def operating_profit_yoy(current, previous) -> dict:
    val = _yoy(current, previous)
    return {
        "name": "営業利益成長率YoY",
        "value": val,
        "unit": "%",
        "industry_avg": 3.0,
        "health": _grade(val, 5, 0),
    }


def eps_growth(current_eps, previous_eps) -> dict:
    val = _yoy(current_eps, previous_eps)
    return {
        "name": "EPS成長率",
        "value": val,
        "unit": "%",
        "industry_avg": 5.0,
        "health": _grade(val, 5, 0),
    }


def cagr_3y(latest, oldest) -> dict:
    """3年CAGR（oldest→latestが3期分）"""
    if latest is None or oldest is None or oldest == 0 or latest / oldest < 0:
        val = None
    else:
        try:
            val = round((math.pow(latest / oldest, 1/3) - 1) * 100, 2)
        except Exception:
            val = None
    return {
        "name": "売上高CAGR（3年）",
        "value": val,
        "unit": "%",
        "industry_avg": 3.0,
        "health": _grade(val, 5, 0),
    }


# ---------------------------------------------------------------------------
# 効率性指標
# ---------------------------------------------------------------------------

def asset_turnover(revenue, total_assets) -> dict:
    val = _ratio(revenue, total_assets)
    return {
        "name": "総資産回転率",
        "value": val,
        "unit": "回",
        "industry_avg": 0.8,
        "health": _grade(val, 1.0, 0.5),
    }


def inventory_days(inventory, cogs) -> dict:
    if inventory is None or cogs is None or cogs == 0:
        val = None
    else:
        val = round(inventory / cogs * 365, 1)
    return {
        "name": "棚卸資産回転日数",
        "value": val,
        "unit": "日",
        "industry_avg": 60.0,
        "health": _grade(val, 45, 90, higher_is_better=False),
    }


def receivable_days(receivables, revenue) -> dict:
    if receivables is None or revenue is None or revenue == 0:
        val = None
    else:
        val = round(receivables / revenue * 365, 1)
    return {
        "name": "売掛金回転日数",
        "value": val,
        "unit": "日",
        "industry_avg": 60.0,
        "health": _grade(val, 45, 90, higher_is_better=False),
    }


def labor_cost_ratio(labor_cost, revenue) -> dict:
    val = _pct(labor_cost, revenue)
    return {
        "name": "人件費率",
        "value": val,
        "unit": "%",
        "industry_avg": 20.0,
        "health": _grade(val, 15, 30, higher_is_better=False),
    }


# ---------------------------------------------------------------------------
# CF系指標
# ---------------------------------------------------------------------------

def operating_cf_margin(operating_cf, revenue) -> dict:
    val = _pct(operating_cf, revenue)
    return {
        "name": "営業CF/売上高率",
        "value": val,
        "unit": "%",
        "industry_avg": 8.0,
        "health": _grade(val, 10, 5),
    }


def free_cash_flow(operating_cf, capex) -> dict:
    if operating_cf is None or capex is None:
        val = None
    else:
        val = operating_cf - abs(capex)
    return {
        "name": "FCF（フリーキャッシュフロー）",
        "value": val,
        "unit": "百万円",
        "industry_avg": None,
        "health": _grade(val, 0, 0) if val is not None else "unknown",
    }


def cf_coverage(operating_cf, total_debt) -> dict:
    val = _pct(operating_cf, total_debt)
    return {
        "name": "CF充当率",
        "value": val,
        "unit": "%",
        "industry_avg": 20.0,
        "health": _grade(val, 20, 10),
    }


def dividend_payout(dividends, net_income) -> dict:
    val = _pct(dividends, net_income)
    return {
        "name": "配当性向",
        "value": val,
        "unit": "%",
        "industry_avg": 30.0,
        "health": _grade(val, 20, 70, higher_is_better=False) if val is not None else "unknown",
    }


# ---------------------------------------------------------------------------
# Piotroski F-Score
# ---------------------------------------------------------------------------

def piotroski_f_score(
    net_income, operating_cf, roa_current, roa_prev,
    long_term_debt_current, long_term_debt_prev,
    current_ratio_current, current_ratio_prev,
    shares_current, shares_prev,
    gross_margin_current, gross_margin_prev,
    asset_turnover_current, asset_turnover_prev,
) -> dict:
    score = 0
    details = []

    def _add(condition: bool, label: str):
        nonlocal score
        pts = 1 if condition else 0
        score += pts
        details.append({"label": label, "point": pts})

    _add((net_income or 0) > 0, "当期純利益 > 0")
    _add((operating_cf or 0) > 0, "営業CF > 0")
    _add((roa_current or 0) > (roa_prev or 0), "ROA改善")
    _add((operating_cf or 0) > (net_income or 0), "営業CF > 純利益（発生主義品質）")
    _add((long_term_debt_current or 0) <= (long_term_debt_prev or 0), "長期負債減少")
    _add((current_ratio_current or 0) >= (current_ratio_prev or 0), "流動比率改善")
    _add((shares_current or 0) <= (shares_prev or 0), "株式数増加なし")
    _add((gross_margin_current or 0) >= (gross_margin_prev or 0), "総利益率改善")
    _add((asset_turnover_current or 0) >= (asset_turnover_prev or 0), "総資産回転率改善")

    if score >= 7:
        health = "good"
    elif score >= 4:
        health = "warning"
    else:
        health = "danger"

    return {
        "name": "Piotroski F-Score",
        "value": score,
        "unit": "/9",
        "industry_avg": 5,
        "health": health,
        "details": details,
    }


# ---------------------------------------------------------------------------
# 全指標を一括計算する便利関数
# ---------------------------------------------------------------------------

def calculate_all(data: dict, prev_data: dict = None) -> dict:
    """
    data: 今期財務データdict
    prev_data: 前期財務データdict（成長性・F-Score用）
    """
    p = data  # 今期
    q = prev_data or {}

    results = {}

    # 収益性
    results["profitability"] = [
        gross_profit_margin(p.get("revenue"), p.get("gross_profit")),
        operating_profit_margin(p.get("revenue"), p.get("operating_profit")),
        ordinary_profit_margin(p.get("revenue"), p.get("ordinary_profit")),
        ebitda_margin(p.get("revenue"), p.get("operating_profit"), p.get("depreciation")),
        roe(p.get("net_income"), p.get("equity")),
        roa(p.get("net_income"), p.get("total_assets")),
        roic(p.get("nopat"), p.get("invested_capital")),
    ]

    # 安全性
    results["safety"] = [
        equity_ratio(p.get("equity"), p.get("total_assets")),
        current_ratio(p.get("current_assets"), p.get("current_liabilities")),
        quick_ratio(p.get("cash"), p.get("receivables"), p.get("current_liabilities")),
        de_ratio(p.get("total_debt"), p.get("equity")),
        interest_coverage_ratio(p.get("operating_profit"), p.get("interest_expense")),
        altman_z_score(
            p.get("working_capital"), p.get("total_assets"), p.get("retained_earnings"),
            p.get("ebit"), p.get("market_cap"), p.get("total_liabilities"), p.get("revenue")
        ),
    ]

    # 成長性
    results["growth"] = [
        revenue_yoy(p.get("revenue"), q.get("revenue")),
        operating_profit_yoy(p.get("operating_profit"), q.get("operating_profit")),
        eps_growth(p.get("eps"), q.get("eps")),
        cagr_3y(p.get("revenue"), p.get("revenue_3y_ago")),
    ]

    # 効率性
    results["efficiency"] = [
        asset_turnover(p.get("revenue"), p.get("total_assets")),
        inventory_days(p.get("inventory"), p.get("cogs")),
        receivable_days(p.get("receivables"), p.get("revenue")),
        labor_cost_ratio(p.get("labor_cost"), p.get("revenue")),
    ]

    # CF系
    results["cashflow"] = [
        operating_cf_margin(p.get("operating_cf"), p.get("revenue")),
        free_cash_flow(p.get("operating_cf"), p.get("capex")),
        cf_coverage(p.get("operating_cf"), p.get("total_debt")),
        dividend_payout(p.get("dividends"), p.get("net_income")),
    ]

    # 総合
    results["comprehensive"] = [
        piotroski_f_score(
            p.get("net_income"), p.get("operating_cf"),
            p.get("roa"), q.get("roa"),
            p.get("long_term_debt"), q.get("long_term_debt"),
            p.get("current_ratio_val"), q.get("current_ratio_val"),
            p.get("shares_outstanding"), q.get("shares_outstanding"),
            p.get("gross_margin"), q.get("gross_margin"),
            p.get("asset_turnover_val"), q.get("asset_turnover_val"),
        ),
    ]

    return results
