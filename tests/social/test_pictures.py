"""Stock prices in the one-message edition, and the outlets' pictures on the Telegram cards."""
from __future__ import annotations

import argparse
import io
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import helpers
import social_cards as cards
import social_feed as feed
import social_post as post_module

ANALYSIS = """
<section id="analysis">
<div class="an-table">
<details class="an-row"><summary class="tr-cols"><span class="tk"><b>NVDA</b><small>Nvidia</small></span>
<span class="n">162.85</span><span class="n down">-2.0%</span><span class="n down">-25.0%</span>
<span class="sc"><em>-80</em></span></summary><div class="an-detail"><dl><dt>1 week</dt><dd>-12.7%</dd></dl></div></details>
<details class="an-row"><summary class="tr-cols"><span class="tk"><b>BBRI</b><small>Bank Rakyat Indonesia</small></span>
<span class="n">3,150</span><span class="n up">+1.6%</span><span class="n up">+24.0%</span></summary></details>
<details class="an-row"><summary class="tr-cols"><span class="tk"><b>AAPL</b><small>Apple</small></span>
<span class="n">356.27</span><span class="n">0.0%</span><span class="n up">+4.2%</span></summary></details>
<details class="an-row"><summary class="tr-cols"><span class="tk"><b>NEW</b><small>Just listed</small></span>
<span class="n">12.00</span><span class="n">–</span><span class="n">–</span></summary></details>
</div>
<div class="an-table">
<details class="an-row"><summary class="va-cols"><span class="tk"><b>NVDA</b><small>Nvidia</small></span>
<span class="n">9.9</span><span class="n">0.20</span></summary><dl class="metrics"><div><dt>Market cap</dt><dd>3.77T USD</dd></div></dl></details>
<details class="an-row"><summary class="va-cols"><span class="tk"><b>BBRI</b><small>Bank Rakyat Indonesia</small></span>
<span class="n">7.0</span></summary><dl class="metrics"><div><dt>Market cap</dt><dd>467.09T IDR</dd></div></dl></details>
<details class="an-row"><summary class="va-cols"><span class="tk"><b>AAPL</b><small>Apple</small></span>
<span class="n">33.4</span></summary><dl class="metrics"><div><dt>Market cap</dt><dd>5.13T USD</dd></div></dl></details>
<details class="an-row"><summary class="va-cols"><span class="tk"><b>NEW</b><small>Just listed</small></span>
<span class="n">1.0</span></summary><dl class="metrics"><div><dt>Market cap</dt><dd>1.0B USD</dd></div></dl></details>
</div>
</section>
"""


def page_with(stories: list[dict], analysis: str = "", pictures: dict[int, str] | None = None) -> str:
    """The helpers' page, plus the analysis table and a picture inside the numbered stories' links."""
    text = helpers.page(stories)
    for number, url in (pictures or {}).items():
        target = f'<a class="story-link" href="https://example.com/story-{number}">'
        assert target in text
        text = text.replace(target, target + f'<img src="{url}" alt="">', 1)
    return text.replace("</body>", analysis + "</body>")


def many_stories(count: int = 9) -> list[dict]:
    stories = [helpers.story(1, "big_tech", 4, kind="lead")]
    stories += [helpers.story(number, "ai" if number % 2 else "space", 1 + number % 3) for number in range(2, count + 1)]
    return stories


def picture_bytes(size: tuple[int, int] = (800, 450), colour=(40, 90, 160), kind: str = "JPEG") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format=kind)
    return buffer.getvalue()


class PictureResponse:
    def __init__(self, status: int = 200, data: bytes = b""):
        self.status_code = status
        self.headers = {"Content-Type": "image/jpeg"}
        self._data = data

    def iter_content(self, size: int):
        for start in range(0, len(self._data), size):
            yield self._data[start:start + size]


class PictureHttp:
    """Answers picture requests by URL. A URL that is not listed is refused."""

    def __init__(self, answers: dict):
        self.answers = answers
        self.asked: list[str] = []
        self.headers: list[dict] = []

    def get(self, url: str, **kwargs):
        self.asked.append(url)
        self.headers.append(kwargs.get("headers") or {})
        answer = self.answers.get(url, PictureResponse(404))
        if isinstance(answer, Exception):
            raise answer
        return answer


