"""Render a short monthly snapshot from the shared dashboard report."""

from datetime import timedelta
from decimal import Decimal
from html import escape

from .email_models import MonthlyEmailPreview, RecipientSettings
from .models import DashboardReport, Period


LABELS = {"shopgoodwill": "ShopGoodwill", "amazon": "Amazon", "ebay": "eBay", "other": "Other vendors"}
MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def money(value: Decimal | None) -> str:
    return "Unavailable" if value is None else f"${value:,.2f}"


def percent(value: Decimal | None) -> str:
    return "Unavailable" if value is None else f"{value:,.2f}%"


def monthly_insights(report: DashboardReport) -> list[str]:
    """Describe observed values, without inventing targets or company health."""
    change = report.comparison.revenue_change_percent
    if change is None:
        movement = "A month-over-month revenue comparison is unavailable."
    elif change == 0:
        movement = "Revenue was unchanged from the previous calendar month."
    else:
        movement = (f"Revenue was {'up' if change > 0 else 'down'} {percent(abs(change))} "
                    f"from the previous calendar month ({money(report.comparison.revenue)}).")
    insights = [movement]
    if report.marketplaces:
        highest = max(row.revenue for row in report.marketplaces)
        leaders = [LABELS.get(row.marketplace, row.marketplace)
                   for row in report.marketplaces if row.revenue == highest]
        if highest > 0:
            # Report ties honestly; Other vendors is a group, not one marketplace.
            insights.append(f"{' and '.join(leaders)} {'led' if len(leaders) == 1 else 'tied for the lead'} "
                            f"in revenue at {money(highest)}.")
    buyers = report.ebay_buyers
    if buyers is not None and buyers.returning_buyer_rate_percent is not None:
        insights.append(f"eBay returning buyer rate: {percent(buyers.returning_buyer_rate_percent)} "
                        f"({buyers.returning_buyers} of {buyers.unique_buyers} identified buyers).")
    else:
        insights.append("eBay buyer information is unavailable for this report.")
    return insights


