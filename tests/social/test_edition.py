"""The cloud edition: when the page is rebuilt without the PC, and the gate a built page must pass."""
import contextlib
import datetime as dt
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import story

import social_edition as cloud
import social_feed as feed

DAY = "November 17, 2026"
TODAY = dt.date(2026, 11, 17)
PUBLISH_WEB = '''import re


def _web_html(html):
    html = re.sub(r"<!--private:start-->.*?<!--private:end-->", "", html, flags=re.S)
    html = html.replace("</body>", '<aside class="wl">waitlist</aside></body>', 1)
    return html.replace("<head>", '<head><meta name="robots" content="noindex,nofollow">', 1)
'''


def at(clock: str, day: str = "2026-11-17") -> dt.datetime:
    return dt.datetime.fromisoformat(f"{day}T{clock}:00+07:00")


def stories(count: int) -> list[dict]:
    sections = list(helpers.SECTIONS)
    return [story(number, section=sections[number % len(sections)]) for number in range(1, count + 1)]


def built(count: int = 20, *, updated: str = "10:28", date: str = DAY, markets: bool = True,
          analysis: bool = True, private: bool = False) -> str:
    """A page as the generator writes it, before it is made public."""
    page = helpers.page(stories(count), date=date, updated=updated, markets=markets)
    extra = '<section id="analysis">charts</section>' if analysis else ""
    if private:
        extra += "<!--private:start--><section id=\"portfolio\">MY HOLDINGS</section><!--private:end-->"
    return page.replace("</body>", extra + "</body>", 1)


def public(page: str) -> str:
    scope: dict = {}
    exec(PUBLISH_WEB, scope)
    return scope["_web_html"](page)


def edition(updated: str = "09:00", date: str = DAY) -> dict:
    return feed.parse_edition(helpers.page(stories(12), date=date, updated=updated))


class DecideTest(unittest.TestCase):
    def test_a_fresh_page_is_left_to_the_pc(self):
        build, publish, reason = cloud.decide("auto", edition("09:00"), at("09:25"), True)
        self.assertEqual((build, publish), (False, False))
        self.assertIn("25 minutes ago", reason)

    def test_two_missed_editions_start_a_cloud_build(self):
        self.assertEqual(cloud.decide("auto", edition("09:00"), at("10:19"), True)[:2], (False, False))
        build, publish, reason = cloud.decide("auto", edition("09:00"), at("10:25"), True)
        self.assertEqual((build, publish), (True, True))
        self.assertIn("85 minutes ago", reason)

    def test_yesterdays_page_is_rebuilt_once_the_pc_had_its_chance(self):
        old = edition("22:00", "November 16, 2026")
        self.assertEqual(cloud.decide("auto", old, at("08:05"), True)[:2], (False, False))
        build, publish, reason = cloud.decide("auto", old, at("08:25"), True)
        self.assertEqual((build, publish), (True, True))
        self.assertIn("16 Nov", reason)

    def test_nothing_is_built_at_night(self):
        old = edition("14:00", "November 16, 2026")
        for clock in ("00:10", "07:59", "08:19", "22:31", "23:59"):
            self.assertEqual(cloud.decide("auto", old, at(clock), True)[:2], (False, False), clock)
        for clock in ("08:20", "15:40", "22:30"):
            self.assertEqual(cloud.decide("auto", old, at(clock), True)[:2], (True, True), clock)

    def test_the_time_is_read_in_jakarta_whatever_zone_it_arrives_in(self):
        utc = dt.datetime(2026, 11, 17, 3, 25, tzinfo=dt.timezone.utc)  # 10:25 in Jakarta
        self.assertEqual(cloud.decide("auto", edition("09:00"), utc, True)[:2], (True, True))

    def test_a_page_with_no_readable_time_is_rebuilt(self):
        for unreadable in ({}, {"date": "", "updated": ""}, {"date": "2026-11-17", "updated": ""},
                           {"date": "2026-11-17", "updated": "25:99"}):
            build, publish, reason = cloud.decide("auto", unreadable, at("12:00"), True)
            self.assertEqual((build, publish), (True, True))
            self.assertIn("no readable", reason)

    def test_without_the_key_nothing_is_built_in_any_mode(self):
        for mode in ("auto", "build", "publish"):
            build, publish, reason = cloud.decide(mode, edition("06:00"), at("12:00"), False)
            self.assertEqual((build, publish), (False, False))
            self.assertIn("GENERATOR_DEPLOY_KEY", reason)

    def test_the_hand_modes_and_the_switch(self):
        fresh = edition("11:55")
        self.assertEqual(cloud.decide("build", fresh, at("12:00"), True)[:2], (True, False))
        self.assertEqual(cloud.decide("publish", fresh, at("03:00"), True)[:2], (True, True))
        self.assertEqual(cloud.decide("off", edition("06:00"), at("12:00"), True)[:2], (False, False))
        self.assertEqual(cloud.decide("sometimes", edition("06:00"), at("12:00"), True)[:2], (False, False))


