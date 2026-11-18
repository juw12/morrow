"""Morrow Brief: decide what to post, freeze it, and deliver it.

    python scripts/social_post.py hold
    python scripts/social_post.py build    --page index.html --out data --run <run id>
    python scripts/social_post.py deliver  --out data --run <run id> --image-base https://raw.githubusercontent.com/<repo>/<sha>/
    python scripts/social_post.py preview  --page index.html --out preview
    python scripts/social_post.py sample   --page index.html --out sample
    python scripts/social_post.py channels

`build` reads the published page, picks at most one new post (the day's digest, or one alert), renders
its cards and freezes it in state.json. `deliver` sends every frozen post that is still pending:
Telegram through the Bot API, Instagram, Threads and X through Buffer. With no credentials nothing is
sent and the targets are recorded as skipped, so the workflow is safe to merge before any account exists.

On Telegram the digest is ONE message: every story on the page as a linked headline with its outlet,
summaries for the most reported stories, the indexes and every stock of the page's analysis table. The
cover is shown above the text as the message's link preview. An alert is the story's card with a caption.

Pictures: `build` fetches the outlets' own pictures for the day's stories. With 4 or more of them the
Telegram cover is a photo grid, each tile numbered as its story is in the message and credited to its
outlet; an alert whose story has a picture gets a photo card. A picture that cannot be fetched is left
out, and with too few the text card is used, so a post never waits for or fails on a picture.

Nothing is posted before 08:00 Jakarta time. `hold` is what makes the digest land at 08:00: a run that
starts between 07:00 and 08:00 waits there until the window opens, any other run does not wait.

`sample` posts the digest the page gives to the Telegram channel at once, without a notification and
without touching state.json. It is started by hand, to see the real post in the real channel.

The workflow saves state.json between the two commands. `build --run` marks every target it is about to
send as `sending` for that run, so a run that dies after sending but before saving the result can never
cause a second send: the next run finds the stale mark and records the target as unconfirmed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import io
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path

import requests
from PIL import Image

import social_cards as cards
import social_feed as feed

WIB = dt.timezone(dt.timedelta(hours=7), "WIB")
WINDOW_START_HOUR = 8
WINDOW_END_HOUR = 22
HOLD_LEAD = dt.timedelta(hours=1)
HOLD_MARGIN_SECONDS = 2
MAX_ALERTS_PER_DAY = 4
ALERT_GAP = dt.timedelta(minutes=90)
MIN_DIGEST_STORIES = 3
MAX_ATTEMPTS = 3
MAX_POST_AGE = dt.timedelta(hours=3)
KEEP_DAYS = 7
TARGETS = ("telegram", "instagram", "threads", "x")
BUFFER_SERVICES = {"instagram": "instagram", "threads": "threads", "twitter": "x", "x": "x"}
BUFFER_API = "https://api.buffer.com"
TELEGRAM_API = "https://api.telegram.org"
WAITING_STATUSES = ("pending", "failed")
PHOTO_TRIES = 14  # pictures asked for at most, for one cover
PHOTO_SECONDS = 75  # ... and the time all of them may take together
PHOTO_MAX_BYTES = 8_000_000
PHOTO_MIN_SIZE = (400, 220)
PHOTO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MorrowBrief/1.0; +https://juw12.github.io/morrow/)",
    "Accept": "image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8",
}
STALE_CLAIM = "an earlier run started sending and never recorded the result"
CREATE_POST = """
mutation CreatePost($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}
"""


class Retryable(Exception):
    """The post was definitely not published. Safe to try again on a later run."""


class Unconfirmed(Exception):
    """The request may have gone through. Trying again could publish twice, so it is not retried."""


class NotConfigured(Exception):
    """No credential or no allowed channel for this target."""


# --------------------------------------------------------------------------- state


def empty_state() -> dict:
    return {"version": 1, "days": {}, "posts": {}}


def load_state(path: Path) -> dict:
    if not path.exists():
        return empty_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        # A corrupt state must not cause a second digest: stop instead of starting from nothing.
        raise SystemExit(f"{path} is not valid JSON. Fix or delete it by hand; refusing to post blind.")
    for key, value in empty_state().items():
        state.setdefault(key, value)
    return state


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def day_record(state: dict, date_iso: str) -> dict:
    return state["days"].setdefault(date_iso, {"digest": None, "alerts": [], "used": [], "last_post_at": None})


def prune(state: dict, out_dir: Path, today: dt.date) -> None:
    """Drop state and card folders older than KEEP_DAYS, so the repo does not grow without limit."""
    cutoff = today - dt.timedelta(days=KEEP_DAYS)

    def is_old(date_iso: str) -> bool:
        try:
            return dt.date.fromisoformat(date_iso) < cutoff
        except ValueError:
            return False

    for date_iso in [key for key in state["days"] if is_old(key)]:
        del state["days"][date_iso]
    for post_id in [key for key, post in state["posts"].items() if is_old(post.get("date", ""))]:
        del state["posts"][post_id]
    cards_dir = out_dir / "cards"
    if cards_dir.is_dir():
        for folder in cards_dir.iterdir():
            if folder.is_dir() and is_old(folder.name):
                shutil.rmtree(folder)


# --------------------------------------------------------------------------- planning


def parse_now(value: str | None) -> dt.datetime:
    if not value:
        return dt.datetime.now(dt.timezone.utc)
    moment = dt.datetime.fromisoformat(value)
    return moment if moment.tzinfo else moment.replace(tzinfo=WIB)


def hold_seconds(now: dt.datetime) -> int:
    """Seconds to wait so that a run started in the hour before the window opens posts as it opens.

    A run that starts earlier than that, or once the window is open, does not wait.
    """
    local = now.astimezone(WIB)
    opens = local.replace(hour=WINDOW_START_HOUR, minute=0, second=0, microsecond=0)
    wait = opens - local
    if dt.timedelta(0) < wait <= HOLD_LEAD:
        return math.ceil(wait.total_seconds()) + HOLD_MARGIN_SECONDS
    return 0


def plan(edition: dict, state: dict, now: dt.datetime) -> tuple[dict | None, str]:
    """Return (the one post to freeze now, or None) and the reason, as plain words for the log."""
    local = now.astimezone(WIB)
    if not edition["date"]:
        return None, "the page has no readable date"
    if edition["date"] != local.date().isoformat():
        return None, f"the page is dated {edition['date']} but today is {local.date()} (stale page, nothing posted)"
    if not WINDOW_START_HOUR <= local.hour < WINDOW_END_HOUR:
        return None, f"{local:%H:%M} WIB is outside the {WINDOW_START_HOUR:02d}:00-{WINDOW_END_HOUR:02d}:00 window"
    record = day_record(state, edition["date"])
    if not record["digest"]:
        stories = feed.pick_digest(edition["stories"])
        if len(stories) < MIN_DIGEST_STORIES:
            return None, f"only {len(stories)} stories on the page, a digest needs {MIN_DIGEST_STORIES}"
        post = feed.digest_post(stories, edition["markets"], edition["date"], edition)
        return post, "first run of the day in the window"
    if len(record["alerts"]) >= MAX_ALERTS_PER_DAY:
        return None, f"the day's {MAX_ALERTS_PER_DAY} alerts are used"
    if record["last_post_at"]:
        since = now - dt.datetime.fromisoformat(record["last_post_at"])
        if since < ALERT_GAP:
            return None, f"last post was {int(since.total_seconds() // 60)} min ago, alerts wait {ALERT_GAP.seconds // 60}"
    candidates = feed.alert_candidates(edition["stories"], set(record["used"]))
    if not candidates:
        return None, f"no unused story is reported by {feed.ALERT_MIN_OUTLETS} or more outlets"
    story = candidates[0]
    return feed.story_post(story, edition["date"]), f"{story['coverage']} outlets report it and it has not been posted"


def freeze(state: dict, post: dict, now: dt.datetime) -> dict:
    """Record the post exactly as it will be sent. A frozen post is never rebuilt or re-selected."""
    if post["id"] in state["posts"]:
        return state["posts"][post["id"]]
    record = day_record(state, post["date"])
    overlap = set(post["story_ids"]) & set(record["used"])
    if overlap:
        raise ValueError(f"story already posted today: {sorted(overlap)}")
    frozen = dict(post)
    frozen["created_at"] = now.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
    frozen["targets"] = {target: {"status": "pending", "attempts": 0} for target in TARGETS}
    state["posts"][post["id"]] = frozen
    record["used"] += post["story_ids"]
    record["last_post_at"] = frozen["created_at"]
    if post["kind"] == "digest":
        record["digest"] = post["id"]
    else:
        record["alerts"].append(post["id"])
    return frozen


# --------------------------------------------------------------------------- payloads


def fetch_picture(http, url: str) -> Image.Image | None:
    """One outlet picture as an RGB image, or None: any refusal, timeout, odd file or small picture is a no."""
    try:
        response = http.get(url, timeout=15, headers=PHOTO_HEADERS, stream=True)
        if response.status_code != 200:
            return None
        data = b""
        for chunk in response.iter_content(65536):
            data += chunk
            if len(data) > PHOTO_MAX_BYTES:
                return None
        picture = Image.open(io.BytesIO(data))
        picture.load()
        picture = picture.convert("RGB")
    except Exception:  # noqa: BLE001 - a picture is optional, whatever went wrong
        return None
    if picture.width < PHOTO_MIN_SIZE[0] or picture.height < PHOTO_MIN_SIZE[1]:
        return None
    return picture


def telegram_picture(post: dict) -> str:
    """The picture Telegram shows with a post: its photo card when one was drawn, else its text card."""
    return post.get("telegram_cover") or post["cards"][0]


def attach_pictures(post: dict, edition: dict, out_dir: Path, http=requests, clock=time.monotonic) -> str:
    """Draw the post's photo card from the outlets' pictures and note it in the post. Returns a line for the log.

    Never raises and never blocks a post: with too few pictures the post keeps its text card."""
    try:
        by_id = {story["id"]: story for story in edition["stories"]}
        if post["kind"] == "digest":
            if not post.get("telegram_edition"):
                return ""
            relative = f"cards/{post['date']}/digest-photos.jpg"
            if (out_dir / relative).exists():
                post["telegram_cover"] = relative
                return "photo cover: already drawn"
            numbers = feed.edition_numbers(post["telegram_edition"])
            candidates = [story for story in feed.ranked(edition["stories"])
                          if story.get("image") and story["url"] in numbers]
            wanted = max(cards.PHOTO_GRIDS)
            deadline = clock() + PHOTO_SECONDS
            tiles, asked, used = [], 0, set()
            for story in candidates[:PHOTO_TRIES]:
                if len(tiles) >= wanted or clock() > deadline:
                    break
                if story["image"] in used:
                    continue
                used.add(story["image"])
                asked += 1
                picture = fetch_picture(http, story["image"])
                if picture:
                    tiles.append({"number": numbers[story["url"]], "title": story["title"],
                                  "source": story["source"], "picture": picture})
            size = next((count for count in sorted(cards.PHOTO_GRIDS, reverse=True) if len(tiles) >= count), 0)
            if not size:
                return (f"photo cover: not drawn, {len(tiles)} of {asked} pictures could be fetched "
                        f"({len(candidates)} stories have one) and a cover needs {min(cards.PHOTO_GRIDS)}")
            tiles = sorted(tiles[:size], key=lambda tile: tile["number"])
            cards.render_photo_cover(tiles, post["date"], len(edition["stories"]),
                                     feed.outlet_total(edition["stories"]), out_dir / relative)
            post["telegram_cover"] = relative
            listed = ", ".join(str(tile["number"]) for tile in tiles)
            return f"photo cover: {size} pictures (stories {listed}), {asked} asked for"
        story = by_id.get(post["story_ids"][0]) if post.get("story_ids") else None
        if not story or not story.get("image"):
            return "photo card: the page shows no picture for this story"
        relative = f"cards/{post['date']}/{story['id']}-photo.jpg"
        if not (out_dir / relative).exists():
            picture = fetch_picture(http, story["image"])
            if not picture:
                return "photo card: the picture could not be fetched, the text card is used"
            cards.render_story_photo_card(story, picture, post["date"], out_dir / relative)
        post["telegram_cover"] = relative
        return "photo card: drawn with the outlet's picture"
    except Exception as error:  # noqa: BLE001 - pictures are optional
        post.pop("telegram_cover", None)
        return f"pictures: skipped ({type(error).__name__})"


def image_assets(post: dict, image_base: str, count: int | None = None) -> list[dict]:
    pairs = list(zip(post["cards"], post["alts"]))[:count]
    return [{"image": {"url": image_base + card, "metadata": {"altText": alt}}} for card, alt in pairs]


def buffer_input(post: dict, target: str, channel_id: str, image_base: str) -> dict:
    """The CreatePostInput for one target. Shapes follow Buffer's introspected schema (docs/SOCIAL.md)."""
    payload = {
        "channelId": channel_id,
        "mode": "shareNow",
        "schedulingType": "automatic",
        "needsApproval": False,
        "source": "morrow-brief",
    }
    if target == "instagram":
        assets = image_assets(post, image_base, 10)
        payload["text"] = post["instagram"]
        payload["assets"] = assets
        payload["metadata"] = {
            "instagram": {"type": "carousel" if len(assets) > 1 else "post", "shouldShareToFeed": True}
        }
    elif target == "threads":
        payload["text"] = post["threads"]
        payload["assets"] = image_assets(post, image_base, 1)
    elif target == "x":
        cover = image_assets(post, image_base, 1)
        payload["text"] = post["x"][0]
        payload["assets"] = cover
        if len(post["x"]) > 1:
            payload["metadata"] = {
                "twitter": {
                    "thread": [
                        {"text": text, "assets": cover if index == 0 else []}
                        for index, text in enumerate(post["x"])
                    ]
                }
            }
    else:
        raise ValueError(f"not a Buffer target: {target}")
    return payload