class StockTest(unittest.TestCase):
    def setUp(self):
        self.edition = feed.parse_edition(page_with(many_stories(), ANALYSIS))

    def test_every_stock_is_read_with_price_move_and_currency(self):
        stocks = {stock["ticker"]: stock for stock in self.edition["stocks"]}
        self.assertEqual(list(stocks), ["NVDA", "BBRI", "AAPL", "NEW"])
        self.assertEqual(stocks["NVDA"], {"ticker": "NVDA", "name": "Nvidia", "price": "162.85", "pct": 2.0,
                                          "dir": "down", "currency": "USD"})
        self.assertEqual((stocks["BBRI"]["price"], stocks["BBRI"]["dir"], stocks["BBRI"]["currency"]),
                         ("3,150", "up", "IDR"))
        self.assertEqual((stocks["AAPL"]["pct"], stocks["AAPL"]["dir"]), (0.0, "flat"))
        self.assertIsNone(stocks["NEW"]["pct"])

    def test_a_page_without_the_table_has_no_stocks(self):
        self.assertEqual(feed.parse_edition(helpers.page(many_stories()))["stocks"], [])
        self.assertEqual(helpers.real_edition()["stocks"], [])

    def test_lines_group_by_currency_with_dollars_first_and_tickers_in_order(self):
        lines = feed.stock_lines(self.edition["stocks"])
        self.assertEqual(lines, [
            "<pre>USD\nAAPL 356.27 =0.0%\nNEW   12.00\nNVDA 162.85 ▼2.0%\n\nIDR\nBBRI 3,150 ▲1.6%</pre>",
        ])

    def test_one_currency_is_not_labelled(self):
        dollars = [stock for stock in self.edition["stocks"] if stock["currency"] == "USD"]
        self.assertEqual(feed.stock_lines(dollars), ["<pre>AAPL 356.27 =0.0%\nNEW   12.00\nNVDA 162.85 ▼2.0%</pre>"])

    def test_the_one_message_names_every_stock_and_stays_inside_the_limit(self):
        message = feed.edition_telegram(self.edition)
        self.assertIn("<b><u>STOCKS</u></b> · last price, 1-day move\n<pre>", message)
        for stock in self.edition["stocks"]:
            self.assertRegex(message, rf"(?m)^{stock['ticker']} +{stock['price']}\b")
        self.assertLessEqual(feed.visible_length(message), feed.EDITION_LIMIT)
        self.assertEqual(message.count("Not financial advice."), 1)
        self.assertLess(message.index("INDEXES"), message.index("STOCKS"))

    def test_a_full_page_still_lists_every_story_with_the_stocks(self):
        stories = [helpers.story(1, "big_tech", 4, kind="lead")]
        stories += [helpers.story(number, "ai", 1, title=f"Story number {number} " + "with a long headline " * 5)
                    for number in range(2, 34)]
        edition = feed.parse_edition(page_with(stories, ANALYSIS))
        message = feed.edition_telegram(edition)
        self.assertLessEqual(feed.visible_length(message), feed.EDITION_LIMIT)
        self.assertEqual(len(feed.edition_numbers(message)), 33)
        self.assertIn("NVDA 162.85", message)

    def test_without_stocks_the_message_is_as_before(self):
        plain = feed.parse_edition(helpers.page(many_stories()))
        message = feed.edition_telegram(plain)
        self.assertNotIn("STOCKS", message)
        self.assertIn("Not financial advice.", message)

    def test_the_tape_reply_and_the_help_carry_the_stocks(self):
        replies = feed.bot_replies(self.edition)
        self.assertIn("NVDA 162.85 ▼2.0%", replies["/tape"])
        self.assertIn("/tape index and stock prices", replies["/help"])
        self.assertLessEqual(feed.visible_length(replies["/tape"]), feed.LIMITS["telegram_message"])
        plain = feed.bot_replies(feed.parse_edition(helpers.page(many_stories())))
        self.assertIn("/tape index moves", plain["/help"])

    def test_numbers_are_read_back_from_the_message(self):
        message = feed.edition_telegram(self.edition)
        numbers = feed.edition_numbers(message)
        self.assertEqual(sorted(numbers.values()), list(range(1, 10)))
        self.assertEqual(numbers["https://example.com/story-1"], 1)


