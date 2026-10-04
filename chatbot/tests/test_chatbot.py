"""Chatbot tests (standard library unittest). From chatbot/:
    .venv/bin/python -m unittest discover -s tests -v

The agent tests use a scripted stand-in for Claude, so they make no API calls.
Database tests use CHATBOT_DATABASE_URL and are skipped if it is unreachable.
"""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from app import agent, config  # noqa: E402
from app.database import QueryRejected, describe_schema, run_query, validate_select  # noqa: E402
from app.verify import numbers_in_answer, unsupported_numbers  # noqa: E402


class SqlGuard(unittest.TestCase):
    def test_accepts_single_select_and_with(self):
        self.assertEqual(validate_select("SELECT 1;"), "SELECT 1")
        validate_select("WITH t AS (SELECT 1 AS x) SELECT x FROM t")
        validate_select("select status from listing where status = 'SOLD'")

    def test_words_inside_string_literals_are_fine(self):
        validate_select("SELECT COUNT(*) FROM review WHERE review_text ILIKE '%update; delete%'")

    def test_rejects_writes_and_tricks(self):
        for sql in ["DELETE FROM review", "UPDATE listing SET status = 'SOLD'", "DROP TABLE source",
                    "SELECT 1; DELETE FROM review", "SELECT 1 -- comment", "SELECT /* x */ 1",
                    "WITH d AS (DELETE FROM review RETURNING *) SELECT * FROM d", "SET ROLE postgres",
                    "SELECT pg_sleep(10)", "COPY source TO '/tmp/x'", "", "   "]:
            with self.assertRaises(QueryRejected, msg=sql):
                validate_select(sql)


def source(columns, rows, sql="SELECT ..."):
    return {"sql": sql, "columns": columns, "rows": rows, "row_count": len(rows), "truncated": False}


class NumberCheck(unittest.TestCase):
    def test_formatted_values_match_results(self):
        sources = [source(["revenue", "asp", "share"], [["1797058.78", "41.1700", "30.69"]])]
        answer = "Revenue was $1,797,058.78 with an ASP of $41.17; ShopGoodwill had 30.7% of sales."
        self.assertEqual(unsupported_numbers(answer, sources), [])

    def test_ratio_shown_as_percentage(self):
        self.assertEqual(unsupported_numbers("Repeat rate is 30.7%.", [source(["r"], [["0.3069"]])]), [])

    def test_invented_number_is_flagged(self):
        sources = [source(["orders"], [[26493]])]
        self.assertEqual(unsupported_numbers("There were 26,493 orders, up 12.5% from last year.", sources),
                         ["12.5%"])

    def test_numbers_without_any_query_are_flagged(self):
        self.assertEqual(unsupported_numbers("Revenue was $500.00.", []), ["$500.00"])

    def test_question_dates_row_counts_and_list_numbering_are_allowed(self):
        sources = [source(["day", "orders"], [["2026-10-03", 44], ["2026-10-02", 33]])]
        answer = "1. Oct 3: 44 orders\n2. Oct 2: 33 orders\nThose are the 2 days you asked about in 2026."
        self.assertEqual(unsupported_numbers(answer, sources, question="Orders for the last 2 days?"), [])

    def test_list_markers_are_not_numbers(self):
        self.assertEqual([t for t, _ in numbers_in_answer("1. First\n2) Second")], [])


# ---------------------------------------------------------------- agent loop with a scripted Claude

def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_block(query, tool_id="t1"):
    return SimpleNamespace(type="tool_use", id=tool_id, name="run_sql", input={"query": query, "purpose": "test"})


def reply(stop_reason, *blocks):
    return SimpleNamespace(stop_reason=stop_reason, content=list(blocks))


