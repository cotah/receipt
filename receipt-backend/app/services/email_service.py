import logging

import resend

from app.config import settings

log = logging.getLogger(__name__)


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not settings.RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email")
        return False

    resend.api_key = settings.RESEND_API_KEY
    try:
        resend.Emails.send(
            {
                "from": settings.FROM_EMAIL,
                "to": [to],
                "subject": subject,
                "html": html,
            }
        )
        return True
    except Exception as exc:
        log.error(f"Failed to send email to {to}: {exc}")
        return False


# ---------------------------------------------------------------------------
# HTML builder
# ---------------------------------------------------------------------------

_PRIMARY = "#1A4D35"
_PRIMARY_DARK = "#0D2B1D"
_PRIMARY_LIGHT = "#2E7D52"
_ACCENT_GREEN = "#3CB371"
_ACCENT_AMBER = "#E8A020"
_BG = "#F7F5F0"
_CARD = "#FFFFFF"
_TEXT = "#1A1A1A"
_TEXT_SEC = "#6B7280"


def _euro(value: float) -> str:
    return f"\u20ac{value:,.2f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _store_rows(by_store: list[dict]) -> str:
    rows = ""
    for s in by_store:
        rows += (
            "<tr>"
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:14px;color:{_TEXT}">{s["store"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:monospace;'
            f'font-size:14px;color:{_TEXT};text-align:right">{_euro(s["total"])}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:14px;color:{_TEXT_SEC};text-align:center">{s["visits"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:14px;color:{_TEXT_SEC};text-align:right">{_pct(s["percentage"])}</td>'
            "</tr>"
        )
    return rows


def _category_rows(by_category: list[dict]) -> str:
    rows = ""
    for c in by_category:
        top = ", ".join(c.get("top_items", [])[:3]) or "—"
        rows += (
            "<tr>"
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:14px;color:{_TEXT}">{c["category"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:monospace;'
            f'font-size:14px;color:{_TEXT};text-align:right">{_euro(c["total"])}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:14px;color:{_TEXT_SEC};text-align:right">{_pct(c["percentage"])}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #E5E7EB;font-family:sans-serif;'
            f'font-size:13px;color:{_TEXT_SEC}">{top}</td>'
            "</tr>"
        )
    return rows


