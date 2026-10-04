// ============================================================================
// TEMPORARY PLACEHOLDER DATA
//
// Every number in this file is a stand-in so the dashboard has something to
// draw before the database is connected. Nothing here is real. Each export is
// marked with the query that should replace it; once the database is wired up
// in ../api/index.js, this file can be deleted.
//
// Marketplace ids ('shopgoodwill', 'amazon', 'ebay') must match
// src/config/channels.js.
// ============================================================================

// ---------------------------------------------------------------------------
// DAILY TAB
// ---------------------------------------------------------------------------

// TODO(database): revenue and customer count per marketplace for the selected day.
export const TEMP_DAILY_CHANNELS = [
  { id: 'shopgoodwill', name: 'ShopGoodwill', revenue: 4071.42, customers: 77 },
  { id: 'amazon', name: 'Amazon', revenue: 1583.47, customers: 23 },
  { id: 'ebay', name: 'eBay', revenue: 1800.49, customers: 33 },
]

// ---------------------------------------------------------------------------
// MONTHLY TAB — selected month
// ---------------------------------------------------------------------------

// TODO(database): month totals per marketplace. sessions = listing views
// (used for conversion rate).
export const TEMP_MONTH_CHANNELS = [
  { id: 'shopgoodwill', name: 'ShopGoodwill', revenue: 121286.23, orders: 2647, customers: 2422, sessions: 87007 },
  { id: 'amazon', name: 'Amazon', revenue: 44712.43, orders: 623, customers: 575, sessions: 6587 },
  { id: 'ebay', name: 'eBay', revenue: 61417.39, orders: 1065, customers: 975, sessions: 23268 },
]

// TODO(database): revenue per marketplace for each day of the month (day 1 first).
export const TEMP_MONTH_DAILY_REVENUE = [
  { shopgoodwill: 3376.03, amazon: 1228.68, ebay: 1527.52 },
  { shopgoodwill: 3628.34, amazon: 1587.48, ebay: 1942.25 },
  { shopgoodwill: 4200.38, amazon: 1242.62, ebay: 2127.54 },
  { shopgoodwill: 3587.59, amazon: 1311.32, ebay: 2323.21 },
  { shopgoodwill: 5282.79, amazon: 2071.1, ebay: 2489.22 },
  { shopgoodwill: 5359.56, amazon: 1927.54, ebay: 2427.72 },
  { shopgoodwill: 3650.43, amazon: 1336.68, ebay: 2025.96 },
  { shopgoodwill: 3513.26, amazon: 1623.87, ebay: 1506.08 },
  { shopgoodwill: 3081.63, amazon: 1406.55, ebay: 1863.84 },
  { shopgoodwill: 3594.37, amazon: 1412.96, ebay: 1997 },
  { shopgoodwill: 4493.91, amazon: 1666.72, ebay: 2324.03 },
  { shopgoodwill: 4733.93, amazon: 1400.73, ebay: 2742.44 },
  { shopgoodwill: 4225.49, amazon: 1935.08, ebay: 1813.56 },
  { shopgoodwill: 3615.57, amazon: 1404.84, ebay: 1782.18 },
  { shopgoodwill: 4036.98, amazon: 1532.4, ebay: 1632.48 },
  { shopgoodwill: 3889.48, amazon: 1474.98, ebay: 1655.36 },
  { shopgoodwill: 3830.49, amazon: 1342.08, ebay: 1650.78 },
  { shopgoodwill: 4794.21, amazon: 1314.91, ebay: 1722.91 },
  { shopgoodwill: 4161.71, amazon: 1701.83, ebay: 2669.66 },
  { shopgoodwill: 4415.58, amazon: 1581.12, ebay: 2648.15 },
  { shopgoodwill: 3671.67, amazon: 1203.33, ebay: 1786.42 },
  { shopgoodwill: 3465.99, amazon: 1158.94, ebay: 2125.88 },
  { shopgoodwill: 4007.76, amazon: 1264.2, ebay: 1603.96 },
  { shopgoodwill: 3859.61, amazon: 1415.82, ebay: 2258.46 },
  { shopgoodwill: 4251.18, amazon: 1407.47, ebay: 2285.27 },
  { shopgoodwill: 3900.74, amazon: 1934.93, ebay: 2396.1 },
  { shopgoodwill: 4214.09, amazon: 1948.41, ebay: 1888.51 },
  { shopgoodwill: 4166.3, amazon: 1168.96, ebay: 1980.89 },
  { shopgoodwill: 4470.69, amazon: 1164.43, ebay: 2022.91 },
  { shopgoodwill: 3806.47, amazon: 1542.45, ebay: 2197.1 },
  { shopgoodwill: 3376.03, amazon: 1228.68, ebay: 1527.52 },
]

// TODO(database): revenue, revenue for the same month last year, cost of goods
// sold (marketplace fees, shipping, supplies) and other operating expenses
// (use 0 if not tracked). Net margin = (revenue - cogs - operatingExpenses) / revenue.
export const TEMP_FINANCIAL = { revenue: 227416.05, revenuePriorYear: 176862.66, cogs: 85669.59, operatingExpenses: 70617.61 }

// TODO(database): units sold and the median sale price for the month.
export const TEMP_SALES = { unitsSold: 5524, medianSalePrice: 26.95 }