def telegram_fields(post: dict, chat_id: str) -> dict:
    return {
        "chat_id": chat_id,
        "caption": post["telegram"],
        "parse_mode": "HTML",
        # One notification a day: the digest pings, alerts arrive silently.
        "disable_notification": "false" if post["kind"] == "digest" else "true",
    }


def telegram_edition_fields(post: dict, chat_id: str, image_base: str | None) -> dict:
    """The digest as one message: the whole edition, with the cover card above the text as its link preview.

    A photo's caption holds 1,024 characters and a message 4,096, so the card rides along as the preview
    of its public URL. With no public URL for the card the message goes out without a picture.
    """
    if image_base:
        preview = {"url": image_base + telegram_picture(post), "prefer_large_media": True, "show_above_text": True}
    else:
        preview = {"is_disabled": True}
    return {
        "chat_id": chat_id,
        "text": post["telegram_edition"],
        "parse_mode": "HTML",
        "disable_notification": "false",
        "link_preview_options": json.dumps(preview),
    }


# --------------------------------------------------------------------------- delivery


def scrub(text: str, secrets: list[str]) -> str:
    """Never let a credential reach a log, the state file or an error message."""
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot***", text)[:300]


def buffer_graphql(http, api_key: str, query: str, variables: dict, is_mutation: bool = False) -> dict:
    try:
        response = http.post(
            BUFFER_API,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"query": query, "variables": variables},
            timeout=45,
        )
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as error:
        raise Retryable(f"Buffer unreachable ({type(error).__name__})") from error
    except requests.exceptions.RequestException as error:
        if is_mutation:
            raise Unconfirmed(f"no answer from Buffer ({type(error).__name__})") from error
        raise Retryable(f"no answer from Buffer ({type(error).__name__})") from error
    if response.status_code == 429:
        raise Retryable("Buffer rate limit (HTTP 429)")
    if response.status_code in (401, 403):
        raise Retryable(f"Buffer refused the API key (HTTP {response.status_code})")
    if response.status_code >= 500:
        if is_mutation:
            raise Unconfirmed(f"Buffer server error (HTTP {response.status_code})")
        raise Retryable(f"Buffer server error (HTTP {response.status_code})")
    try:
        body = response.json()
    except ValueError as error:
        raise Retryable(f"Buffer answered HTTP {response.status_code} without JSON") from error
    if body.get("errors"):
        raise Retryable("Buffer rejected the request: " + str(body["errors"][0].get("message", "unknown error")))
    return body.get("data") or {}


