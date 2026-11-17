# Morrow Brief: where things are, and how to pick the work up again

Last updated 17 November 2026. This page is the entry point; details are in [SOCIAL.md](SOCIAL.md).
No secret values are written here or anywhere in this repository.

## What it is

Morrow Brief is the social page of the Morrow news edition (https://juw12.github.io/morrow/).

| Thing | Where |
| --- | --- |
| Telegram channel | [@morrowbrief](https://t.me/morrowbrief), title "Morrow Brief" |
| Telegram bot | [@Morrow_brief_bot](https://t.me/Morrow_brief_bot), admin of the channel |
| Code | this repository: `scripts/social_*.py`, `bot/worker.js`, `tests/social/`, `.github/workflows/social*.yml` |
| Page generator | a separate private repository and the PC task; not changed by this work |
| Notes | Obsidian vault `GitHub/morrow.md` and `Update Log/` notes named "morrow"; Cairn finds them with `search query="morrow brief"` |

## What runs today

- **08:00 Jakarta time, every day:** one Telegram message with every story of the edition under its section,
  each with a link to its outlet, then a table of index prices and a table of every stock's price and one-day
  move. Its cover is one image with up to 6 of the outlets' pictures, numbered to match the stories.
- **Alerts:** a short post when 3 or more outlets report the same story, with that story's picture.
- **Bot:** `/today`, `/full`, section commands, `/tape` (index and stock prices), `/find`, `/sources`, `/about`,
  `/privacy`. Answers come from `feed.json`; the Cloudflare Worker replies at once and a workflow polls as a
  fallback.
- **Page refresh:** when the PC stops publishing, the `edition` job of `social.yml` builds the page in the cloud.

## How to check it is healthy

1. Actions, "Morrow Brief" (`social.yml`): the latest run should be green.
2. Actions, "Morrow Brief bot" (`social-bot.yml`), run with action `channel-view`: it lists the channel's latest
   posts with their length and whether they carry a picture. Use this when `t.me` cannot be opened.
3. Tests: `python -m unittest discover -s tests/social` and `node --test bot/worker.test.mjs`.

## How to try a change without waiting for 08:00

Run `social.yml` by hand with `sample` ticked. It posts the day's message to the channel without a notification
and does not count as the day's digest. After changing the bot's or the channel's texts, run `social-bot.yml`
with action `setup` (bot profile and menu) or `channel-setup` (channel description and pinned post).

## Open items

| Item | Who | Note |
| --- | --- | --- |
| Secret `GITHUB_DISPATCH_TOKEN` on the Cloudflare Worker | Juwen | without it the Worker's hourly clock starts nothing; steps in SOCIAL.md, Setup |
| Rotate the bot token in BotFather, save it as `TELEGRAM_BOT_TOKEN` | Juwen | it was pasted in a chat |
| Instagram, Threads and X accounts, connected in Buffer; Buffer key as a secret | Juwen | the code for these is written and tested against fake servers only |
| Look at the daily message and its cover on a phone | Juwen | never seen in the app during this work |
| The generator's own publish has no retry | later | lives in the private repository |
| Delete sample posts 16 to 21 and 23 in the channel | optional | they are test posts |

## Decisions already made

- One message a day, not several. Every story is listed; summaries fill the room that is left.
- The headline is plain text and the outlet's name is the link.
- Stock prices come from the page's analysis table, A to Z, US dollars first, then rupiah.
- Pictures are the outlets' own, small, credited, on Telegram only. Fewer than 4 available means the text card.
- Plain wording everywhere, no emoji, no slogans; see "Wording" in SOCIAL.md.
