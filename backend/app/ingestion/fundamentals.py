"""
Fundamentals fetcher — uses yfinance with .NS suffix for NSE stocks.
All monetary values are in INR (yfinance returns INR for .NS tickers).
"""
from typing import Optional
import asyncio
import yfinance as yf
from datetime import datetime, timezone

from app.models import Stock


import requests
from bs4 import BeautifulSoup

def _fetch_screener_sync(ticker: str) -> dict:
    """Fallback / enrichment fundamentals scraper from Screener.in."""
    try:
        clean_symbol = ticker.split(".")[0].upper()
        url = f"https://www.screener.in/company/{clean_symbol}/consolidated/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code != 200:
            url = f"https://www.screener.in/company/{clean_symbol}/"
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code != 200:
                return {}

        soup = BeautifulSoup(resp.text, "html.parser")
        ratios = {}
        # Parse top key ratios from Screener.in
        for item in soup.select("#top-ratios li"):
            name_el = item.select_one(".name")
            value_el = item.select_one(".value")
            if name_el and value_el:
                name = name_el.get_text(strip=True).lower()
                val = value_el.get_text(strip=True).replace(",", "").replace("%", "").strip()
                ratios[name] = val
        return ratios
    except Exception:
        return {}


def _fetch_fundamentals_sync(ticker_ns: str) -> dict:
    """Blocking yfinance call enriched with Screener.in — run in executor."""
    try:
        yf_stock = yf.Ticker(ticker_ns)
        info = yf_stock.info or {}

        # Get recent price history
        hist = yf_stock.history(period="5d")
        last_price = float(hist["Close"].iloc[-1]) if not hist.empty else None

        # Financial statements
        try:
            financials = yf_stock.financials
            total_revenue = float(financials.loc["Total Revenue"].iloc[0]) if "Total Revenue" in financials.index else None
            net_income = float(financials.loc["Net Income"].iloc[0]) if "Net Income" in financials.index else None
        except Exception:
            total_revenue = None
            net_income = None

        # Fetch Screener.in fallback / enrichment metrics
        screener_data = _fetch_screener_sync(ticker_ns)

        pe = info.get("trailingPE")
        if pe is None and "stock p/e" in screener_data:
            try:
                pe = float(screener_data["stock p/e"])
            except ValueError:
                pass

        pb = info.get("priceToBook")
        if pb is None and "book value" in screener_data and (last_price or info.get("currentPrice")):
            try:
                bv = float(screener_data["book value"])
                price = last_price or info.get("currentPrice")
                if bv > 0 and price:
                    pb = round(price / bv, 2)
            except ValueError:
                pass

        roe = info.get("returnOnEquity")
        if roe is None and "roe" in screener_data:
            try:
                roe = float(screener_data["roe"]) / 100.0
            except ValueError:
                pass

        div_yield = info.get("dividendYield")
        if div_yield is None and "dividend yield" in screener_data:
            try:
                div_yield = float(screener_data["dividend yield"]) / 100.0
            except ValueError:
                pass

        return {
            "ticker_ns": ticker_ns,
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "exchange": info.get("exchange", "NSI"),
            # Prices in INR
            "last_price": last_price or info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "week_52_high": info.get("fiftyTwoWeekHigh"),
            "week_52_low": info.get("fiftyTwoWeekLow"),
            # Valuation
            "pe_ratio": pe,
            "forward_pe": info.get("forwardPE"),
            "pb_ratio": pb,
            "ps_ratio": info.get("priceToSalesTrailing12Months"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            # Profitability
            "roe": roe,
            "roa": info.get("returnOnAssets"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            # Balance sheet
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            # Income
            "revenue": total_revenue or info.get("totalRevenue"),
            "net_profit": net_income or info.get("netIncomeToCommon"),
            "eps": info.get("trailingEps"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            # Dividends
            "dividend_yield": div_yield,
            "dividend_rate": info.get("dividendRate"),
            "payout_ratio": info.get("payoutRatio"),
            # Misc
            "beta": info.get("beta"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "description": info.get("longBusinessSummary"),
            "website": info.get("website"),
            "employees": info.get("fullTimeEmployees"),
            "screener_ratios": screener_data,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"error": str(e), "ticker_ns": ticker_ns}


async def fetch_fundamentals(ticker_ns: str) -> dict:
    """Async wrapper for yfinance + Screener.in fetch."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_fundamentals_sync, ticker_ns)



def fundamentals_to_chunks(data: dict, ticker: str) -> list[str]:
    """
    Convert fundamentals dict into text chunks for embedding.
    All figures stated in INR (Rs.).
    """
    if "error" in data:
        return []

    def fmt_inr(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        if val >= 1e12:
            return f"Rs. {val/1e12:.2f} Lakh Cr"
        if val >= 1e7:
            return f"Rs. {val/1e7:.2f} Cr"
        if val >= 1e5:
            return f"Rs. {val/1e5:.2f} Lakh"
        return f"Rs. {val:,.2f}"

    def fmt_pct(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val * 100:.2f}%"

    def fmt_x(val: Optional[float]) -> str:
        if val is None:
            return "N/A"
        return f"{val:.2f}x"

    name = data.get("name", ticker)
    sector = data.get("sector", "Unknown")

    chunks = [
        # Overview chunk
        f"""Company Overview - {name} ({ticker})
Sector: {sector} | Industry: {data.get('industry', 'N/A')}
Exchange: {data.get('exchange', 'NSE')}
Last Price: {fmt_inr(data.get('last_price'))}
Market Capitalisation: {fmt_inr(data.get('market_cap'))}
52-Week High: {fmt_inr(data.get('week_52_high'))} | 52-Week Low: {fmt_inr(data.get('week_52_low'))}
Business: {(data.get('description') or '')[:300]}""",

        # Valuation chunk
        f"""Valuation Metrics - {name} ({ticker})
Price-to-Earnings (P/E): {fmt_x(data.get('pe_ratio'))} | Forward P/E: {fmt_x(data.get('forward_pe'))}
Price-to-Book (P/B): {fmt_x(data.get('pb_ratio'))}
Price-to-Sales (P/S): {fmt_x(data.get('ps_ratio'))}
EV/EBITDA: {fmt_x(data.get('ev_ebitda'))}
EPS (TTM): {fmt_inr(data.get('eps'))}""",

        # Profitability chunk
        f"""Profitability & Returns - {name} ({ticker})
Revenue (TTM): {fmt_inr(data.get('revenue'))}
Net Profit (TTM): {fmt_inr(data.get('net_profit'))}
Return on Equity (ROE): {fmt_pct(data.get('roe'))}
Return on Assets (ROA): {fmt_pct(data.get('roa'))}
Profit Margin: {fmt_pct(data.get('profit_margin'))}
Operating Margin: {fmt_pct(data.get('operating_margin'))}
Revenue Growth (YoY): {fmt_pct(data.get('revenue_growth'))}
Earnings Growth (YoY): {fmt_pct(data.get('earnings_growth'))}""",

        # Balance sheet chunk
        f"""Balance Sheet & Liquidity - {name} ({ticker})
Debt-to-Equity Ratio: {fmt_x(data.get('debt_to_equity'))}
Current Ratio: {fmt_x(data.get('current_ratio'))}
Quick Ratio: {fmt_x(data.get('quick_ratio'))}
Beta: {data.get('beta', 'N/A')}""",

        # Dividends chunk
        f"""Dividends - {name} ({ticker})
Dividend Yield: {fmt_pct(data.get('dividend_yield'))}
Dividend Rate: {fmt_inr(data.get('dividend_rate'))} per share
Payout Ratio: {fmt_pct(data.get('payout_ratio'))}""",
    ]
    return chunks