def buffer_channels(http, api_key: str) -> list[dict]:
    data = buffer_graphql(http, api_key, "query { account { organizations { id name } } }", {})
    found = []
    for organization in ((data.get("account") or {}).get("organizations") or []):
        result = buffer_graphql(
            http, api_key,
            "query Channels($input: ChannelsInput!) { channels(input: $input) "
            "{ id name displayName service isDisconnected } }",
            {"input": {"organizationId": organization["id"]}},
        )
        for channel in result.get("channels") or []:
            found.append({
                "id": channel["id"],
                "name": channel.get("displayName") or channel.get("name") or "",
                "service": (channel.get("service") or "").lower(),
                "disconnected": bool(channel.get("isDisconnected")),
            })
    return found


def allowed_channels(channels: list[dict], allow: set[str]) -> dict[str, str]:
    """Map target -> channel id, using only ids the owner listed. An unlisted channel is never used."""
    chosen: dict[str, str] = {}
    for channel in channels:
        target = BUFFER_SERVICES.get(channel["service"])
        if target and channel["id"] in allow and not channel["disconnected"]:
            chosen.setdefault(target, channel["id"])
    return chosen


def send_buffer(http, api_key: str, payload: dict) -> str:
    data = buffer_graphql(http, api_key, CREATE_POST, {"input": payload}, is_mutation=True)
    result = data.get("createPost") or {}
    post = result.get("post")
    if post and post.get("id"):
        return f"buffer:{post['id']}"
    raise Retryable("Buffer did not create the post: " + str(result.get("message") or result.get("__typename") or "no detail"))


