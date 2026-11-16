"""Morrow Brief: the Telegram channel the bot posts to.

    python scripts/social_channel.py find --chat "@handle, t.me/handle/12, t.me/c/1234567890/12"
    python scripts/social_channel.py status --chat @handle   (what the channel shows, what the bot may do)
    python scripts/social_channel.py setup --chat @handle    (name, description, picture, pinned welcome)
    python scripts/social_channel.py test --chat @handle     (posts, edits, reacts, then deletes its posts)

Without --chat the commands use TELEGRAM_CHAT_ID. A bot cannot list the chats it is in, so `find` asks
Telegram about each name it is given, or about the likely Morrow Brief handles, and reports where the bot
is an admin. Run logs are public: a private channel's id is never printed.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time

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


def description(bot_username: str) -> str:
    """The channel's About text: what is posted, where the full edition and the bot are."""
    return "\n".join([
        "Tech and markets, read across the outlets.",
        f"One brief a day: the {feed.DIGEST_SIZE} stories that matter, each linked to its source. "
        "Nothing rewritten.",
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
        f"• One brief a day: the {feed.DIGEST_SIZE} stories that matter across AI and chips, big tech, robotics, "
        "space, technology and markets.",
        f"• An alert when {feed.ALERT_MIN_OUTLETS} or more outlets report the same story.",
        "• Every headline links to the outlet that reported it. Nothing is rewritten.",
        "",
        "<b>Want one section, or a search?</b>",
        f"Ask @{bot_username}: /today, /ai, /markets, or /find nvidia. No sign-up, and it keeps no list of users.",
        "",
        "Automated selection from published reporting. Not financial advice.",
    ])
    buttons = {"inline_keyboard": [[
        {"text": "Read today's edition", "url": feed.SITE_URL},
        {"text": "Ask the bot", "url": f"https://t.me/{bot_username}"},
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


def target(args) -> str | None:
    """The chat a command acts on: --chat, or else TELEGRAM_CHAT_ID."""
    return chat_reference(args.chat or "") or chat_reference(os.environ.get("TELEGRAM_CHAT_ID") or "")


def run(args) -> int:
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        print("Set TELEGRAM_BOT_TOKEN first.")
        return 1
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
    if args.command == "status":
        log, member = status(requests, token, chat_id)
        print("\n".join(log))
        return 0 if member.get("status") == "administrator" else 1
    if args.command == "setup":
        log, failed = setup(requests, token, chat_id, avatar_jpeg())
    else:
        log, failed = test(requests, token, chat_id, avatar_jpeg())
    print("\n".join(log))
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["find", "status", "setup", "test"])
    parser.add_argument("--chat", default="", help="@handle, t.me link, post link or numeric id")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
