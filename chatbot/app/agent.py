"""Answer questions from the database with Claude and a read-only SQL tool.

Claude may only state facts it read from `run_sql` results in this
conversation. After Claude answers, verify.unsupported_numbers() checks every
figure against those results. An answer that still fails after a correction
attempt is withheld rather than shown.
"""

import json
from dataclasses import dataclass, field

import anthropic

from . import config
from .database import run_query
from .verify import unsupported_numbers

DOMAIN_NOTES = """\
Business context
- Goodwill Michiana sells donated items online. Marketplaces are rows in `source` (Amazon, eBay, ShopGoodwill).
- The data is synthetic test data from Nov 2023 to early Oct 2026. Find the actual range with MIN/MAX(ordered_at).

How the tables relate
- sales_order (one per marketplace order) -> order_item (one per item sold) -> listing (one marketplace sale
  attempt) -> product (the physical item, by sku_number) -> category. category.parent_category_id points to
  the root category (e.g. Home -> Furniture); products may also sit directly in a root category.
- A product listed more than once was relisted (e.g. unsold on ShopGoodwill, relisted on eBay).
- listing.status is ACTIVE, SOLD, ENDED_UNSOLD or CANCELLED; ACTIVE listings have ended_at NULL.
- Days to sell = sales_order.ordered_at - listing.listed_at.
- ingestion_batch records which source file each row came from.

Money (all stored as non-negative amounts)
- sales_order_mv has one row per order (join on order_id):
  merchandise_revenue = item prices after discounts, before refunds;
  refund_impact = minus the refunded amount;
  total_transaction_revenue = merchandise + refunds + buyer shipping - carrier cost - marketplace fees;
  customer_transaction_total = what the buyer paid, including tax.
- Unless the user asks otherwise, "revenue" means SUM(merchandise_revenue). Say which definition you used.
- Average selling price = SUM(quantity * unit_price - discount_amount) / SUM(quantity) over order_item.
- sales_order.status is COMPLETED, SHIPPED or REFUNDED (every line fully refunded).

Customers
- Only eBay provides buyer identity; Amazon and ShopGoodwill orders have customer_id NULL.
- Buyer counts and repeat buyers therefore cover eBay only - say so. Repeat buyer = customer with 2+ orders.
- Names, usernames, cities and zip codes are not accessible; state and country are.

Reviews
- review.rating is on each marketplace's own scale: eBay feedback 1 positive / 0 neutral / -1 negative,
  Amazon 1-5 stars. Never average or compare ratings across marketplaces.

Not in the database
- Labor hours, employees, donation intake, unlisted backlog, cost of goods, profit or margin.
  If asked, say the database does not record it.

Dates
- Queries run with the session time zone set to America/Indiana/Indianapolis (Goodwill's local time),
  so ordered_at::date is the local business date.
"""

RULES = """\
You answer questions about Goodwill Michiana's e-commerce data. You can only learn facts by calling run_sql.

Rules - follow all of them:
1. Use only data returned by run_sql in this conversation. Never use outside knowledge or assumptions about
   Goodwill's figures. If the results do not answer the question, say so plainly and say what is missing.
2. Compute every number you will state in SQL: totals, counts, averages, percentages (as 0-100 values),
   differences and rankings. Use ROUND(x, 2) for money and ROUND(x, 1) for percentages. Do not do arithmetic
   yourself. Copy each number exactly as returned; you may add $ signs and thousands separators, but do not
   abbreviate (write 1,797,058.78, not 1.8 million).
3. Run as many queries as you need. If a query errors, read the error, fix the SQL and try again.
4. Briefly state the definition or filters behind each figure (for example "revenue = merchandise after
   discounts, Sept 2026, all marketplaces").
5. Keep answers short: a direct answer first, then a few bullet points if useful. Plain text only - no
   markdown tables or headings.
6. Do not reveal or guess personal information about customers.
"""

RUN_SQL_TOOL = {
    "name": "run_sql",
    "description": (
        "Run one read-only PostgreSQL SELECT (or WITH ... SELECT) against the Goodwill database and return the "
        f"columns and up to {config.MAX_RESULT_ROWS} rows as JSON. Use aggregates and LIMIT to keep results small. "
        "Only SELECT is allowed: no comments, no multiple statements, no writes. Errors are returned as text."
    ),
    "strict": True,
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "A single PostgreSQL SELECT statement."},
            "purpose": {"type": "string", "description": "One short sentence: what this query is for."},
        },
        "required": ["query", "purpose"],
        "additionalProperties": False,
    },
}


@dataclass
class ChatResult:
    answer: str
    verified: bool
    sources: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)


def build_system_prompt(schema_text):
    return f"{RULES}\nDatabase schema (tables and the columns you may read):\n{schema_text}\n\n{DOMAIN_NOTES}"


def _text_of(response):
    return "\n".join(b.text for b in response.content if b.type == "text").strip()


def answer_question(history, schema_text, client=None, query_runner=run_query):
    """history: [{"role": "user"|"assistant", "content": str}, ...] ending with the user's question."""
    client = client or anthropic.Anthropic()
    question = history[-1]["content"]
    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    system = [{"type": "text", "text": build_system_prompt(schema_text), "cache_control": {"type": "ephemeral"}}]
    sources = []
    retries_left = config.MAX_VERIFICATION_RETRIES

    for _ in range(config.MAX_TOOL_ROUNDS):
        response = client.beta.messages.create(
            model=config.MODEL,
            max_tokens=16000,
            system=system,
            tools=[RUN_SQL_TOOL],
            messages=messages,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            # On a safety decline, re-run on Anthropic's recommended fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

        if response.stop_reason == "refusal":
            return ChatResult("I can't help with that request.", verified=False, sources=sources)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                if block.name != "run_sql" or not isinstance(block.input, dict) or "query" not in block.input:
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": "Unknown tool or missing 'query'. Call run_sql with a query."})
                    continue
                result = query_runner(block.input["query"])
                result["purpose"] = block.input.get("purpose", "")
                sources.append(result)
                if "error" in result:
                    results.append({"type": "tool_result", "tool_use_id": block.id, "is_error": True,
                                    "content": f"Query failed: {result['error']}"})
                else:
                    payload = {k: result[k] for k in ("columns", "rows", "row_count", "truncated")}
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": json.dumps(payload)})
            messages.append({"role": "user", "content": results})
            continue

        if response.stop_reason == "max_tokens":
            return ChatResult("The answer was too long to complete. Try a narrower question.",
                              verified=False, sources=sources)

        # end_turn (or stop_sequence): check the answer against the query results.
        answer = _text_of(response)
        successful = [s for s in sources if "rows" in s]
        unsupported = unsupported_numbers(answer, successful, question)
        if not unsupported:
            return ChatResult(answer, verified=True, sources=sources)
        if retries_left <= 0:
            return ChatResult(
                "I couldn't verify every figure in my answer against the database, so I'm not showing it. "
                "Try rephrasing the question or asking about one figure at a time.",
                verified=False, sources=sources, unsupported=unsupported)
        retries_left -= 1
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": (
            "Automatic check: these numbers in your answer do not appear in any query result: "
            + ", ".join(unsupported)
            + ". Compute each of them with run_sql (or remove it), then give the corrected final answer.")})

    return ChatResult("I couldn't finish answering within the allowed number of steps. "
                      "Try a more specific question.", verified=False, sources=sources)