def telegram_call(http, token: str, method: str, sleep=time.sleep, **request) -> str:
    """One Bot API call that posts a message. Returns its reference, or raises Retryable or Unconfirmed."""
    for attempt in range(2):
        try:
            response = http.post(f"{TELEGRAM_API}/bot{token}/{method}", timeout=60, **request)
        except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as error:
            raise Retryable(f"Telegram unreachable ({type(error).__name__})") from error
        except requests.exceptions.RequestException as error:
            raise Unconfirmed(f"no answer from Telegram ({type(error).__name__})") from error
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code == 200 and body.get("ok"):
            return f"telegram:{body['result'].get('message_id')}"
        if response.status_code == 429:
            wait = int((body.get("parameters") or {}).get("retry_after", 60))
            if attempt == 0 and wait <= 30:
                sleep(wait)
                continue
            raise Retryable(f"Telegram rate limit, retry after {wait}s")
        if response.status_code >= 500:
            raise Unconfirmed(f"Telegram server error (HTTP {response.status_code})")
        raise Retryable(f"Telegram refused: {body.get('description') or response.status_code}")
    raise Retryable("Telegram rate limit")


def send_telegram(http, token: str, fields: dict, card_path: Path, sleep=time.sleep) -> str:
    if not card_path.exists():
        raise Retryable(f"card file missing: {card_path.name}")
    # The bytes, not an open file, so the second try after a rate limit sends the whole card again.
    kind = "image/jpeg" if card_path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    photo = (card_path.name, card_path.read_bytes(), kind)
    return telegram_call(http, token, "sendPhoto", sleep, data=fields, files={"photo": photo})


