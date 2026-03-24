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
_TEXT_LIGHT = "#9CA3AF"

_WORDMARK_URL = (
    "https://raw.githubusercontent.com/cotah/receipt/main/"
    "receipt-mobile/assets/smartdocket-wordmark.png"
)

_FONT = "font-family:'Segoe UI',Helvetica,Arial,sans-serif"
_MONO = "font-family:'SF Mono',Menlo,Consolas,monospace"


def _euro(value: float) -> str:
    return f"\u20ac{value:,.2f}"


def _pct(value: float) -> str:
    return f"{value:.1f}%"


def _trend_badge(pct: float, direction: str) -> str:
    """Coloured badge showing month-over-month change."""
    if direction == "down":
        bg, fg, arrow = "#DCFCE7", _ACCENT_GREEN, "&darr;"
        label = f"{arrow} {abs(pct):.1f}% less"
    elif direction == "up":
        bg, fg, arrow = "#FEF3C7", _ACCENT_AMBER, "&uarr;"
        label = f"{arrow} {pct:.1f}% more"
    else:
        bg, fg = "#F3F4F6", _TEXT_SEC
        label = "— stable"
    return (
        f'<span style="display:inline-block;padding:4px 10px;border-radius:20px;'
        f'background:{bg};color:{fg};{_FONT};font-size:12px;font-weight:600">'
        f"{label}</span>"
    )


def _store_table(by_store: list[dict]) -> str:
    """'Where you shopped' table with badges."""
    if not by_store:
        return ""

    most_visits = max(s["visits"] for s in by_store)
    sorted_by_avg = sorted(by_store, key=lambda s: s["total"] / max(s["visits"], 1))
    cheapest_store = sorted_by_avg[0]["store"] if sorted_by_avg else ""

    rows = ""
    for s in by_store:
        avg_visit = s["total"] / max(s["visits"], 1)
        store_label = s["store"]

        # Badges
        badges = ""
        if s["visits"] == most_visits and most_visits > 1:
            badges += (
                f' <span style="display:inline-block;padding:1px 6px;border-radius:8px;'
                f'background:#DCFCE7;color:{_ACCENT_GREEN};font-size:10px;font-weight:600">'
                f"most visited</span>"
            )
        if s["store"] == cheapest_store and len(by_store) > 1:
            badges += (
                ' <span style="display:inline-block;padding:1px 6px;border-radius:8px;'
                'background:#EDE9FE;color:#7C3AED;font-size:10px;font-weight:600">'
                "cheapest avg</span>"
            )

        rows += (
            "<tr>"
            f'<td style="padding:10px 12px;border-bottom:1px solid #F3F4F6;{_FONT};'
            f'font-size:14px;color:{_TEXT}">{store_label}{badges}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #F3F4F6;{_MONO};'
            f'font-size:14px;color:{_TEXT};text-align:right">{_euro(s["total"])}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #F3F4F6;{_FONT};'
            f'font-size:14px;color:{_TEXT};text-align:center">{s["visits"]}</td>'
            f'<td style="padding:10px 12px;border-bottom:1px solid #F3F4F6;{_MONO};'
            f'font-size:14px;color:{_TEXT_SEC};text-align:right">{_euro(avg_visit)}</td>'
            "</tr>"
        )

    return f"""\
    <h2 style="margin:0 0 12px;{_FONT};font-size:16px;color:{_PRIMARY_DARK}">
      Where you shopped</h2>
    <table width="100%" cellpadding="0" cellspacing="0"
           style="border-collapse:collapse;border-radius:8px;overflow:hidden;border:1px solid #E5E7EB">
      <tr style="background-color:{_PRIMARY}">
        <th style="padding:10px 12px;text-align:left;{_FONT};font-size:11px;color:#fff;text-transform:uppercase;letter-spacing:0.5px">Store</th>
        <th style="padding:10px 12px;text-align:right;{_FONT};font-size:11px;color:#fff;text-transform:uppercase;letter-spacing:0.5px">Spent</th>
        <th style="padding:10px 12px;text-align:center;{_FONT};font-size:11px;color:#fff;text-transform:uppercase;letter-spacing:0.5px">Visits</th>
        <th style="padding:10px 12px;text-align:right;{_FONT};font-size:11px;color:#fff;text-transform:uppercase;letter-spacing:0.5px">Avg/visit</th>
      </tr>
      {rows}
    </table>"""


def _category_bars(by_category: list[dict]) -> str:
    """Category bars with percentage fill."""
    if not by_category:
        return ""

    max_pct = max((c.get("percentage", 0) for c in by_category), default=1) or 1
    bars = ""
    colours = [_PRIMARY, _PRIMARY_LIGHT, _ACCENT_GREEN, _ACCENT_AMBER, "#6B7280", "#9CA3AF"]

    for i, c in enumerate(by_category[:6]):
        pct = c.get("percentage", 0)
        bar_width = max(int(pct / max_pct * 100), 4)
        colour = colours[i % len(colours)]
        bars += f"""\
    <tr><td style="padding:6px 0">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="width:110px;{_FONT};font-size:13px;color:{_TEXT};padding-right:8px">{c["category"]}</td>
        <td><div style="background:#F3F4F6;border-radius:6px;overflow:hidden;height:22px">
          <div style="background:{colour};height:22px;width:{bar_width}%;border-radius:6px;
                       line-height:22px;padding-left:8px;{_MONO};font-size:11px;color:#fff;white-space:nowrap">
            {_euro(c["total"])} ({_pct(pct)})
          </div></div></td>
      </tr></table>
    </td></tr>"""

    return f"""\
    <h2 style="margin:0 0 12px;{_FONT};font-size:16px;color:{_PRIMARY_DARK}">
      Spending by category</h2>
    <table width="100%" cellpadding="0" cellspacing="0">{bars}</table>"""


