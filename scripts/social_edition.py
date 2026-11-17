"""Morrow Brief: build the page in the cloud when the PC has stopped publishing it.

    python scripts/social_edition.py due --page index.html --mode auto --key true
    python scripts/social_edition.py buildlog build.log
    python scripts/social_edition.py accept --built generator/output/latest.html --generator generator --page index.html

The page is normally built and published by a PC every 30 minutes. When that PC is off, asleep or cannot
reach GitHub, the page stops changing and the day's digest never goes out. The workflow then builds the
page itself from the private generator repository and commits it here.

`due` decides whether to do that: only between 08:20 and 22:30 Jakarta time, and only when the page's own
"Updated" time is more than 80 minutes old, so a PC that is publishing always wins. `accept` is the gate:
the built page replaces the published one only if it is today's, holds no private section, and is not
much thinner than the page it replaces. `buildlog` prints a short summary of the generator's log, because
run logs here are public and the generator's own log names feeds and tickers.

Modes: auto (the rule above), build (build and check, publish nothing), publish (build and publish now),
off (never).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import re
import sys
from pathlib import Path

import social_feed as feed

WIB = feed.WIB
MODES = ("auto", "build", "publish", "off")
WINDOW_OPENS = dt.time(8, 20)  # the PC's own 08:00 edition gets the first chance
WINDOW_CLOSES = dt.time(22, 30)
STALE_AFTER = dt.timedelta(minutes=80)  # the PC publishes every 30 minutes, so this is two missed editions
MIN_STORIES = 10
MIN_STORY_SHARE = 0.6  # of the page being replaced
MIN_INDEX_SHARE = 0.5
PRIVATE_MARK = "<!--private:"
ANALYSIS_MARK = 'id="analysis"'
WEB_MARKS = ('class="wl"', 'name="robots"')  # what the generator adds to the public page only
SECRET_KEY = "GENERATOR_DEPLOY_KEY"


def parse_now(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(dt.timezone.utc)
    moment = dt.datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=WIB)


def page_stamp(edition: dict) -> dt.datetime | None:
    """When the page says it was last built: its date and its "Updated HH:MM", in Jakarta time."""
    if not edition.get("date") or not edition.get("updated"):
        return None
    try:
        day = dt.date.fromisoformat(edition["date"])
        hour, minute = (int(part) for part in edition["updated"].split(":"))
        return dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=WIB)
    except ValueError:
        return None


def decide(mode: str, edition: dict, now: dt.datetime, has_key: bool) -> tuple[bool, bool, str]:
    """Return (build the page, publish it if it passes, the reason in plain words)."""
    if mode not in MODES:
        return False, False, f"unknown mode {mode!r}; nothing built"
    if mode == "off":
        return False, False, "the cloud edition is switched off"
    if not has_key:
        return False, False, f"the secret {SECRET_KEY} is not set, so the generator cannot be read"
    if mode == "build":
        return True, False, "asked for by hand: build and check, publish nothing"
    if mode == "publish":
        return True, True, "asked for by hand: build, check and publish"
    local = now.astimezone(WIB)
    if not WINDOW_OPENS <= local.time() <= WINDOW_CLOSES:
        return False, False, (
            f"{local:%H:%M} WIB is outside {WINDOW_OPENS:%H:%M}-{WINDOW_CLOSES:%H:%M}, "
            "the hours the cloud edition covers"
        )
    stamp = page_stamp(edition)
    if stamp is None:
        return True, True, "the page shows no readable date and time"
    age = now - stamp
    minutes = int(age.total_seconds() // 60)
    if age < STALE_AFTER:
        return False, False, f"the page was updated {stamp:%H:%M}, {max(minutes, 0)} minutes ago: the PC is publishing"
    limit = int(STALE_AFTER.total_seconds() // 60)
    if stamp.date() != local.date():
        return True, True, f"the page is still the {stamp:%d %b} edition (updated {stamp:%H:%M})"
    return True, True, f"the page was updated {stamp:%H:%M}, {minutes} minutes ago (more than {limit})"


def web_page(built_html: str, generator_dir: Path) -> str:
    """The public form of a built page, made by the generator's own code so the two never drift apart."""
    module_path = Path(generator_dir) / "publish_web.py"
    if not module_path.exists():
        raise RuntimeError("the generator has no publish_web.py; the page is not published")
    spec = importlib.util.spec_from_file_location("morrow_publish_web", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    convert = getattr(module, "_web_html", None)
    if not callable(convert):
        raise RuntimeError("the generator's publish_web.py has no _web_html; the page is not published")
    return convert(built_html)


def page_problems(page_html: str, current_html: str | None, today: dt.date) -> list[str]:
    """Why this page must not replace the published one. An empty list means it may."""
    problems: list[str] = []
    edition = feed.parse_edition(page_html)
    if PRIVATE_MARK in page_html:
        problems.append("it still holds a private section")
    for mark in WEB_MARKS:
        if mark not in page_html:
            problems.append(f"it is not the public form of the page ({mark} is missing)")
    if edition["date"] != today.isoformat():
        problems.append(f"it is dated {edition['date'] or 'nothing readable'} and today is {today.isoformat()}")
    if page_stamp(edition) is None:
        problems.append("it shows no readable date and time")
    need = MIN_STORIES
    current = feed.parse_edition(current_html) if current_html else None
    if current:
        need = max(need, int(len(current["stories"]) * MIN_STORY_SHARE))
    if len(edition["stories"]) < need:
        problems.append(f"it has {len(edition['stories'])} stories and needs {need}")
    if current:
        need_indexes = int(len(current["markets"]) * MIN_INDEX_SHARE + 0.5)
        if len(edition["markets"]) < need_indexes:
            problems.append(
                f"it has {len(edition['markets'])} of the {len(current['markets'])} indexes "
                "on the published page (market data did not load)"
            )
        if ANALYSIS_MARK in current_html and ANALYSIS_MARK not in page_html:
            problems.append("it has no stock analysis and the published page has one")
    return problems


def describe(page_html: str) -> str:
    edition = feed.parse_edition(page_html)
    stories = edition["stories"]
    analysis = "with" if ANALYSIS_MARK in page_html else "without"
    return (
        f"dated {edition['date']}, updated {edition['updated']}, {len(stories)} stories from "
        f"{feed.outlet_total(stories)} outlets, {len(edition['markets'])} indexes, {analysis} the stock analysis"
    )


LOG_LINE = re.compile(r"^\[(?P<time>[^\]]+)\] (?P<text>.*)$")
SAFE_LINES = (
    re.compile(r"^=== Morrow run (start|complete) ===$"),
    re.compile(r"^brief: (extractive|Ollama)\b[^/\\]*$"),
    re.compile(r"^stock analysis: [\d\w ,.]+$"),
    re.compile(r"^data collected with \d+ warning\(s\):$"),
    re.compile(r"^news window [\d.]+h, skipped \d+ story\(ies\) already printed in earlier editions$"),
    # Either of these says whether the generator tried to publish by itself. In the cloud it must not.
    re.compile(r"^web publish skipped: no GitHub login on this PC$"),
    re.compile(r"^web edition: \d+ file\(s\) updated\b"),
)
WROTE = re.compile(r"^wrote .*?([\w.-]+\.html) \((\d+) bytes\)$")
FLAG = re.compile(r"^(FATAL|WARN) ([^\n]{0,90})")
WARNING_ITEM = re.compile(r"^\s+- (\w+)")


def summarize_log(text: str) -> list[str]:
    """The generator's log, reduced to lines that name no feed, ticker, path or line of its code."""
    lines: list[str] = []
    kinds: dict[str, int] = {}
    for raw in text.splitlines():
        found = LOG_LINE.match(raw.rstrip())
        if not found:
            continue  # tracebacks and anything else unstamped
        message = found.group("text")
        item = WARNING_ITEM.match(message)
        if item:
            kinds[item.group(1)] = kinds.get(item.group(1), 0) + 1
            continue
        wrote = WROTE.match(message)
        flag = FLAG.match(message)
        if wrote:
            lines.append(f"wrote {wrote.group(1)} ({wrote.group(2)} bytes)")
        elif flag:
            lines.append(f"{flag.group(1)} {flag.group(2).split(' - ')[0].split(':')[0].strip()}")
        elif any(pattern.match(message) for pattern in SAFE_LINES):
            lines.append(message.split(" -> ")[0])
    if kinds:
        counted = ", ".join(f"{count} {kind}" for kind, count in sorted(kinds.items()))
        lines.append(f"warnings by kind: {counted}")
    return lines


def write_outputs(**values: str) -> None:
    target = os.environ.get("GITHUB_OUTPUT")
    if not target:
        return
    with open(target, "a", encoding="utf-8") as handle:
        for name, value in values.items():
            handle.write(f"{name}={value}\n")


def command_due(args: argparse.Namespace) -> int:
    page = Path(args.page)
    edition = feed.parse_edition(page.read_text(encoding="utf-8")) if page.exists() else {}
    mode = (args.mode or "auto").strip().lower()
    build, publish, reason = decide(mode, edition, parse_now(args.now), args.key.strip().lower() == "true")
    print(f"cloud edition ({mode}): {'build' if build else 'nothing to do'} - {reason}")
    write_outputs(due=str(build).lower(), push=str(publish).lower(), mode=mode)
    return 0


def command_buildlog(args: argparse.Namespace) -> int:
    path = Path(args.log)
    lines = summarize_log(path.read_text(encoding="utf-8", errors="replace")) if path.exists() else []
    print("\n".join(lines) if lines else "the generator wrote no log")
    return 0


def command_accept(args: argparse.Namespace) -> int:
    built = Path(args.built)
    if not built.exists():
        print("the generator wrote no page; the published page stays")
        return 1
    try:
        page_html = web_page(built.read_text(encoding="utf-8"), Path(args.generator))
    except Exception as error:  # the generator's code: anything it raises means "do not publish"
        print(f"the built page could not be made public ({type(error).__name__}); the published page stays")
        return 1
    target = Path(args.page)
    current_html = target.read_text(encoding="utf-8") if target.exists() else None
    today = parse_now(args.now).astimezone(WIB).date()
    print(f"built page: {describe(page_html)}")
    if current_html:
        print(f"published page: {describe(current_html)}")
    problems = page_problems(page_html, current_html, today)
    if problems:
        print("the built page is not published:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    # The PC writes Windows line ends. Keeping the published page's style keeps each edition's change small.
    windows = target.exists() and b"\r\n" in target.read_bytes()
    target.write_text(page_html, encoding="utf-8", newline="\r\n" if windows else "\n")
    print(f"the built page passed every check and is written to {target.name}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    due = commands.add_parser("due")
    due.add_argument("--page", default="index.html")
    due.add_argument("--mode", default="auto")
    due.add_argument("--key", default="false", help="true when the generator's deploy key is set")
    due.add_argument("--now", help="ISO time, for tests")
    due.set_defaults(run=command_due)
    buildlog = commands.add_parser("buildlog")
    buildlog.add_argument("log")
    buildlog.set_defaults(run=command_buildlog)
    accept = commands.add_parser("accept")
    accept.add_argument("--built", default="generator/output/latest.html")
    accept.add_argument("--generator", default="generator")
    accept.add_argument("--page", default="index.html")
    accept.add_argument("--now", help="ISO time, for tests")
    accept.set_defaults(run=command_accept)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
