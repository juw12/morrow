"""Wording: nothing a reader sees may use stock marketing phrases, emoji or hype."""
import unittest

import helpers
import social_bot as bot
import social_channel as channel
import social_feed as feed

BANNED = [
    "that matter", "stay ahead", "game-chang", "unlock", "dive in", "deep dive", "cutting-edge", "seamless",
    "curated for you", "pick your source", "are on this", "supercharge", "revolution", "elevate", "effortless",
    "in today's fast-paced", "look no further", "!",
]


def reader_texts() -> dict[str, str]:
    edition = helpers.real_edition()
    texts = {f"bot reply {name}": reply for name, reply in feed.bot_replies(edition).items()
             if name in ("/start", "/help", "/about", "/privacy")}
    texts["bot description"] = bot.DESCRIPTION
    texts["bot short description"] = bot.SHORT_DESCRIPTION
    texts["bot menu"] = "\n".join(label for _command, label in bot.MENU)
    texts["channel description"] = channel.description("Morrow_brief_bot")
    texts["channel welcome"] = channel.welcome("Morrow_brief_bot")[0]
    texts["tagline"] = feed.TAGLINE
    return texts


def own_words(text: str, edition: dict) -> str:
    """The text without the outlets' own headlines and summaries, which are theirs to word."""
    for story in edition["stories"]:
        for theirs in (story["title"], story["dek"], feed.esc(story["title"]), feed.esc(story["dek"])):
            if theirs:
                text = text.replace(theirs, "")
    return text


class WordingTest(unittest.TestCase):
    def test_no_stock_phrase_or_emoji_in_anything_a_reader_sees(self):
        edition = helpers.real_edition()
        for name, text in reader_texts().items():
            ours = own_words(text, edition).lower()
            for phrase in BANNED:
                self.assertNotIn(phrase, ours, f"{name}: {phrase!r}")
            self.assertFalse(feed.has_emoji(text), name)

    def test_the_frame_of_the_daily_message_and_of_an_alert_is_plain(self):
        edition = helpers.real_edition()
        lead = feed.ranked(edition["stories"])[0]
        plain = feed.edition_telegram({**edition, "stories": [{**item, "dek": ""} for item in edition["stories"]]})
        for name, text in (("daily message", plain), ("alert", feed.story_telegram({**lead, "dek": ""}))):
            ours = own_words(text, edition).lower()
            for phrase in BANNED:
                self.assertNotIn(phrase, ours, f"{name}: {phrase!r}")

    def test_an_alert_says_who_reported_it_in_plain_words(self):
        story = helpers.story(1, "ai", 3, kind="lead")
        text = feed.story_telegram(story)
        self.assertRegex(text, r"(Reported by 3 outlets|Source: )")


if __name__ == "__main__":
    unittest.main()