class PictureParseTest(unittest.TestCase):
    def test_a_story_carries_the_picture_the_page_shows(self):
        edition = feed.parse_edition(page_with(many_stories(), pictures={
            2: "https://img.example.com/two.jpg", 3: "http://img.example.com/plain.jpg", 4: "data:image/png;base64,AAAA"}))
        images = {story["url"].rsplit("-", 1)[1]: story["image"] for story in edition["stories"]}
        self.assertEqual(images["2"], "https://img.example.com/two.jpg")
        self.assertEqual(images["3"], "")  # not https
        self.assertEqual(images["4"], "")
        self.assertEqual(images["5"], "")

    def test_the_public_feed_does_not_carry_picture_addresses(self):
        edition = feed.parse_edition(page_with(many_stories(), pictures={2: "https://img.example.com/two.jpg"}))
        self.assertNotIn("img.example.com", json.dumps(feed.public_feed(edition, [])))


class PhotoCardTest(unittest.TestCase):
    def tiles(self, count: int) -> list[dict]:
        return [{"number": index * 3 + 1, "title": f"Headline number {index} about something that happened today",
                 "source": f"Outlet {index}", "picture": Image.new("RGB", (900, 500), (30 * index, 80, 150))}
                for index in range(count)]

    def test_cover_with_six_and_with_four_tiles_stays_on_the_card(self):
        for count in (6, 4):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "digest-photos.jpg"
                metrics = cards.render_photo_cover(self.tiles(count), "2026-11-17", 33, 14, path)
                with Image.open(path) as saved:
                    self.assertEqual((saved.format, saved.size), ("JPEG", (cards.WIDTH, cards.HEIGHT)))
                self.assertLess(path.stat().st_size, 5_000_000)
            self.assertEqual(metrics["tiles"], count)
            self.assertFalse(metrics["clipped"])
            for left, top, right, bottom in metrics["boxes"]:
                self.assertGreaterEqual(left, 0)
                self.assertLessEqual(right, cards.WIDTH)
                self.assertLessEqual(bottom, metrics["grid_bottom"])
            boxes = metrics["boxes"]
            for first in range(len(boxes)):
                for second in range(first + 1, len(boxes)):
                    a, b = boxes[first], boxes[second]
                    self.assertTrue(a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])

    def test_a_tile_shows_its_picture(self):
        tiles = self.tiles(6)
        tiles[0]["picture"] = Image.new("RGB", (900, 500), (0, 200, 0))
        canvas_metrics = cards.render_photo_cover(tiles, "2026-11-17", 33, 14)
        self.assertEqual(canvas_metrics["tiles"], 6)

    def test_a_very_long_headline_is_cut_and_reported(self):
        tiles = self.tiles(6)
        tiles[2]["title"] = "A headline that goes on and on " * 8
        self.assertTrue(cards.render_photo_cover(tiles, "2026-11-17", 33, 14)["clipped"])

    def test_story_photo_card_keeps_the_headline_clear_of_the_outlet_count(self):
        edition = feed.parse_edition(helpers.page(many_stories()))
        for story in edition["stories"][:4]:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "story-photo.jpg"
                metrics = cards.render_story_photo_card(story, Image.new("RGB", (640, 640), (90, 20, 20)),
                                                        "2026-11-17", path)
                self.assertTrue(path.exists())
            self.assertFalse(metrics["overlaps"])
            self.assertFalse(metrics["clipped"])
            self.assertLessEqual(metrics["max_right"], cards.WIDTH - cards.MARGIN + 1)


