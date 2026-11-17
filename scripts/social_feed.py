"""Morrow Brief: turn the published edition (index.html) into social posts.

Pure functions only: parse the page, pick the stories, write the text for each platform and the
Telegram bot's replies. No network, no files. `social_post.py` schedules and delivers the result.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html as htmllib
import re
import unicodedata

from bs4 import BeautifulSoup

BRAND = "Morrow Brief"
SITE_URL = "https://juw12.github.io/morrow/"
SITE_SHORT = "juw12.github.io/morrow"
REPO_URL = "https://github.com/juw12/morrow"
CHANNEL_URL = "https://t.me/morrowbrief"
CHANNEL_SHORT = "t.me/morrowbrief"
# Cards, state and the bot's feed live on their own branch, so the generator's pushes to main never collide.
DATA_BRANCH = "social-data"
DATA_URL = f"https://raw.githubusercontent.com/juw12/morrow/{DATA_BRANCH}/"
DIGEST_SIZE = 5
# A headline longer than this is cut at a word; a summary shorter than MIN_DEK is dropped, not shown as a stub.
MAX_TITLE = 300
MIN_DEK = 40
DIGEST_DEK = 240  # the longest summary a digest caption gives one story
MIN_THREADS_STORIES = 3  # below this the Threads digest shortens headlines rather than the list
MAX_THREADS_URL = 160
MAX_PER_SECTION = 2
ALERT_MIN_OUTLETS = 3
# A story whose address sits in one of these parts of its outlet's site is not tech or markets news,
# whatever section the page filed it under. It is left out of the brief; the page is not changed.
OFF_TOPIC_PATHS = frozenset({"lifestyle", "entertainment", "celebrity", "showbiz", "hiburan", "horoscope"})
# The full edition goes out as text messages after the digest. Each stays under Telegram's 4096 with room to spare.
# One Telegram message holds 4,096 characters; the margin covers anything Telegram counts differently.
EDITION_LIMIT = 4000
EDITION_TITLE = 140  # a headline longer than this is shortened in the one-message edition
EDITION_MIN_TITLE = 40
EDITION_DEK = 240  # the longest summary one story gets there
WIB = dt.timezone(dt.timedelta(hours=7), "WIB")
LIMITS = {
    "x": 280,
    "threads": 500,
    "telegram_caption": 1024,
    "telegram_message": 4096,
    "instagram": 2200,
}
TAGLINE = "Tech and markets, read across the outlets. One brief a day, every story sourced."
DISCLOSURE = (
    "Automated selection from published reporting. Headlines belong to their outlets; "
    "every story names its source."
)
SECTION_HASHTAGS = {
    "ai": ["AI", "Chips"],
    "big_tech": ["BigTech"],
    "robotics": ["Robotics"],
    "space": ["Space"],
    "technology": ["Tech"],
    "markets_news": ["Markets"],
}
SECTION_COMMANDS = {
    "ai": "/ai",
    "big_tech": "/bigtech",
    "robotics": "/robotics",
    "space": "/space",
    "technology": "/tech",
    "markets_news": "/markets",
}
URL_PATTERN = re.compile(r"https?://\S+")
SENTENCE_BREAK = re.compile(r"[.!?][\"'\u201d\u2019)]*\s+")
# A full stop after one of these does not end a sentence.
ABBREVIATIONS = frozenset(
    "Mr Mrs Ms Dr Prof Inc Corp Co Ltd vs St Jr Sr Gen Sen Rep Gov No Fig approx est "
    "Jan Feb Mar Apr Jun Jul Aug Sep Sept Oct Nov Dec".split()
)
EMOJI_PATTERN = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\uFE0F\u200D]"
)


# An outlet's trailing label for its own page, such as "(video)" or "[Photos]": not part of the headline.
MEDIA_TAG = re.compile(
    r"\s*[\(\[]\s*(?:videos?|photos?|pics|gallery|watch|audio|podcast|updated?)\s*[\)\]]\s*$",
    re.IGNORECASE,
)


def clean_title(text: str | None) -> str:
    """A headline without the outlet's trailing media tag. A headline that is only a tag is kept."""
    title = clean(text)
    return MEDIA_TAG.sub("", title).strip() or title


def clean(text: str | None) -> str:
    """Collapse whitespace and drop emoji, so an outlet's decorated headline cannot break the no-emoji rule."""
    return re.sub(r"\s+", " ", EMOJI_PATTERN.sub(" ", text or "")).strip()


