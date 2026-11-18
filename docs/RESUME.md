# Morrow Brief: where things are, and how to pick the work up again

Last updated 18 November 2026. This page is the entry point; details are in [SOCIAL.md](SOCIAL.md).
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
- **Numbers:** each run of `social.yml` writes the day's line to `metrics.csv` on the `social-data` branch:
  subscribers, and the typical views of posts a day to eight days old. See "Readers" in SOCIAL.md.

## How to check it is healthy

1. Actions, "Morrow Brief" (`social.yml`): the latest run should be green.
2. Actions, "Morrow Brief bot" (`social-bot.yml`), run with action `channel-view`: it lists the channel's latest
   posts with their length and whether they carry a picture. Use this when `t.me` cannot be opened.
3. Readers: open https://raw.githubusercontent.com/juw12/morrow/social-data/metrics.csv, or run
   `social-bot.yml` with action `channel-metrics` to print today's line.
4. Tests: `python -m unittest discover -s tests/social` and `node --test bot/worker.test.mjs`.

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
| Share `t.me/morrowbrief` with people (own groups) | Juwen | the channel had 2 subscribers on 17 and on 18 Nov 2026; links on pages bring few readers |
| LinkedIn post about the channel | done | posted by ReachPilot on 18 Nov 2026 at 08:16 Jakarta time: https://www.linkedin.com/feed/update/urn:li:share:7528627121267814400/ . The same text went to Bluesky, Mastodon, Substack notes, Threads and X. The three links are in the post itself, because LinkedIn refused the first comment |
| Promotion e-mails | running | ReachPilot's promote module has the product `morrow` since 17 Nov 2026. On 18 Nov: 91 channels found, 14 with a usable address, the first e-mail sent at 10:03, no reply yet. It shares a cap of 10 e-mails a day with the other products, so expect about one Morrow e-mail a day. To stop: set `"active": false` on `morrow` in its `products.json` |
| Link the channel from the web edition | done | the page shows the "Morrow Brief on Telegram" line since 18 Nov 2026 (generator commit `15f84ae`, on the PC and in cloud builds) |
| Portfolio card | done | the Morrow card on https://juwenlie.pages.dev/ links the channel (`juw12/projects` commit `d8cf13b`) |
| Directory listing | waiting, Juwen | TGDirectory (telegramchannels.io) rejected the channel on 18 Nov 2026 without a reason, most likely because it was one day old with 2 subscribers; resubmit on 1 Dec 2026. By hand in a browser, because their forms have bot protection: telegram-group.com, tdirectory.me, tgramsearch.com (through its Telegram bot) and TGStat. Most other directories do not open from the office network |
| The generator's own publish had no retry | done, one step for Juwen | generator commit `c1c489b` (18 Nov 2026): three attempts when the connection, the server or the GitHub login fails. From 7 to 17 Nov the PC's log shows 178 publishes, 36 skipped for "no GitHub login" and 14 network errors. The cloud build uses the new code (run 44226785952). The PC gets it when `Update.bat` in the generator folder is run once |
| Readers card in ReachPilot | done | its Overview page shows subscribers, typical views and the target of 250 by 31 Dec 2026, read from `metrics.csv` |
| Delete sample posts 16 to 21 and 23 in the channel | optional | they are test posts |

## Decisions already made

- One message a day, not several. Every story is listed; summaries fill the room that is left.
- The headline is plain text and the outlet's name is the link.
- Stock prices come from the page's analysis table, A to Z, US dollars first, then rupiah.
- Pictures are the outlets' own, small, credited, on Telegram only. Fewer than 4 available means the text card.
- Plain wording everywhere, no emoji, no slogans; see "Wording" in SOCIAL.md.
- Stories whose outlet address is under lifestyle, entertainment, celebrity or horoscope are left out of the brief (commit `5f7fd16`).
- Most stories are in English and a few are in Indonesian, so texts about the channel say "mostly in English".