def build_email_preview(report: DashboardReport, settings: RecipientSettings) -> MonthlyEmailPreview:
    if report.period != Period.month:
        raise ValueError("Monthly emails require a monthly report.")
    month = f"{MONTHS[report.start.month - 1]} {report.start.year}"
    demo = " [DEMO]" if report.data_mode == "mock" else ""
    subject = f"Goodwill Michiana E-commerce Report - {month}{demo}"
    coverage = (f"{report.start.isoformat()} through "
                f"{(report.end_exclusive - timedelta(days=1)).isoformat()} "
                f"({report.reporting_timezone})")
    highlights = [("Total item revenue", money(report.totals.revenue)),
                  ("Paid transactions", str(report.totals.transactions)),
                  ("Units sold", str(report.totals.units_sold))]
    insights = monthly_insights(report)
    notes = ["Retention covers eBay only; returning buyers purchased before this month."]
    buyers = report.ebay_buyers
    if buyers is not None and buyers.transactions_missing_buyer_id:
        notes.append(f"{buyers.transactions_missing_buyer_id} eBay transactions lack buyer IDs and are excluded from retention.")
    if report.unavailable_metrics:
        notes.append("Some metrics are unavailable; this snapshot does not assess overall profitability.")
    notes.append("Comparison uses the full previous calendar month; an unfinished month is not directly comparable.")
    lines = [subject, report.notice, coverage, "", *[f"{label}: {value}" for label, value in highlights],
             f"Average selling price per unit: {money(report.totals.average_selling_price)}",
             "", "What stood out:", *[f"- {line}" for line in insights], "", "Revenue by marketplace:"]

    # These table bars need no remote images or JavaScript. Exact numbers remain
    # readable if a mail client strips the decorative backgrounds.
    rows = []
    maximum = max((row.revenue for row in report.marketplaces), default=Decimal(0))
    for row in report.marketplaces:
        label = LABELS.get(row.marketplace, row.marketplace)
        transaction_label = "transaction" if row.transactions == 1 else "transactions"
        lines.append(f"- {label}: {money(row.revenue)}; {row.transactions} {transaction_label}")
        width = float(max(row.revenue, Decimal(0)) / maximum * 100) if maximum > 0 else 0
        bar = (f'<table role="presentation" width="{width:.2f}%" cellspacing="0" cellpadding="0">'
               '<tr><td height="7" style="background:#397ba6;border-radius:4px;font-size:1px">&nbsp;</td></tr></table>'
               if width > 0 else "")
        rows.append(f'<tr><td style="padding:10px 12px 10px 0;width:65%">{escape(label)}'
                    f'<div style="margin-top:7px">{bar}</div></td>'
                    f'<td style="padding:10px 0;text-align:right;white-space:nowrap">{money(row.revenue)}'
                    f'<br><span style="font-size:12px;color:#526273">{row.transactions} {transaction_label}</span></td></tr>')
    lines.extend(["", "Notes:", *notes])
    cards = "".join(f'<td width="33%" valign="top" style="padding:16px 8px;background:#edf3f7">'
                    f'<span style="font-size:12px;color:#526273">{escape(label)}</span><br>'
                    f'<strong style="font-size:24px;line-height:1.6">{escape(value)}</strong></td>'
                    for label, value in highlights)
    bullets = "".join(f'<li style="margin-bottom:10px">{escape(line)}</li>' for line in insights)
    # All source text is escaped. Detailed dashboard definitions stay out of this
    # short email, while limitations relevant to interpreting it remain visible.
    html_body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{escape(subject)}</title></head>'
        '<body style="margin:0;background:#f1f4f7;font-family:Arial,sans-serif;color:#19344b;line-height:1.6">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 12px">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;background:#fff;border-radius:12px">'
        '<tr><td style="padding:28px 28px 18px;border-top:5px solid #397ba6">'
        '<p style="margin:0;font-size:12px;letter-spacing:2px;color:#526273">GOODWILL MICHIANA</p>'
        f'<h1 style="margin:8px 0;font-size:28px;line-height:1.3">{escape(month)} at a glance{demo}</h1>'
        '<p style="margin:0;color:#526273">Your monthly e-commerce snapshot</p>'
        f'<p style="font-size:12px;color:#526273;margin:12px 0 0">{escape(report.notice)}</p></td></tr>'
        f'<tr><td style="padding:0 28px"><table role="presentation" width="100%" cellspacing="4" cellpadding="0"><tr>{cards}</tr></table>'
        f'<p style="font-size:13px;color:#526273;margin:8px 0">Average selling price: {money(report.totals.average_selling_price)}</p></td></tr>'
        '<tr><td style="padding:12px 28px"><h2 style="font-size:18px;margin:0 0 10px">What stood out</h2>'
        f'<ul style="margin:0;padding-left:20px;font-size:15px">{bullets}</ul></td></tr>'
        '<tr><td style="padding:8px 28px 18px"><h2 style="font-size:18px;margin:0 0 4px">Revenue by marketplace</h2>'
        f'<table aria-label="Marketplace revenue; bars relative to the highest revenue" width="100%" cellspacing="0" cellpadding="0">{"".join(rows)}</table></td></tr>'
        '<tr><td style="padding:18px 28px;background:#f7f9fb;font-size:12px;color:#526273">'
        f'<p style="margin:0 0 8px">{escape(coverage)}</p>'
        f'<p style="margin:0">{escape(" ".join(notes))}</p></td></tr></table></td></tr></table></body></html>'
    )
    return MonthlyEmailPreview(start=report.start, end_exclusive=report.end_exclusive,
                               recipients=settings.recipients, subject=subject,
                               text_body="\n".join(lines), html_body=html_body, data_mode=report.data_mode)