def _price_comparison(report: dict) -> str:
    """Top 3 most-bought products compared across stores."""
    comparisons = report.get("price_comparisons", [])
    if not comparisons:
        return ""

    cards = ""
    for comp in comparisons[:3]:
        product = comp.get("product", "—")
        stores = comp.get("stores", [])
        if not stores:
            continue

        cheapest_price = min(s["price"] for s in stores)
        most_expensive = max(s["price"] for s in stores)
        saving = most_expensive - cheapest_price

        store_lines = ""
        for s in stores:
            is_cheapest = s["price"] == cheapest_price
            price_colour = _ACCENT_GREEN if is_cheapest else _TEXT
            weight = "bold" if is_cheapest else "normal"
            badge = (
                f' <span style="color:{_ACCENT_GREEN};font-size:11px">&#10003; cheapest</span>'
                if is_cheapest and len(stores) > 1
                else ""
            )
            store_lines += (
                f'<tr><td style="padding:4px 0;{_FONT};font-size:13px;color:{_TEXT_SEC}">'
                f'{s["store"]}</td>'
                f'<td style="padding:4px 0;{_MONO};font-size:13px;color:{price_colour};'
                f'font-weight:{weight};text-align:right">{_euro(s["price"])}{badge}</td></tr>'
            )

        saving_html = ""
        if saving > 0.01:
            saving_html = (
                f'<p style="margin:6px 0 0;{_FONT};font-size:12px;color:{_ACCENT_GREEN}">'
                f"Save {_euro(saving)} by choosing the cheapest</p>"
            )

        cards += f"""\
      <td style="padding:6px;width:33%;vertical-align:top">
        <div style="background:{_BG};border-radius:8px;padding:12px">
          <p style="margin:0 0 8px;{_FONT};font-size:13px;font-weight:600;color:{_TEXT}">
            {product}</p>
          <table width="100%" cellpadding="0" cellspacing="0">{store_lines}</table>
          {saving_html}
        </div>
      </td>"""

    return f"""\
    <h2 style="margin:0 0 12px;{_FONT};font-size:16px;color:{_PRIMARY_DARK}">
      Price comparison</h2>
    <table width="100%" cellpadding="0" cellspacing="0"><tr>{cards}</tr></table>"""