def story_id(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


# --------------------------------------------------------------------------- parsing


def _edition_date(soup: BeautifulSoup) -> dt.date | None:
    title = clean(soup.title.string if soup.title else "")
    match = re.search(r"(\w+) (\d{1,2}), (\d{4})", title)
    if not match:
        return None
    try:
        return dt.datetime.strptime(" ".join(match.groups()), "%B %d %Y").date()
    except ValueError:
        return None


def _section_titles(soup: BeautifulSoup) -> dict[str, str]:
    """Map a section's display title to its id, read from the page's own section blocks."""
    titles = {}
    for block in soup.select('section[id^="s-"]'):
        heading = block.select_one(".block-head h2, h2, h3")
        if heading:
            titles[clean(heading.get_text(" "))] = block["id"][2:]
    return titles


def off_topic(url: str) -> bool:
    """True when the outlet itself filed the article under lifestyle, entertainment or the like."""
    path = re.sub(r"^https?://[^/]+", "", url).split("?", 1)[0].lower()
    return any(part in OFF_TOPIC_PATHS for part in path.split("/"))


def _parse_story(article, section_titles: dict[str, str]) -> dict | None:
    link = article.select_one("a.story-link[href]")
    heading = article.select_one("h2, h3, h4")
    if not link or not heading:
        return None
    url = link["href"].strip()
    title = clean_title(heading.get_text(" "))
    if not url.startswith("http") or not title:
        return None
    kicker = clean(article.select_one(".kicker").get_text(" ")) if article.select_one(".kicker") else ""
    section, _, tag = kicker.partition(" · ")
    block = article.find_parent("section", id=re.compile(r"^s-"))
    section_id = block["id"][2:] if block else section_titles.get(section, slugify(section))
    if not section:
        # Row stories carry no kicker; their section is the block they sit in.
        section = next((name for name, ident in section_titles.items() if ident == section_id), "")
    coverage_tag = article.select_one(".cov")
    coverage_match = re.search(r"\d+", (coverage_tag.get("title") or coverage_tag.get_text()) if coverage_tag else "")
    related = []
    for item in article.select("details.related li a[href]"):
        outlet = item.select_one("b")
        outlet_name = clean(outlet.get_text(" ")) if outlet else ""
        if outlet:
            outlet.extract()
        related.append({"source": outlet_name, "title": clean_title(item.get_text(" ")), "url": item["href"].strip()})
    time_tag = article.select_one("time[datetime]")
    source_tag = article.select_one(".src")
    dek_tag = article.select_one(".dek")
    image_tag = article.select_one("img[src]")
    image = image_tag["src"].strip() if image_tag else ""
    return {
        "id": story_id(url),
        "title": title,
        "url": url,
        "source": clean(source_tag.get_text(" ")) if source_tag else "",
        "section": section,
        "section_id": section_id,
        "tag": tag,
        "dek": clean(dek_tag.get_text(" ")) if dek_tag else "",
        "published_iso": time_tag["datetime"] if time_tag else "",
        "coverage": max(int(coverage_match.group()) if coverage_match else 1, 1 + len(related)),
        "related": related,
        "is_lead": "lead" in (article.get("class") or []),
        # The outlet's own picture for the story, where the page shows one.
        "image": image if image.startswith("https://") else "",
    }


def _parse_markets(soup: BeautifulSoup) -> list[dict]:
    quotes = []
    for card in soup.select(".qcard"):
        name = card.select_one(".qname")
        pct = card.select_one(".qpct")
        price = card.select_one(".qprice")
        number = re.search(r"-?\d+(?:\.\d+)?", pct.get_text() if pct else "")
        if not name or not number:
            continue
        classes = card.get("class") or []
        direction = "up" if "up" in classes else "down" if "down" in classes else "flat"
        quotes.append({
            "name": clean(name.get_text(" ")),
            "pct": abs(float(number.group())),
            "dir": direction,
            "price": clean(price.get_text(" ")) if price else "",
        })
    return quotes


def _parse_stocks(soup: BeautifulSoup) -> list[dict]:
    """Every stock in the page's analysis table: ticker, name, last price and the one-day move.

    The currency comes from the market value the page prints for the same ticker, where it prints one."""
    analysis = soup.select_one("#analysis")
    if not analysis:
        return []
    currencies: dict[str, str] = {}
    for row in analysis.select(".an-row"):
        ticker_tag = row.select_one(".tk b")
        value = re.search(r"Market cap\s+\S+\s+([A-Z]{3})\b", row.get_text(" "))
        if ticker_tag and value:
            currencies.setdefault(clean(ticker_tag.get_text(" ")), value.group(1))
    stocks: list[dict] = []
    seen: set[str] = set()
    for summary in analysis.select(".an-row > summary.tr-cols"):
        ticker_tag = summary.select_one(".tk b")
        name_tag = summary.select_one(".tk small")
        numbers = [clean(cell.get_text(" ")) for cell in summary.find_all("span", class_="n", recursive=False)]
        ticker = clean(ticker_tag.get_text(" ")) if ticker_tag else ""
        if not ticker or ticker in seen or not numbers or not re.search(r"\d", numbers[0]):
            continue
        move = re.fullmatch(r"([+-]?)(\d+(?:\.\d+)?)%", numbers[1].replace("\u2212", "-")) if len(numbers) > 1 else None
        pct = float(move.group(2)) if move else None
        direction = "flat"
        if pct:
            direction = "down" if move.group(1) == "-" else "up"
        seen.add(ticker)
        stocks.append({
            "ticker": ticker,
            "name": clean(name_tag.get_text(" ")) if name_tag else "",
            "price": numbers[0],
            "pct": pct,
            "dir": direction,
            "currency": currencies.get(ticker, ""),
        })
    return stocks


def _parse_brief(soup: BeautifulSoup, story_urls: set[str]) -> list[dict]:
    """The page's 'Also today' list: one line of text and the outlet it links to. Front-page stories are left out."""
    items = []
    for entry in soup.select(".brief-list li"):
        anchor = entry.select_one("a.brief-src[href]")
        if not anchor:
            continue
        url = anchor["href"].strip()
        source = clean(anchor.get_text(" ")).rstrip("\u2197 ").strip()
        anchor.extract()
        # The page joins headline and comment with a full stop, which leaves "?." after a question.
        text = re.sub(r"([?!])\.(?=\s|$)", r"\1", clean(entry.get_text(" ")))
        if url.startswith("http") and text and url not in story_urls:
            items.append({"text": text, "source": source, "url": url})
    return items


def parse_edition(page_html: str) -> dict:
    """Read the published page into {date, updated, stories, markets, stocks, brief}. Stories keep page order."""
    soup = BeautifulSoup(page_html, "html.parser")
    section_titles = _section_titles(soup)
    stories: list[dict] = []
    seen: dict[str, dict] = {}
    for article in soup.select("article.story"):
        story = _parse_story(article, section_titles)
        if not story or off_topic(story["url"]):
            continue
        if story["id"] in seen:
            first = seen[story["id"]]
            first["coverage"] = max(first["coverage"], story["coverage"])
            first["related"] = first["related"] or story["related"]
            continue
        story["order"] = len(stories)
        seen[story["id"]] = story
        stories.append(story)
    edition_date = _edition_date(soup)
    header = soup.select_one("header")
    updated = re.search(r"Updated (\d{1,2}:\d{2})", header.get_text(" ") if header else "")
    return {
        "date": edition_date.isoformat() if edition_date else "",
        "updated": updated.group(1) if updated else "",
        "stories": stories,
        "markets": _parse_markets(soup),
        "stocks": _parse_stocks(soup),
        "brief": _parse_brief(soup, {story["url"] for story in stories}),
    }


# --------------------------------------------------------------------------- selection


def ranked(stories: list[dict]) -> list[dict]:
    """Lead first, then the most widely reported, then the page's own order."""
    return sorted(stories, key=lambda story: (not story["is_lead"], -story["coverage"], story["order"]))


def pick_digest(stories: list[dict], size: int = DIGEST_SIZE, per_section: int = MAX_PER_SECTION) -> list[dict]:
    picked: list[dict] = []
    per_section_count: dict[str, int] = {}
    for story in ranked(stories):
        if len(picked) == size:
            break
        if per_section_count.get(story["section_id"], 0) >= per_section:
            continue
        per_section_count[story["section_id"]] = per_section_count.get(story["section_id"], 0) + 1
        picked.append(story)
    return picked


def alert_candidates(stories: list[dict], used_ids: set[str]) -> list[dict]:
    return [
        story for story in ranked(stories)
        if story["coverage"] >= ALERT_MIN_OUTLETS and story["id"] not in used_ids
    ]


def outlet_names(story: dict) -> list[str]:
    names: list[str] = []
    for name in [story["source"]] + [item["source"] for item in story["related"]]:
        if name and name not in names:
            names.append(name)
    return names


def outlet_total(stories: list[dict]) -> int:
    return len({name for story in stories for name in outlet_names(story)})


# --------------------------------------------------------------------------- text helpers


def x_length(text: str) -> int:
    """Length the way X counts it: every link is 23, most Latin and punctuation 1, the rest 2."""
    total = 0
    for char in unicodedata.normalize("NFC", URL_PATTERN.sub("x" * 23, text)):
        code = ord(char)
        light = (
            code <= 0x10FF
            or 0x2000 <= code <= 0x200D
            or 0x2010 <= code <= 0x201F
            or 0x2032 <= code <= 0x2037
        )
        total += 1 if light else 2
    return total


def visible_length(telegram_html: str) -> int:
    """Telegram counts a caption after entities are parsed, so tags and hrefs do not count."""
    return len(htmllib.unescape(re.sub(r"<[^>]+>", "", telegram_html)))


def truncate(text: str, limit: int, measure=len) -> str:
    """Cut at a word boundary and end with an ellipsis; never returns more than `limit`."""
    if measure(text) <= limit:
        return text
    words = text.split(" ")
    while len(words) > 1:
        words.pop()
        candidate = " ".join(words).rstrip(" ,;:-—–") + "…"
        if measure(candidate) <= limit:
            return candidate
    # A single word that does not fit (a long URL-like token): cut inside it.
    word = words[0]
    while word:
        word = word[:-1]
        if word and measure(word + "…") <= limit:
            return word + "…"
    return ""


def fit_title(build, title: str, limit: int, measure=len) -> str:
    """Return build(title), shortening the title until the whole text fits the limit."""
    overhead = measure(build(""))
    return build(truncate(title, max(limit - overhead, 0), measure))


def sentences(text: str) -> list[str]:
    """Split a summary into sentences without breaking on 'Nov. 13', 'U.S. Navy' or 'Inc. said'."""
    parts: list[str] = []
    start = 0
    for match in SENTENCE_BREAK.finditer(text):
        word = text[start:match.start()].split(" ")[-1].lstrip("\"'\u201c\u2018(")
        following = text[match.end():match.end() + 1]
        if text[match.start()] == "." and (word in ABBREVIATIONS or len(word) <= 1 or "." in word):
            continue
        if not (following.isupper() or following in "\"'\u201c\u2018("):
            continue
        parts.append(text[start:match.end()].strip())
        start = match.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts


def fit_dek(dek: str, room: int, measure=len, cut: bool = True) -> str:
    """The summary as whole sentences that fit `room`.

    Outlet feeds often end a summary mid-sentence with an ellipsis; that fragment is dropped when a
    whole sentence stands before it. With cut=False nothing is ever shortened inside a sentence: the
    summary is left out instead. With cut=True the last resort is a word-boundary cut with an ellipsis.
    """
    dek = dek.strip()
    if not dek or room < MIN_DEK:
        return ""
    parts = sentences(dek)
    if parts and parts[-1].endswith(("\u2026", "...")):
        parts = parts[:-1]
    kept = ""
    for part in parts:
        candidate = f"{kept} {part}".strip()
        if measure(candidate) > room:
            break
        kept = candidate
    if kept and (kept == dek or len(kept) >= MIN_DEK):
        return kept
    if not cut:
        return ""
    return truncate(dek, room, measure)


def esc(text: str) -> str:
    return htmllib.escape(text, quote=False)


def link(url: str, label: str) -> str:
    return f'<a href="{htmllib.escape(url, quote=True)}">{esc(label)}</a>'


def short_date(date_iso: str) -> str:
    day = dt.date.fromisoformat(date_iso)
    return f"{day:%a} {day.day} {day:%b}"


def long_date(date_iso: str) -> str:
    day = dt.date.fromisoformat(date_iso)
    return f"{day:%A} {day.day} {day:%B} {day.year}"


def outlets_phrase(story: dict, max_names: int = 4) -> str:
    """'5 outlets: Space.com, Spaceflight Now +3', '3 outlets, first: CNBC' or 'via CNBC'.

    The page lists the other outlets only for its lead story. Elsewhere it gives the count alone,
    so the count is kept and only the outlet actually linked is named.
    """
    names = outlet_names(story)
    if story["coverage"] <= 1:
        return f"via {story['source']}"
    if len(names) <= 1:
        return f"{story['coverage']} outlets, first: {story['source']}"
    shown = names[:max_names]
    hidden = story["coverage"] - len(shown)
    return f"{story['coverage']} outlets: {', '.join(shown)}" + (f" +{hidden}" if hidden > 0 else "")


def reported_by(story: dict, max_names: int = 4) -> str:
    """The same fact as outlets_phrase, as a full phrase for captions and cards."""
    phrase = outlets_phrase(story, max_names)
    if phrase.startswith("via "):
        return "Reported by " + phrase[4:]
    return "Reported by " + phrase


def section_line(story: dict, max_names: int = 2) -> str:
    return " · ".join(part for part in (story["section"], outlets_phrase(story, max_names)) if part)


def outlet_links(story: dict) -> str:
    """Every outlet's own article, so the reader picks the source."""
    links = [link(story["url"], story["source"])]
    seen = {story["source"]}
    for item in story["related"]:
        if item["source"] and item["source"] not in seen:
            seen.add(item["source"])
            links.append(link(item["url"], item["source"]))
    return " · ".join(links)


def markets_line(markets: list[dict], count: int = 4) -> str:
    arrows = {"up": "▲", "down": "▼", "flat": "="}
    parts = [f"{quote['name']} {arrows[quote['dir']]}{quote['pct']:.2f}%" for quote in markets[:count]]
    return " · ".join(parts)


def _table(rows: list[tuple[str, str, str]]) -> list[str]:
    """Rows of name, price and move as columns of equal width, for a fixed-width block."""
    name_width = max(len(name) for name, _, _ in rows)
    price_width = max(len(price) for _, price, _ in rows)
    return [f"{name:<{name_width}} {price:>{price_width}} {move}".rstrip() for name, price, move in rows]


def tape_lines(markets: list[dict]) -> list[str]:
    """Every index on the page with its last price and move, as one fixed-width table."""
    arrows = {"up": "▲", "down": "▼", "flat": "="}
    rows = [(quote["name"], str(quote["price"]), f"{arrows[quote['dir']]}{quote['pct']:.2f}%") for quote in markets]
    return ["<pre>" + esc("\n".join(_table(rows))) + "</pre>"] if rows else []


def stock_lines(stocks: list[dict]) -> list[str]:
    """Every stock with its last price and one-day move, as one fixed-width table, tickers in A to Z order.

    US dollars come first. The currency is named only when the page has more than one, so a price in
    rupiah is never read as dollars."""
    arrows = {"up": "▲", "down": "▼", "flat": "="}
    groups: dict[str, list[dict]] = {}
    for stock in sorted(stocks, key=lambda item: item["ticker"]):
        groups.setdefault(stock.get("currency") or "", []).append(stock)
    parts = []
    for currency in sorted(groups, key=lambda name: (name != "USD", name == "", name)):
        rows = []
        for stock in groups[currency]:
            move = "" if stock["pct"] is None else f"{arrows[stock['dir']]}{stock['pct']:.1f}%"
            rows.append((stock["ticker"], str(stock["price"]), move))
        heading = [f"{currency or 'Other'}"] if len(groups) > 1 else []
        parts.append("\n".join([*heading, *_table(rows)]))
    return ["<pre>" + esc("\n\n".join(parts)) + "</pre>"] if parts else []


def edition_numbers(edition_html: str) -> dict[str, int]:
    """The number each story carries in the one-message edition, by the story's link."""
    found = re.findall(r'<b>(\d+)</b>  [^\n]*?<a href="([^"]+)">', edition_html)
    return {htmllib.unescape(url): int(number) for number, url in found}


def hashtags(stories: list[dict], limit: int = 5) -> str:
    tags: list[str] = []
    for story in stories:
        candidates = SECTION_HASHTAGS.get(story["section_id"], []) + [re.sub(r"[^A-Za-z0-9]", "", story["tag"])]
        for tag in candidates:
            if tag and tag not in tags:
                tags.append(tag)
    return " ".join(f"#{tag}" for tag in tags[:limit])


def has_emoji(text: str) -> bool:
    return bool(EMOJI_PATTERN.search(text))


def post_problems(post: dict) -> list[str]:
    """Every rule a post must pass before it is frozen. An empty list means it is safe to send."""
    problems: list[str] = []
    checks = [("telegram", visible_length(post["telegram"]), LIMITS["telegram_caption"]),
              ("threads", len(post["threads"]), LIMITS["threads"]),
              ("instagram", len(post["instagram"]), LIMITS["instagram"])]
    checks += [(f"x {number}", x_length(text), LIMITS["x"]) for number, text in enumerate(post["x"], 1)]
    # Only a digest built from the edition carries the one-message edition; alerts do not.
    if "telegram_edition" in post:
        checks.append(("telegram edition", visible_length(post["telegram_edition"]), LIMITS["telegram_message"]))
    for name, length, limit in checks:
        if length > limit:
            problems.append(f"{name} text is {length}, the limit is {limit}")
        if length == 0:
            problems.append(f"{name} text is empty")
    texts = [post["telegram"], post["threads"], post["instagram"], *post["x"], *post["alts"],
             post.get("telegram_edition", "")]
    if any(has_emoji(text) for text in texts):
        problems.append("emoji in the text")
    if "<a href=" not in post["telegram"]:
        problems.append("telegram text has no link")
    if not all(URL_PATTERN.search(text) for text in [post["threads"], *post["x"]]):
        problems.append("an X or Threads text has no link")
    if len(post["cards"]) != len(post["alts"]) or not post["cards"]:
        problems.append("cards and alt texts do not match")
    return problems


# --------------------------------------------------------------------------- story (alert) posts


def story_telegram(story: dict) -> str:
    title = truncate(story["title"], MAX_TITLE)

    def build(dek: str) -> str:
        lines = [f"<b>{esc(title)}</b>"]
        if dek:
            lines += ["", esc(dek)]
        if len(outlet_names(story)) > 1:
            lines += ["", f"Reported by {story['coverage']} outlets:", outlet_links(story)]
        elif story["coverage"] > 1:
            lines += ["", f"Reported by {story['coverage']} outlets. First: " + outlet_links(story)]
        else:
            lines += ["", "Source: " + outlet_links(story)]
        return "\n".join(lines)

    room = LIMITS["telegram_caption"] - visible_length(build(""))
    return build(fit_dek(story["dek"], room - 2))


def _x_story(story: dict, prefix: str, max_names: int) -> str:
    """One X post: headline, a summary only as whole sentences, the outlets, the source link."""
    def build(title: str, dek: str = "") -> str:
        middle = f"\n\n{dek}" if dek else ""
        return f"{prefix}{title}{middle}\n\n{outlets_phrase(story, max_names)}\n{story['url']}"

    title = truncate(story["title"], max(LIMITS["x"] - x_length(build("")), 0), x_length)
    room = LIMITS["x"] - x_length(build(title)) - 2
    return build(title, fit_dek(story["dek"], room, x_length, cut=False))


def story_x(story: dict) -> str:
    return _x_story(story, "", 3)


def story_threads(story: dict) -> str:
    # Threads counts a link at full length, so a tracking-laden URL gives way to the edition link.
    url = story["url"] if len(story["url"]) <= MAX_THREADS_URL else SITE_URL

    def build(title: str, dek: str = "") -> str:
        middle = f"\n\n{dek}" if dek else ""
        return f"{title}{middle}\n\n{outlets_phrase(story)}\n{url}"

    title = truncate(story["title"], max(LIMITS["threads"] - len(build("")), 0))
    room = LIMITS["threads"] - len(build(title)) - 2
    return build(title, fit_dek(story["dek"], room))


def story_instagram(story: dict) -> str:
    def build(dek: str) -> str:
        lines = [truncate(story["title"], MAX_TITLE), ""]
        if dek:
            lines += [dek, ""]
        lines += [
            reported_by(story, 6),
            "",
            f"Every story links to its source: {SITE_SHORT} (link in bio).",
            DISCLOSURE,
            "",
            hashtags([story]),
        ]
        return "\n".join(lines)

    room = LIMITS["instagram"] - len(build("")) - 2
    return build(fit_dek(story["dek"], room))


def story_alt(story: dict) -> str:
    return truncate(f"{BRAND} card. {story['title']}. {reported_by(story, 6)}.", 400)


def story_post(story: dict, date_iso: str) -> dict:
    return {
        "id": f"story-{story['id']}",
        "kind": "alert",
        "date": date_iso,
        "story_ids": [story["id"]],
        "cards": [f"cards/{date_iso}/{story['id']}.png"],
        "alts": [story_alt(story)],
        "telegram": story_telegram(story),
        "x": [story_x(story)],
        "threads": story_threads(story),
        "instagram": story_instagram(story),
    }


# --------------------------------------------------------------------------- digest post


def digest_telegram(stories: list[dict], markets: list[dict], date_iso: str) -> str:
    """The caption under the cover card. The lead carries a link to every outlet the page names."""
    limit = LIMITS["telegram_caption"]

    def build(title_budget: int, lead_links: bool = False, lead_dek: str = "") -> str:
        lines = [f"<b>{BRAND}</b> · {short_date(date_iso)}", ""]
        for number, story in enumerate(stories, 1):
            lines.append(f"<b>{number}.</b> {link(story['url'], truncate(story['title'], title_budget))}")
            if number == 1 and lead_dek:
                lines.append(esc(lead_dek))
            if number == 1 and lead_links and len(outlet_names(story)) > 1:
                hidden = story["coverage"] - len(outlet_names(story))
                more = f" +{hidden}" if hidden > 0 else ""
                lines.append(f"{esc(story['section'])} · {story['coverage']} outlets: {outlet_links(story)}{more}")
            else:
                lines.append(esc(section_line(story)))
            lines.append("")
        if markets:
            lines += [esc("Markets: " + markets_line(markets)), ""]
        lines.append(link(SITE_URL, "Read the full edition"))
        return "\n".join(lines)

    # First choice: full headlines and the lead's outlets as links, plus its summary if whole
    # sentences fit. Then the plain list, shortening headlines only when nothing else is left.
    if stories and visible_length(build(140, lead_links=True)) <= limit:
        room = limit - visible_length(build(140, lead_links=True)) - 1
        return build(140, lead_links=True, lead_dek=fit_dek(stories[0]["dek"], room, cut=False))
    for title_budget in range(140, 30, -10):
        text = build(title_budget)
        if visible_length(text) <= limit:
            return text
    return build(30)


def digest_x(stories: list[dict], date_iso: str) -> list[str]:
    """One thread: each post is a story with its summary, outlets and link. The first carries the masthead."""
    total = len(stories)
    thread = []
    for number, story in enumerate(stories, 1):
        head = f"{BRAND} · {short_date(date_iso)}\n\n" if number == 1 else ""
        thread.append(_x_story(story, f"{head}{number}/{total} ", 2))
    return thread


def digest_threads(stories: list[dict], date_iso: str) -> str:
    """One post. Headlines are printed whole; stories that do not fit are named by outlet instead."""
    def line(number: int, story: dict, title: str) -> str:
        extra = f" +{story['coverage'] - 1}" if story["coverage"] > 1 else ""
        return f"{number}. {title} ({story['source']}{extra})"

    def build(shown: int) -> str:
        lines = [f"{BRAND} · {short_date(date_iso)}", ""]
        lines += [line(number, story, story["title"]) for number, story in enumerate(stories[:shown], 1)]
        rest = stories[shown:]
        if rest:
            outlets = list(dict.fromkeys(story["source"] for story in rest))
            footer = f"+{len(rest)} more from {', '.join(outlets)}. Full edition, every story sourced: {SITE_URL}"
        else:
            footer = f"Full edition, every story linked to its source: {SITE_URL}"
        return "\n".join(lines + ["", footer])

    for shown in range(len(stories), min(MIN_THREADS_STORIES, len(stories)) - 1, -1):
        if len(build(shown)) <= LIMITS["threads"]:
            return build(shown)

    # Headlines too long to print even three whole: keep every story and shorten the headlines.
    def build_short(title_budget: int) -> str:
        lines = [f"{BRAND} · {short_date(date_iso)}", ""]
        lines += [line(number, story, truncate(story["title"], title_budget))
                  for number, story in enumerate(stories, 1)]
        return "\n".join(lines + ["", f"Full edition, every story sourced: {SITE_URL}"])

    for title_budget in range(110, 20, -5):
        if len(build_short(title_budget)) <= LIMITS["threads"]:
            return build_short(title_budget)
    return build_short(20)


def digest_instagram(stories: list[dict], markets: list[dict], date_iso: str) -> str:
    def build(title_budget: int, with_summaries: bool) -> str:
        lines = [f"{BRAND} · {long_date(date_iso)}", ""]
        for number, story in enumerate(stories, 1):
            lines.append(f"{number}. {truncate(story['title'], title_budget)}")
            summary = fit_dek(story["dek"], DIGEST_DEK, cut=False) if with_summaries else ""
            if summary:
                lines.append(f"   {summary}")
            lines += [f"   {reported_by(story, 4)}", ""]
        if markets:
            lines += ["Markets: " + markets_line(markets), ""]
        lines += [
            f"Every story links to its source: {SITE_SHORT} (link in bio).",
            DISCLOSURE,
            "",
            hashtags(stories),
        ]
        return "\n".join(lines)

    if len(build(MAX_TITLE, True)) <= LIMITS["instagram"]:
        return build(MAX_TITLE, True)
    # Shorten the headlines, never the list: every story keeps its line and its outlets.
    for title_budget in range(MAX_TITLE, 40, -20):
        text = build(title_budget, False)
        if len(text) <= LIMITS["instagram"]:
            return text
    return build(40, False)


def _edition_story(number: int, story: dict, title_budget: int, summary: str) -> str:
    """One story of the one-message edition: linked headline, its outlet, and the summary when it has one."""
    title = truncate(story["title"], title_budget)
    if story["source"]:
        extra = f" +{story['coverage'] - 1}" if story["coverage"] > 1 else ""
        line = f"<b>{number}</b>  {esc(title)} · {link(story['url'], story['source'])}{extra}"
    else:
        line = f"<b>{number}</b>  {link(story['url'], title)}"
    return f"{line}\n<i>{esc(summary)}</i>" if summary else line


def edition_telegram(edition: dict, limit: int = EDITION_LIMIT) -> str:
    """The whole edition as ONE Telegram message.

    Every story on the page is there as a linked headline with its outlet, under its section, in the
    page's order, then every index and every stock of the page's analysis table with its price and
    one-day move. The room that is left goes to summaries, whole sentences only,
    most widely reported story first. A message holds 4,096 characters and a full page needs about
    twice that with every summary, so on a big day the rest of the summaries stay on the page.
    Only when the headlines alone do not fit are they shortened, and after that the list.
    """
    date_iso = edition["date"]
    stories = edition["stories"]
    if not date_iso or not stories:
        return ""
    order = ranked(stories)
    summarised = {story["id"] for story in stories if story["dek"] and story["dek"] != story["title"]}

    def build(title_budget: int, summaries: dict[str, str], shown: int) -> str:
        keep = {story["id"] for story in order[:shown]}
        hidden = len(stories) - len(keep)
        count = f"{len(stories)} stories · {outlet_total(stories)} outlets"
        blocks = [f"<b>{esc(BRAND.upper())}</b> · {short_date(date_iso)}\n{count}\nTap the outlet's name to read a story."]
        number = 0
        for section in dict.fromkeys(story["section"] or "More" for story in stories):
            lines = []
            for story in stories:
                if (story["section"] or "More") == section and story["id"] in keep:
                    number += 1
                    lines.append(_edition_story(number, story, title_budget, summaries.get(story["id"], "")))
            if lines:
                blocks.append("\n\n".join([f"<b><u>{esc(section.upper())}</u></b>", *lines]))
        stocks = edition.get("stocks") or []
        if edition["markets"]:
            blocks.append("\n".join(["<b><u>INDEXES</u></b> · last close", *tape_lines(edition["markets"]),
                                     *([] if stocks else ["Not financial advice."])]))
        if stocks:
            blocks.append("\n".join(["<b><u>STOCKS</u></b> · last price, 1-day move", *stock_lines(stocks),
                                     "Not financial advice."]))
        left = [f"+{hidden} more stories"] if hidden else []
        if summarised - set(summaries):
            left.append("every summary")
        if left:
            footer = f"{', '.join(left)}, the charts and the stock analysis".capitalize() + ": "
        else:
            footer = "Charts and the stock analysis: "
        blocks.append(footer + link(SITE_URL, SITE_SHORT))
        return "\n\n".join(blocks)

    def fits(text: str) -> bool:
        return visible_length(text) <= limit

    for title_budget in range(EDITION_TITLE, EDITION_MIN_TITLE - 1, -10):
        if fits(build(title_budget, {}, len(stories))):
            break
    else:
        # Even short headlines do not all fit: list as many of the most reported stories as do.
        title_budget = EDITION_MIN_TITLE
        for shown in range(len(stories) - 1, 0, -1):
            if fits(build(title_budget, {}, shown)):
                return build(title_budget, {}, shown)
        return build(title_budget, {}, 1)
    summaries: dict[str, str] = {}
    for story in order:
        if story["id"] not in summarised:
            continue
        # A summary may make the footer one phrase shorter, never longer, so the room is a safe measure.
        room = limit - visible_length(build(title_budget, summaries, len(stories))) - 1
        summary = fit_dek(story["dek"], min(room, EDITION_DEK), cut=False)
        if summary:
            summaries[story["id"]] = summary
    return build(title_budget, summaries, len(stories))


def digest_post(stories: list[dict], markets: list[dict], date_iso: str, edition: dict | None = None) -> dict:
    """The day's digest. Given the edition, Telegram gets the whole edition as one message instead of the caption."""
    post = {
        "id": f"digest-{date_iso}",
        "kind": "digest",
        "date": date_iso,
        "story_ids": [story["id"] for story in stories],
        "cards": [f"cards/{date_iso}/digest.png"] + [f"cards/{date_iso}/{story['id']}.png" for story in stories],
        "alts": [truncate(f"{BRAND} for {long_date(date_iso)}: " + "; ".join(s["title"] for s in stories), 400)]
        + [story_alt(story) for story in stories],
        "telegram": digest_telegram(stories, markets, date_iso),
        "x": digest_x(stories, date_iso),
        "threads": digest_threads(stories, date_iso),
        "instagram": digest_instagram(stories, markets, date_iso),
    }
    if edition:
        post["telegram_edition"] = edition_telegram(edition)
    return post


# --------------------------------------------------------------------------- Telegram bot replies


def _story_line(story: dict) -> str:
    extra = f" +{story['coverage'] - 1}" if story["coverage"] > 1 else ""
    return f"• {link(story['url'], truncate(story['title'], 120))} ({esc(story['source'])}{extra})"


def _list_reply(heading: str, stories: list[dict], footer: str = "") -> str:
    lines = [f"<b>{esc(heading)}</b>", ""] + [_story_line(story) for story in stories]
    if footer:
        lines += ["", footer]
    text = "\n".join(lines)
    while visible_length(text) > LIMITS["telegram_message"] and stories:
        stories = stories[:-1]
        text = "\n".join([f"<b>{esc(heading)}</b>", ""] + [_story_line(story) for story in stories])
    return text


def bot_replies(edition: dict) -> dict[str, str]:
    """Every fixed command's reply, pre-rendered, so the bot itself needs no logic or state."""
    stories = edition["stories"]
    date_label = short_date(edition["date"]) if edition["date"] else "today"
    section_names: dict[str, str] = {}
    for story in stories:
        section_names.setdefault(story["section_id"], story["section"])
    section_lines = [f"{command} {esc(section_names[section])}" for section, command in SECTION_COMMANDS.items()
                     if section in section_names]
    names = sorted({name for story in stories for name in outlet_names(story)}, key=str.lower)
    dated = f" ({date_label})" if edition["date"] else ""
    stocks = edition.get("stocks") or []
    tape_label = "index and stock prices" if stocks else "index moves"
    # /start is the welcome: three things to try and what is in today's edition. /help is the full list.
    start_text = "\n".join([
        f"<b>{BRAND}</b>",
        TAGLINE,
        "",
        "Start with one of these:",
        "/today the five most reported stories",
        "/find <i>word</i> search today's stories, for example /find nvidia",
        "/help every command",
        "",
        f"{len(stories)} stories from {len(names)} outlets in today's edition{esc(dated)}. "
        "Every headline links to the outlet that reported it.",
        "",
        f"The brief every morning at 08:00 Jakarta time: {link(CHANNEL_URL, CHANNEL_SHORT)}",
        f"Full edition: {link(SITE_URL, SITE_SHORT)}",
    ])
    help_blocks = [
        ["<b>The brief</b>", "/today the five most reported stories", "/full every story in one message"],
        ["<b>Sections</b>", *section_lines] if section_lines else [],
        ["<b>Numbers and sources</b>", f"/tape {tape_label}", "/sources outlets in today's edition"],
        ["<b>Search</b>", "/find <i>word</i> search today's stories, for example /find nvidia"],
        ["<b>About</b>", "/about how stories are chosen", "/privacy what this bot stores"],
        [f"Daily channel: {link(CHANNEL_URL, CHANNEL_SHORT)}", f"Full edition: {link(SITE_URL, SITE_SHORT)}"],
    ]
    help_text = "\n\n".join(
        ["<b>" + esc(f"{BRAND} · commands") + "</b>"] + ["\n".join(block) for block in help_blocks if block]
    )
    replies = {
        "/start": start_text,
        "/help": help_text,
        "/today": _list_reply(
            f"{BRAND} · {date_label}", pick_digest(stories),
            esc("Markets: " + markets_line(edition["markets"])) if edition["markets"] else "",
        ),
        "/about": "\n".join([
            f"<b>How {BRAND} works</b>",
            "",
            f"{BRAND} is built from Morrow, a daily paper that reads hundreds of headlines and merges "
            "coverage of the same story across outlets.",
            "",
            "• Selection is automated: the most widely reported stories come first.",
            "• Nothing is rewritten. Headlines belong to their outlets and every story links to them.",
            "• A number after an outlet, like +3, counts the other outlets that carried the same story.",
            "• Replies follow the latest edition, so /today changes when the paper does.",
            "",
            "Not financial advice.",
            "",
            f"{link(SITE_URL, 'Full edition')} · {link(REPO_URL, 'Source code')}",
        ]),
        "/privacy": "\n".join([
            "<b>Privacy</b>",
            "",
            "This bot has no database. It keeps no list of users and stores no messages: it reads the command "
            "you send, answers from today's public edition and keeps nothing afterwards.",
            "",
            "No sign-up and no ads. Story links go straight to the outlet; the bot adds nothing to them.",
            "",
            "Telegram carries the message, so Telegram's own privacy policy covers the app itself.",
            "",
            f"The code is public: {link(REPO_URL, 'github.com/juw12/morrow')}",
        ]),
    }
    if edition["date"] and stories:
        replies["/full"] = edition_telegram(edition)
    for section, command in SECTION_COMMANDS.items():
        section_stories = [story for story in ranked(stories) if story["section_id"] == section][:6]
        if section_stories:
            replies[command] = _list_reply(f"{section_names[section]} · {date_label}", section_stories)
    if edition["markets"]:
        tape = [f"<b>Tape · {date_label}</b>", "", "<b>Indexes</b> · last close", *tape_lines(edition["markets"])]
        if stocks:
            tape += ["", "<b>Stocks</b> · last price, 1-day move", *stock_lines(stocks)]
        replies["/tape"] = "\n".join([*tape, "", "Not financial advice."])
    replies["/sources"] = (
        f"<b>{len(stories)} stories from {len(names)} outlets · {date_label}</b>\n\n" + esc(", ".join(names))
    )
    return replies


def search_reply(stories: list[dict], query: str) -> str:
    words = [word for word in re.findall(r"[a-z0-9]+", query.lower()) if len(word) > 1]
    if not words:
        return "Send /find and a word, for example: /find nvidia"
    hits = []
    for story in ranked(stories):
        haystack = " ".join([story["title"], story["dek"], story["tag"], story["source"]]).lower()
        if all(word in haystack for word in words):
            hits.append(story)
    if not hits:
        return f"Nothing on “{esc(query.strip())}” in today's edition. Try /today."
    noun = "story" if len(hits) == 1 else "stories"
    return _list_reply(f"{len(hits)} {noun} on “{query.strip()}”", hits[:6])


# --------------------------------------------------------------------------- public feed


def public_feed(edition: dict, posts: list[dict]) -> dict:
    """What gets published as feed.json on the data branch: today's stories, posts and the bot's replies."""
    return {
        "brand": BRAND,
        "site": SITE_URL,
        "date": edition["date"],
        "updated": edition["updated"],
        "stats": {"stories": len(edition["stories"]), "outlets": outlet_total(edition["stories"])},
        "markets": edition["markets"],
        "stories": [
            {key: story[key] for key in (
                "id", "title", "url", "source", "section", "section_id", "tag", "dek",
                "published_iso", "coverage", "related", "is_lead", "order",
            )}
            for story in edition["stories"]
        ],
        "posts": posts,
        "bot": bot_replies(edition) if edition["date"] else {},
    }