class ScriptedClaude:
    """Returns the scripted responses in order and records each request."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        # Snapshot the conversation: the agent keeps appending to the same list.
        self.requests.append(dict(kwargs, messages=list(kwargs["messages"])))
        return self.responses.pop(0)


def fake_runner(results):
    def run(query):
        return dict(results[query], sql=query)
    return run


QUESTION = [{"role": "user", "content": "How many orders are there?"}]
COUNT_SQL = "SELECT COUNT(*) AS orders FROM sales_order"
COUNT_RESULT = {COUNT_SQL: {"columns": ["orders"], "rows": [[26537]], "row_count": 1, "truncated": False}}


class AgentLoop(unittest.TestCase):
    def test_answer_built_from_query_is_verified_with_sources(self):
        claude = ScriptedClaude(reply("tool_use", tool_block(COUNT_SQL)),
                                reply("end_turn", text_block("There are 26,537 orders.")))
        result = agent.answer_question(QUESTION, "schema", client=claude, query_runner=fake_runner(COUNT_RESULT))
        self.assertTrue(result.verified)
        self.assertEqual(result.answer, "There are 26,537 orders.")
        self.assertEqual(result.sources[0]["sql"], COUNT_SQL)
        # The tool result sent back to Claude carries the real rows.
        tool_result = claude.requests[1]["messages"][-1]["content"][0]
        self.assertEqual(json.loads(tool_result["content"])["rows"], [[26537]])

    def test_request_uses_read_only_tool_and_fallbacks(self):
        claude = ScriptedClaude(reply("end_turn", text_block("I can only answer from the database.")))
        agent.answer_question(QUESTION, "schema", client=claude, query_runner=fake_runner({}))
        request = claude.requests[0]
        self.assertEqual(request["model"], config.MODEL)
        self.assertEqual([t["name"] for t in request["tools"]], ["run_sql"])
        self.assertEqual(request["fallbacks"], "default")
        self.assertIn("server-side-fallback-2026-07-01", request["betas"])

    def test_unsupported_number_triggers_one_correction(self):
        claude = ScriptedClaude(reply("tool_use", tool_block(COUNT_SQL)),
                                reply("end_turn", text_block("There are 26,537 orders, about 9,000 a year.")),
                                reply("end_turn", text_block("There are 26,537 orders.")))
        result = agent.answer_question(QUESTION, "schema", client=claude, query_runner=fake_runner(COUNT_RESULT))
        self.assertTrue(result.verified)
        correction = claude.requests[2]["messages"][-1]["content"]
        self.assertIn("9,000", correction)

    def test_answer_withheld_when_correction_also_fails(self):
        claude = ScriptedClaude(reply("tool_use", tool_block(COUNT_SQL)),
                                reply("end_turn", text_block("About 9,000 a year.")),
                                reply("end_turn", text_block("Still about 9,000 a year.")))
        result = agent.answer_question(QUESTION, "schema", client=claude, query_runner=fake_runner(COUNT_RESULT))
        self.assertFalse(result.verified)
        self.assertNotIn("9,000", result.answer)
        self.assertEqual(result.unsupported, ["9,000"])

    def test_query_errors_are_returned_to_claude(self):
        bad = "SELECT nope FROM sales_order"
        runner = fake_runner({bad: {"error": 'column "nope" does not exist'}, **COUNT_RESULT})
        claude = ScriptedClaude(reply("tool_use", tool_block(bad)),
                                reply("tool_use", tool_block(COUNT_SQL, "t2")),
                                reply("end_turn", text_block("There are 26,537 orders.")))
        result = agent.answer_question(QUESTION, "schema", client=claude, query_runner=runner)
        self.assertTrue(result.verified)
        error_result = claude.requests[1]["messages"][-1]["content"][0]
        self.assertTrue(error_result["is_error"])
        self.assertIn("does not exist", error_result["content"])

    def test_refusal_is_reported(self):
        claude = ScriptedClaude(reply("refusal"))
        result = agent.answer_question(QUESTION, "schema", client=claude, query_runner=fake_runner({}))
        self.assertFalse(result.verified)


# ---------------------------------------------------------------- real database (read-only role)

def database_available():
    try:
        with psycopg.connect(config.DATABASE_URL, connect_timeout=3):
            return True
    except psycopg.Error:
        return False


@unittest.skipUnless(database_available(), "chatbot database not reachable")
class ReadOnlyDatabase(unittest.TestCase):
    def test_select_returns_rows(self):
        result = run_query("SELECT name FROM source ORDER BY name")
        self.assertEqual(result["columns"], ["name"])
        self.assertEqual(sorted(r[0] for r in result["rows"]), ["Amazon", "ShopGoodwill", "eBay"])

    def test_money_is_exact_text(self):
        result = run_query("SELECT ROUND(SUM(merchandise_revenue), 2) AS total FROM sales_order_mv")
        self.assertRegex(result["rows"][0][0], r"^\d+\.\d{2}$")

    def test_personal_columns_are_denied(self):
        self.assertIn("permission denied", run_query("SELECT first_name FROM customer")["error"])

    def test_writes_fail_even_if_the_guard_were_bypassed(self):
        with psycopg.connect(config.DATABASE_URL) as conn:
            with self.assertRaises(psycopg.Error):
                conn.execute("DELETE FROM review")

    def test_row_limit(self):
        result = run_query("SELECT order_id FROM sales_order", max_rows=5)
        self.assertEqual(result["row_count"], 5)
        self.assertTrue(result["truncated"])

    def test_schema_lists_only_readable_columns(self):
        schema = describe_schema()
        self.assertIn("sales_order_mv(", schema)
        self.assertIn("state", schema)
        self.assertNotIn("first_name", schema)
        self.assertNotIn("zipcode", schema)


if __name__ == "__main__":
    unittest.main()