def build_monthly_report_html(report: dict, user_name: str) -> str:
    """Build a branded HTML email from a monthly report dict."""
    period = report["period"]
    summary = report["summary"]
    by_store = report.get("by_store", [])
    by_category = report.get("by_category", [])
    insights = report.get("insights", [])

    # Key stats
    most_used_store = by_store[0]["store"] if by_store else "—"
    receipts_count = summary.get("receipts_count", 0)
    avg_per_shop = summary["total_spent"] / max(receipts_count, 1)

    # Most bought product
    product_counts: dict[str, int] = {}
    for cat in by_category:
        for item_name in cat.get("top_items", []):
            product_counts[item_name] = product_counts.get(item_name, 0) + 1
    most_bought = max(product_counts, key=product_counts.get) if product_counts else "—"  # type: ignore[arg-type]

    # Trend
    trend = summary.get("vs_previous_month", {})
    trend_pct = trend.get("percent", 0)
    trend_dir = trend.get("trend", "stable")
    prev_total = trend.get("previous_total", 0)

    # Insights HTML
    insights_html = ""
    for tip in insights:
        insights_html += (
            f'<li style="margin-bottom:8px;{_FONT};font-size:14px;'
            f'color:{_TEXT};line-height:1.5">{tip}</li>'
        )

    # Previous month name
    prev_month = trend.get("previous_period", "last month")

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:{_BG}">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:{_BG}">
<tr><td align="center" style="padding:24px 16px">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

  <!-- HEADER with wordmark -->
  <tr><td style="background-color:{_PRIMARY};border-radius:12px 12px 0 0;padding:24px;text-align:center">
    <img src="{_WORDMARK_URL}" alt="SmartDocket" height="50"
         style="height:50px;width:auto;display:inline-block" />
    <p style="margin:10px 0 0;{_FONT};font-size:13px;color:#C8E6D0;letter-spacing:0.3px">
      Your monthly spending report</p>
  </td></tr>

  <!-- GREETING -->
  <tr><td style="background-color:{_CARD};padding:24px 24px 16px">
    <p style="margin:0;{_FONT};font-size:16px;color:{_TEXT};line-height:1.5">
      Hi <strong>{user_name}</strong>,<br>
      here's how your groceries looked in <strong>{period}</strong>.
    </p>
  </td></tr>

  <!-- MONTH OVER MONTH -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{_BG};border-radius:10px;overflow:hidden">
      <tr>
        <td style="padding:16px;text-align:center;width:40%;border-right:1px solid #E5E7EB">
          <p style="margin:0;{_FONT};font-size:11px;color:{_TEXT_SEC};text-transform:uppercase;letter-spacing:0.5px">
            {prev_month}</p>
          <p style="margin:6px 0 0;{_MONO};font-size:22px;font-weight:bold;color:{_TEXT_LIGHT}">
            {_euro(prev_total)}</p>
        </td>
        <td style="padding:16px;text-align:center;width:40%">
          <p style="margin:0;{_FONT};font-size:11px;color:{_TEXT_SEC};text-transform:uppercase;letter-spacing:0.5px">
            {period}</p>
          <p style="margin:6px 0 0;{_MONO};font-size:22px;font-weight:bold;color:{_PRIMARY}">
            {_euro(summary["total_spent"])}</p>
        </td>
        <td style="padding:16px;text-align:center;width:20%">
          {_trend_badge(trend_pct, trend_dir)}
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- 3 STAT CARDS -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="8">
      <tr>
        <td style="background:{_BG};border-radius:10px;padding:16px;text-align:center;width:33%">
          <p style="margin:0;{_MONO};font-size:20px;font-weight:bold;color:{_ACCENT_AMBER}">
            {_euro(avg_per_shop)}</p>
          <p style="margin:4px 0 0;{_FONT};font-size:11px;color:{_TEXT_SEC}">Avg per shop</p>
        </td>
        <td style="background:{_BG};border-radius:10px;padding:16px;text-align:center;width:33%">
          <p style="margin:0;{_FONT};font-size:18px;font-weight:bold;color:{_PRIMARY}">
            {most_used_store}</p>
          <p style="margin:4px 0 0;{_FONT};font-size:11px;color:{_TEXT_SEC}">Most visited</p>
        </td>
        <td style="background:{_BG};border-radius:10px;padding:16px;text-align:center;width:33%">
          <p style="margin:0;{_FONT};font-size:16px;font-weight:bold;color:{_TEXT}">
            {most_bought}</p>
          <p style="margin:4px 0 0;{_FONT};font-size:11px;color:{_TEXT_SEC}">Most bought</p>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- WHERE YOU SHOPPED -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    {_store_table(by_store)}
  </td></tr>

  <!-- PRICE COMPARISON -->
  {"" if not report.get("price_comparisons") else f'''<tr><td style="background-color:{_CARD};padding:0 24px 24px">
    {_price_comparison(report)}
  </td></tr>'''}

  <!-- CATEGORY BARS -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    {_category_bars(by_category)}
  </td></tr>

  <!-- DISCOUNTS BANNER -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px">
    <table width="100%" cellpadding="0" cellspacing="0"
           style="background:{_PRIMARY_DARK};border-radius:10px;overflow:hidden">
      <tr><td style="padding:24px;text-align:center">
        <p style="margin:0;{_FONT};font-size:12px;color:{_TEXT_LIGHT};text-transform:uppercase;letter-spacing:1px">
          Total saved in promotions</p>
        <p style="margin:8px 0 0;{_MONO};font-size:32px;font-weight:bold;color:{_ACCENT_GREEN}">
          {_euro(summary.get("total_saved", 0))}</p>
        <p style="margin:6px 0 0;{_FONT};font-size:13px;color:#C8E6D0">
          from receipt discounts in {period}</p>
      </td></tr>
    </table>
  </td></tr>

  <!-- INSIGHTS -->
  {"" if not insights else f'''<tr><td style="background-color:{_CARD};padding:24px">
    <h2 style="margin:0 0 12px;{_FONT};font-size:16px;color:{_PRIMARY_DARK}">
      &#128161; Personalised insights</h2>
    <ul style="margin:0;padding-left:20px">{insights_html}</ul>
  </td></tr>'''}

  <!-- CTA BUTTON -->
  <tr><td style="background-color:{_CARD};padding:0 24px 24px;text-align:center">
    <a href="https://smartdocket.ie" target="_blank"
       style="display:inline-block;padding:14px 40px;background:{_PRIMARY};color:#fff;
              {_FONT};font-size:15px;font-weight:600;text-decoration:none;
              border-radius:10px;letter-spacing:0.3px">
      Open SmartDocket
    </a>
  </td></tr>

  <!-- FOOTER -->
  <tr><td style="background-color:{_PRIMARY_DARK};border-radius:0 0 12px 12px;padding:24px;text-align:center">
    <p style="margin:0;{_FONT};font-size:12px;color:{_TEXT_LIGHT};line-height:1.6">
      You received this email because you have reports enabled in SmartDocket.<br>
      To unsubscribe, open the app &rarr; Profile &rarr; turn off Monthly Reports.
    </p>
    <p style="margin:12px 0 0;{_FONT};font-size:11px;color:#6B7280">
      &copy; 2026 SmartDocket &middot; Dublin, Ireland
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""
