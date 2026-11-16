# Morrow Brief: the social pages

Morrow Brief is Morrow's page on Telegram, Instagram, Threads and X. It posts one digest a day and a few alerts,
all taken from the published edition at https://juw12.github.io/morrow/. A Telegram bot answers questions about
the day's edition.

> Tech and markets, read across the outlets. One brief a day, every story sourced.

Live now: the Telegram bot, [@Morrow_brief_bot](https://t.me/Morrow_brief_bot), the publish job, which
builds the day's posts and cards on every run, and the Telegram channel "Morrow Brief". The channel is private
(people join by invite link), the bot is its administrator, and the daily digest is sent to it at 08:00 Jakarta
time. The first digest through that path is due on 17 November 2026; so far the channel has received its setup,
a capability test and one sample sent by hand. Not live yet: Instagram, Threads and X. No Buffer key or account
is connected, so those three targets are recorded as `skipped`.
[What has been run for real](#what-has-been-run-for-real) and [What is not verified](#what-is-not-verified)
say exactly where the line is.

## Why this page, when AI news channels already exist

The closest comparison is Girsta AI News (`t.me/girsta`), an English AI news channel on Telegram. Its public
preview (`t.me/s/girsta`) was read on 16 November 2026: the channel page and 111 posts, numbers 1577 to 1702. The
Girsta column reports what those posts show.

| | Girsta AI News | Morrow Brief |
|---|---|---|
| Volume | separate posts through the day: 28 in the six days from 10 to 15 November, between 2 and 8 a day | one digest of 5 stories, plus at most 4 alerts a day |
| Sourcing | no post links to the reporting behind it; 3 of the 28 name a news outlet in the text. Every link goes to its own Instagram pages or, in older posts, its Discord | every story says how many outlets report it, and the lead links to each one the page names |
| Format | an emoji, a headline and two or three short paragraphs (66 words at the median); a photo or video on 25 of the 28 | the outlet's own headline, no emoji, and a card drawn from the text |
| Scope | AI | AI and chips, big tech, robotics, space, tech, plus a market line |
| Platforms | Telegram, with its Instagram pages linked under each post | built for Telegram, Instagram, Threads and X. On Telegram the bot is live and the channel is set up; the other three are not connected |
| Bot | none named on the channel page or in the posts read | section commands and `/find <word>` |

Three subjects appear on both in the same two days: the fallout from Jensen Huang's exit at Nvidia, the
Microsoft 365 outage and ChatGPT Wallet. Girsta's posts on them give its own summary and no link. Morrow Brief's
digest gives each one with the outlet's headline, a link to that article, and the number of outlets reporting
it (3, 2 and 3).

The channel page showed 484 subscribers, and the 28 November posts had between 12 and 78 views each. The preview
shows no posts between 4 July and 10 November 2026. Not checked: its Instagram pages, what its photos and videos
show, posts before number 1577, and any bot the channel does not name.

Three more things are true of Morrow Brief on their own account, whatever a competitor does:

- **Sourcing.** Every story says how many outlets report it, and the lead links to each one the page names.
- **Cards.** Each post carries its own typographic card: a red bar on the top edge, the headline, and the outlet
  count as a large numeral. No publisher photos.
- **Tone.** No emoji, and a plain statement that the selection is automated.

## What gets posted

**The digest** goes out once a day at 08:00 Jakarta time (WIB). An edition published between 07:00 and 08:00
starts a run that waits until 08:00 and then reads the newest page. With no edition in that hour, the digest
goes out with the first edition after 08:00, up to 22:00. It holds 5 stories: the page's lead story, then the
stories the most outlets report, with at most 2 from any one section. If the edition has fewer than 3 stories,
no digest is sent.

**An alert** is a single story outside the digest that 3 or more outlets report. Alerts are limited to 4 a day,
at least 90 minutes apart, between 08:00 and 22:00 WIB. Most days have none or one. On Telegram an alert arrives
silently; only the digest sends a notification.

No story is posted twice in a day, and a story in the digest is never sent again as an alert.

Each platform gets its own format:

| Platform | Digest | Alert | Limit enforced |
|---|---|---|---|
| Telegram | cover card with a caption: 5 linked headlines, section, outlet count, a link to each outlet the page names for the lead, market line | card, headline, summary, a link to each outlet the page names | 1024 |
| X | thread of 5, one post per story: headline, a one-sentence summary where it fits, outlets, source link; cover card on the first | one post with the card | 280, links counted as 23 |
| Threads | one post: as many whole headlines as fit (at least 3), the rest named by outlet, linking to the edition | headline, summary, source link | 500 |
| Instagram | carousel: cover and one card per story; the caption gives each story a summary and names its outlets | one card | 2200 |

Instagram captions cannot hold links, so they name the outlets and point to the link in the bio.

An X post often has no summary. After the headline, the outlets and the link there is rarely room for a whole
sentence, and half a sentence is not sent. In today's thread the first post has 76 characters free and the
lead's first sentence is 213 characters long, so it goes without. The card on that post carries the summary.

Rules that hold for every post, each checked by a test:

- every story names its source outlet and says how many outlets report it;
- no emoji, in text or on cards (`▲`, `▼` and `•` are the only marks used);
- a post over its platform limit is never sent;
- a summary is kept as whole sentences or left out, never cut mid-sentence, in captions and on cards alike.
  When an outlet's own feed ends a summary mid-sentence, that fragment is dropped. A headline is shortened (at a
  word boundary, with an ellipsis) only when the post would not fit otherwise; today's digest shortens none;
- cards are 1080 x 1350, drawn from text alone (no publisher photos), with every colour pair at 4.5:1 or better.
  The cover sets the lead headline large (at least 1.6 times the rows when the text allows), with the other
  four as numbered rows and the market moves below;
- Instagram captions carry this line: "Automated selection from published reporting. Headlines belong to their
  outlets; every story names its source."

Run `python scripts/social_post.py preview --page index.html --out preview` to see exactly what today's edition
would post. It writes `preview/preview.md`, the cards, and the request bodies, and sends nothing. The "Morrow
Brief" workflow attaches the same preview to every pull request as the artifact `morrow-brief-preview`.

## How it runs

```
private generator --push--> index.html on main
                                 |
                  .github/workflows/social.yml
                                 |
        tests -> build -> save -> deliver -> save
                                 |
              branch social-data: state.json, feed.json, cards/
                        |                         |
           Buffer fetches the cards      the bot reads feed.json
```

1. The private generator pushes a new `index.html`. That push starts the workflow. A run that starts between
   07:00 and 08:00 WIB waits in the publish job until 08:00 (`social_post.py hold`), then fetches the newest
   `index.html`, so the 08:00 digest is built from the latest edition and not from the one that started the
   run. The workflow also has a 3-hour schedule as a fallback, but GitHub has not started a single scheduled
   run of it so far, so the timing rests on the edition push. A run that finds nothing new posts nothing.
2. The tests run. If they fail, nothing is posted.
3. `build` reads the page, decides whether a digest or alert is due, draws the cards and freezes the post into
   `state.json`. A frozen post is never rewritten, even if the page changes before it is sent.
4. The state is saved to the `social-data` branch, and only then does `deliver` send: Telegram directly, and
   Instagram, Threads and X through Buffer's API.
5. The results are saved again.

To see a digest in the channel without waiting for 08:00, start "Morrow Brief" from the Actions tab with the
`sample` box ticked. A separate job posts today's digest to the Telegram channel without a notification
(`social_post.py sample`). It reads and writes no state, so it does not count as the day's digest and the real
one still goes out. Each sample is one more post in the channel; delete it in the app if it is not wanted.

State, cards and the bot's feed live on the `social-data` branch and never touch `main`, so the workflow cannot
collide with the generator's pushes. Each run replaces the branch with a fresh commit, so it does not grow. Posts
and cards older than 7 days are dropped.

Buffer's free plan allows 3 channels, which is why there are three Buffer platforms. Telegram is sent directly
because Buffer does not support it.

## What happens when something goes wrong

Every target (one platform for one post) has a status in `state.json`. The run summary in the Actions tab lists them.

| Status | Meaning | Sent again? |
|---|---|---|
| `pending` | frozen, not yet tried | yes |
| `sending` | claimed by a run that is about to send it | only by that same run |
| `delivered` | the platform accepted it | no |
| `failed` | a clear refusal or a network error before anything was sent | yes, up to 3 attempts |
| `gave_up` | failed 3 times | no |
| `unconfirmed` | the request may or may not have gone through | no |
| `skipped` | the platform has no credentials | no |
| `expired` | still unsent 3 hours after it was frozen | no |

The design rule is that a post may be lost but must never appear twice.

- **The run dies halfway.** Before sending, a run marks its targets `sending` with its own run id and saves that.
  If it dies, the next run finds a claim that is not its own and marks the target `unconfirmed` without sending.
- **A timeout or an unreadable reply.** The target becomes `unconfirmed` and is left alone.
- **The data branch cannot be read.** The run fails before posting. Only a branch that does not exist yet
  (the very first run) starts from an empty state.
- **The page is stale.** If the edition's date is not today in WIB, nothing is frozen.
- **A wrong channel.** Buffer posts go only to channel ids listed in the variable `MORROW_BUFFER_CHANNELS`. A
  key that also holds other channels cannot post to them, and with the variable empty nothing is sent to Buffer.
- **Secrets are added later.** Targets skipped while a platform had no credentials stay skipped, so adding a
  secret does not release a backlog of old posts.
- **A card is not yet served.** `deliver` waits up to 90 seconds for the first card URL to answer, then tries
  the second URL, and fails the target (to be retried) if neither serves it.
- **Two runs at once.** The publish job is in one concurrency group, so runs queue.

## The Telegram bot

The bot answers from `feed.json`, which holds ready-made replies for the day. It stores nothing: no subscriber
list, no chat ids, no message history.

| Command | Reply |
|---|---|
| `/start` | a short welcome: what the brief is, three commands to begin with, and the day's story and outlet counts |
| `/help` | every command, grouped: the brief, sections, numbers and sources, search, about |
| `/today` | the day's digest |
| `/ai`, `/bigtech`, `/robotics`, `/space`, `/tech` | that section's stories |
| `/markets` | the markets stories |
| `/tape` | index moves, one per line |
| `/sources` | the story and outlet counts, and every outlet's name |
| `/find <word>` | up to 6 stories whose headline, summary, topic tag or outlet contains every word given |
| `/about` | what Morrow Brief is and how stories are chosen |
| `/privacy` | what the bot stores (nothing) and where the code is |

Anything else gets the `/help` reply.

There are two ways to run it. Use one.

- **Cloudflare Worker (in use).** `bot/worker.js` answers each message as it arrives. It runs at
  `https://morrow-brief-bot.juwenmondial.workers.dev`. It holds no bot token: it replies in the webhook response
  itself. Its only secret is `WEBHOOK_SECRET`, which Telegram sends back with every call so the Worker can
  refuse anyone else. The Worker reads every reply from `feed.json` and keeps it for 2 minutes, so the wording
  of a reply changes with the next publish run and the Worker is not deployed again.
- **GitHub cron (fallback).** The "Morrow Brief bot" workflow polls every 5 minutes and listens for 4 minutes each
  time. The schedule does nothing unless the variable `MORROW_BOT` is `on`; it is `off` now. GitHub starts
  scheduled runs late or not at all: on 16 November 2026, with the variable on, the 5-minute schedule did not
  start one run in more than 80 minutes, and the bot answered nobody until a run was started by hand.

If a webhook is set, polling is refused by Telegram; the poller logs that and stops.

The "Morrow Brief bot" workflow can also be run by hand from the Actions tab with one of these actions:

| Action | What it does |
|---|---|
| `status` | prints the bot's `@username` and link, whether a webhook is set, and how many messages are waiting |
| `setup` | sets the bot's name, its two descriptions, the command menu people see when they type `/`, the menu button, and the rights offered when the bot is added to a channel as an admin (post messages, nothing else) |
| `photo` | draws the profile picture (the red square with the white M) and sets it |
| `poll` | answers whatever is waiting, once |
| `set-webhook`, `delete-webhook` | hands the bot to the Worker, or back to the poller |
| `channel-find` | asks Telegram about a list of likely `@handles` (or the ones typed in the `chat` box) and says which exist and where the bot is an admin |
| `channel-status` | prints the channel's name, description, subscriber count and the rights the bot holds there, with what each right is needed for |
| `channel-setup` | sets the channel's name, description and picture, then posts the welcome post and pins it |
| `channel-test` | tries each thing a bot can do in a channel and deletes every test post afterwards: a post with a link button, an edit, a reaction, a picture, an album of two, a poll, the subscriber count, the admin list |
| `channel-listen` | for a private channel: waits until Telegram reports the channel, then runs `channel-setup`, `channel-test` and `channel-status` on it in the same run |

`channel-find`, `channel-status`, `channel-setup` and `channel-test` act on the channel in the `chat` box: its `@handle`, a `t.me` link, the link of
any post in it (which also works for a private channel), or its numeric id. With the box empty they use
`TELEGRAM_CHAT_ID`. The run log never shows a private channel's id.

A bot cannot list the chats it is in, cannot schedule a post inside Telegram, cannot read a channel's earlier
posts or their view counts, cannot see who the subscribers are (only how many), and cannot create a channel or
set its `@handle`. `channel-test` prints these with its results so the report does not leave them out.

### Finding a private channel: `channel-listen`

A private channel has no `@handle` to ask about, and its invite link (`t.me/+...`) tells a bot nothing: the
Bot API has no call that turns an invite link into a chat. So the bot waits for the channel to show itself.
Any one of these, done by a channel admin, is enough:

- post anything in the channel;
- change the bot's admin rights in the channel (untick and tick one right, then save);
- forward one of the channel's posts to the bot in a private chat.

The run accepts a channel only if its name contains "morrow" and the bot is an admin there. Other channels
are counted, never named and never touched. When the channel shows up, the same run sets its name,
description and picture, posts and pins the welcome post, runs the capability test, and prints the status.

What to know while it is listening:

- **Who answers.** Telegram delivers messages either to a webhook or to a listener, never both. The run turns
  the webhook off, answers `/start`, `/today` and the rest itself from the same `feed.json`, and turns the
  webhook back on when it ends, also when it fails or is cancelled. Messages that arrive in between are kept
  for the Worker, not dropped.
- **How long.** One round listens for 320 minutes, because a GitHub job is stopped after 6 hours. The `rounds`
  box says how many rounds to chain; each round that finds nothing starts the next one. Between two rounds
  there is about a minute in which the Worker answers messages and a post in the channel is not seen. Post
  again if a round changed at that moment.
- **What stops it.** Running `poll`, `set-webhook` or `delete-webhook` by hand takes the messages away from the
  listener; it says so in its log and stops.
- **The id.** The run log is public, so the channel's numeric id is printed only in a sealed form that the
  repo secret `CHANNEL_HANDOFF_KEY` opens. The id then goes into the secret `TELEGRAM_CHAT_ID`.
- **The risk.** Anyone who names a channel "Morrow..." and makes this bot an admin of it while a round is
  listening would be taken for the channel. The setup would then land in their channel, which they asked for
  by adding the bot. Check the name and subscriber count in the status lines before storing the id.

The poller also hears when the bot is added to a channel or group, and writes one line to the run log:
`now administrator in channel 'Morrow Brief' @handle, chat id -100...`. That id is the value for
`TELEGRAM_CHAT_ID`. Private chats are never written to the log. A Worker webhook only receives messages, so this
line appears only while the poller is the one answering.

## Setup

The Telegram part (steps 1, 2 and the two Telegram secrets in step 5) is done. Until the Buffer steps are
done, Instagram, Threads and X are recorded as `skipped`.

1. Create the page accounts: a Telegram channel, an Instagram professional account, Threads and X. Suggested
   handle `morrowbrief`, with `morrowdaily` as a fallback. On Telegram, `channel-find` saw no chat under either
   name on 16 November 2026, which is not proof that the name is free; `readmorrow`, `morrownews`, `morrow_ai`,
   `morrowchannel` and `morrow_official` belong to other people. Nothing has been checked on Instagram, Threads
   or X.
2. The bot already exists: @Morrow_brief_bot, with its token stored as the secret `TELEGRAM_BOT_TOKEN` and its
   name, descriptions, command menu and picture set. Add it to the channel as an admin. Telegram offers
   "Post messages" already ticked, which is enough for the daily brief. For the bot to set the channel's own
   profile, also tick "Change channel info" (name, description, picture) and "Edit messages of others" (the
   right Telegram asks for to pin a post in a channel). Then run `channel-status` with the channel's `@handle`
   or the link of any post in it, then `channel-setup`, then `channel-test`. For a private channel with no
   post link at hand, run `channel-listen` with the Worker's URL instead and post one word in the channel:
   it does all three. For a public channel
   `TELEGRAM_CHAT_ID` can be the `@handle`. For a private one it is the numeric id: `-100` followed by the
   number in a post link `t.me/c/<number>/<post>`. (For a new bot: create it with @BotFather, then run the
   "Morrow Brief bot" workflow with action `setup`, then `photo`.)
3. In Buffer, connect the Instagram, Threads and X accounts and create an API key. A separate Buffer account for
   Morrow Brief keeps it apart from any personal channels.
4. List the channel ids:
   ```
   BUFFER_API_KEY=... python scripts/social_post.py channels
   ```
5. In the repo settings, add:

   | Kind | Name | Value |
   |---|---|---|
   | secret | `BUFFER_API_KEY` | the Buffer key |
   | secret | `TELEGRAM_BOT_TOKEN` | the token from @BotFather |
   | secret | `TELEGRAM_CHAT_ID` | the channel, as `@handle` or its numeric id |
   | variable | `MORROW_BUFFER_CHANNELS` | the three channel ids, comma separated |

   Set a secret from a program, not through a PowerShell pipe. `"value" | gh secret set NAME` put an
   invisible byte-order mark in front of `CHANNEL_HANDOFF_KEY`, and the key then failed to open the sealed
   channel id. Python's `subprocess.run(["gh", "secret", "set", "NAME"], input=value, text=True)`
   stored it cleanly.

6. Run "Morrow Brief" once from the Actions tab and read the run summary.

For the bot, either:

- create a Cloudflare Worker, paste in `bot/worker.js`, and add a Worker secret `WEBHOOK_SECRET` (any long random
  string). Add the same string to the repo as the secret `TELEGRAM_WEBHOOK_SECRET`. Then run "Morrow Brief bot"
  from the Actions tab with action `set-webhook` and the Worker's URL; or
- set the repo variable `MORROW_BOT` to `on` and run `delete-webhook`.

The first is how the bot runs today.

To stop posting, disable the "Morrow Brief" workflow in the Actions tab. To stop one platform, remove its id from
`MORROW_BUFFER_CHANNELS`, or remove the Telegram secrets.

## What has been run for real

On 16 November 2026, on `main`, with the real bot token:

| Run | Result |
|---|---|
| [status](https://github.com/juw12/morrow/actions/runs/43786940190) | Telegram accepted the token: `@Morrow_brief_bot`, no webhook, 0 messages waiting |
| [setup](https://github.com/juw12/morrow/actions/runs/43787085632) | name, short description, description and command menu all set |
| [Morrow Brief](https://github.com/juw12/morrow/actions/runs/43787090204) | tests passed; the publish job read the 16 Nov edition (32 stories from 14 outlets; the samples below are the 14 Nov edition, which had 15), froze the digest, pushed `feed.json`, `state.json` and the cards to the `social-data` branch, and recorded all 4 targets as `skipped` |
| [poll](https://github.com/juw12/morrow/actions/runs/43787233467) | fetched the published feed, listened to Telegram for 4 minutes, 0 messages answered because nobody had written yet |

Later the same day the bot moved to the Worker:

| Run | Result |
|---|---|
| [poll](https://github.com/juw12/morrow/actions/runs/43796706036) | started by hand after the schedule had not fired; answered the 4 messages that were waiting |
| [set-webhook](https://github.com/juw12/morrow/actions/runs/43797805792) | Telegram accepted the Worker's URL: "webhook set" |
| [setup](https://github.com/juw12/morrow/actions/runs/43799461017) | all six steps accepted: name, short description, description, command menu, menu button, channel admin rights |
| [photo](https://github.com/juw12/morrow/actions/runs/43799663066) | `setMyProfilePhoto` accepted |
| [status](https://github.com/juw12/morrow/actions/runs/43799779878) | `@Morrow_brief_bot (Morrow Brief)`, webhook is the Worker's URL, 0 messages waiting |

Looking for the channel, after the bot was added to one:

| Run | Result |
|---|---|
| [channel-find](https://github.com/juw12/morrow/actions/runs/43813733921) | 24 likely names asked; 22 not found or not visible to the bot; `@readmorrow` and `@morrownews` exist and belong to other people; 0 with the bot as admin |
| [channel-find](https://github.com/juw12/morrow/actions/runs/43814647188) | 30 more names asked; 27 not found or not visible; `@morrow_ai`, `@morrowchannel` and `@morrow_official` belong to other people; 0 with the bot as admin |
| [channel-find](https://github.com/juw12/morrow/actions/runs/43834584832) | 30 spellings of "Morrow News" asked; none exist |
| [channel-status](https://github.com/juw12/morrow/actions/runs/43830646525) | `@MorrowNews` is a group in Russian owned by someone else; the bot is not in it. Nothing was changed there |
| [channel-listen](https://github.com/juw12/morrow/actions/runs/43841280255) | started 09:36 UTC with 4 rounds and ended in the first, 22 minutes later: it saw a post in the channel, set the name "Morrow Brief", the description and the picture, pinned a welcome post, and ran the capability test: 9 of 9 checks passed and 6 of 6 test posts were deleted again |
| [status](https://github.com/juw12/morrow/actions/runs/43841481333) | run while the listener waits: "webhook: none", so the listener, not the Worker, holds the bot's messages |

The find runs end red on purpose, because nothing was found: 84 names asked in three runs, 0 with the bot as
admin. The channel was called "Morrow News" and is private. The only link to it was an invite link
(`t.me/+...`), and the Bot API cannot turn an invite link into a chat. A private channel has no `@handle`, so
the bot can only be pointed at it with the link of a post in it (`https://t.me/c/<number>/<post>`) or its
numeric id. The webhook was set to deliver messages only, so the moment the bot was made an admin was never
delivered either. `channel-listen` was written for this case: it waits for a post in the channel instead of
asking for its id, and that is how the channel was found.

With the channel found, its id went into the secret `TELEGRAM_CHAT_ID`:

| Run | Result |
|---|---|
| [status](https://github.com/juw12/morrow/actions/runs/43846051667) | after the listener ended: `@Morrow_brief_bot`, webhook is the Worker's URL again |
| [channel-status](https://github.com/juw12/morrow/actions/runs/43846072991) | read from the stored id: channel "Morrow Brief", private, description of 253 characters, picture set, pinned post yes, comments off, 2 subscribers; the bot is administrator with "Post messages" and "Change channel info" |
| [Morrow Brief](https://github.com/juw12/morrow/actions/runs/43849244842) | started by hand at 17:29 WIB with the 08:00 change: "no wait, the 08:00 opening is not within the next hour"; "no new post: no unused story is reported by 3 or more outlets"; nothing sent |
| [Morrow Brief, sample](https://github.com/juw12/morrow/actions/runs/43852358827) | started by hand at 17:50 WIB with `sample` ticked: "sample of digest-2026-11-16 posted to the Telegram channel without a notification". Telegram returned a message id, so the channel accepted the digest card and caption. The publish job in the same run had nothing new to post |

The digest and the one alert of 16 November were frozen before the channel was linked, with
Telegram recorded as `skipped`. A skipped target is not retried, so that day's digest did not go to the channel
through the normal path; the sample above is the same digest sent by hand.

Of the 9 runs of "Morrow Brief" so far, 3 were started by an edition push, 4 by hand and 2 by a pull request.
None was started by the schedule, in about 9 hours with a run due every 3.

Two commits (`6db1b78`, `1009b61`) carry a personal e-mail address as author instead of the GitHub no-reply
address. They were not rewritten: the same address is on a commit from 8 November, 93 commits back, so only a
rewrite of the whole history would remove it, and the edition publisher pushes to `main` every few minutes.
Commits since then use the no-reply address.

The Worker itself was called directly: a `GET` returns 200, a `POST` without the secret returns 403, and a
`POST` with the secret and a made-up `/start`, `/help`, `/about` or `/privacy` message returns the same text
that `feed.json` holds for that command.

The variable `MORROW_BOT` is `off`.

## What is not verified

Tested here means unit tests against fake HTTP servers, plus a rehearsal of the workflow's git steps against a
local repository. The following have not been run against the real services:

- a real Buffer `createPost`. The request shape follows Buffer's live schema, read by introspection;
- a real person's message answered through the webhook. The poller answered 4 real messages, and the Worker
  answers a made-up message sent with the secret, but no message from Telegram to the Worker has been seen;
- how the bot's profile and the channel look in the app. Telegram accepted every call and reported the
  channel's name, description, picture and pinned post back; the result has not been looked at on a phone
  as part of this work;
- a digest sent at 08:00 through the normal path. The first is due on 17 November 2026. The wait itself is
  covered by unit tests with a fake clock; no real run has started between 07:00 and 08:00 WIB yet;
- an alert in the channel. None has been due since it was linked;
- the 08:00 digest on a day when the PC that publishes the edition is off or its refresh is skipped. There is
  then no new page to post from, and the digest goes out with the first edition after 08:00;
- `channel-listen` over more than one round, and answering a real person's message while it listens;
- whether Buffer and Instagram accept card images served from `raw.githubusercontent.com`;
- whether X shows the cover card once or repeats it in the thread;
- whether Threads counts a link at full length (the code assumes it does);
- the schedule. The generator's pushes do start the workflow (3 runs on 16 November), but GitHub has not
  started one scheduled run of it. If a push ever fails to start a run, nothing else is known to;
- handle availability on Instagram, Threads and X, and on Telegram beyond the 54 names asked;
- anything about Girsta beyond the 111 posts and the channel page read on 16 November 2026.

## Files

| Path | What it does |
|---|---|
| `scripts/social_feed.py` | reads the edition, picks the digest and alerts, writes the text for each platform |
| `scripts/social_cards.py` | draws the cards |
| `scripts/social_post.py` | `build`, `deliver`, `channels`, `preview`, `hold` (the wait for 08:00) and `sample` (today's digest to the channel by hand) |
| `scripts/social_bot.py` | the polling bot, and `status`, `setup`, `photo`, `set-webhook` / `delete-webhook` |
| `scripts/social_channel.py` | `find`, `status`, `setup` and `test` for the channel, and the channel's description and welcome post |
| `scripts/social_save.sh` | saves the data folder to the `social-data` branch |
| `bot/worker.js` | the webhook bot |
| `tests/social/` | Python tests; `bot/worker.test.mjs` holds the Worker's |
| `assets/fonts/` | Source Serif 4 and Source Sans 3, under the SIL Open Font License |

Run the tests with:

```
pip install -r scripts/social_requirements.txt
python -m unittest discover -s tests/social
node --test bot/worker.test.mjs
```
