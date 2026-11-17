"""Morrow Brief: the Telegram channel the bot posts to.

    python scripts/social_channel.py find --chat "@handle, t.me/handle/12, t.me/c/1234567890/12"
    python scripts/social_channel.py status --chat @handle   (what the channel shows, what the bot may do)
    python scripts/social_channel.py setup --chat @handle    (name, description, picture, pinned welcome)
    python scripts/social_channel.py test --chat @handle     (posts, edits, reacts, then deletes its posts)
    python scripts/social_channel.py listen --seconds 19200  (waits for the channel to show itself, then
                                                              runs setup, test and status on it)
    python scripts/social_channel.py view                    (the newest posts as the public page shows them)
    python scripts/social_channel.py metrics --out data/metrics.csv   (today's subscribers and views, one line a day)

Without --chat the commands use TELEGRAM_CHAT_ID. A bot cannot list the chats it is in, so `find` asks
Telegram about each name it is given, or about the likely Morrow Brief handles, and reports where the bot
is an admin. A private channel has no name to ask about and its invite link (t.me/+...) tells a bot nothing,
so `listen` waits until Telegram reports the channel: a post in it, a change to the bot's admin rights, or
one of its posts forwarded to the bot. Run logs are public: a private channel's id is never printed, only
a sealed form that the holder of CHANNEL_HANDOFF_KEY can read.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import io
import json
import os
import re
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

import social_bot as bot
import social_feed as feed

LIKELY_HANDLES = [
    "morrowbrief", "morrow_brief", "morrowbriefs", "morrow_briefs", "themorrowbrief", "the_morrow_brief",
    "morrowbrief_channel", "morrow_brief_channel", "morrowbriefchannel", "morrowbriefnews", "morrow_brief_news",
    "morrowbriefdaily", "morrow_brief_daily", "morrowbriefing", "morrow_briefing", "readmorrow", "morrowdaily",
    "morrow_daily", "morrownews", "morrow_news", "morrowpaper", "morrow_paper", "morrowtech", "morrow_tech",
]
TITLE = feed.BRAND
MAX_DESCRIPTION = 255
# The rights a channel admin can hold, in the words the Telegram app uses, and what each is needed for here.
RIGHTS = [
    ("can_post_messages", "Post messages", "post the daily brief, pictures, albums and polls"),
    ("can_edit_messages", "Edit messages of others", "pin the welcome post"),
    ("can_delete_messages", "Delete messages of others", "nothing: it can already delete its own posts"),
    ("can_change_info", "Change channel info", "set the channel name, description and picture"),
    ("can_invite_users", "Add subscribers", "nothing: no invite links are made"),
    ("can_promote_members", "Add new admins", "nothing"),
    ("can_manage_video_chats", "Manage live streams", "nothing"),
    ("can_post_stories", "Post stories", "nothing"),
    ("can_manage_direct_messages", "Manage direct messages", "nothing"),
]
TEST_NOTE = "Test post from the Morrow Brief bot, checking what it can do here. It is deleted within a minute."
THUMBS_UP = "\U0001F44D"
# What the Bot API has no method for. Stated here so the test report does not leave them out.
NOT_POSSIBLE = [
    "schedule a post inside Telegram (the GitHub workflow's timetable does the scheduling instead)",
    "read the channel's earlier posts or their view counts",
    "see who the subscribers are (only how many)",
    "create the channel or set its public @handle (only the owner can, in the app)",
]
# What the listener asks Telegram to report. The webhook only asks for "message", which is why a channel
# the bot was added to earlier left no trace.
LISTEN_UPDATES = ["message", "channel_post", "my_chat_member"]
LISTEN_POLL_SECONDS = 50
LISTEN_MAX_FAILURES = 8
LISTEN_FEED_REFRESH_SECONDS = 900
SETTLE_ROUNDS = 5
# The word a channel's name must contain before the listener takes it for the Morrow channel.
CHANNEL_NAME_WORD = "morrow"
PUBLIC_PAGE = "https://t.me/s/"  # a public channel's posts as anyone sees them in a browser
SEAL_NONCE_BYTES = 8
SEAL_ID_BYTES = 24
SEAL_CHECK_BYTES = 4


def description(bot_username: str) -> str:
    """The channel's About text: what is posted, where the full edition and the bot are."""
    return "\n".join([
        "Tech and markets, read across the outlets.",
        "Daily at 08:00 Jakarta time: every story linked to its outlet, and stock prices.",
        "",
        f"Full edition: {feed.SITE_SHORT}",
        f"Sections and search: @{bot_username}",
        "",
        "Automated selection. Not financial advice.",
    ])