// TODO(database): sales, cost (fees, shipping, supplies) and units sold per category.
export const TEMP_CATEGORIES = [
  { name: 'Jewelry & Gemstones', revenue: 37857.46, cost: 9218.8, unitsSold: 509 },
  { name: 'Electronics', revenue: 34597.31, cost: 15331.62, unitsSold: 571 },
  { name: 'Clothing', revenue: 19519.87, cost: 8966.01, unitsSold: 766 },
  { name: 'Home', revenue: 19318.72, cost: 8439.7, unitsSold: 633 },
  { name: 'Collectibles', revenue: 19917.66, cost: 5875.41, unitsSold: 489 },
  { name: 'Cameras & Photo', revenue: 18058.18, cost: 5886.66, unitsSold: 186 },
  { name: 'Video Games', revenue: 10661.55, cost: 4180.11, unitsSold: 362 },
  { name: 'Books', revenue: 10830.96, cost: 5567.62, unitsSold: 548 },
  { name: 'Toys & Games', revenue: 13435.15, cost: 5801.83, unitsSold: 493 },
  { name: 'Musical Instruments', revenue: 9147.11, cost: 3053.05, unitsSold: 97 },
  { name: 'Art', revenue: 9119.64, cost: 2429.2, unitsSold: 166 },
  { name: 'Handbags & Accessories', revenue: 7226.12, cost: 2482.18, unitsSold: 150 },
  { name: 'Shoes', revenue: 5830.86, cost: 2794.64, unitsSold: 178 },
  { name: 'Sporting Goods', revenue: 6757.56, cost: 3266.86, unitsSold: 173 },
  { name: 'Kitchen', revenue: 5137.91, cost: 2375.9, unitsSold: 203 },
]

// TODO(database): unique buyers split into first-time and repeat; satisfaction
// rating out of 5; Net Promoter Score (null when not available).
export const TEMP_CUSTOMERS = { buyers: 3454, repeatBuyers: 1062, newBuyers: 2392, satisfaction: 4.77, nps: 49 }

// ---------------------------------------------------------------------------
// MONTHLY TAB — prior month (for month-over-month deltas)
// ---------------------------------------------------------------------------

// TODO(database): the same fields as above, for the month before the selected one.
export const TEMP_PREVIOUS_MONTH = {
  channels: [
    { id: 'shopgoodwill', name: 'ShopGoodwill', revenue: 120113.88, orders: 2611, customers: 2356, sessions: 84770 },
    { id: 'amazon', name: 'Amazon', revenue: 44934.63, orders: 626, customers: 572, sessions: 6623 },
    { id: 'ebay', name: 'eBay', revenue: 59140.39, orders: 1046, customers: 952, sessions: 22249 },
  ],
  financial: { revenue: 224188.9, revenuePriorYear: 179347.32, cogs: 88856.46, operatingExpenses: 72629.02 },
  sales: { unitsSold: 5833, medianSalePrice: 25.41 },
  customers: { buyers: 3357, repeatBuyers: 1055, newBuyers: 2302, satisfaction: 4.7, nps: 46 },
}

// ---------------------------------------------------------------------------
// MONTHLY TAB — trailing 12 months (for trend charts), oldest first
// ---------------------------------------------------------------------------

// TODO(database): per month — revenue, revenue for the same month a year
// earlier, and unique buyers split into first-time and repeat.
export const TEMP_MONTHLY_HISTORY = [
  { revenue: 196375.88, revenuePriorYear: 161855.57, buyers: 2978, newBuyers: 2132, repeatBuyers: 846 },
  { revenue: 223528.53, revenuePriorYear: 179250.56, buyers: 3389, newBuyers: 2400, repeatBuyers: 989 },
  { revenue: 251335.98, revenuePriorYear: 206650.02, buyers: 3703, newBuyers: 2679, repeatBuyers: 1024 },
  { revenue: 189842.15, revenuePriorYear: 154858.52, buyers: 2885, newBuyers: 2019, repeatBuyers: 866 },
  { revenue: 163999.71, revenuePriorYear: 133129.72, buyers: 2468, newBuyers: 1734, repeatBuyers: 734 },
  { revenue: 197034.83, revenuePriorYear: 167222.12, buyers: 2909, newBuyers: 2066, repeatBuyers: 843 },
  { revenue: 202795.88, revenuePriorYear: 164664.59, buyers: 3020, newBuyers: 2080, repeatBuyers: 940 },
  { revenue: 216401.01, revenuePriorYear: 176701.9, buyers: 3263, newBuyers: 2282, repeatBuyers: 981 },
  { revenue: 201568.14, revenuePriorYear: 162044, buyers: 3058, newBuyers: 2103, repeatBuyers: 955 },
  { revenue: 211287.82, revenuePriorYear: 169304.79, buyers: 3100, newBuyers: 2157, repeatBuyers: 943 },
  { revenue: 224188.9, revenuePriorYear: 179347.32, buyers: 3357, newBuyers: 2302, repeatBuyers: 1055 },
  { revenue: 227416.05, revenuePriorYear: 176862.66, buyers: 3454, newBuyers: 2392, repeatBuyers: 1062 },
]