def build_monthly_report_html(report: dict, user_name: str) -> str:
    """Build a branded HTML email from a monthly report dict."""
    period = report["period"]
    summary = report["summary"]
    by_store = report.get("by_store", [])
    by_category = report.get("by_category", [])
    insights = report.get("insights", [])

    # Key stats
    most_used_store = by_store[0]["store"] if by_store else "—"
    cheapest_store = by_store[-1]["store"] if len(by_store) > 1 else most_used_store

    # Most bought product: find the product that appears most across categories
    product_counts: dict[str, int] = {}
    for cat in by_category:
        for item_name in cat.get("top_items", []):
            product_counts[item_name] = product_counts.get(item_name, 0) + 1
    most_bought = max(product_counts, key=product_counts.get) if product_counts else "—"  # type: ignore[arg-type]

    # Trend arrow
    trend = summary.get("vs_previous_month", {})
    trend_pct = trend.get("percent", 0)
    trend_dir = trend.get("trend", "stable")
    if trend_dir == "down":
        trend_html = f'<span style="color:{_ACCENT_GREEN}">&darr; {abs(trend_pct):.1f}%</span>'
    elif trend_dir == "up":
        trend_html = f'<span style="color:{_ACCENT_AMBER}">&uarr; {trend_pct:.1f}%</span>'
    else:
        trend_html = '<span style="color:#9CA3AF">— stable</span>'

    insights_html = ""
    for tip in insights:
        insights_html += (
            f'<li style="margin-bottom:6px;font-family:sans-serif;font-size:14px;'
            f'color:{_TEXT}">{tip}</li>'
        )

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:{_BG}">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG}">
<tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

  <!-- HEADER -->
  <tr><td style="background-color:{_PRIMARY};border-radius:12px 12px 0 0;padding:32px 24px;text-align:center">
    <h1 style="margin:0;font-family:Georgia,serif;font-size:28px;color:#FFFFFF;letter-spacing:1px">SmartDocket</h1>
    <p style="margin:8px 0 0;font-family:sans-serif;font-size:14px;color:#C8E6D0">Your monthly spending report</p>
  </td></tr>

  <!-- GREETING -->
  <tr><td style="background-color:{_CARD};padding:24px">
    <p style="margin:0;font-family:sans-serif;font-size:16px;color:{_TEXT}">
      Hi {user_name},<br>here's how your groceries looked in <strong>{period}</strong>.
    </p>
  </td></tr>

  <!-- SUMMARY BANNER -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background-color:{_BG};border-radius:8px;overflow:hidden">
      <tr>
        <td style="padding:16px;text-align:center;width:33%">
          <p style="margin:0;font-family:monospace;font-size:24px;font-weight:bold;color:{_ACCENT_AMBER}">
            {_euro(summary["total_spent"])}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:12px;color:{_TEXT_SEC}">
            Total spent</p>
        </td>
        <td style="padding:16px;text-align:center;width:33%">
          <p style="margin:0;font-family:monospace;font-size:24px;font-weight:bold;color:{_PRIMARY_LIGHT}">
            {summary["receipts_count"]}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:12px;color:{_TEXT_SEC}">
            Receipts</p>
        </td>
        <td style="padding:16px;text-align:center;width:33%">
          <p style="margin:0;font-family:sans-serif;font-size:18px;font-weight:bold">
            {trend_html}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:12px;color:{_TEXT_SEC}">
            vs last month</p>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- KEY STATS -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="8">
      <tr>
        <td style="background-color:{_BG};border-radius:8px;padding:14px;text-align:center;width:33%">
          <p style="margin:0;font-family:sans-serif;font-size:16px;font-weight:bold;color:{_PRIMARY}">
            {most_used_store}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:11px;color:{_TEXT_SEC}">
            Most visited</p>
        </td>
        <td style="background-color:{_BG};border-radius:8px;padding:14px;text-align:center;width:33%">
          <p style="margin:0;font-family:sans-serif;font-size:16px;font-weight:bold;color:{_ACCENT_GREEN}">
            {cheapest_store}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:11px;color:{_TEXT_SEC}">
            Cheapest store</p>
        </td>
        <td style="background-color:{_BG};border-radius:8px;padding:14px;text-align:center;width:33%">
          <p style="margin:0;font-family:sans-serif;font-size:16px;font-weight:bold;color:{_TEXT}">
            {most_bought}</p>
          <p style="margin:4px 0 0;font-family:sans-serif;font-size:11px;color:{_TEXT_SEC}">
            Most bought</p>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- BY STORE -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <h2 style="margin:0 0 12px;font-family:sans-serif;font-size:18px;color:{_PRIMARY_DARK}">
      Spending by store</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #E5E7EB">
      <tr style="background-color:{_PRIMARY}">
        <th style="padding:10px 12px;text-align:left;font-family:sans-serif;font-size:12px;color:#fff">Store</th>
        <th style="padding:10px 12px;text-align:right;font-family:sans-serif;font-size:12px;color:#fff">Total</th>
        <th style="padding:10px 12px;text-align:center;font-family:sans-serif;font-size:12px;color:#fff">Visits</th>
        <th style="padding:10px 12px;text-align:right;font-family:sans-serif;font-size:12px;color:#fff">%</th>
      </tr>
      {_store_rows(by_store)}
    </table>
  </td></tr>

  <!-- BY CATEGORY -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <h2 style="margin:0 0 12px;font-family:sans-serif;font-size:18px;color:{_PRIMARY_DARK}">
      Spending by category</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #E5E7EB">
      <tr style="background-color:{_PRIMARY}">
        <th style="padding:10px 12px;text-align:left;font-family:sans-serif;font-size:12px;color:#fff">Category</th>
        <th style="padding:10px 12px;text-align:right;font-family:sans-serif;font-size:12px;color:#fff">Total</th>
        <th style="padding:10px 12px;text-align:right;font-family:sans-serif;font-size:12px;color:#fff">%</th>
        <th style="padding:10px 12px;text-align:left;font-family:sans-serif;font-size:12px;color:#fff">Top items</th>
      </tr>
      {_category_rows(by_category)}
    </table>
  </td></tr>

  <!-- DISCOUNTS -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:linear-gradient(135deg,{_ACCENT_GREEN},{_PRIMARY_LIGHT});border-radius:8px">
      <tr><td style="padding:20px;text-align:center">
        <p style="margin:0;font-family:monospace;font-size:28px;font-weight:bold;color:#fff">
          {_euro(summary["total_saved"])}</p>
        <p style="margin:6px 0 0;font-family:sans-serif;font-size:13px;color:#E8F5EE">
          Total receipt discounts in {period}</p>
      </td></tr>
    </table>
  </td></tr>

  <!-- INSIGHTS -->
  {"" if not insights else f'''<tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <h2 style="margin:0 0 12px;font-family:sans-serif;font-size:18px;color:{_PRIMARY_DARK}">
      Insights</h2>
    <ul style="margin:0;padding-left:20px">{insights_html}</ul>
  </td></tr>'''}

  <!-- FOOTER -->
  <tr><td style="background-color:{_PRIMARY_DARK};border-radius:0 0 12px 12px;padding:24px;text-align:center">
    <p style="margin:0;font-family:sans-serif;font-size:12px;color:#9CA3AF">
      You received this email because you have reports enabled in SmartDocket.<br>
      To unsubscribe, open the app &rarr; Profile &rarr; turn off Monthly Reports.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
