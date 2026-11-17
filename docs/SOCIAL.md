# Morrow Brief: the social pages

Picking this work up again? Start at [RESUME.md](RESUME.md).

Morrow Brief is Morrow's page on Telegram, Instagram, Threads and X. It posts one digest a day and a few alerts,
all taken from the published edition at https://juw12.github.io/morrow/. A Telegram bot answers questions about
the day's edition.

> Tech and markets, read across the outlets. One brief a day, every story sourced.

Live now: the Telegram channel [@morrowbrief](https://t.me/morrowbrief) ("Morrow Brief", public, with the bot as
its administrator), the Telegram bot [@Morrow_brief_bot](https://t.me/Morrow_brief_bot), and the publish job,
which builds the day's posts and cards on every run. The daily digest is sent to the channel at 08:00 Jakarta
time as one message: the cover card, every story on the page as a headline with its outlet as the link, summaries
for the most reported stories, and the indexes. The first digest through that path went out on 17 November
2026 at 08:04. The page behind it is built by a PC, and by a job in this repository when that PC stops
publishing. Not live yet: Instagram, Threads and X. No Buffer key or account is connected, so those three
targets are recorded as `skipped`.
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
| Format | an emoji, a headline and two or three short paragraphs (66 words at the median); a photo or video on 25 of the 28 | the outlet's own headline, no emoji, and a card: on Telegram a grid of the outlets' own pictures, each credited, elsewhere drawn from the text |
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
  count as a large numeral. On Telegram the digest's cover and an alert's card also carry the outlets' own
  pictures (since 17 November 2026, see [Pictures](#pictures)); the cards for Instagram, Threads and X stay
  text only.
- **Tone.** No emoji, and a plain statement that the selection is automated.

## What gets posted

**The digest** goes out once a day at 08:00 Jakarta time (WIB). An edition published between 07:00 and 08:00
starts a run that waits until 08:00 and then reads the newest page. With no edition in that hour, the digest
goes out with the first edition after 08:00, up to 22:00. It holds 5 stories: the page's lead story, then the
stories the most outlets report, with at most 2 from any one section. If the edition has fewer than 3 stories,
no digest is sent.

**On Telegram the digest is one message.** Not a post followed by more posts: one message a day, and it is the
one that sends a notification. It holds, in this order:

- the cover, shown above the text: a grid of 6 (or 4) of the day's pictures, each with its headline, its
  outlet and the number its story has in the text below. With fewer than 4 pictures it is the text cover card.
  The cover is the message's link preview, which is how a picture and a long text fit in one message (a
  photo's own caption stops at 1,024 characters);
- every story on the page, numbered, under its underlined section heading, each one set apart by an empty
  line: the outlet's headline as plain text, then the outlet's name as the link to the article and how many
  more outlets report the story (`+2`). Only the outlet's name is blue, so the list reads as text and not as a
  wall of links;
- the page's summary for as many stories as the remaining room holds, starting with the lead and then the most
  widely reported, always as whole sentences, in italics under the headline;
- every index on the page's market tape, with its last close and its move, as a fixed-width table;
- every stock in the page's analysis table, with its last price and one-day move (`NVDA 162.85 ▼2.0%`), tickers
  in A to Z order, as a fixed-width table of one stock per line, US dollar prices first and rupiah prices
  under their own `IDR` line;
- one line that links to the page for every summary, the charts and the stock analysis.

One Telegram message holds 4,096 characters, and the text is built to 4,000. The edition of 17 November 2026
came to 3,975: every headline with its outlet, the 5 indexes, and room for 7 summaries. All of that day's
summaries together would need about 8,700 characters, more than two messages, which is why the rest stay on
the page behind the link. On a day when even the headlines do not fit, they are shortened to 140 characters at
a word; if that is still not enough, the top stories are listed and the message says how many more are on the
page.

The stock prices are part of the fixed content, like the headlines and the indexes, so they take room from the
summaries: on the 09:30 edition of 17 November (33 stories, 22 stocks) the prices took about 420 characters and
2 summaries fitted. The rest are on the page behind the link.

`/full` in the bot gives the same message at any time, and `/tape` gives the indexes and the stock prices.

### Pictures

One Telegram message can show one picture, so the day's pictures are drawn into one cover:

- the page already shows the outlet's own picture for about half of its stories. `build` asks for those
  pictures, the lead and the most reported stories first, until it has 6 (at most 14 requests and 75 seconds);
- with 6 it draws a grid of 6, with 4 or 5 a grid of 4, each tile with the story's number in the message, its
  headline and the outlet's name. With fewer than 4 the text cover card is used, and the run log says how many
  pictures could be fetched;
- a picture that is refused, too slow, not a picture, over 8 MB or smaller than 400 x 220 is left out. Nothing
  about a picture can delay or stop a post;
- an alert whose story has a picture gets a photo card (the picture, the headline, the outlet count) instead
  of the text card; without one it keeps the text card;
- the pictures belong to their outlets. They are shown small, each with its outlet's name, next to a link to
  the outlet's article, and the cards are kept for 7 days like every other card. If an outlet objects, remove
  its pictures by leaving its stories out in `attach_pictures` in `scripts/social_post.py`;
- Instagram, Threads and X get the text cards only.

What the message is not: the articles themselves. The page holds a headline and one to three sentences per
story; the full article stays with the outlet, behind the link. The page's stock analysis section (charts and
long explanations, about 41,000 characters) and its "Also today" list are left out.

One kind of story on the page is also left out: an article its outlet filed under lifestyle or entertainment
(the address has a part such as `/lifestyle/`). On 17 November 2026 a film-casting story sat second in the
digest under Markets. The list is `OFF_TOPIC_PATHS` in `scripts/social_feed.py`; the page itself is not changed.

Until 17 November 2026 the digest was a photo with a 5-story caption, followed by the whole edition as two or
three silent text messages. The 08:04 digest of that day was the last in that form.

**An alert** is a single story outside the digest that 3 or more outlets report. Alerts are limited to 4 a day,
at least 90 minutes apart, between 08:00 and 22:00 WIB. Most days have none or one. On Telegram an alert arrives
silently; only the digest sends a notification.

No story is posted twice in a day, and a story in the digest is never sent again as an alert.

Each platform gets its own format:

| Platform | Digest | Alert | Limit enforced |
|---|---|---|---|
| Telegram | one message: the cover above the text (as its link preview; a grid of the outlets' pictures, or the text card), every story as a headline with its outlet as the link, summaries for the most reported stories, the indexes, the stock prices, a link to the page | card (with the outlet's picture when it has one), headline, summary, a link to each outlet the page names (one message) | 4096 for a message (the digest is built to 4000), 1024 for an alert's caption |
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
- cards are 1080 x 1350. The text cards are drawn from text alone, with every colour pair at 4.5:1 or better.
  The cover sets the lead headline large (at least 1.6 times the rows when the text allows), with the other
  four as numbered rows and the market moves below;
- Instagram captions carry this line: "Automated selection from published reporting. Headlines belong to their
  outlets; every story names its source."

Run `python scripts/social_post.py preview --page index.html --out preview` to see exactly what today's edition
would post. It writes `preview/preview.md`, the cards, and the request bodies, and sends nothing. The "Morrow
Brief" workflow attaches the same preview to every pull request as the artifact `morrow-brief-preview`.

### Wording

Everything a reader sees is written plainly, and `tests/social/test_wording.py` checks it:

- say what is in the post and where it comes from; no slogans and no claims about importance ("the five most
  reported stories", not "the stories that matter");
- no emoji, no exclamation marks, no questions used as headings;
- headlines and summaries are the outlets' own and are never reworded;
- the same thing has the same name everywhere: the daily message, an alert, the bot, the full edition.

The pictures follow the same idea: they are the outlets' own photographs with a credit. Nothing is drawn by an
image generator.

## How it runs

```
generator on the PC --push--> index.html on main <--commit-- edition job (only when the PC has stopped)
                                     |
                       .github/workflows/social.yml
                                     |
           tests -> (edition) -> build -> save -> deliver -> save
                                     |
                   branch social-data: state.json, feed.json, cards/
                             |                         |
                Buffer fetches the cards      the bot reads feed.json
```

1. Three things start a run: the generator pushing a new `index.html`, the clock in the bot's Worker (once an
   hour, when it has its token), and the workflow's own schedule (twice an hour; GitHub starts few of those
   runs and starts them late). A run that starts between 07:00 and 08:00 WIB waits in the publish job until
   08:00 (`social_post.py hold`), then fetches the newest `index.html`, so the 08:00 digest is built from the
   latest edition and not from the one that started the run. A run that finds nothing new posts nothing.
2. The tests run. If they fail, nothing is posted.
3. `build` reads the page, decides whether a digest or alert is due, draws the cards and freezes the post into
   `state.json`. A frozen post is never rewritten, even if the page changes before it is sent.
4. The state is saved to the `social-data` branch, and only then does `deliver` send: Telegram directly, and
   Instagram, Threads and X through Buffer's API.
5. The results are saved again.

To see a digest in the channel without waiting for 08:00, start "Morrow Brief" from the Actions tab with the
`sample` box ticked. A separate job posts today's digest to the Telegram channel as one message, without a
notification (`social_post.py sample`). It reads and writes no state, so it does not count as the day's digest
and the real one still goes out. Each sample adds one post to the channel; delete it in the app if it is not
wanted. The job's log says how long the message is and then, read from the channel's public page, whether the
post has its picture.

State, cards and the bot's feed live on the `social-data` branch and never touch `main`, so the workflow cannot
collide with the generator's pushes. Each run replaces the branch with a fresh commit, so it does not grow. Posts
and cards older than 7 days are dropped.

Buffer's free plan allows 3 channels, which is why there are three Buffer platforms. Telegram is sent directly
because Buffer does not support it.

## When the PC stops publishing

The page is built by a PC that refreshes it every 30 minutes from 07:00 to 22:00 WIB. When that PC is off or
asleep, or is on but cannot reach GitHub (which is what happened on the night of 16 November 2026), the page
stops changing, and with a page still dated yesterday no digest is sent. Two things now cover that.

**The cloud edition.** The `edition` job of "Morrow Brief" builds the page in GitHub Actions, from the same
generator code, and commits it to `main` as "edition YYYY-MM-DD HH:MM (built in the cloud)". It runs on the
clock and the schedule, never on an edition push.

- It builds only between 08:20 and 22:30 WIB, and only when the page's own "Updated" time is more than
  80 minutes old (two missed refreshes), so a PC that is publishing always wins. At 08:20 a page still dated
  yesterday is rebuilt, and the digest goes out from that run a few minutes later.
- The generator lives in a private repository. The job reads it with a read-only deploy key
  (`GENERATOR_DEPLOY_KEY`). Run logs here are public, so the generator's output goes to a file and only a short
  summary is printed: no feed address, no ticker, no path and no line of its code.
- The generator publishes by itself when it finds a GitHub login. In this job it is run without one, and its
  log line "web publish skipped" confirms that on every build.
- The built page must pass a gate before it replaces anything (`social_edition.py accept`): it is made public
  by the generator's own code (which removes the private holdings section); it must be dated today; it must
  hold no private section; it needs at least 10 stories and at least 60% of the stories on the page it
  replaces; it must not have lost the indexes or the stock analysis that page has. A page that fails is
  dropped with a warning and the published page stays.
- The push is not forced. If the PC published while the job was building, the PC's edition stays.
- The publish job waits for this job and then reads the newest page, so the digest or an alert comes from the
  same run.

What a cloud edition lacks: the list of stories earlier editions already printed, which stays on the PC, so
a story from the last 72 hours that the PC would have left out can appear again (the PC's own log shows it
leaving out 2 on 17 November); and the AI-written brief, which needs the model on the PC (the PC itself falls
back to the same extract when that model is not running). The holdings and alerts never leave the PC and are
in neither edition.

To run it by hand: start "Morrow Brief" from the Actions tab and choose `cloud_edition`: `build` builds and
checks but publishes nothing, `publish` builds and publishes now whatever the page's age. The variable
`MORROW_CLOUD_EDITION=off` switches the job off.

**The clock.** GitHub's own schedule is unreliable in this repository, so the bot's Cloudflare Worker starts
the workflow once an hour from 08:25 to 22:25 WIB. It needs one secret that only the repository's owner can
create; see [Setup](#setup). Until that secret exists the schedule (twice an hour, 07:23 to 22:53 WIB, when
GitHub starts it) is the only thing that starts a run on a day the PC publishes nothing.

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
- **The digest's cover card is not public.** On Telegram the card is shown as the message's link preview, so
  Telegram has to fetch it from a public URL. If neither URL serves it, the digest is still sent, as the same
  one message without a picture.
- **The page stops changing.** See [When the PC stops publishing](#when-the-pc-stops-publishing).
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
| `/start` | a short welcome: what the brief is, three commands to begin with, the day's story and outlet counts, and a link to the channel |
| `/help` | every command, grouped: the brief, sections, numbers and sources, search, about |
| `/today` | the day's digest |
| `/full` | the whole edition in one message, the same text the channel gets at 08:00 |
| `/ai`, `/bigtech`, `/robotics`, `/space`, `/tech` | that section's stories |
| `/markets` | the markets stories |
| `/tape` | index moves, one per line, then every stock of the analysis table with its last price and one-day move |
| `/sources` | the story and outlet counts, and every outlet's name |
| `/find <word>` | up to 6 stories whose headline, summary, topic tag or outlet contains every word given |
| `/about` | what Morrow Brief is and how stories are chosen |
| `/privacy` | what the bot stores (nothing) and where the code is |

Anything else gets the `/help` reply.

There are two ways to run it. Use one.

- **Cloudflare Worker (in use).** `bot/worker.js` answers each message as it arrives. It runs at
  `https://morrow-brief-bot.juwenmondial.workers.dev`. It holds no bot token: it replies in the webhook response
  itself. `WEBHOOK_SECRET` is the secret Telegram sends back with every call so the Worker can
  refuse anyone else. The Worker reads every reply from `feed.json` and keeps it for 2 minutes, so the wording
  of a reply changes with the next publish run and the Worker is not deployed again.
  The same Worker is the clock: once an hour from 08:25 to 22:25 WIB Cloudflare calls it, and it asks GitHub
  to start "Morrow Brief". That needs the Worker secret `GITHUB_DISPATCH_TOKEN` (see [Setup](#setup)); without
  it the clock does nothing.
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
| `channel-view` | needs no token: reads the channel's public page (`t.me/s/<handle>`) and lists the newest posts with their length, their links and whether each has a photo, a link preview with a picture, or none. It is how a post is checked without a phone |

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

## Readers

The channel's numbers are recorded once a day so that growth can be read from a file and not from memory.
The `publish` job of `social.yml` runs `scripts/social_channel.py metrics --out data/metrics.csv` after it
delivers, and the file is saved with the rest of the data on the `social-data` branch:
https://raw.githubusercontent.com/juw12/morrow/social-data/metrics.csv

| Column | Meaning |
| --- | --- |
| `date` | the day in Jakarta time; a later run on the same day replaces the line |
| `subscribers` | what Telegram reports for the channel |
| `posts_counted` | posts on the public page that are between one and eight days old and show a view counter |
| `median_views` | the middle view count of those posts; empty when there are none |
| `views_per_100_subscribers` | `median_views` as a share of the subscribers, in percent |

A post younger than a day is left out because it is still collecting views. The view counts come from the
public page (`t.me/s/morrowbrief`), which shows only the newest posts and rounds large counts (1.2K). A bot
cannot see who the subscribers are or where they came from. A failed reading does not stop the run; the day
then has no line or a line without views.

## Setup

The Telegram part (steps 1, 2 and the two Telegram secrets in step 5) is done. Until the Buffer steps are
done, Instagram, Threads and X are recorded as `skipped`.

1. Create the page accounts: a Telegram channel, an Instagram professional account, Threads and X. The Telegram
   channel is `@morrowbrief` (https://t.me/morrowbrief), public since 17 November 2026. Suggested handle for the
   other three: `morrowbrief`, with `morrowdaily` as a fallback. Nothing has been checked on Instagram, Threads
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

For the Worker's clock (it starts "Morrow Brief" once an hour, so the timing does not rest on GitHub's schedule):

1. On GitHub: Settings, Developer settings, Personal access tokens, Fine-grained tokens, Generate new token
   (https://github.com/settings/personal-access-tokens/new). Repository access: only `juw12/morrow`.
   Permissions: Actions, Read and write. Nothing else.
2. In the Cloudflare dashboard: Workers & Pages, `morrow-brief-bot`, Settings, Variables and Secrets, add a
   secret named `GITHUB_DISPATCH_TOKEN` with that token as its value.

The trigger itself (`25 1-15 * * *`, which is 08:25 to 22:25 WIB) is already set. Without the secret the clock
does nothing. A token with wider rights is not needed and should not be used there.

For the cloud edition: a read-only deploy key on the private generator repository, with its private half
stored here as the secret `GENERATOR_DEPLOY_KEY`. That is done (the key is named "morrow cloud edition (read
only)" under the generator repository's Settings, Deploy keys). To switch the cloud edition off, set the
variable `MORROW_CLOUD_EDITION` to `off`, or delete that deploy key.

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
admin. The channel was called "Morrow News" and was private then. The only link to it was an invite link
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

The same evening the daily post was changed to carry the full edition, and a second sample was sent:

| Run | Result |
|---|---|
| [Morrow Brief, sample](https://github.com/juw12/morrow/actions/runs/43865082679) | started by hand at 19:16 WIB with `sample` ticked, on commit `6ca2d2b`: 216 Python tests and 13 Worker tests passed; "sample of digest-2026-11-16 posted to the Telegram channel without a notification" and "full edition: 2 messages accepted by Telegram, 15 stories and 0 more items". The publish job in the same run had nothing new to post. The log holds no chat id and no token |

That sample left 3 silent posts in the channel: the card with its caption and the 2 full edition messages.

Of the 11 runs of "Morrow Brief" by the evening of 16 November, 3 were started by an edition push, 5 by hand, 2 by a pull request
and 1 by the schedule. That one
[scheduled run](https://github.com/juw12/morrow/actions/runs/43859308855) started at 18:36 WIB, 2 hours
19 minutes after the 16:17 WIB slot it belongs to, and had nothing new to post. The slots before it, due
every 3 hours since the morning, did not start a run.

### 17 November 2026: first scheduled digest, one message, public handle, clock, cloud edition

| Run | Result |
|---|---|
| [Morrow Brief, edition push](https://github.com/juw12/morrow/actions/runs/43992611883) | started by the PC's 08:03 edition. "frozen digest-2026-11-17: first run of the day in the window", delivered at 08:04 WIB as post 16 and 3 full edition messages (the earlier form, 4 posts). The first digest through the normal path |
| [channel-status](https://github.com/juw12/morrow/actions/runs/43998724624) | with `@morrowbrief` in the `chat` box: channel "Morrow Brief", `@morrowbrief`, the bot is administrator, description set, a post is pinned, 2 subscribers. The channel is public at https://t.me/morrowbrief |
| [Morrow Brief, sample](https://github.com/juw12/morrow/actions/runs/43999542170) | on commit `e83abea`: "sample of digest-2026-11-17 posted to the Telegram channel without a notification (telegram:20)", "one message, 3975 of 4096 characters, 31 stories, with the cover card as its preview". `channel-view` in the same run read the public page: post 20 is 3,914 characters with 34 links and a link preview with a picture; posts 16 to 19 are the morning's photo and 3 texts |
| [setup](https://github.com/juw12/morrow/actions/runs/43999547169) | `setMyCommands: done`, so the command menu now lists `/full` |
| [Morrow Brief, cloud edition `build`](https://github.com/juw12/morrow/actions/runs/44001060288) | on commit `9e6afb1`: 241 Python tests and 16 Worker tests passed. The generator was fetched with the read-only deploy key and ran in about a minute: "stock analysis: 22 stocks, 2 indices, 22 with fundamentals", "web publish skipped: no GitHub login on this PC". The gate: "built page: dated 2026-11-17, updated 09:11, 34 stories from 14 outlets, 5 indexes, with the stock analysis", passed, "build mode: the page passed the gate and is not published" |
| [Morrow Brief, cloud edition `publish`](https://github.com/juw12/morrow/actions/runs/44001374831) | on commit `577a9dd`: built page updated 09:14, 34 stories, passed the gate, "published: edition 2026-11-17 09:14 (built in the cloud)" as commit `5ecc498` (154 lines changed against the PC's 09:00 edition). GitHub Pages built that commit, and https://juw12.github.io/morrow/ then showed "Updated 09:14" with no private section and the waitlist line. The publish job of the same run read the 09:14 page: "no new post: last post was 69 min ago, alerts wait 90" |
| [status](https://github.com/juw12/morrow/actions/runs/44001653880) | after the Worker was deployed again with the clock: the webhook is still the Worker's URL and no messages are waiting |
| [sample, with stock prices and pictures](https://github.com/juw12/morrow/actions/runs/44005672421) | on commit `39f4d86`: 270 Python tests and 16 Worker tests passed. The sample job drew the cards, pushed them to the branch `social-sample` and sent: "photo cover: 6 pictures (stories 3, 5, 6, 11, 14, 28), 6 asked for", "one message, 3965 of 4096 characters, 33 stories, 22 stocks, with the photo cover as its preview", post 21. `channel-view` read the public page: 3,903 characters, 36 links, a link preview with a picture. With the stock block (about 420 characters) 2 summaries fitted, against 7 without it. The publish job of the same run sent the first alert through the normal path, post 22, "sent as a photo", 265 characters, silently, with the photo card of its story |
| [setup](https://github.com/juw12/morrow/actions/runs/44006043832) | `setMyDescription: done` and `setMyCommands: done`, so the menu and description say `/tape` gives index and stock prices |
| [sample, tidier layout](https://github.com/juw12/morrow/actions/runs/44008491997) | on commit `182169f`: 271 Python tests and 16 Worker tests passed. "one message, 3999 of 4096 characters, 33 stories, 22 stocks, with the photo cover as its preview", post 23. Telegram accepted the underlined headings and the two fixed-width tables. `channel-view`: 3,880 characters, 34 links (33 outlets and the page), a link preview with a picture. 2 summaries fitted |
| [setup](https://github.com/juw12/morrow/actions/runs/44059446193) and [channel-setup](https://github.com/juw12/morrow/actions/runs/44059463667) | on commit `624e255`, the plain wording: every bot step `done`; in the channel "description: done" and "welcome post (updated in place): done", so the pinned post was reworded and not posted a second time |
| [publish](https://github.com/juw12/morrow/actions/runs/44059480386) | 274 Python tests and 16 Worker tests passed; "feed.json updated", "no new post: the day's 4 alerts are used". Read back from the `social-data` branch, the bot's `/start` answer has the new wording and `/tape` and `/full` have the new layout |

The Worker was deployed again through Cloudflare's API with the clock in it. Cloudflare reported the handlers
`scheduled` and `fetch`, the trigger `25 1-15 * * *`, and the same single binding as before (`WEBHOOK_SECRET`).
Called directly afterwards, a `GET` returned 200 and a `POST` without the secret returned 403. The account's
six other Workers were not changed.

Why the page went stale overnight, read from the generator's own log on the PC: the PC was on. From 16:38 on
16 November to 08:02 on 17 November its refresh task ran 12 times and published none of them. 4 runs hung and
wrote nothing, 5 logged "web publish skipped: no GitHub login on this PC" (reading the saved GitHub login took
longer than the 15 seconds the generator allows), and 2 failed on the proxy or its certificate. The 08:03, 08:35
and 09:00 runs on 17 November published normally. The generator does not retry a failed publish; that is in
the private repository and was not changed here. The cloud edition is what now covers such a night.

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
- the one-message digest at 08:00 through the normal path. A digest did go out through that path on
  17 November 2026 at 08:04 WIB, in the earlier four-post form. The one-message form has been sent once, as a
  sample; the first scheduled one is due on 18 November. No real run has started between 07:00 and 08:00 WIB
  yet, so the wait for 08:00 is covered by unit tests with a fake clock only;
- how the one-message digest looks in the app. The channel's public page shows it as one post with a picture
  preview; it has not been looked at on a phone as part of this work;
- the digest when Telegram refuses the message or does not answer: unit tests with fake servers only;
- whether the price tables stay on one line each on a narrow phone (the widest row is 31 characters);
- how the photo cover and the photo alert card look in the app. The log says the cover was the preview of
  post 21 and that post 22 went as a photo; the public page reports a picture on post 21. Neither picture has
  been looked at in the channel, on a phone or otherwise (`t.me` is blocked where this work was done);
- a scheduled digest with stock prices and the photo cover. The form has been sent once, as a sample; the
  first scheduled one is due on 18 November;
- the digest when fewer than 4 pictures can be fetched (it falls back to the text card): unit tests only;
- the Worker's clock starting a run. The clock is deployed and Cloudflare lists its hourly trigger, but it has
  no `GITHUB_DISPATCH_TOKEN` yet, so it has started nothing;
- the cloud edition starting by itself. It has been run twice by hand (`build`, then `publish`) and both
  worked; no automatic run has yet found the page stale and rebuilt it. A cloud edition that the gate refuses,
  and a push that loses to the PC, are covered by unit tests and by reading the workflow only;
- `channel-listen` over more than one round, and answering a real person's message while it listens;
- whether Buffer and Instagram accept card images served from `raw.githubusercontent.com`;
- whether X shows the cover card once or repeats it in the thread;
- whether Threads counts a link at full length (the code assumes it does);
- the schedule as a way to hit 08:00. GitHub starts few of this repository's scheduled runs, and late (1 of the
  slots on 16 November, more than 2 hours late). Until the Worker's clock has its token, a day on which the PC
  publishes nothing rests on that schedule, so the page and the digest can be hours late;
- handle availability on Instagram, Threads and X, and on Telegram beyond the 54 names asked;
- anything about Girsta beyond the 111 posts and the channel page read on 16 November 2026.

## Files

| Path | What it does |
|---|---|
| `scripts/social_feed.py` | reads the edition, picks the digest and alerts, writes the text for each platform and the one-message edition for Telegram |
| `scripts/social_cards.py` | draws the cards |
| `scripts/social_post.py` | `build`, `deliver`, `channels`, `preview`, `hold` (the wait for 08:00) and `sample` (today's digest to the channel by hand) |
| `scripts/social_edition.py` | the cloud edition: `due` (has the PC stopped publishing?), `buildlog` (a safe summary of the generator's log) and `accept` (the gate a built page must pass) |
| `scripts/social_bot.py` | the polling bot, and `status`, `setup`, `photo`, `set-webhook` / `delete-webhook` |
| `scripts/social_channel.py` | `find`, `status`, `setup`, `test` and `view` for the channel, and the channel's description and welcome post |
| `scripts/social_save.sh` | saves the data folder to the `social-data` branch |
| `bot/worker.js` | the webhook bot and the hourly clock |
| `tests/social/` | Python tests; `bot/worker.test.mjs` holds the Worker's |
| `assets/fonts/` | Source Serif 4 and Source Sans 3, under the SIL Open Font License |

Run the tests with:

```
pip install -r scripts/social_requirements.txt
python -m unittest discover -s tests/social
node --test bot/worker.test.mjs
```
