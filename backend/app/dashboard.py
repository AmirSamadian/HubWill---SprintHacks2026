"""Shared business calculations over stored facts.

Every figure the dashboard and the monthly email show is computed here (DECISIONS
D008). Only metrics the frontend displays are calculated. Money stays Decimal
until the JSON boundary; values the database cannot support are None
("unavailable"), never zero.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from zoneinfo import ZoneInfo

from .config import settings

# Order status vocabulary is not finalized (DATABASE_SPEC §9). These are the
# statuses the current data uses; anything else is excluded and reported.
INCLUDED_STATUSES = {'COMPLETED', 'SHIPPED', 'REFUNDED'}
NAMED_MARKETPLACES = ('shopgoodwill', 'amazon', 'ebay')
ZERO = Decimal(0)

# Monthly KPIs and how month-over-month changes are expressed. Totals that grow
# with the number of days are not compared while a month is still in progress.
ADDITIVE_KPIS = {'revenue', 'unitsSold', 'listingsCreated', 'buyers', 'newBuyers'}
POINT_KPIS = {'revenueGrowthYoY', 'grossMarginPct', 'netMarginPct', 'repeatBuyerRate'}

# Watch list rule (from the dashboard's product requirements): a subcategory is
# flagged when its revenue fell at least 15% from the previous full month and it
# sold at least $500 that month. Ranked by dollars lost.
WATCH_DROP_THRESHOLD = Decimal('-0.15')
WATCH_MIN_PRIOR_REVENUE = Decimal('500')

UNAVAILABLE_METRICS = [
    'Gross and net margin need cost-of-goods and expense data, which the database does not store.',
    'Customer satisfaction needs an agreed rating scale across marketplaces.',
]


class ReportError(ValueError):
    """A request the reports cannot answer (bad date, future period)."""


# ---------------------------------------------------------------- small helpers

def add_months(day: date, offset: int) -> date:
    index = day.year * 12 + day.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def parse_month(value: str) -> date:
    try:
        if len(value) != 7:
            raise ValueError
        day = date.fromisoformat(value + '-01')
        if not 2 <= day.year <= 9998:
            raise ValueError
        return day
    except ValueError:
        raise ReportError('Use a month in YYYY-MM format.') from None


def ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator else None


def change(current, previous):
    """Relative change (0.25 = +25%); None without a usable baseline."""
    return ratio(current - previous, previous) if current is not None and previous is not None else None


def sum_known(values):
    """Sum, or None when any value is unknown (unknown is never zero)."""
    values = list(values)
    return None if any(v is None for v in values) else sum(values, ZERO)


def marketplace_key(name: str) -> str:
    key = name.casefold()
    return key if key in NAMED_MARKETPLACES else 'other'


# ---------------------------------------------------------------- calculations

class ReportData:
    """Indexes one snapshot of stored facts and computes report figures from it."""

    def __init__(self, snapshot, config=None, today=None):
        self.config = config or settings()
        self.today = today or datetime.now(ZoneInfo(self.config.reporting_timezone)).date()
        self.snapshot = snapshot
        self.sources = sorted(snapshot.sources, key=lambda s: s['source_id'])
        self.source_by_id = {s['source_id']: s for s in self.sources}
        self.ebay_ids = {s['source_id'] for s in self.sources if s['name'].casefold() == 'ebay'}

        self.excluded_by_day = defaultdict(set)
        self.orders_by_day = defaultdict(list)
        for order in snapshot.orders:
            if order['status'] in INCLUDED_STATUSES:
                self.orders_by_day[order['day']].append(order)
            else:
                self.excluded_by_day[order['day']].add(order['status'])
        self.lines = defaultdict(list)
        for line in snapshot.lines:
            self.lines[line['order_id']].append(line)
        self.listings_by_day = defaultdict(int)
        for listing in snapshot.listings:
            self.listings_by_day[listing['day']] += 1
        # First stored order per identified eBay buyer, for new vs. repeat buyers.
        self.first_order_day = {}
        for day, orders in self.orders_by_day.items():
            for order in orders:
                if order['source_id'] in self.ebay_ids and order['customer_id'] is not None:
                    known = self.first_order_day.get(order['customer_id'])
                    self.first_order_day[order['customer_id']] = day if known is None else min(known, day)

    # -- selection -------------------------------------------------------

    def orders_between(self, start: date, end: date) -> list[dict]:
        days = (end - start).days
        return [o for i in range(max(days, 0)) for o in self.orders_by_day.get(start + timedelta(days=i), ())]

    def lines_of(self, orders):
        return [line for o in orders for line in self.lines[o['order_id']]]

    # -- revenue (definition chosen by DASHBOARD_REVENUE_METRIC) ---------

    def order_revenue(self, order):
        metric = self.config.revenue_metric
        if metric == 'merchandise_before_refunds':
            return order['merchandise_revenue']
        if metric == 'merchandise_after_refunds':
            if order['merchandise_revenue'] is None:
                return None
            return order['merchandise_revenue'] + order['refund_impact']
        return order['total_transaction_revenue']

    def line_revenue(self, line):
        """Revenue of one item. Transaction revenue includes order-level shipping
        and fees, which have no agreed allocation to items, so it is None."""
        merchandise = line['quantity'] * line['unit_price'] - line['discount_amount']
        metric = self.config.revenue_metric
        if metric == 'merchandise_before_refunds':
            return merchandise
        if metric == 'merchandise_after_refunds':
            return merchandise - line['refund_amount']
        return None

    def revenue(self, orders):
        return sum_known(self.order_revenue(o) for o in orders)

    # -- figures -----------------------------------------------------------

    def summary(self, orders):
        """Revenue, transactions, units and average selling price.
        ASP = merchandise after discounts / units sold (DATABASE_SPEC §6)."""
        units = sum(line['quantity'] for line in self.lines_of(orders))
        merchandise = sum_known(o['merchandise_revenue'] for o in orders)
        return {'revenue': self.revenue(orders), 'transactions': len(orders), 'units': units,
                'average_selling_price': ratio(merchandise, units)}

    def customers(self, orders):
        """Distinct identified buyers, or None when any order lacks a buyer
        (only eBay supplies buyer identity)."""
        if any(o['customer_id'] is None for o in orders):
            return None
        return len({o['customer_id'] for o in orders})

    def channels(self, orders):
        by_source = defaultdict(list)
        for order in orders:
            by_source[order['source_id']].append(order)
        rows = []
        for source in self.sources:
            subset = by_source.get(source['source_id'], [])
            key = source['name'].casefold()
            rows.append({
                'id': key if key in NAMED_MARKETPLACES else f"source-{source['source_id']}",
                'name': source['name'], 'revenue': self.revenue(subset),
                'orders': len(subset), 'customers': self.customers(subset),
            })
        return rows

    def ebay_buyers(self, orders, start):
        """Identified eBay buyers in the period. Repeat = bought before the period
        started; new = first stored order falls in the period."""
        ebay = [o for o in orders if o['source_id'] in self.ebay_ids]
        ids = {o['customer_id'] for o in ebay if o['customer_id'] is not None}
        repeat = sum(1 for customer in ids if self.first_order_day[customer] < start)
        return {'buyers': len(ids), 'repeatBuyers': repeat, 'newBuyers': len(ids) - repeat,
                'missingBuyerOrders': sum(1 for o in ebay if o['customer_id'] is None),
                'repeatBuyerRate': ratio(Decimal(repeat), len(ids))}

    def categories(self, orders):
        """Sales by root category (a subcategory's parent, or the category itself)."""
        rows = {}
        for line in self.lines_of(orders):
            name = line['parent_category_name'] or line['category_name']
            row = rows.setdefault(name, {'name': name, 'revenue': ZERO, 'unitsSold': 0, 'merchandise': ZERO})
            revenue = self.line_revenue(line)
            row['revenue'] = None if revenue is None or row['revenue'] is None else row['revenue'] + revenue
            row['unitsSold'] += line['quantity']
            row['merchandise'] += line['quantity'] * line['unit_price'] - line['discount_amount']
        return [{
            'name': row['name'], 'revenue': row['revenue'], 'unitsSold': row['unitsSold'],
            'asp': ratio(row['merchandise'], row['unitsSold']),
            # No cost-of-goods data: margin cannot be calculated (DATABASE_SPEC §6).
            'cost': None, 'margin': None, 'marginPct': None,
        } for row in rows.values()]

    def subcategory_revenue(self, orders):
        """Revenue per (category, subcategory); products filed directly under a
        root category have no subcategory and are not included."""
        totals = {}
        for line in self.lines_of(orders):
            if not line['parent_category_name']:
                continue
            key = (line['parent_category_name'], line['category_name'])
            revenue = self.line_revenue(line)
            totals[key] = None if revenue is None or totals.get(key, ZERO) is None else totals.get(key, ZERO) + revenue
        return totals

    def listings_created(self, start, end):
        return sum(self.listings_by_day.get(start + timedelta(days=i), 0) for i in range((end - start).days))

    def warnings(self, start, end, orders):
        notes = []
        excluded = sorted(set().union(*(self.excluded_by_day.get(start + timedelta(days=i), set())
                                        for i in range((end - start).days))))
        if excluded:
            notes.append('Orders with unapproved statuses are excluded: ' + ', '.join(excluded))
        if any(not self.lines[o['order_id']] for o in orders):
            notes.append('Some orders have no items, so revenue totals are unavailable.')
        return notes

    def metadata(self, start, end, orders):
        return {
            'dataMode': self.snapshot.data_mode,
            'reportingTimezone': self.config.reporting_timezone,
            'revenueDefinition': self.config.revenue_definition,
            'warnings': self.warnings(start, end, orders),
        }


# ---------------------------------------------------------------- dashboard API

def daily_report(data: ReportData, selected: date) -> dict:
    if selected >= data.today:
        raise ReportError('Daily reports are available through yesterday.')
    end = selected + timedelta(days=1)
    orders = data.orders_between(selected, end)
    channels = data.channels(orders)
    return {
        'date': selected.isoformat(),
        'channels': channels,
        # Team decision: a marketplace without buyer identity stays null on its
        # own row but counts as 0 in the total, so the total is identified
        # (in practice eBay) customers.
        'totals': {'revenue': data.revenue(orders), 'orders': len(orders),
                   'customers': sum(c['customers'] or 0 for c in channels)},
        **data.metadata(selected, end, orders),
    }


def _month_window(data, month_start):
    if month_start >= data.today:
        raise ReportError('Choose a month that has at least one completed day.')
    calendar_end = add_months(month_start, 1)
    end = min(calendar_end, data.today)
    return end, end < calendar_end


def _prior_year_window(start, end, partial):
    """Same month a year earlier; a month in progress compares the same number of days."""
    prior_start = start.replace(year=start.year - 1)
    prior_full_end = add_months(prior_start, 1)
    if not partial:
        return prior_start, prior_full_end
    return prior_start, min(prior_start + (end - start), prior_full_end)


def monthly_figures(data: ReportData, month_start: date) -> dict:
    """Core monthly figures, without month-over-month deltas or the watch list."""
    end, partial = _month_window(data, month_start)
    orders = data.orders_between(month_start, end)
    summary = data.summary(orders)
    lines = data.lines_of(orders)
    prior_start, prior_end = _prior_year_window(month_start, end, partial)
    prior_revenue = data.revenue(data.orders_between(prior_start, prior_end))
    buyers = data.ebay_buyers(orders, month_start)
    kpis = {
        'revenue': summary['revenue'],
        'revenueGrowthYoY': change(summary['revenue'], prior_revenue),
        'grossMarginPct': None, 'netMarginPct': None,
        'unitsSold': summary['units'],
        'avgSellingPrice': summary['average_selling_price'],
        'medianSalePrice': median(line['unit_price'] for line in lines) if lines else None,
        'listingsCreated': data.listings_created(month_start, end),
        'buyers': buyers['buyers'], 'newBuyers': buyers['newBuyers'],
        'repeatBuyerRate': buyers['repeatBuyerRate'], 'satisfaction': None,
    }
    return {
        'month': month_start.strftime('%Y-%m'), 'start': month_start, 'end': end, 'isPartial': partial,
        'orders': orders, 'summary': summary, 'priorYearRevenue': prior_revenue, 'buyers': buyers,
        'kpis': kpis,
    }


def kpi_deltas(current: dict, previous: dict, partial: bool) -> dict:
    deltas = {}
    for key, value in current['kpis'].items():
        prior = previous['kpis'].get(key)
        delta = None
        if value is not None and prior is not None and not (partial and key in ADDITIVE_KPIS):
            if key in POINT_KPIS:
                delta = {'kind': 'points', 'value': value - prior}
            elif (relative := change(value, prior)) is not None:
                delta = {'kind': 'relative', 'value': relative}
        deltas[key] = delta
    return deltas


def watch_items(data: ReportData, current: dict, previous: dict):
    """Subcategories whose revenue fell past the watch threshold. None when the
    revenue definition cannot be split by item; [] for a month in progress."""
    if data.config.revenue_metric == 'transaction_revenue':
        return None
    if current['isPartial']:
        return []
    now = data.subcategory_revenue(current['orders'])
    before = data.subcategory_revenue(previous['orders'])
    flagged = []
    for (category, item), prior in before.items():
        revenue = now.get((category, item), ZERO)
        drop = change(revenue, prior)
        if prior is None or drop is None or prior < WATCH_MIN_PRIOR_REVENUE or drop > WATCH_DROP_THRESHOLD:
            continue
        flagged.append({
            'id': f'{category}::{item}', 'item': item, 'category': category,
            'change': drop, 'revenue': revenue, 'previousRevenue': prior,
            'message': f'{item} sales in the {category} category have gone down by '
                       f'{abs(drop) * 100:.1f}% since last month',
        })
    flagged.sort(key=lambda row: row['previousRevenue'] - row['revenue'], reverse=True)
    return flagged


def monthly_report(data: ReportData, month: str) -> dict:
    month_start = parse_month(month)
    current = monthly_figures(data, month_start)
    previous = monthly_figures(data, add_months(month_start, -1))
    start, end, orders = current['start'], current['end'], current['orders']
    daily = []
    cursor = start
    while cursor < end:
        day_orders = data.orders_between(cursor, cursor + timedelta(days=1))
        daily.append({'date': cursor.isoformat(),
                      'channels': [{'id': c['id'], 'revenue': c['revenue']} for c in data.channels(day_orders)]})
        cursor += timedelta(days=1)
    kpis = current['kpis']
    return {
        'month': current['month'], 'previousMonth': previous['month'],
        'isPartial': current['isPartial'], 'through': (end - timedelta(days=1)).isoformat(),
        'daysReported': (end - start).days,
        'channels': data.channels(orders),
        'daily': daily,
        'financial': {'revenue': kpis['revenue'], 'revenuePriorYear': current['priorYearRevenue'],
                      'cogs': None, 'operatingExpenses': None},
        'sales': {'unitsSold': kpis['unitsSold'], 'medianSalePrice': kpis['medianSalePrice']},
        'listings': {'created': kpis['listingsCreated']},
        'categories': data.categories(orders),
        'customers': {**current['buyers'], 'satisfaction': None,
                      'scope': 'Identified eBay buyers only; Amazon and ShopGoodwill do not provide buyer identity.'},
        'kpis': kpis,
        'kpiDeltas': kpi_deltas(current, previous, current['isPartial']),
        'watchItems': watch_items(data, current, previous),
        'unavailableMetrics': UNAVAILABLE_METRICS,
        **data.metadata(start, end, orders),
    }


def monthly_history(data: ReportData, month: str, months: int) -> list[dict]:
    if not 1 <= months <= 36:
        raise ReportError('months must be between 1 and 36.')
    last = parse_month(month)
    rows = []
    for offset in range(1 - months, 1):
        start = add_months(last, offset)
        if start >= data.today:
            continue
        figures = monthly_figures(data, start)
        rows.append({
            'month': figures['month'], 'revenue': figures['kpis']['revenue'],
            'revenuePriorYear': figures['priorYearRevenue'], 'growth': figures['kpis']['revenueGrowthYoY'],
            'buyers': figures['buyers']['buyers'], 'newBuyers': figures['buyers']['newBuyers'],
            'repeatBuyers': figures['buyers']['repeatBuyers'],
        })
    return rows


# ---------------------------------------------------------------- JSON boundary

def to_json(value):
    """Decimals become numbers; dates become ISO strings."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json(v) for v in value]
    return value