def welcome(bot_username: str) -> tuple[str, dict]:
    """The pinned post a new visitor reads first, and the two buttons under it."""
    text = "\n".join([
        f"<b>{feed.BRAND}</b>",
        "Tech and markets, read across the outlets.",
        "",
        "<b>What is posted here</b>",
        "• Every morning at 08:00 Jakarta time, one message: the day's stories by section, each with a link to "
        "its outlet, then index and stock prices.",
        f"• An alert when {feed.ALERT_MIN_OUTLETS} or more outlets report the same story.",
        "• Nothing is rewritten. Headlines belong to their outlets.",
        "",
        "<b>Sections and search</b>",
        f"Send @{bot_username} a command: /today, /ai, /markets or /find nvidia. No sign-up, and it keeps no list "
        "of users.",
        "",
        "Automated selection from published reporting. Not financial advice.",
    ])
    buttons = {"inline_keyboard": [[
        {"text": "Read today's edition", "url": feed.SITE_URL},
        {"text": "Open the bot", "url": f"https://t.me/{bot_username}"},
    ]]}
    return text, buttons


def chat_reference(text: str) -> str | None:
    """Turn what a person pastes into what the Bot API accepts.

    '@name', 'name', 't.me/name', 'https://t.me/name/12' become '@name'.
    'https://t.me/c/1234567890/12' (a post link from a private channel) and '-1001234567890' become the id."""
    value = (text or "").strip().strip("<>").rstrip("/")
    value = re.sub(r"^(https?://)?(www\.)?(t|telegram)\.me/", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^s/", "", value)  # the web preview address, t.me/s/name
    private = re.fullmatch(r"c/(\d+)(/\d+)*", value)
    if private:
        return f"-100{private.group(1)}"
    if re.fullmatch(r"-100\d{5,}", value):
        return value
    handle = re.fullmatch(r"@?([A-Za-z][A-Za-z0-9_]{3,31})(/\d+)?", value)
    return f"@{handle.group(1)}" if handle else None


def references(text: str) -> list[str]:
    """Every chat named in a comma, space or line separated list, in order, without repeats."""
    found = []
    for part in re.split(r"[\s,;]+", text or ""):
        reference = chat_reference(part)
        if reference and reference.lower() not in [item.lower() for item in found]:
            found.append(reference)
    return found


def shown(chat: dict) -> str:
    """How a chat is named in the public run log: a public channel by handle, a private one by title only."""
    if chat.get("username"):
        return f"{chat.get('title', '')!r} @{chat['username']} (id {chat.get('id')})"
    return f"{chat.get('title', '')!r} (private, id not shown in a public log)"


def ask(http, token: str, method: str, payload: dict | None = None, files: dict | None = None):
    """One Bot API call. Returns (result, None) or (None, why it failed); the token never reaches the reason."""
    url = f"{bot.TELEGRAM_API}/bot{token}/{method}"
    try:
        if files:
            # An upload is sent as a form, where true must be spelled the way JSON spells it.
            form = {key: json.dumps(value) if isinstance(value, bool) else value
                    for key, value in (payload or {}).items()}
            response = http.post(url, data=form, files=files, timeout=60)
        else:
            response = http.post(url, json=payload or {}, timeout=40)
    except requests.exceptions.RequestException as error:
        return None, f"Telegram unreachable ({type(error).__name__})"
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code == 200 and body.get("ok"):
        return body.get("result"), None
    return None, bot.scrub(str(body.get("description") or response.status_code), token)


def avatar_jpeg() -> bytes:
    import social_cards as cards  # needs Pillow and the bundled fonts, so it is only loaded here

    picture = io.BytesIO()
    cards.render_avatar().save(picture, "JPEG", quality=92)
    return picture.getvalue()


def membership(http, token: str, chat_id: str, bot_id: int) -> tuple[str, dict]:
    """The bot's standing in a chat: ('administrator', its rights), or (another status or the error, {})."""
    member, error = ask(http, token, "getChatMember", {"chat_id": chat_id, "user_id": bot_id})
    if error:
        return error, {}
    return member.get("status", "unknown"), member


def find(http, token: str, candidates: list[str]) -> tuple[list[str], list[dict]]:
    """Ask about each candidate. Returns the log and the chats where the bot is an admin."""
    log: list[str] = []
    me, error = ask(http, token, "getMe")
    if error:
        return [f"getMe failed: {error}"], []
    admin_of = []
    missing = 0
    for candidate in candidates:
        chat, error = ask(http, token, "getChat", {"chat_id": candidate})
        if error:
            if "Too Many Requests" in error:
                log.append(f"Telegram asked for a pause ({error}); stopped before {candidate}")
                break
            missing += 1
            continue
        status, _member = membership(http, token, candidate, me["id"])
        if status == "administrator":
            admin_of.append(chat)
            log.append(f"FOUND: the bot is an admin of {chat.get('type')} {shown(chat)}")
        else:
            log.append(f"{candidate} is a {chat.get('type')} named {chat.get('title', '')!r}, "
                       "and the bot is not an admin there")
    log.append(f"{len(candidates)} names asked, {missing} not found or not visible to the bot, "
               f"{len(admin_of)} with the bot as admin")
    return log, admin_of


def status(http, token: str, chat_id: str) -> tuple[list[str], dict]:
    """What the channel shows and what the bot may do there. Returns the log and the bot's rights."""
    me, error = ask(http, token, "getMe")
    if error:
        return [f"getMe failed: {error}"], {}
    chat, error = ask(http, token, "getChat", {"chat_id": chat_id})
    if error:
        return [f"getChat failed: {error}",
                "The bot cannot see this chat. Check the handle or id, and that the bot is an admin of it."], {}
    log = [f"channel: {chat.get('type')} {shown(chat)}"]
    about = chat.get("description") or ""
    log.append(f"description: {len(about)} characters" + (f", starts {about.splitlines()[0][:70]!r}" if about else ""))
    log.append("picture: " + ("set" if chat.get("photo") else "none"))
    log.append("pinned post: " + ("yes" if chat.get("pinned_message") else "none"))
    log.append("comments (linked group): " + ("on" if chat.get("linked_chat_id") else "off"))
    count, error = ask(http, token, "getChatMemberCount", {"chat_id": chat_id})
    log.append(f"subscribers: {error or count}")
    standing, member = membership(http, token, chat_id, me["id"])
    log.append(f"the bot @{me.get('username')} is: {standing}")
    for key, label, used_for in RIGHTS:
        log.append(f"  {'yes' if member.get(key) else 'no '}  {label} ({used_for})")
    return log, member


def setup(http, token: str, chat_id: str, picture: bytes) -> tuple[list[str], int]:
    """Give the channel its name, description, picture and pinned welcome. Returns the log and the failures."""
    me, error = ask(http, token, "getMe")
    if error:
        return [f"getMe failed: {error}"], 1
    chat, error = ask(http, token, "getChat", {"chat_id": chat_id})
    if error:
        return [f"getChat failed: {error}"], 1
    _standing, member = membership(http, token, chat_id, me["id"])
    log, failed = [f"channel: {shown(chat)}"], 0

    def record(step: str, error: str | None, needs: str | None = None) -> bool:
        nonlocal failed
        if error and "not modified" in error.lower():
            error = None  # already as asked
        if error:
            failed += 1
            hint = ""
            if needs and not member.get(needs):
                label = next(name for key, name, _use in RIGHTS if key == needs)
                hint = f" (the bot lacks the admin right \"{label}\": channel > Administrators > the bot)"
            log.append(f"{step}: FAILED, {error}{hint}")
        else:
            log.append(f"{step}: done")
        return not error

    about = description(me["username"])
    if chat.get("title") == TITLE:
        log.append("name: already " + repr(TITLE))
    else:
        record("name", ask(http, token, "setChatTitle", {"chat_id": chat_id, "title": TITLE})[1], "can_change_info")
    if (chat.get("description") or "") == about:
        log.append("description: already set")
    else:
        record("description", ask(http, token, "setChatDescription",
                                  {"chat_id": chat_id, "description": about})[1], "can_change_info")
    record("picture", ask(http, token, "setChatPhoto", {"chat_id": chat_id},
                          files={"photo": ("morrow-brief.jpg", picture, "image/jpeg")})[1], "can_change_info")

    text, buttons = welcome(me["username"])
    pinned = chat.get("pinned_message") or {}
    if (pinned.get("text") or "").startswith(feed.BRAND + "\n"):
        # The welcome is already pinned: bring its wording up to date instead of posting a second one.
        record("welcome post (updated in place)", ask(http, token, "editMessageText", {
            "chat_id": chat_id, "message_id": pinned["message_id"], "text": text, "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True}, "reply_markup": buttons,
        })[1])
        return log, failed
    post, error = ask(http, token, "sendMessage", {
        "chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_notification": True,
        "link_preview_options": {"is_disabled": True}, "reply_markup": buttons,
    })
    if record("welcome post", error, "can_post_messages"):
        record("pin the welcome post", ask(http, token, "pinChatMessage", {
            "chat_id": chat_id, "message_id": post["message_id"], "disable_notification": True,
        })[1], "can_edit_messages")
    return log, failed


def test(http, token: str, chat_id: str, picture: bytes, sleep=time.sleep) -> tuple[list[str], int]:
    """Try each thing the bot might do in the channel, silently, then delete what it posted.

    Returns the log and how many of the two things the daily brief depends on (post, delete) failed."""
    log: list[str] = []
    posted: list[int] = []
    outcome: dict[str, bool] = {}

    def attempt(label: str, method: str, payload: dict | None = None, files: dict | None = None):
        result, error = ask(http, token, method, payload, files)
        outcome[label] = error is None
        log.append(f"{'PASS' if error is None else 'FAIL'}  {label}" + (f": {error}" if error else ""))
        for message in result if isinstance(result, list) else [result]:
            if isinstance(message, dict) and "message_id" in message:
                posted.append(message["message_id"])
        sleep(1)
        return result

    quiet = {"chat_id": chat_id, "disable_notification": True}
    first = attempt("post text with a link button, without a notification", "sendMessage", {
        **quiet, "text": TEST_NOTE, "link_preview_options": {"is_disabled": True},
        "reply_markup": {"inline_keyboard": [[{"text": "Read today's edition", "url": feed.SITE_URL}]]},
    })
    if first:
        attempt("edit its own post", "editMessageText", {
            "chat_id": chat_id, "message_id": first["message_id"], "text": TEST_NOTE + " (edited)",
        })
        attempt("react to a post", "setMessageReaction", {
            "chat_id": chat_id, "message_id": first["message_id"],
            "reaction": [{"type": "emoji", "emoji": THUMBS_UP}],
        })
    attempt("post a picture with a caption", "sendPhoto", {**quiet, "caption": TEST_NOTE},
            files={"photo": ("test.jpg", picture, "image/jpeg")})
    album = [{"type": "photo", "media": "attach://one", "caption": TEST_NOTE}, {"type": "photo", "media": "attach://two"}]
    attempt("post an album of two pictures", "sendMediaGroup", {**quiet, "media": json.dumps(album)},
            files={"one": ("one.jpg", picture, "image/jpeg"), "two": ("two.jpg", picture, "image/jpeg")})
    attempt("post a poll", "sendPoll", {
        **quiet, "question": "Test poll from the Morrow Brief bot. It is deleted within a minute.",
        "options": [{"text": "Option one"}, {"text": "Option two"}],
    })
    attempt("read the subscriber count", "getChatMemberCount", {"chat_id": chat_id})
    attempt("read the list of admins", "getChatAdministrators", {"chat_id": chat_id})

    left = list(posted)
    if posted:
        _result, error = ask(http, token, "deleteMessages", {"chat_id": chat_id, "message_ids": posted})
        if error:
            # Fall back to one at a time, so a single refusal does not leave every test post behind.
            left = [number for number in posted
                    if ask(http, token, "deleteMessage", {"chat_id": chat_id, "message_id": number})[1]]
        else:
            left = []
        outcome["delete"] = not left
        log.append(f"{'PASS' if not left else 'FAIL'}  delete its own posts: {len(posted) - len(left)} of "
                   f"{len(posted)} test posts removed"
                   + (f"; still in the channel, to delete by hand: post numbers {left}" if left else ""))
    for limit in NOT_POSSIBLE:
        log.append(f"NO    {limit}: Telegram gives bots no way to do this")
    needed = [outcome.get("post text with a link button, without a notification", False), outcome.get("delete", False)]
    log.append(f"{sum(outcome.values())} of {len(outcome)} checks passed")
    return log, needed.count(False)


def view(http, handle: str, count: int = 5) -> tuple[list[str], int]:
    """What the channel's newest posts look like on its public page. Returns the lines and how many posts it saw.

    It needs no token: this is the page any reader gets. A run uses it to check that the digest arrived
    as one message and whether Telegram attached the cover card to it.
    """
    try:
        response = http.get(PUBLIC_PAGE + handle, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    except requests.exceptions.RequestException as error:
        return [f"the public page of @{handle} could not be read ({type(error).__name__})"], 0
    if response.status_code != 200:
        return [f"the public page of @{handle} answered HTTP {response.status_code}"], 0
    posts = feed.BeautifulSoup(response.text, "html.parser").select(".tgme_widget_message[data-post]")
    if not posts:
        return [f"no posts on the public page of @{handle}: the channel is private or empty, or the page changed"], 0
    lines = [f"@{handle}: the public page shows {len(posts)} posts, the newest {min(count, len(posts))} are:"]
    for post in posts[-count:]:
        body = post.select_one(".tgme_widget_message_text")
        moment = post.select_one("time[datetime]")
        if post.select_one(".tgme_widget_message_photo_wrap, .tgme_widget_message_video_player"):
            picture = "sent as a photo"
        elif post.select_one(".link_preview_image, .link_preview_right_image"):
            picture = "link preview with a picture"
        elif post.select_one(".tgme_widget_message_link_preview"):
            picture = "link preview without a picture"
        else:
            picture = "no picture"
        lines.append(
            f"post {post['data-post'].rsplit('/', 1)[-1]} · {moment['datetime'] if moment else 'no time'} · "
            f"{len(body.get_text()) if body else 0} characters, {len(body.select('a[href]')) if body else 0} links · "
            f"{picture}"
        )
    return lines, len(posts)


METRICS_HEADER = "date,subscribers,posts_counted,median_views,views_per_100_subscribers"
JAKARTA = timezone(timedelta(hours=7))
SETTLED_AFTER = timedelta(days=1)  # a newer post is still collecting views
SETTLED_UNTIL = timedelta(days=8)


def view_count(shown_text: str) -> int | None:
    """A view counter as the public page prints it: 78, 1.2K or 3.4M."""
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([KM]?)", shown_text.strip(), re.IGNORECASE)
    if not match:
        return None
    return round(float(match.group(1)) * {"": 1, "K": 1_000, "M": 1_000_000}[match.group(2).upper()])


def post_views(http, handle: str) -> tuple[list[tuple[datetime, int]], str | None]:
    """When each post on the public page was sent and the views it shows. Returns the posts, or why there are none."""
    try:
        response = http.get(PUBLIC_PAGE + handle, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    except requests.exceptions.RequestException as error:
        return [], f"the public page of @{handle} could not be read ({type(error).__name__})"
    if response.status_code != 200:
        return [], f"the public page of @{handle} answered HTTP {response.status_code}"
    posts = []
    for post in feed.BeautifulSoup(response.text, "html.parser").select(".tgme_widget_message[data-post]"):
        moment = post.select_one("time[datetime]")
        counter = post.select_one(".tgme_widget_message_views")
        views = view_count(counter.get_text()) if counter else None
        if not moment or views is None:
            continue
        try:
            posts.append((datetime.fromisoformat(moment["datetime"]), views))
        except ValueError:
            continue
    return posts, None if posts else f"no posts with a view counter on the public page of @{handle}"


def metrics_row(now: datetime, subscribers: int, posts: list[tuple[datetime, int]]) -> str:
    """One day's line. Only posts between one and eight days old are counted, so the views have settled."""
    settled = [views for sent, views in posts if SETTLED_AFTER <= now - sent <= SETTLED_UNTIL]
    typical = statistics.median(settled) if settled else None
    share = round(100 * typical / subscribers) if settled and subscribers else None
    cells = [now.astimezone(JAKARTA).date().isoformat(), subscribers, len(settled), typical, share]
    return ",".join("" if cell is None else f"{cell:g}" if isinstance(cell, float) else str(cell) for cell in cells)


def record(path: Path, row: str) -> None:
    """Keep one line a day: a later reading on the same day replaces the earlier one."""
    day = row.split(",", 1)[0]
    kept = []
    if path.exists():
        kept = [line for line in path.read_text(encoding="utf-8").splitlines()[1:]
                if line and not line.startswith(day + ",")]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([METRICS_HEADER, *kept, row]) + "\n", encoding="utf-8")


def metrics(http, token: str, chat_id: str, now: datetime) -> tuple[list[str], str | None]:
    """Today's subscriber count and typical views. Returns the log and the line, or no line if it failed."""
    count, error = ask(http, token, "getChatMemberCount", {"chat_id": chat_id})
    if error:
        return [f"subscribers could not be read: {error}"], None
    chat, _error = ask(http, token, "getChat", {"chat_id": chat_id})
    handle = (chat or {}).get("username")
    if handle:
        posts, why = post_views(http, handle)
    else:
        posts, why = [], "the channel has no public page"
    row = metrics_row(now, count, posts)
    log = [METRICS_HEADER, row]
    if why:
        log.append(f"views not read: {why}")
    return log, row


def target(args) -> str | None:
    """The chat a command acts on: --chat, or else TELEGRAM_CHAT_ID."""
    return chat_reference(args.chat or "") or chat_reference(os.environ.get("TELEGRAM_CHAT_ID") or "")


def _seal_pad(key: str, nonce: bytes) -> bytes:
    return hmac.new(key.encode(), b"pad" + nonce, hashlib.sha256).digest()[:SEAL_ID_BYTES]


def _seal_check(key: str, body: bytes) -> bytes:
    return hmac.new(key.encode(), b"check" + body, hashlib.sha256).digest()[:SEAL_CHECK_BYTES]


def seal(chat_id, key: str) -> str:
    """Hide a private channel's id so it can pass through a public run log. Only the key opens it.

    The id is padded to a fixed length and mixed with a one-time pad made from the key and a fresh nonce,
    so two seals of the same id look unrelated and the length says nothing."""
    nonce = os.urandom(SEAL_NONCE_BYTES)
    plain = str(chat_id).encode().ljust(SEAL_ID_BYTES)
    hidden = bytes(a ^ b for a, b in zip(plain, _seal_pad(key, nonce)))
    return (nonce + hidden + _seal_check(key, nonce + hidden)).hex()


def unseal(sealed: str, key: str) -> str | None:
    """The id inside a seal, or None when the text is not a seal made with this key."""
    try:
        raw = bytes.fromhex((sealed or "").strip())
    except ValueError:
        return None
    if len(raw) != SEAL_NONCE_BYTES + SEAL_ID_BYTES + SEAL_CHECK_BYTES:
        return None
    body, check = raw[:-SEAL_CHECK_BYTES], raw[-SEAL_CHECK_BYTES:]
    if not hmac.compare_digest(check, _seal_check(key, body)):
        return None
    nonce, hidden = body[:SEAL_NONCE_BYTES], body[SEAL_NONCE_BYTES:]
    return bytes(a ^ b for a, b in zip(hidden, _seal_pad(key, nonce))).decode().strip()


def channel_in(update: dict) -> dict | None:
    """The channel an update came from or points to, if any.

    A post in the channel, a change to the bot's place in it, or one of its posts forwarded to the bot."""
    message = update.get("message") or {}
    places = [
        (update.get("channel_post") or {}).get("chat"),
        (update.get("my_chat_member") or {}).get("chat"),
        (message.get("forward_origin") or {}).get("chat"),
        message.get("forward_from_chat"),
    ]
    for chat in places:
        if isinstance(chat, dict) and chat.get("type") == "channel" and "id" in chat:
            return chat
    return None


def say_now(line: str) -> None:
    """Print without waiting for the buffer: a run that waits for hours must show its first line at once."""
    print(line, flush=True)


def listen(http, token: str, feed_data: dict, seconds: int, say=say_now, clock=time.monotonic,
           sleep=time.sleep, refresh=None) -> tuple[dict | None, int | None]:
    """Take over from the webhook and wait for the Morrow channel to show itself.

    While it waits it answers the bot's messages, as the Worker would. Returns the channel (or None when
    the time is up) and the offset to hand to `settle`. Other chats are counted, never named."""
    me, error = ask(http, token, "getMe")
    if error:
        say(f"getMe failed: {error}")
        return None, None
    _result, error = ask(http, token, "deleteWebhook", {"drop_pending_updates": False})
    if error:
        say(f"deleteWebhook failed: {error}")
        return None, None
    say(f"listening as @{me.get('username')} for up to {seconds // 60} minutes. The webhook is off: this run "
        "answers the bot's messages until it hands back.")
    say(f"waiting for a channel with \"{CHANNEL_NAME_WORD}\" in its name where the bot is an admin: post "
        "anything in it, change the bot's admin rights, or forward one of its posts to the bot")
    offset: int | None = None
    found: dict | None = None
    answered = ignored = failures = 0
    started = clock()
    deadline = started + seconds
    refreshed = started
    while found is None and clock() < deadline:
        if refresh and clock() - refreshed >= LISTEN_FEED_REFRESH_SECONDS:
            refreshed = clock()
            newer = refresh()
            if newer:
                feed_data.clear()
                feed_data.update(newer)
        wait = max(1, min(LISTEN_POLL_SECONDS, int(deadline - clock())))
        payload = {"timeout": wait, "allowed_updates": LISTEN_UPDATES}
        if offset is not None:
            payload["offset"] = offset
        try:
            status, body = bot.call(http, token, "getUpdates", payload, timeout=wait + 20)
            reason = bot.scrub(str(body.get("description") or status), token)
        except requests.exceptions.RequestException as problem:
            status, body, reason = 0, {}, f"Telegram unreachable ({type(problem).__name__})"
        if status == 409:
            say(f"stopped: something else is reading the bot's messages ({reason})")
            break
        if status != 200 or not body.get("ok"):
            failures += 1
            if failures >= LISTEN_MAX_FAILURES:
                say(f"stopped after {failures} failed calls in a row: {reason}")
                break
            sleep(min(60, 15 * failures))
            continue
        failures = 0
        for update in body.get("result") or []:
            # Move the offset first: an update that cannot be handled is skipped, never retried forever.
            offset = update["update_id"] + 1
            chat = channel_in(update)
            if chat:
                named = CHANNEL_NAME_WORD in (chat.get("title") or "").casefold()
                if named and membership(http, token, chat["id"], me["id"])[0] == "administrator":
                    found = chat
                    break
                ignored += 1
            try:
                line = bot.answer(http, token, feed_data, update)
            except requests.exceptions.RequestException:
                line = None
            answered += bool(line and line.startswith("answered"))
    say(f"{answered} messages answered while listening, {ignored} updates from other channels ignored")
    say(f"FOUND: the bot is an admin of {shown(found)}" if found else "no Morrow channel showed itself in this round")
    return found, offset


def settle(http, token: str, feed_data: dict, offset: int | None) -> int:
    """Answer what arrived since `listen` stopped and tell Telegram which updates are dealt with.

    Without this the Worker would be handed messages that were already answered. Returns the answers sent."""
    answered = 0
    if offset is None:
        return answered
    for _round in range(SETTLE_ROUNDS):
        try:
            status, body = bot.call(http, token, "getUpdates", {
                "timeout": 0, "offset": offset, "allowed_updates": LISTEN_UPDATES,
            }, timeout=20)
        except requests.exceptions.RequestException:
            return answered
        updates = body.get("result") or []
        if status != 200 or not body.get("ok") or not updates:
            return answered
        for update in updates:
            offset = update["update_id"] + 1
            try:
                line = bot.answer(http, token, feed_data, update)
            except requests.exceptions.RequestException:
                line = None
            answered += bool(line and line.startswith("answered"))
    # Still busy: acknowledge what was answered. The one update this call returns is left for the Worker.
    try:
        bot.call(http, token, "getUpdates", {
            "timeout": 0, "limit": 1, "offset": offset, "allowed_updates": LISTEN_UPDATES,
        }, timeout=20)
    except requests.exceptions.RequestException:
        pass
    return answered


def fetched_feed(http, url: str) -> dict | None:
    """Today's feed from where the publisher puts it, or None when it cannot be read just now."""
    try:
        response = http.get(url, timeout=30)
        return response.json() if response.status_code == 200 else None
    except (requests.exceptions.RequestException, ValueError):
        return None


def run_listen(args, token: str) -> int:
    path = Path(args.feed)
    feed_data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    refresh = (lambda: fetched_feed(requests, args.feed_url)) if args.feed_url else None
    chat, offset = listen(requests, token, feed_data, args.seconds, refresh=refresh)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"found={'true' if chat else 'false'}\n")
    if not chat:
        settle(requests, token, feed_data, offset)
        return 0
    chat_id = str(chat["id"])
    key = (os.environ.get("CHANNEL_HANDOFF_KEY") or "").strip()
    say_now("sealed id: " + seal(chat_id, key) if key
            else "CHANNEL_HANDOFF_KEY is not set, so the channel's id is not handed over")
    picture = avatar_jpeg()
    failed = 0
    say_now("--- setup ---")
    log, problems = setup(requests, token, chat_id, picture)
    say_now("\n".join(log))
    failed += problems
    say_now("--- test ---")
    log, problems = test(requests, token, chat_id, picture, sleep=time.sleep)
    say_now("\n".join(log))
    failed += problems
    say_now("--- status ---")
    say_now("\n".join(status(requests, token, chat_id)[0]))
    settle(requests, token, feed_data, offset)
    return 1 if failed else 0


def run(args) -> int:
    if args.command == "view":
        named = chat_reference(args.chat or "") or ""
        handle = named[1:] if named.startswith("@") else feed.CHANNEL_URL.rsplit("/", 1)[-1]
        log, seen = view(requests, handle)
        print("\n".join(log))
        return 0 if seen else 1
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN first.")
        return 1
    if args.command == "listen":
        return run_listen(args, token)
    if args.command == "find":
        candidates = references(args.chat or "") or [f"@{handle}" for handle in LIKELY_HANDLES]
        log, admin_of = find(requests, token, candidates)
        print("\n".join(log))
        if not admin_of:
            print("Not found. A bot cannot list its own chats: give the channel's @handle, or the link of any "
                  "post in it (open the post's menu and choose Copy link), as the chat input.")
        return 0 if admin_of else 1
    chat_id = target(args)
    if not chat_id:
        print("No channel given. Pass --chat with its @handle or a post link, or set TELEGRAM_CHAT_ID.")
        return 1
    if args.command == "metrics":
        log, row = metrics(requests, token, chat_id, datetime.now(timezone.utc))
        print("\n".join(log))
        if row and args.out:
            record(Path(args.out), row)
            print(f"saved to {args.out}")
        return 0 if row else 1
    if args.command == "status":
        log, member = status(requests, token, chat_id)
        print("\n".join(log))
        return 0 if member.get("status") == "administrator" else 1
    if args.command == "setup":
        log, failed = setup(requests, token, chat_id, avatar_jpeg())
    else:
        log, failed = test(requests, token, chat_id, avatar_jpeg(), sleep=time.sleep)
    print("\n".join(log))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["find", "status", "setup", "test", "listen", "view", "metrics"])
    parser.add_argument("--chat", default="", help="@handle, t.me link, post link or numeric id")
    parser.add_argument("--feed", default="data/feed.json", help="listen: the feed its answers come from")
    parser.add_argument("--feed-url", default="", help="listen: where to re-read the feed while waiting")
    parser.add_argument("--seconds", type=int, default=600, help="listen: how long to wait for the channel")
    parser.add_argument("--out", default="", help="metrics: the file that keeps one line a day")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
