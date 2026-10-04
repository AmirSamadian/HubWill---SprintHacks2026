"""Frontend report contract and shared business calculations over stored facts.

Money stays Decimal until the dashboard JSON boundary. No fixture fallback,
database writes, or allocation of order-level fees to products/categories.
"""

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from statistics import median
from zoneinfo import ZoneInfo

from .config import settings

INCLUDED_STATUSES = {'COMPLETED', 'SHIPPED', 'REFUNDED'}
REVENUE_DEFINITION = (
    'Transaction revenue: merchandise after discounts and refunds + buyer shipping '
    '− carrier cost − fees; tax excluded. Refunds use the original order date.'
)
UNAVAILABLE = [
    'Gross/net/category margins need cost-of-goods and expense data.',
    'Customer satisfaction needs an agreed rating scale.',
    'Item-type watch list needs an agreed item taxonomy.',
    'Category transaction revenue needs an agreed allocation of order shipping and fees.',
]
ZERO = Decimal(0)


def add_months(day, offset):
    index = day.year * 12 + day.month - 1 + offset
    year, month = divmod(index, 12)
    return date(year, month + 1, 1)


def parse_month(value):
    try:
        day = date.fromisoformat(value + '-01')
        if len(value) != 7 or not 3 <= day.year <= 9997:
            raise ValueError
        return day
    except ValueError:
        raise ValueError('Use a month in YYYY-MM format, between years 0003 and 9997.') from None


def ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator else None


def growth(current, previous):
    return ratio(current - previous, previous) if current is not None and previous is not None else None


def sum_known(values):
    values = list(values)
    return None if any(value is None for value in values) else sum(values, ZERO)


def report_calendar(config=None, today=None):
    config = config or settings()
    today = today or datetime.now(ZoneInfo(config.reporting_timezone)).date()
    latest = today - timedelta(days=1)
    return {
        'latestDate': latest.isoformat(),
        'months': [add_months(latest.replace(day=1), -i).strftime('%Y-%m') for i in range(24)],
        'defaultMonth': add_months(today.replace(day=1), -1).strftime('%Y-%m'),
        'reportingTimezone': config.reporting_timezone,
    }