def send_telegram_post(http, token: str, chat_id: str, post: dict, out_dir: Path, image_base: str | None = None,
                       sleep=time.sleep, silent: bool = False) -> str:
    """Send one post as one Telegram message and return its reference.

    A digest built from the edition is the one-message edition; an alert, or a digest frozen before that
    existed, is the card with its caption.
    """
    if post.get("telegram_edition"):
        fields = telegram_edition_fields(post, chat_id, image_base)
        if silent:
            fields["disable_notification"] = "true"
        return telegram_call(http, token, "sendMessage", sleep, data=fields)
    fields = telegram_fields(post, chat_id)
    if silent:
        fields["disable_notification"] = "true"
    card_path = out_dir / telegram_picture(post)
    if not card_path.exists():
        # The photo card is an extra: without its file the text card goes out.
        card_path = out_dir / post["cards"][0]
    return send_telegram(http, token, fields, card_path, sleep)


def find_image_base(http, candidates: list[str], probe: str, wait_seconds: int = 0, sleep=time.sleep) -> str | None:
    """Return the first base URL that serves the probe card as an image. Only the first one is waited for."""
    for index, base in enumerate(candidates):
        deadline = time.monotonic() + (wait_seconds if index == 0 else 0)
        while True:
            try:
                response = http.get(base + probe, timeout=20, stream=True)
                if response.status_code == 200 and str(response.headers.get("Content-Type", "")).startswith("image/"):
                    return base
            except requests.exceptions.RequestException:
                pass
            if time.monotonic() >= deadline:
                break
            sleep(15)
    return None


def claim(state: dict, run_id: str) -> int:
    """Mark every target that is waiting to be sent as `sending`, owned by this run.

    The workflow saves the state after this and before `deliver`. If the run then dies between a send and
    the final save, the mark is still there for the next run, which records the target as unconfirmed
    and does not send it again.
    """
    claimed = 0
    for post in state["posts"].values():
        for target in TARGETS:
            entry = post["targets"][target]
            if entry["status"] in WAITING_STATUSES:
                entry["status"] = "sending"
                entry["claim"] = run_id
                claimed += 1
    return claimed


def record_outcome(entry: dict, outcome: str, detail: str = "") -> None:
    entry["status"] = outcome
    entry.pop("claim", None)
    if detail:
        entry["detail"] = detail
    else:
        entry.pop("detail", None)


