"""Render a factual monthly overview from the same dashboard calculations."""

import calendar
from decimal import Decimal
from html import escape

from .email_models import MonthlyEmailPreview, RecipientSettings
from .models import DashboardReport, Period


def money(value: Decimal | None) -> str:
    return "Unavailable" if value is None else f"${value:,.2f}"


def percent(value: Decimal | None) -> str:
    return "Unavailable" if value is None else f"{value:,.2f}%"


def build_email_preview(report: DashboardReport, settings: RecipientSettings) -> MonthlyEmailPreview:
    if report.period != Period.month:
        raise ValueError("Monthly emails require a monthly report.")
    # Avoid machine locale affecting month names in the subject.
    month = f"{calendar.month_name[report.start.month]} {report.start.year}"
    demo = " [DEMO]" if report.data_mode == "mock" else ""
    subject = f"Goodwill Michiana E-commerce Report - {month}{demo}"
    labels = {"shopgoodwill": "ShopGoodwill", "amazon": "Amazon", "ebay": "eBay", "other": "Other vendors"}
    lines = [
        subject, report.notice, "",
        f"Total item revenue: {money(report.totals.revenue)}",
        f"Change from previous calendar month: {percent(report.comparison.revenue_change_percent)}",
        f"Paid transactions: {report.totals.transactions}",
        f"Units sold: {report.totals.units_sold}",
        f"Average selling price per unit: {money(report.totals.average_selling_price)}",
        "", "Marketplace breakdown:",
    ]
    rows = []
    for row in report.marketplaces:
        label = labels.get(row.marketplace, row.marketplace)
        lines.append(f"- {label}: {money(row.revenue)}; {row.transactions} transactions")
        # Escape dynamic content before putting it into HTML.
        rows.append(f"<tr><td>{escape(label)}</td><td>{money(row.revenue)}</td><td>{row.transactions}</td></tr>")

    buyers = report.ebay_buyers
    if buyers is not None:
        lines.extend([
            "", "eBay buyer information only:",
            f"Unique buyers: {buyers.unique_buyers}",
            f"Returning buyers: {buyers.returning_buyers}",
            f"Returning buyer rate: {percent(buyers.returning_buyer_rate_percent)}",
            f"Transactions missing buyer identifiers: {buyers.transactions_missing_buyer_id}",
            buyers.definition,
        ])
    lines.extend(["", "Unavailable metrics:", *[f"- {metric}" for metric in report.unavailable_metrics]])
    lines.extend(["", "Definitions:", report.revenue_definition, report.comparison.definition])

    # Use the same factual text for both formats, with a readable HTML vendor table.
    paragraphs = "\n".join(f"<p>{escape(line)}</p>" for line in lines if line)
    html_body = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>{escape(subject)}</title></head><body>"
        f"{paragraphs}<h2>Marketplace summary</h2>"
        '<table border="1" cellpadding="8"><thead><tr><th scope="col">Marketplace</th>'
        '<th scope="col">Revenue</th><th scope="col">Transactions</th></tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table></body></html>"
    )
    return MonthlyEmailPreview(
        start=report.start, end_exclusive=report.end_exclusive,
        recipients=settings.recipients, subject=subject, text_body="\n".join(lines),
        html_body=html_body, data_mode=report.data_mode,
    )