class DashboardService:
    def __init__(self, repository, config=None, today=None):
        self.config = config or settings()
        self.today = today or datetime.now(ZoneInfo(self.config.reporting_timezone)).date()
        self.snapshot = repository.snapshot(self.config.reporting_timezone)
        self.sources = self.snapshot.sources
        self.orders = [o for o in self.snapshot.orders if o['status'] in INCLUDED_STATUSES]
        self.lines = defaultdict(list)
        for line in self.snapshot.lines:
            self.lines[line['order_id']].append(line)
        self.ebay_ids = {s['source_id'] for s in self.sources if s['name'].casefold() == 'ebay'}

    def metadata(self, start, end):
        warnings = []
        unknown = sorted({o['status'] for o in self.snapshot.orders
                          if start <= o['day'] < end and o['status'] not in INCLUDED_STATUSES})
        if unknown:
            warnings.append('Excluded unapproved order statuses: ' + ', '.join(unknown))
        if any(not self.lines[o['order_id']] for o in self.select(start, end)):
            warnings.append('Orders without items make revenue and selling-price totals unavailable.')
        return {
            'dataMode': 'database', 'reportingTimezone': self.config.reporting_timezone,
            'revenueDefinition': REVENUE_DEFINITION,
            'warnings': warnings,
            'notice': 'Stored records only; zero means no matching stored sales, not verified import completeness.',
        }

    def select(self, start, end):
        return [o for o in self.orders if start <= o['day'] < end]

    @staticmethod
    def revenue(orders):
        return sum_known(o['total_transaction_revenue'] for o in orders)

    def summary(self, orders):
        lines = [line for o in orders for line in self.lines[o['order_id']]]
        units = sum(line['quantity'] for line in lines)
        merchandise = sum_known(o['merchandise_revenue'] for o in orders)
        return {
            'revenue': self.revenue(orders), 'transactions': len(orders), 'units_sold': units,
            'average_selling_price': ratio(merchandise, units),
        }

    def channels(self, orders):
        total = self.revenue(orders)
        result = []
        for source in self.sources:
            subset = [o for o in orders if o['source_id'] == source['source_id']]
            known = source['name'].casefold()
            channel_id = known if known in {'amazon', 'ebay', 'shopgoodwill'} else f"source-{source['source_id']}"
            customers = (None if any(o['customer_id'] is None for o in subset)
                         else len({o['customer_id'] for o in subset}))
            revenue = self.revenue(subset)
            result.append({
                'id': channel_id, 'name': source['name'], 'revenue': revenue,
                'customers': customers, 'orders': len(subset), 'share': ratio(revenue, total),
            })
        return result

    def daily(self, selected):
        if selected >= self.today:
            raise ValueError('Daily reports are available through yesterday in the reporting timezone.')
        end = selected + timedelta(days=1)
        orders = self.select(selected, end)
        channels = self.channels(orders)
        return {
            'date': selected.isoformat(), 'channels': channels,
            'totals': {'revenue': self.revenue(orders),
                       'customers': sum_known(c['customers'] for c in channels)},
            **self.metadata(selected, end),
        }

    def buyers(self, orders, start):
        ebay = [o for o in orders if o['source_id'] in self.ebay_ids]
        ids = {o['customer_id'] for o in ebay if o['customer_id'] is not None}
        prior = {o['customer_id'] for o in self.orders
                 if o['source_id'] in self.ebay_ids and o['day'] < start and o['customer_id'] is not None}
        repeat = len(ids & prior)
        return {
            'scope': 'Identified eBay buyers only; first-time means first in stored order history.',
            'buyers': len(ids), 'repeatBuyers': repeat, 'newBuyers': len(ids) - repeat,
            'missingBuyerOrders': sum(o['customer_id'] is None for o in ebay),
            'repeatBuyerRate': ratio(Decimal(repeat), len(ids)), 'satisfaction': None,
            'newBuyerShare': ratio(Decimal(len(ids) - repeat), len(ids)),
        }

    def monthly(self, month, include_deltas=True):
        start = parse_month(month)
        if start >= self.today:
            raise ValueError('Choose a month containing at least one completed reporting day.')
        calendar_end = add_months(start, 1)
        end = min(calendar_end, self.today)
        partial = end < calendar_end
        orders = self.select(start, end)
        summary = self.summary(orders)
        lines = [line for o in orders for line in self.lines[o['order_id']]]
        prior_start = start.replace(year=start.year - 1)
        prior_end = (prior_start + timedelta(days=min((end - start).days,
                      calendar.monthrange(prior_start.year, prior_start.month)[1]))
                     if partial else add_months(prior_start, 1))
        prior_revenue = self.revenue(self.select(prior_start, prior_end))
        customers = self.buyers(orders, start)
        categories = {}
        for line in lines:
            row = categories.setdefault(line['category_id'], {
                'categoryId': str(line['category_id']), 'name': line['category_name'],
                'unitsSold': 0, 'merchandise': ZERO,
            })
            row['unitsSold'] += line['quantity']
            row['merchandise'] += line['quantity'] * line['unit_price'] - line['discount_amount']
        category_rows = [{
            'categoryId': row['categoryId'], 'name': row['name'], 'unitsSold': row['unitsSold'],
            'revenue': None, 'cost': None, 'margin': None, 'marginPct': None,
            'asp': ratio(row['merchandise'], row['unitsSold']),
        } for row in categories.values()]
        kpis = {
            'revenue': summary['revenue'], 'revenueGrowthYoY': growth(summary['revenue'], prior_revenue),
            'grossMarginPct': None, 'netMarginPct': None, 'unitsSold': summary['units_sold'],
            'avgSellingPrice': summary['average_selling_price'],
            'medianSalePrice': median([line['unit_price'] for line in lines]) if lines else None,
            'listingsCreated': sum(start <= l['day'] < end for l in self.snapshot.listings),
            'buyers': customers['buyers'], 'newBuyers': customers['newBuyers'],
            'repeatBuyerRate': customers['repeatBuyerRate'], 'satisfaction': None,
        }
        daily = []
        cursor = start
        while cursor < end:
            daily.append({'date': cursor.isoformat(), 'channels': self.channels(self.select(cursor, cursor + timedelta(days=1)))})
            cursor += timedelta(days=1)
        result = {
            'month': month, 'isPartial': partial, 'through': (end - timedelta(days=1)).isoformat(),
            'daysReported': (end - start).days, 'channels': self.channels(orders), 'daily': daily,
            'financial': {'revenue': summary['revenue'], 'revenuePriorYear': prior_revenue,
                          'cogs': None, 'operatingExpenses': None},
            'sales': {'unitsSold': kpis['unitsSold'], 'medianSalePrice': kpis['medianSalePrice']},
            'listings': {'created': kpis['listingsCreated']}, 'categories': category_rows,
            'topCategories': {'revenue': [], 'margin': []}, 'items': [], 'watchItems': None,
            'customers': customers, 'kpis': kpis, 'kpiDeltas': {},
            'unavailableMetrics': UNAVAILABLE, **self.metadata(start, end),
        }
        if include_deltas:
            previous = self.monthly(add_months(start, -1).strftime('%Y-%m'), include_deltas=False)
            additive = {'revenue', 'unitsSold', 'listingsCreated', 'buyers', 'newBuyers'}
            points = {'revenueGrowthYoY', 'grossMarginPct', 'netMarginPct', 'repeatBuyerRate'}
            for key, current in kpis.items():
                prior = previous['kpis'][key]
                delta = None
                if current is not None and prior is not None and not (partial and key in additive):
                    value = current - prior if key in points else growth(current, prior)
                    if value is not None:
                        delta = {'kind': 'points' if key in points else 'relative', 'value': value}
                result['kpiDeltas'][key] = delta
        return result

    def history(self, month, months):
        start = parse_month(month)
        rows = []
        for offset in range(1 - months, 1):
            report = self.monthly(add_months(start, offset).strftime('%Y-%m'), include_deltas=False)
            rows.append({
                'month': report['month'], 'revenue': report['financial']['revenue'],
                'revenuePriorYear': report['financial']['revenuePriorYear'],
                'growth': report['kpis']['revenueGrowthYoY'],
                **{key: report['customers'][key] for key in ('buyers', 'newBuyers', 'repeatBuyers')},
            })
        return rows