def deliver(state: dict, out_dir: Path, env: dict, now: dt.datetime, http=requests,
            image_bases: list[str] | None = None, image_wait: int = 0, sleep=time.sleep,
            run_id: str | None = None) -> list[str]:
    """Send every waiting target of every frozen post, and every target this run claimed. Returns the log lines."""
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (env.get("TELEGRAM_CHAT_ID") or "").strip()
    api_key = (env.get("BUFFER_API_KEY") or "").strip()
    allow = {item for item in re.split(r"[\s,]+", env.get("MORROW_BUFFER_CHANNELS") or "") if item}
    secrets = [token, api_key]
    log: list[str] = []
    channels: dict[str, str] | None = None
    channels_error: Exception | None = None
    image_base: str | None = None
    image_base_checked = False

    for post in state["posts"].values():
        waiting = []
        for name in TARGETS:
            entry = post["targets"][name]
            if entry["status"] in WAITING_STATUSES:
                waiting.append(name)
            elif entry["status"] == "sending":
                if run_id and entry.get("claim") == run_id:
                    waiting.append(name)
                else:
                    # Another run claimed this and never saved a result. It may have been sent.
                    record_outcome(entry, "unconfirmed", STALE_CLAIM)
                    log.append(f"{post['id']} {name}: unconfirmed, will not retry ({STALE_CLAIM})")
        if not waiting:
            continue
        age = now - dt.datetime.fromisoformat(post["created_at"])
        for target in waiting:
            entry = post["targets"][target]
            if age > MAX_POST_AGE:
                record_outcome(entry, "expired", "older than 3 hours when delivery was tried")
                log.append(f"{post['id']} {target}: expired, not sent")
                continue
            note = ""
            try:
                if target == "x" and post.get("kind") != "digest":
                    # X is the owner's own account: one thread a day, not the alerts as well.
                    raise NotConfigured("X gets the daily digest thread only")
                if target == "telegram":
                    if not token or not chat_id:
                        raise NotConfigured("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set")
                    if post.get("telegram_edition"):
                        if not image_base_checked:
                            image_base = find_image_base(http, image_bases or [], telegram_picture(post), image_wait, sleep)
                            image_base_checked = True
                        # The news does not wait for the picture: without a public card it goes out as text.
                        cover = "photo cover" if post.get("telegram_cover") else "cover card"
                        note = (f", the whole edition in one message with the {cover} as its preview" if image_base
                                else ", the whole edition in one message, no cover card: it is not at a public URL yet")
                    reference = send_telegram_post(http, token, chat_id, post, out_dir, image_base, sleep)
                else:
                    if not api_key:
                        raise NotConfigured("BUFFER_API_KEY is not set")
                    if not allow:
                        raise NotConfigured("MORROW_BUFFER_CHANNELS is empty, so no channel is allowed")
                    if channels is None and channels_error is None:
                        try:
                            channels = allowed_channels(buffer_channels(http, api_key), allow)
                        except Retryable as error:
                            channels_error = error
                    if channels_error:
                        raise channels_error
                    if target not in channels:
                        raise NotConfigured(f"no allowed, connected Buffer channel for {target}")
                    if not image_base_checked:
                        image_base = find_image_base(http, image_bases or [], post["cards"][0], image_wait, sleep)
                        image_base_checked = True
                    if not image_base:
                        raise Retryable("the cards are not reachable at a public URL yet")
                    reference = send_buffer(http, api_key, buffer_input(post, target, channels[target], image_base))
            except NotConfigured as error:
                record_outcome(entry, "skipped", str(error))
                log.append(f"{post['id']} {target}: skipped ({error})")
            except Unconfirmed as error:
                entry["attempts"] += 1
                record_outcome(entry, "unconfirmed", scrub(str(error), secrets))
                log.append(f"{post['id']} {target}: unconfirmed, will not retry ({entry['detail']})")
            except Retryable as error:
                entry["attempts"] += 1
                outcome = "gave_up" if entry["attempts"] >= MAX_ATTEMPTS else "failed"
                record_outcome(entry, outcome, scrub(str(error), secrets))
                log.append(f"{post['id']} {target}: {outcome} after attempt {entry['attempts']} ({entry['detail']})")
            else:
                entry["attempts"] += 1
                entry["ref"] = reference
                entry["at"] = now.astimezone(dt.timezone.utc).isoformat(timespec="seconds")
                record_outcome(entry, "delivered")
                log.append(f"{post['id']} {target}: delivered ({reference}{note})")
    return log


# --------------------------------------------------------------------------- commands


def report(lines: list[str]) -> None:
    lines = [line for line in lines if line]
    for line in lines:
        print(line)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(f"- {line}" for line in lines) + "\n")


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def public_post(post: dict) -> dict:
    return {key: value for key, value in post.items() if key != "targets"}


def command_hold(args, sleep=time.sleep) -> int:
    now = parse_now(args.now)
    seconds = hold_seconds(now)
    local = now.astimezone(WIB)
    if not seconds:
        print(f"{local:%H:%M} WIB: no wait, the {WINDOW_START_HOUR:02d}:00 opening is not within the next hour")
        return 0
    print(f"{local:%H:%M} WIB: waiting {seconds // 60} min {seconds % 60} s for the {WINDOW_START_HOUR:02d}:00 opening",
          flush=True)
    sleep(seconds)
    print("the window is open")
    return 0


def command_build(args, http=requests) -> int:
    out_dir = Path(args.out)
    now = parse_now(args.now)
    edition = feed.parse_edition(Path(args.page).read_text(encoding="utf-8"))
    state = load_state(out_dir / "state.json")
    post, reason = plan(edition, state, now)
    lines = [f"edition {edition['date'] or 'unknown'} updated {edition['updated'] or '?'}: "
             f"{len(edition['stories'])} stories from {feed.outlet_total(edition['stories'])} outlets"]
    problems = feed.post_problems(post) if post else []
    if problems:
        # A post that breaks a platform rule is never frozen, so it can never be sent.
        lines.append(f"not posted, {post['id']} failed its checks: " + "; ".join(problems))
    elif post:
        cards.render_post_cards(post, edition, out_dir)
        pictures = attach_pictures(post, edition, out_dir, http)
        freeze(state, post, now)
        lines.append(f"frozen {post['id']}: {reason}")
        if pictures:
            lines.append(pictures)
    else:
        lines.append(f"no new post: {reason}")
    prune(state, out_dir, now.astimezone(WIB).date())
    if args.run_id:
        claimed = claim(state, args.run_id)
        if claimed:
            lines.append(f"{claimed} targets claimed by run {args.run_id}")
    save_state(out_dir / "state.json", state)
    todays = [public_post(item) for item in state["posts"].values() if item["date"] == edition["date"]]
    feed_text = json.dumps(feed.public_feed(edition, todays), indent=1, ensure_ascii=False) + "\n"
    if edition["date"] and write_if_changed(out_dir / "feed.json", feed_text):
        lines.append("feed.json updated")
    report(lines)
    return 0