class GateTest(unittest.TestCase):
    def test_a_full_page_of_today_passes(self):
        self.assertEqual(cloud.page_problems(public(built()), public(built(22, updated="08:35")), TODAY), [])
        self.assertEqual(cloud.page_problems(public(built()), None, TODAY), [])

    def test_a_private_section_never_passes(self):
        problems = cloud.page_problems(built(private=True), None, TODAY)
        self.assertTrue(any("private" in problem for problem in problems))
        self.assertTrue(any("public form" in problem for problem in problems))
        self.assertNotIn("MY HOLDINGS", public(built(private=True)))

    def test_a_page_of_another_day_does_not_pass(self):
        problems = cloud.page_problems(public(built(date="November 16, 2026")), None, TODAY)
        self.assertEqual(len(problems), 1)
        self.assertIn("2026-11-16", problems[0])

    def test_a_thin_page_does_not_replace_a_full_one(self):
        self.assertTrue(cloud.page_problems(public(built(9)), None, TODAY))
        current = public(built(30, updated="08:35"))
        self.assertEqual(cloud.page_problems(public(built(18)), current, TODAY), [])
        problems = cloud.page_problems(public(built(17)), current, TODAY)
        self.assertEqual(problems, ["it has 17 stories and needs 18"])

    def test_a_page_without_market_data_does_not_replace_one_that_has_it(self):
        current = public(built(20, updated="08:35"))
        problems = cloud.page_problems(public(built(markets=False)), current, TODAY)
        self.assertEqual(len(problems), 1)
        self.assertIn("indexes", problems[0])
        problems = cloud.page_problems(public(built(analysis=False)), current, TODAY)
        self.assertEqual(problems, ["it has no stock analysis and the published page has one"])
        bare = public(built(20, updated="08:35", markets=False, analysis=False))
        self.assertEqual(cloud.page_problems(public(built(markets=False, analysis=False)), bare, TODAY), [])


class AcceptTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.generator = self.root / "generator"
        (self.generator / "output").mkdir(parents=True)
        (self.generator / "publish_web.py").write_text(PUBLISH_WEB, encoding="utf-8")
        self.built = self.generator / "output" / "latest.html"
        self.page = self.root / "index.html"
        self.before = public(built(22, updated="08:35"))
        self.page.write_text(self.before, encoding="utf-8")

    def accept(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cloud.main([
                "accept", "--built", str(self.built), "--generator", str(self.generator),
                "--page", str(self.page), "--now", "2026-11-17T10:30:00+07:00",
            ])
        return code, out.getvalue()

    def test_a_good_page_is_made_public_and_written(self):
        self.built.write_text(built(private=True), encoding="utf-8")
        code, said = self.accept()
        self.assertEqual(code, 0, said)
        written = self.page.read_text(encoding="utf-8")
        self.assertEqual(written, public(built(private=True)))
        self.assertNotIn("MY HOLDINGS", written)
        self.assertIn("20 stories", said)
        self.assertIn("updated 10:28", said)

    def test_a_bad_page_leaves_the_published_one_alone(self):
        self.built.write_text(built(5), encoding="utf-8")
        code, said = self.accept()
        self.assertEqual(code, 1)
        self.assertIn("it has 5 stories and needs 13", said)
        self.assertEqual(self.page.read_text(encoding="utf-8"), self.before)

    def test_no_built_page_or_no_generator_code_fails_closed(self):
        code, said = self.accept()
        self.assertEqual(code, 1)
        self.assertIn("wrote no page", said)
        self.built.write_text(built(), encoding="utf-8")
        for broken in ("", "def other():\n    pass\n", "def _web_html(html):\n    raise ValueError(html)\n"):
            (self.generator / "publish_web.py").write_text(broken, encoding="utf-8")
            code, said = self.accept()
            self.assertEqual(code, 1, broken)
            self.assertNotIn("Story number", said)
            self.assertEqual(self.page.read_text(encoding="utf-8"), self.before)
        (self.generator / "publish_web.py").unlink()
        self.assertEqual(self.accept()[0], 1)
        self.assertEqual(self.page.read_text(encoding="utf-8"), self.before)


class DueCommandTest(unittest.TestCase):
    def run_due(self, *arguments: str) -> tuple[str, str]:
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / "index.html"
            page.write_text(helpers.page(stories(12), date=DAY, updated="09:00"), encoding="utf-8")
            outputs = Path(folder) / "outputs"
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(outputs)}), contextlib.redirect_stdout(out):
                code = cloud.main(["due", "--page", str(page), *arguments])
            self.assertEqual(code, 0)
            return outputs.read_text(encoding="utf-8"), out.getvalue()

    def test_the_decision_reaches_the_workflow(self):
        outputs, said = self.run_due("--mode", "auto", "--key", "true", "--now", "2026-11-17T11:25:00+07:00")
        self.assertEqual(outputs, "due=true\npush=true\nmode=auto\n")
        self.assertIn("build", said)
        outputs, said = self.run_due("--mode", "auto", "--key", "true", "--now", "2026-11-17T09:25:00+07:00")
        self.assertEqual(outputs, "due=false\npush=false\nmode=auto\n")
        outputs, _ = self.run_due("--mode", "BUILD", "--key", "true", "--now", "2026-11-17T09:25:00+07:00")
        self.assertEqual(outputs, "due=true\npush=false\nmode=build\n")
        outputs, said = self.run_due("--mode", "publish", "--key", "", "--now", "2026-11-17T09:25:00+07:00")
        self.assertEqual(outputs, "due=false\npush=false\nmode=publish\n")
        self.assertIn("GENERATOR_DEPLOY_KEY", said)