class AttachPicturesTest(unittest.TestCase):
    def setUp(self):
        self.pictures = {number: f"https://img.example.com/{number}.jpg" for number in range(2, 10)}
        self.edition = feed.parse_edition(page_with(many_stories(), ANALYSIS, self.pictures))
        self.digest = feed.digest_post(feed.pick_digest(self.edition["stories"]), self.edition["markets"],
                                       self.edition["date"], self.edition)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.out = Path(self.folder.name)

    def http(self, good: int, **special) -> PictureHttp:
        answers = {url: PictureResponse(200, picture_bytes()) for url in list(self.pictures.values())[:good]}
        answers.update(special)
        return PictureHttp(answers)

    def test_six_pictures_make_a_photo_cover_numbered_as_the_message(self):
        http = self.http(8)
        line = post_module.attach_pictures(self.digest, self.edition, self.out, http)
        self.assertEqual(self.digest["telegram_cover"], f"cards/{self.edition['date']}/digest-photos.jpg")
        self.assertTrue((self.out / self.digest["telegram_cover"]).exists())
        self.assertIn("photo cover: 6 pictures", line)
        self.assertEqual(len(http.asked), 6)  # it stops asking once the grid is full
        self.assertTrue(all("MorrowBrief" in headers.get("User-Agent", "") for headers in http.headers))
        self.assertEqual(post_module.telegram_picture(self.digest), self.digest["telegram_cover"])

    def test_four_or_five_pictures_make_a_cover_of_four(self):
        line = post_module.attach_pictures(self.digest, self.edition, self.out, self.http(5))
        self.assertIn("photo cover: 4 pictures", line)

    def test_too_few_pictures_keep_the_text_card(self):
        line = post_module.attach_pictures(self.digest, self.edition, self.out, self.http(3))
        self.assertNotIn("telegram_cover", self.digest)
        self.assertIn("not drawn, 3 of 8 pictures", line)
        self.assertEqual(post_module.telegram_picture(self.digest), self.digest["cards"][0])

    def test_bad_answers_are_left_out_one_by_one(self):
        urls = list(self.pictures.values())
        http = self.http(
            8,
            **{
                urls[0]: PictureResponse(403),
                urls[1]: PictureResponse(200, b"<html>not a picture</html>"),
                urls[2]: PictureResponse(200, picture_bytes((120, 80))),
                urls[3]: ConnectionError("no route"),
            },
        )
        line = post_module.attach_pictures(self.digest, self.edition, self.out, http)
        self.assertIn("photo cover: 4 pictures", line)
        self.assertEqual(len(http.asked), 8)

    def test_a_picture_that_is_too_large_is_refused(self):
        huge = PictureResponse(200, b"\xff" * (post_module.PHOTO_MAX_BYTES + 10))
        self.assertIsNone(post_module.fetch_picture(PictureHttp({"https://x/y.jpg": huge}), "https://x/y.jpg"))

    def test_the_time_budget_ends_the_asking(self):
        ticks = iter(range(0, 100000, 40))
        line = post_module.attach_pictures(self.digest, self.edition, self.out, self.http(8), clock=lambda: next(ticks))
        self.assertIn("not drawn", line)

    def test_a_cover_already_drawn_is_used_again_without_asking(self):
        post_module.attach_pictures(self.digest, self.edition, self.out, self.http(8))
        again = feed.digest_post(feed.pick_digest(self.edition["stories"]), self.edition["markets"],
                                 self.edition["date"], self.edition)
        http = self.http(0)
        line = post_module.attach_pictures(again, self.edition, self.out, http)
        self.assertEqual(http.asked, [])
        self.assertIn("already drawn", line)
        self.assertEqual(again["telegram_cover"], self.digest["telegram_cover"])

    def test_the_preview_of_the_message_points_at_the_photo_cover(self):
        post_module.attach_pictures(self.digest, self.edition, self.out, self.http(8))
        fields = post_module.telegram_edition_fields(self.digest, "-100", "https://cards.example/")
        preview = json.loads(fields["link_preview_options"])
        self.assertEqual(preview["url"], "https://cards.example/" + self.digest["telegram_cover"])
        self.assertTrue(preview["show_above_text"])

    def test_an_alert_gets_a_photo_card_and_it_is_what_is_sent(self):
        story = next(item for item in self.edition["stories"] if item["image"])
        alert = feed.story_post(story, self.edition["date"])
        cards.render_post_cards(alert, self.edition, self.out)
        line = post_module.attach_pictures(alert, self.edition, self.out, self.http(8))
        self.assertIn("photo card: drawn", line)
        self.assertTrue(alert["telegram_cover"].endswith(f"{story['id']}-photo.jpg"))
        http = helpers.FakeHttp()
        post_module.send_telegram_post(http, "123:abc", "-100", alert, self.out)
        url, kwargs = http.calls[-1]
        self.assertTrue(url.endswith("/sendPhoto"))
        name, data, kind = kwargs["files"]["photo"]
        self.assertEqual((name, kind), (f"{story['id']}-photo.jpg", "image/jpeg"))
        self.assertEqual(data, (self.out / alert["telegram_cover"]).read_bytes())

    def test_an_alert_without_a_picture_keeps_its_text_card(self):
        story = self.edition["stories"][0]
        self.assertEqual(story["image"], "")
        alert = feed.story_post(story, self.edition["date"])
        cards.render_post_cards(alert, self.edition, self.out)
        post_module.attach_pictures(alert, self.edition, self.out, self.http(8))
        self.assertNotIn("telegram_cover", alert)
        refused = feed.story_post(next(item for item in self.edition["stories"] if item["image"]), self.edition["date"])
        line = post_module.attach_pictures(refused, self.edition, self.out, self.http(0))
        self.assertIn("could not be fetched", line)
        self.assertNotIn("telegram_cover", refused)

    def test_a_photo_card_whose_file_is_gone_falls_back_to_the_text_card(self):
        story = next(item for item in self.edition["stories"] if item["image"])
        alert = feed.story_post(story, self.edition["date"])
        cards.render_post_cards(alert, self.edition, self.out)
        alert["telegram_cover"] = f"cards/{self.edition['date']}/missing-photo.jpg"
        http = helpers.FakeHttp()
        post_module.send_telegram_post(http, "123:abc", "-100", alert, self.out)
        name, _, kind = http.calls[-1][1]["files"]["photo"]
        self.assertEqual((name, kind), (f"{story['id']}.png", "image/png"))

    def test_build_freezes_the_digest_with_its_photo_cover(self):
        page_path = self.out / "index.html"
        page_path.write_text(page_with(many_stories(), ANALYSIS, self.pictures), encoding="utf-8")
        data = self.out / "data"
        args = argparse.Namespace(page=str(page_path), out=str(data), now="2026-11-14T09:30:00+07:00", run_id="")
        self.assertEqual(post_module.command_build(args, http=self.http(8)), 0)
        state = json.loads((data / "state.json").read_text(encoding="utf-8"))
        frozen = next(iter(state["posts"].values()))
        self.assertEqual(frozen["kind"], "digest")
        self.assertTrue((data / frozen["telegram_cover"]).exists())
        self.assertIn("STOCKS", frozen["telegram_edition"])

    def test_sample_can_draw_first_and_send_later(self):
        page_path = self.out / "index.html"
        page_path.write_text(page_with(many_stories(), ANALYSIS, self.pictures), encoding="utf-8")
        sample = self.out / "sample"
        env = {"TELEGRAM_BOT_TOKEN": "123:abc", "TELEGRAM_CHAT_ID": "-1001234567890"}
        drawn = argparse.Namespace(page=str(page_path), out=str(sample), image_base=None, render_only=True, image_wait=0)
        pictures = self.http(8)
        self.assertEqual(post_module.command_sample(drawn, http=pictures, env=env, sleep=lambda seconds: None), 0)
        self.assertEqual(len(pictures.asked), 6)
        http = helpers.FakeHttp()
        sent = argparse.Namespace(page=str(page_path), out=str(sample), image_base=["https://cards.example/"],
                                  render_only=False, image_wait=0)
        self.assertEqual(post_module.command_sample(sent, http=http, env=env, sleep=lambda seconds: None), 0)
        probe = [url for url, _ in http.calls if url.startswith("https://cards.example/")]
        self.assertTrue(probe and probe[0].endswith("digest-photos.jpg"))
        fields = [kwargs for url, kwargs in http.calls if url.endswith("/sendMessage")][-1]["data"]
        self.assertTrue(json.loads(fields["link_preview_options"])["url"].endswith("digest-photos.jpg"))


if __name__ == "__main__":
    unittest.main()