def command_deliver(args) -> int:
    out_dir = Path(args.out)
    state = load_state(out_dir / "state.json")
    lines = deliver(state, out_dir, dict(os.environ), parse_now(args.now),
                    image_bases=args.image_base or [], image_wait=args.image_wait, run_id=args.run_id)
    save_state(out_dir / "state.json", state)
    report(lines or ["nothing to deliver"])
    return 0


def command_channels(_args) -> int:
    api_key = (os.environ.get("BUFFER_API_KEY") or "").strip()
    if not api_key:
        print("Set BUFFER_API_KEY first.")
        return 1
    try:
        found = buffer_channels(requests, api_key)
    except Retryable as error:
        print(scrub(str(error), [api_key]))
        return 1
    for channel in found:
        state = "disconnected" if channel["disconnected"] else "connected"
        usable = "usable" if channel["service"] in BUFFER_SERVICES else "not used by Morrow Brief"
        print(f"{channel['id']}  {channel['service']:<10} {channel['name']}  ({state}, {usable})")
    print("Put the ids of the Morrow Brief channels, comma separated, in the repo variable MORROW_BUFFER_CHANNELS.")
    return 0


def sample_alert(edition: dict, digest: dict) -> tuple[dict | None, str]:
    used = set(digest["story_ids"])
    candidates = feed.alert_candidates(edition["stories"], used)
    if candidates:
        return feed.story_post(candidates[0], edition["date"]), "a real alert candidate on this page"
    rest = [story for story in feed.ranked(edition["stories"]) if story["id"] not in used]
    if not rest:
        return None, ""
    return feed.story_post(rest[0], edition["date"]), (
        "format sample only: no story outside the digest is reported by "
        f"{feed.ALERT_MIN_OUTLETS} or more outlets on this page, so no alert would be sent"
    )