class BuildLogTest(unittest.TestCase):
    LOG = """[2026-11-17T10:26:01] === Morrow run start ===
[2026-11-17T10:26:20] brief: Ollama with qwen3:8b not reachable at http://localhost:11434
[2026-11-17T10:26:20] brief: extractive  - 5 bullets
[2026-11-17T10:26:25] stock analysis: 22 stocks, 2 indices, 22 with fundamentals, 2.1s
[2026-11-17T10:26:25] WARN portfolio summary failed
Traceback (most recent call last):
  File "/home/runner/work/morrow/morrow/generator/build_news.py", line 88, in main
    summary = portfolio.portfolio_summary(livechart.chart_payload)
FileNotFoundError: portfolio.json
[2026-11-17T10:26:25] data collected with 3 warning(s):
[2026-11-17T10:26:25]   - quote SECRETTICKER: HTTP 404
[2026-11-17T10:26:25]   - feed https://private.example/rss: timed out
[2026-11-17T10:26:25]   - feed https://other.example/rss: timed out
[2026-11-17T10:26:25] news window 72.0h, skipped 0 story(ies) already printed in earlier editions
[2026-11-17T10:26:26] wrote /home/runner/work/morrow/morrow/generator/output/morning-paper-2026-11-17.html (478280 bytes)
[2026-11-17T10:26:26] WARN live chart server check failed
[2026-11-17T10:26:26] web publish skipped: no GitHub login on this PC
[2026-11-17T10:26:26] WARN web edition not updated: 401 for https://api.github.com/repos/x/y with a token
[2026-11-17T10:26:26] === Morrow run complete ===
"""

    def test_the_summary_names_no_feed_ticker_path_or_code(self):
        lines = cloud.summarize_log(self.LOG)
        text = "\n".join(lines)
        for leak in ("SECRETTICKER", "example", "http", "/home/runner", "Traceback", "portfolio.json", "token", "line 88"):
            self.assertNotIn(leak, text)
        self.assertEqual(lines, [
            "=== Morrow run start ===",
            "brief: extractive  - 5 bullets",
            "stock analysis: 22 stocks, 2 indices, 22 with fundamentals, 2.1s",
            "WARN portfolio summary failed",
            "data collected with 3 warning(s):",
            "news window 72.0h, skipped 0 story(ies) already printed in earlier editions",
            "wrote morning-paper-2026-11-17.html (478280 bytes)",
            "WARN live chart server check failed",
            "web publish skipped: no GitHub login on this PC",
            "WARN web edition not updated",
            "=== Morrow run complete ===",
            "warnings by kind: 2 feed, 1 quote",
        ])

    def test_a_fatal_line_keeps_its_cause_and_nothing_after_it(self):
        lines = cloud.summarize_log(
            "[2026-11-17T10:26:01] FATAL no articles collected (network/proxy problem?) - keeping previous paper\n"
            "[2026-11-17T10:26:01] FATAL newsdata.collect failed\nTraceback (most recent call last):\n  secret line\n"
        )
        self.assertEqual(lines, ["FATAL no articles collected (network/proxy problem?)", "FATAL newsdata.collect failed"])

    def test_a_generator_that_published_by_itself_shows(self):
        lines = cloud.summarize_log("[2026-11-17T10:26:26] web edition: 1 file(s) updated -> https://juw12.github.io/morrow/\n")
        self.assertEqual(lines, ["web edition: 1 file(s) updated"])

    def test_a_missing_log_is_said_plainly(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(cloud.main(["buildlog", os.path.join(tempfile.gettempdir(), "no-such-morrow-log")]), 0)
        self.assertIn("no log", out.getvalue())


if __name__ == "__main__":
    unittest.main()