def command_preview(args, http=requests) -> int:
    """Render what would be posted from a page, without state or schedule. Used on pull requests.

    The only network it uses is the outlets' pictures, and `--no-pictures` leaves those out too."""
    out_dir = Path(args.out)
    edition = feed.parse_edition(Path(args.page).read_text(encoding="utf-8"))
    stories = feed.pick_digest(edition["stories"])
    if len(stories) < MIN_DIGEST_STORIES:
        print("not enough stories on the page for a digest")
        return 1
    digest = feed.digest_post(stories, edition["markets"], edition["date"], edition)
    posts = [(digest, "the day's digest")]
    alert, note = sample_alert(edition, digest)
    if alert:
        posts.append((alert, note))
    image_base = feed.DATA_URL
    lines = [f"# {feed.BRAND} preview for {edition['date']}", ""]
    payloads = {}
    for post, note in posts:
        cards.render_post_cards(post, edition, out_dir)
        pictures = "" if getattr(args, "no_pictures", False) else attach_pictures(post, edition, out_dir, http)
        lines += [f"## {post['id']} ({note})", "", "Cards: " + ", ".join(post["cards"]), ""]
        if pictures:
            lines += [f"Telegram picture: {telegram_picture(post)} ({pictures})", ""]
        caption_note = ", kept for a day the edition cannot be read" if post.get("telegram_edition") else ""
        lines += [f"### Telegram caption{caption_note} ({feed.visible_length(post['telegram'])} "
                  f"of {feed.LIMITS['telegram_caption']})",
                  "", "```html", post["telegram"], "```", ""]
        if post.get("telegram_edition"):
            lines += [f"### Telegram, the one message that is sent ({feed.visible_length(post['telegram_edition'])} "
                      f"of {feed.LIMITS['telegram_message']})", "", "```html", post["telegram_edition"], "```", ""]
        for number, text in enumerate(post["x"], 1):
            lines += [f"### X {number}/{len(post['x'])} ({feed.x_length(text)} of {feed.LIMITS['x']})",
                      "", "```text", text, "```", ""]
        lines += [f"### Threads ({len(post['threads'])} of {feed.LIMITS['threads']})",
                  "", "```text", post["threads"], "```", ""]
        lines += [f"### Instagram ({len(post['instagram'])} of {feed.LIMITS['instagram']})",
                  "", "```text", post["instagram"], "```", ""]
        payloads[post["id"]] = {
            "telegram": (telegram_edition_fields(post, "<TELEGRAM_CHAT_ID>", image_base)
                         if post.get("telegram_edition") else telegram_fields(post, "<TELEGRAM_CHAT_ID>")),
            **{target: buffer_input(post, target, f"<{target}-channel-id>", image_base)
               for target in ("instagram", "threads", "x")},
        }
    (out_dir / "preview.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    (out_dir / "payloads.json").write_text(
        json.dumps(payloads, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "feed.json").write_text(
        json.dumps(feed.public_feed(edition, [post for post, _ in posts]), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n")
    print(f"preview written to {out_dir}: {len(posts)} posts, {sum(len(post['cards']) for post, _ in posts)} card slots")
    return 0


def command_sample(args, http=requests, env: dict | None = None, sleep=time.sleep) -> int:
    """Post the digest this page gives to the Telegram channel now, as one message without a notification.

    For the day a channel is connected, and to see a format change in the real app. It reads no state
    and writes none, so the day's own digest and alerts are not affected. Started by hand only.
    """
    env = dict(os.environ) if env is None else env
    token = (env.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat_id = (env.get("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat_id:
        report(["sample not sent: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is not set"])
        return 1
    out_dir = Path(args.out)
    edition = feed.parse_edition(Path(args.page).read_text(encoding="utf-8"))
    stories = feed.pick_digest(edition["stories"])
    if len(stories) < MIN_DIGEST_STORIES:
        report([f"sample not sent: only {len(stories)} stories on the page, a digest needs {MIN_DIGEST_STORIES}"])
        return 1
    post = feed.digest_post(stories, edition["markets"], edition["date"], edition)
    problems = feed.post_problems(post)
    if problems:
        report([f"sample not sent, {post['id']} failed its checks: " + "; ".join(problems)])
        return 1
    cards.render_post_cards(post, edition, out_dir)
    pictures = attach_pictures(post, edition, out_dir, http)
    if getattr(args, "render_only", False):
        # The workflow puts the folder at a public URL between this and the sending call.
        report([f"edition {edition['date']} updated {edition['updated'] or '?'}",
                f"sample cards drawn in {out_dir.name}, nothing sent", pictures])
        return 0
    # The cover this run drew, at the URL the workflow gave; else the day's own cover on the data branch.
    image_base = find_image_base(http, args.image_base or [feed.DATA_URL], telegram_picture(post),
                                 getattr(args, "image_wait", 0), sleep)
    try:
        reference = send_telegram_post(http, token, chat_id, post, out_dir, image_base, sleep, silent=True)
    except (Retryable, Unconfirmed) as error:
        report([f"sample of {post['id']} not confirmed: {scrub(str(error), [token, chat_id])}"])
        return 1
    cover = "photo cover" if post.get("telegram_cover") else "cover card"
    picture = (f"with the {cover} as its preview" if image_base
               else f"without a {cover} (none is public for this date yet)")
    report([f"edition {edition['date']} updated {edition['updated'] or '?'}",
            f"sample of {post['id']} posted to the Telegram channel without a notification ({reference})",
            f"one message, {feed.visible_length(post['telegram_edition'])} of {feed.LIMITS['telegram_message']} "
            f"characters, {len(edition['stories'])} stories, {len(edition.get('stocks') or [])} stocks, {picture}",
            pictures])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    hold = commands.add_parser("hold")
    hold.add_argument("--now", help="ISO time, for tests")
    hold.set_defaults(run=command_hold)
    build = commands.add_parser("build")
    build.add_argument("--page", default="index.html")
    build.add_argument("--out", default="data")
    build.add_argument("--now", help="ISO time, for tests")
    build.add_argument("--run", dest="run_id", help="id of this workflow run; claims the waiting targets before the state is saved")
    build.set_defaults(run=command_build)
    send = commands.add_parser("deliver")
    send.add_argument("--out", default="data")
    send.add_argument("--now", help="ISO time, for tests")
    send.add_argument("--run", dest="run_id", help="the id given to build; targets claimed by any other run are not sent")
    send.add_argument("--image-base", action="append",
                      help="public URL of the data folder, where Telegram and Buffer fetch the cards; repeat for a fallback")
    send.add_argument("--image-wait", type=int, default=90, help="seconds to wait for the first URL to serve a card")
    send.set_defaults(run=command_deliver)
    listing = commands.add_parser("channels")
    listing.set_defaults(run=command_channels)
    preview = commands.add_parser("preview")
    preview.add_argument("--page", default="index.html")
    preview.add_argument("--out", default="preview")
    preview.add_argument("--no-pictures", action="store_true", help="do not fetch the outlets' pictures")
    preview.set_defaults(run=command_preview)
    sample = commands.add_parser("sample")
    sample.add_argument("--page", default="index.html")
    sample.add_argument("--out", default="sample")
    sample.add_argument("--image-base", action="append",
                        help="public URL of a folder that already holds this date's cards; default is the data branch")
    sample.add_argument("--image-wait", type=int, default=0, help="seconds to wait for the first URL to serve the cover")
    sample.add_argument("--render-only", action="store_true",
                        help="draw the cards into --out and send nothing; the next call sends them")
    sample.set_defaults(run=command_sample)
    args = parser.parse_args(argv)
    return args.run(args)


if __name__ == "__main__":
    sys.exit(main())
