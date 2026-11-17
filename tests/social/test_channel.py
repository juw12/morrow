"""The channel commands: finding it, reading the bot's rights, setting its profile, and the capability test."""
import contextlib
import datetime
import io
import json
import os
import pathlib
import tempfile
import unittest
from unittest import mock

import requests

import helpers  # noqa: F401  (puts scripts/ on the path)
from helpers import FakeResponse

import social_channel as channel
import social_feed as feed

TOKEN = "123456789:AAExampleBotTokenThatMustNeverLeak"
ME = {"id": 42, "username": "Morrow_brief_bot", "first_name": "Morrow Brief"}
PUBLIC = {"id": -1001234567890, "type": "channel", "title": "Morrow Brief", "username": "morrowbrief"}
PRIVATE = {"id": -1009876543210, "type": "channel", "title": "My channel"}
POST_ONLY = {"status": "administrator", "can_post_messages": True}
FULL = {**POST_ONLY, "can_edit_messages": True, "can_delete_messages": True, "can_change_info": True}
JPEG = b"\xff\xd8\xff test picture"


def ok(result=True) -> FakeResponse:
    return FakeResponse(200, {"ok": True, "result": result})


def refused(text: str, status: int = 400) -> FakeResponse:
    return FakeResponse(status, {"ok": False, "description": text})


class Telegram:
    """Stands in for `requests`: answers by Bot API method name, and numbers the posts it is sent."""

    def __init__(self, **answers):
        self.answers = {"getMe": ok(ME), **answers}
        self.calls: list[tuple[str, dict]] = []
        self.next_post = 100

    def post(self, url: str, **kwargs):
        method = url.rsplit("/", 1)[1]
        self.calls.append((method, kwargs))
        answer = self.answers.get(method)
        if callable(answer):
            answer = answer(kwargs)
        if isinstance(answer, Exception):
            raise answer
        if answer is not None:
            return answer
        if method == "sendMediaGroup":
            self.next_post += 2
            return ok([{"message_id": self.next_post - 1}, {"message_id": self.next_post}])
        if method.startswith("send"):
            self.next_post += 1
            return ok({"message_id": self.next_post})
        return ok(True)

    def methods(self) -> list[str]:
        return [method for method, _kwargs in self.calls]

    def sent(self, method: str) -> list[dict]:
        return [kwargs.get("json") or kwargs.get("data") for name, kwargs in self.calls if name == method]


class ReferenceTest(unittest.TestCase):
    def test_what_a_person_pastes_becomes_what_telegram_accepts(self):
        cases = {
            "@morrowbrief": "@morrowbrief",
            "morrowbrief": "@morrowbrief",
            "t.me/morrowbrief": "@morrowbrief",
            "https://t.me/morrowbrief/12": "@morrowbrief",
            "https://t.me/s/morrowbrief": "@morrowbrief",
            "https://telegram.me/Morrow_Brief/": "@Morrow_Brief",
            "https://t.me/c/1234567890/12": "-1001234567890",
            "t.me/c/1234567890": "-1001234567890",
            "-1001234567890": "-1001234567890",
            " <https://t.me/morrowbrief> ": "@morrowbrief",
        }
        for pasted, expected in cases.items():
            with self.subTest(pasted=pasted):
                self.assertEqual(channel.chat_reference(pasted), expected)

    def test_what_is_not_a_chat_is_refused(self):
        for pasted in ("", "abc", "https://example.com/morrowbrief", "t.me/+AbCdEfInviteLink", "12345", "@1name"):
            with self.subTest(pasted=pasted):
                self.assertIsNone(channel.chat_reference(pasted))

    def test_a_list_keeps_its_order_and_drops_repeats(self):
        self.assertEqual(
            channel.references("@morrowbrief, t.me/MorrowBrief/3\nhttps://t.me/c/1234567890/5 nonsense!"),
            ["@morrowbrief", "-1001234567890"],
        )

    def test_the_likely_handles_are_all_valid_and_distinct(self):
        self.assertEqual(len(channel.LIKELY_HANDLES), len(set(channel.LIKELY_HANDLES)))
        for handle in channel.LIKELY_HANDLES:
            self.assertEqual(channel.chat_reference(handle), f"@{handle}")


class CopyTest(unittest.TestCase):
    def test_the_description_fits_and_names_the_site_and_the_bot(self):
        text = channel.description(ME["username"])
        self.assertLessEqual(len(text), channel.MAX_DESCRIPTION)
        self.assertIn(feed.SITE_SHORT, text)
        self.assertIn("@Morrow_brief_bot", text)
        self.assertIn("Not financial advice", text)
        self.assertFalse(feed.EMOJI_PATTERN.search(text))

    def test_the_welcome_fits_a_message_and_its_buttons_lead_somewhere(self):
        text, buttons = channel.welcome(ME["username"])
        self.assertLessEqual(feed.visible_length(text), feed.LIMITS["telegram_message"])
        self.assertTrue(text.startswith(f"<b>{feed.BRAND}</b>\n"))
        self.assertFalse(feed.EMOJI_PATTERN.search(text))
        self.assertIn("Not financial advice", text)
        self.assertIn("08:00 Jakarta time", text)
        self.assertIn(f"{feed.ALERT_MIN_OUTLETS} or more outlets", text)
        self.assertNotIn("that matter", text)
        urls = [button["url"] for row in buttons["inline_keyboard"] for button in row]
        self.assertEqual(urls, [feed.SITE_URL, "https://t.me/Morrow_brief_bot"])

    def test_the_title_is_the_brand(self):
        self.assertEqual(channel.TITLE, feed.BRAND)
        self.assertLessEqual(len(channel.TITLE), 128)


class FindTest(unittest.TestCase):
    def test_reports_only_the_chat_where_the_bot_is_admin(self):
        chats = {"@other": {**PUBLIC, "title": "Someone else", "username": "other"}, "@morrowbrief": PUBLIC}
        http = Telegram(
            getChat=lambda kwargs: ok(chats[kwargs["json"]["chat_id"]])
            if kwargs["json"]["chat_id"] in chats else refused("Bad Request: chat not found"),
            getChatMember=lambda kwargs: ok(POST_ONLY if kwargs["json"]["chat_id"] == "@morrowbrief"
                                            else {"status": "left"}),
        )
        log, admin_of = channel.find(http, TOKEN, ["@missing", "@other", "@morrowbrief"])
        self.assertEqual([chat["username"] for chat in admin_of], ["morrowbrief"])
        text = "\n".join(log)
        self.assertIn("FOUND", text)
        self.assertIn("@morrowbrief", text)
        self.assertIn("not an admin there", text)
        self.assertIn("3 names asked, 1 not found", text)
        self.assertNotIn(TOKEN, text)

    def test_a_rate_limit_stops_the_search(self):
        http = Telegram(getChat=refused("Too Many Requests: retry after 300", 429))
        log, admin_of = channel.find(http, TOKEN, ["@one", "@two", "@three"])
        self.assertEqual(admin_of, [])
        self.assertEqual(http.methods().count("getChat"), 1)
        self.assertIn("pause", log[0])

    def test_a_private_channel_id_stays_out_of_the_log(self):
        http = Telegram(getChat=ok(PRIVATE), getChatMember=ok(POST_ONLY))
        log, admin_of = channel.find(http, TOKEN, ["-1009876543210"])
        self.assertEqual(len(admin_of), 1)
        self.assertNotIn("9876543210", "\n".join(log))


class StatusTest(unittest.TestCase):
    def test_lists_what_the_channel_shows_and_each_right(self):
        http = Telegram(getChat=ok({**PUBLIC, "description": "Old words\nmore"}), getChatMember=ok(POST_ONLY),
                        getChatMemberCount=ok(3))
        log, member = channel.status(http, TOKEN, "@morrowbrief")
        text = "\n".join(log)
        self.assertEqual(member["status"], "administrator")
        self.assertIn("subscribers: 3", text)
        self.assertIn("picture: none", text)
        self.assertIn("yes  Post messages", text)
        self.assertIn("no   Change channel info", text)
        self.assertEqual(sum(line.startswith("  ") for line in log), len(channel.RIGHTS))

    def test_a_chat_the_bot_cannot_see_says_what_to_check(self):
        http = Telegram(getChat=refused("Bad Request: chat not found"))
        log, member = channel.status(http, TOKEN, "@nowhere")
        self.assertEqual(member, {})
        self.assertIn("admin", log[-1])


class SetupTest(unittest.TestCase):
    def test_sets_the_name_description_picture_and_pins_a_welcome(self):
        http = Telegram(getChat=ok({**PUBLIC, "title": "test"}), getChatMember=ok(FULL))
        log, failed = channel.setup(http, TOKEN, "@morrowbrief", JPEG)
        self.assertEqual(failed, 0, log)
        self.assertEqual(http.methods(), ["getMe", "getChat", "getChatMember", "setChatTitle", "setChatDescription",
                                          "setChatPhoto", "sendMessage", "pinChatMessage"])
        self.assertEqual(http.sent("setChatTitle")[0]["title"], feed.BRAND)
        self.assertEqual(http.sent("setChatDescription")[0]["description"], channel.description(ME["username"]))
        (_method, upload), = [call for call in http.calls if call[0] == "setChatPhoto"]
        self.assertEqual(upload["files"]["photo"][1], JPEG)
        welcome = http.sent("sendMessage")[0]
        self.assertIs(welcome["disable_notification"], True)
        self.assertEqual(welcome["parse_mode"], "HTML")
        pin = http.sent("pinChatMessage")[0]
        self.assertEqual(pin["message_id"], 101)
        self.assertIs(pin["disable_notification"], True)

    def test_what_is_already_right_is_left_alone_and_the_welcome_is_not_posted_twice(self):
        pinned = {"message_id": 7, "text": feed.BRAND + "\nTech and markets, read across the outlets."}
        chat = {**PUBLIC, "description": channel.description(ME["username"]), "pinned_message": pinned}
        http = Telegram(getChat=ok(chat), getChatMember=ok(FULL))
        log, failed = channel.setup(http, TOKEN, "@morrowbrief", JPEG)
        self.assertEqual(failed, 0, log)
        self.assertNotIn("setChatTitle", http.methods())
        self.assertNotIn("setChatDescription", http.methods())
        self.assertNotIn("sendMessage", http.methods())
        self.assertEqual(http.sent("editMessageText")[0]["message_id"], 7)

    def test_a_missing_right_is_named_in_the_words_the_app_uses(self):
        no_rights = refused("Bad Request: not enough rights to change chat title")
        http = Telegram(getChat=ok({**PUBLIC, "title": "test"}), getChatMember=ok(POST_ONLY), setChatTitle=no_rights,
                        setChatDescription=no_rights, setChatPhoto=no_rights,
                        pinChatMessage=refused("Bad Request: not enough rights to manage pinned messages in the chat"))
        log, failed = channel.setup(http, TOKEN, "@morrowbrief", JPEG)
        text = "\n".join(log)
        self.assertEqual(failed, 4)
        self.assertIn('"Change channel info"', text)
        self.assertIn('"Edit messages of others"', text)
        self.assertIn("welcome post: done", text)

    def test_telegram_saying_nothing_changed_counts_as_done(self):
        http = Telegram(getChat=ok({**PUBLIC, "title": "test"}), getChatMember=ok(FULL),
                        setChatDescription=refused("Bad Request: chat description is not modified"))
        log, failed = channel.setup(http, TOKEN, "@morrowbrief", JPEG)
        self.assertEqual(failed, 0, log)


class CapabilityTest(unittest.TestCase):
    def run_test(self, **answers):
        http = Telegram(**answers)
        log, failed = channel.test(http, TOKEN, "@morrowbrief", JPEG, sleep=lambda _seconds: None)
        return http, log, failed

    def test_every_post_is_silent_labelled_and_deleted(self):
        http, log, failed = self.run_test()
        self.assertEqual(failed, 0, log)
        for method in ("sendMessage", "sendPhoto", "sendMediaGroup", "sendPoll"):
            payload = http.sent(method)[0]
            self.assertIn(payload["disable_notification"], (True, "true"), method)
        self.assertIn("Test post", http.sent("sendMessage")[0]["text"])
        self.assertIn("Test post", http.sent("sendPhoto")[0]["caption"])
        self.assertEqual(http.sent("deleteMessages")[0]["message_ids"], [101, 102, 103, 104, 105])
        self.assertEqual(http.methods()[-1], "deleteMessages")
        self.assertIn("5 of 5 test posts removed", "\n".join(log))
        self.assertEqual(sum(line.startswith("PASS") for line in log), 9)
        self.assertEqual(sum(line.startswith("NO ") for line in log), len(channel.NOT_POSSIBLE))

    def test_the_album_is_two_attached_pictures(self):
        http, _log, _failed = self.run_test()
        (_method, upload), = [call for call in http.calls if call[0] == "sendMediaGroup"]
        media = json.loads(upload["data"]["media"])
        self.assertEqual([item["media"] for item in media], ["attach://one", "attach://two"])
        self.assertEqual(sorted(upload["files"]), ["one", "two"])

    def test_a_refusal_is_reported_and_the_rest_still_runs(self):
        http, log, failed = self.run_test(sendPoll=refused("Bad Request: polls can't be sent to this chat"),
                                          setMessageReaction=refused(f"Bad Request: REACTION_INVALID bot{TOKEN}"))
        text = "\n".join(log)
        self.assertEqual(failed, 0)
        self.assertIn("FAIL  post a poll: Bad Request", text)
        self.assertIn("FAIL  react to a post", text)
        self.assertIn("PASS  post an album", text)
        self.assertNotIn(TOKEN, text)
        self.assertEqual(http.sent("deleteMessages")[0]["message_ids"], [101, 102, 103, 104])

    def test_posts_that_cannot_be_deleted_are_listed_for_the_owner(self):
        http, log, failed = self.run_test(
            deleteMessages=refused("Bad Request: method not available"),
            deleteMessage=lambda kwargs: refused("Bad Request: message can't be deleted")
            if kwargs["json"]["message_id"] == 103 else ok(True),
        )
        self.assertEqual(failed, 1)
        self.assertIn("4 of 5 test posts removed", "\n".join(log))
        self.assertIn("[103]", "\n".join(log))

    def test_a_bot_that_cannot_post_fails_and_deletes_nothing(self):
        no = refused("Bad Request: need administrator rights in the channel chat")
        http, log, failed = self.run_test(sendMessage=no, sendPhoto=no, sendMediaGroup=no, sendPoll=no)
        self.assertEqual(failed, 2)
        self.assertNotIn("deleteMessages", http.methods())
        self.assertNotIn("editMessageText", http.methods())

    def test_no_network_is_a_failure_not_a_crash(self):
        http, log, failed = self.run_test(sendMessage=requests.exceptions.ConnectionError("down"))
        self.assertIn("Telegram unreachable (ConnectionError)", "\n".join(log))


class CommandLineTest(unittest.TestCase):
    def run_main(self, argv: list[str], env: dict, http: Telegram | None = None) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(output), \
                mock.patch.object(channel, "requests", http or Telegram()), \
                mock.patch.object(channel, "avatar_jpeg", lambda: JPEG), \
                mock.patch.object(channel.time, "sleep", lambda _seconds: None):
            for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
                if name not in env:
                    os.environ.pop(name, None)
            code = channel.main(argv)
        return code, output.getvalue()

    def test_every_command_needs_a_token(self):
        for command in ("find", "status", "setup", "test", "listen"):
            self.assertEqual(self.run_main([command], {})[0], 1)

    def test_without_a_channel_it_says_how_to_give_one(self):
        code, text = self.run_main(["status"], {"TELEGRAM_BOT_TOKEN": TOKEN})
        self.assertEqual(code, 1)
        self.assertIn("--chat", text)

    def test_the_secret_is_used_when_no_chat_is_given(self):
        http = Telegram(getChat=ok(PUBLIC), getChatMember=ok(POST_ONLY), getChatMemberCount=ok(1))
        code, text = self.run_main(["status"], {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "@morrowbrief"}, http)
        self.assertEqual(code, 0, text)
        self.assertEqual(http.sent("getChat")[0]["chat_id"], "@morrowbrief")
        self.assertNotIn(TOKEN, text)

    def test_find_without_names_tries_the_likely_handles_and_explains_a_miss(self):
        http = Telegram(getChat=refused("Bad Request: chat not found"))
        code, text = self.run_main(["find"], {"TELEGRAM_BOT_TOKEN": TOKEN}, http)
        self.assertEqual(code, 1)
        self.assertEqual(http.methods().count("getChat"), len(channel.LIKELY_HANDLES))
        self.assertIn("Copy link", text)

    def test_setup_and_test_run_end_to_end_from_the_command_line(self):
        http = Telegram(getChat=ok({**PUBLIC, "title": "test"}), getChatMember=ok(FULL))
        env = {"TELEGRAM_BOT_TOKEN": TOKEN}
        code, text = self.run_main(["setup", "--chat", "https://t.me/morrowbrief/2"], env, http)
        self.assertEqual(code, 0, text)
        self.assertIn("pin the welcome post: done", text)
        code, text = self.run_main(["test", "--chat", "@morrowbrief"], env, Telegram())
        self.assertEqual(code, 0, text)
        self.assertIn("checks passed", text)

    def test_the_real_picture_is_a_jpeg(self):
        self.assertEqual(channel.avatar_jpeg()[:3], b"\xff\xd8\xff")


MORROW = {"id": -1005550001111, "type": "channel", "title": "Morrow News"}
FEED = {"bot": {"/help": "the menu", "/today": "five stories"}, "stories": []}
KEY = "a key only the owner holds"


def text_message(update_id: int, text: str) -> dict:
    return {"update_id": update_id, "message": {"text": text, "chat": {"id": 500, "type": "private"}}}


def channel_post(update_id: int, chat: dict) -> dict:
    return {"update_id": update_id, "channel_post": {"message_id": 7, "text": "hello", "chat": chat}}


def batches(*groups):
    """getUpdates answers: one list of updates per call, then nothing new."""
    waiting = list(groups)

    def answer(_kwargs):
        return ok(waiting.pop(0) if waiting else [])

    return answer


class Clock:
    """Each look at the clock moves it on, so a wait ends without real time passing."""

    def __init__(self, step: int = 30):
        self.now = 0
        self.step = step

    def __call__(self) -> int:
        self.now += self.step
        return self.now


def run_listen(http: Telegram, seconds: int = 600, feed_data: dict | None = None, step: int = 30, refresh=None):
    said: list[str] = []
    chat, offset = channel.listen(
        http, TOKEN, dict(FEED) if feed_data is None else feed_data, seconds,
        say=said.append, clock=Clock(step), sleep=lambda _seconds: None, refresh=refresh,
    )
    return chat, offset, "\n".join(said)


class SealTest(unittest.TestCase):
    def test_the_key_holder_reads_the_id_back(self):
        for chat_id in (-1005550001111, "-1001234567890", -42):
            with self.subTest(chat_id=chat_id):
                self.assertEqual(channel.unseal(channel.seal(chat_id, KEY), KEY), str(chat_id))

    def test_the_id_is_not_readable_in_the_seal(self):
        sealed = channel.seal(MORROW["id"], KEY)
        self.assertNotIn("5550001111", sealed)
        self.assertNotIn(b"5550001111", bytes.fromhex(sealed))
        self.assertRegex(sealed, r"^[0-9a-f]+$")

    def test_two_seals_of_one_id_differ_and_length_says_nothing(self):
        first, second = channel.seal(MORROW["id"], KEY), channel.seal(MORROW["id"], KEY)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first), len(channel.seal(-42, KEY)))

    def test_the_wrong_key_or_a_damaged_seal_opens_nothing(self):
        sealed = channel.seal(MORROW["id"], KEY)
        self.assertIsNone(channel.unseal(sealed, "another key"))
        self.assertIsNone(channel.unseal(sealed[:-2] + ("00" if sealed[-2:] != "00" else "11"), KEY))
        for text in ("", "not hex", "abcd"):
            self.assertIsNone(channel.unseal(text, KEY))


class ChannelInTest(unittest.TestCase):
    def test_each_way_a_channel_shows_itself(self):
        forwarded = {"text": "hello", "chat": {"id": 500, "type": "private"}}
        cases = {
            "a post in the channel": channel_post(1, MORROW),
            "a change to the bot's place": {"update_id": 1, "my_chat_member": {
                "chat": MORROW, "new_chat_member": {"status": "administrator"}}},
            "a post forwarded to the bot": {"update_id": 1, "message": {
                **forwarded, "forward_origin": {"type": "channel", "chat": MORROW, "message_id": 3}}},
            "a post forwarded to the bot, as older apps send it": {"update_id": 1, "message": {
                **forwarded, "forward_from_chat": MORROW}},
        }
        for name, update in cases.items():
            with self.subTest(name=name):
                self.assertEqual(channel.channel_in(update), MORROW)

    def test_messages_groups_and_people_are_not_channels(self):
        group = {"id": -100777, "type": "supergroup", "title": "Morrow chat"}
        for update in (
            text_message(1, "/today"),
            {"update_id": 2, "my_chat_member": {"chat": group, "new_chat_member": {"status": "member"}}},
            {"update_id": 3, "message": {"chat": {"id": 5, "type": "private"},
                                         "forward_origin": {"type": "user", "sender_user": {"id": 9}}}},
            {"update_id": 4},
        ):
            self.assertIsNone(channel.channel_in(update))


class ListenTest(unittest.TestCase):
    def test_finds_the_channel_from_each_trigger_after_taking_over_from_the_webhook(self):
        triggers = [
            channel_post(11, MORROW),
            {"update_id": 11, "my_chat_member": {"chat": MORROW, "new_chat_member": FULL}},
            {"update_id": 11, "message": {"chat": {"id": 500, "type": "private"}, "text": "see this",
                                          "forward_origin": {"type": "channel", "chat": MORROW}}},
        ]
        for trigger in triggers:
            with self.subTest(kind=[key for key in trigger if key != "update_id"][0]):
                http = Telegram(getUpdates=batches([trigger]), getChatMember=ok(FULL))
                chat, offset, text = run_listen(http)
                self.assertEqual(chat, MORROW)
                self.assertEqual(offset, 12)
                self.assertEqual(http.methods()[:3], ["getMe", "deleteWebhook", "getUpdates"])
                self.assertEqual(http.sent("deleteWebhook")[0], {"drop_pending_updates": False})
                self.assertEqual(http.sent("getUpdates")[0]["allowed_updates"], channel.LISTEN_UPDATES)
                self.assertEqual(http.sent("getChatMember")[0], {"chat_id": MORROW["id"], "user_id": ME["id"]})
                self.assertIn("FOUND", text)
                self.assertIn("Morrow News", text)
                self.assertNotIn("5550001111", text)
                self.assertNotIn(TOKEN, text)
                self.assertNotIn("sendMessage", http.methods())

    def test_a_channel_with_another_name_is_counted_and_never_named(self):
        http = Telegram(getUpdates=batches([channel_post(3, PRIVATE)]))
        chat, _offset, text = run_listen(http, seconds=200)
        self.assertIsNone(chat)
        self.assertNotIn("getChatMember", http.methods())
        self.assertIn("1 updates from other channels ignored", text)
        self.assertNotIn("My channel", text)
        self.assertNotIn("9876543210", text)

    def test_a_morrow_channel_where_the_bot_is_not_admin_is_not_taken(self):
        http = Telegram(getUpdates=batches([channel_post(3, MORROW)]), getChatMember=ok({"status": "left"}))
        chat, _offset, text = run_listen(http, seconds=200)
        self.assertIsNone(chat)
        self.assertIn("1 updates from other channels ignored", text)

    def test_messages_are_answered_while_it_waits(self):
        http = Telegram(
            getUpdates=batches([text_message(1, "/today"), text_message(2, "hi")], [channel_post(3, MORROW)]),
            getChatMember=ok(FULL),
        )
        chat, offset, text = run_listen(http)
        self.assertEqual(chat, MORROW)
        self.assertEqual(offset, 4)
        self.assertEqual([sent["text"] for sent in http.sent("sendMessage")], ["five stories", "the menu"])
        self.assertEqual(http.sent("getUpdates")[1]["offset"], 3)
        self.assertIn("2 messages answered", text)

    def test_the_time_running_out_ends_it_without_a_channel(self):
        http = Telegram(getUpdates=batches())
        chat, offset, text = run_listen(http, seconds=200)
        self.assertIsNone(chat)
        self.assertIsNone(offset)
        self.assertGreaterEqual(http.methods().count("getUpdates"), 1)
        self.assertIn("no Morrow channel", text)

    def test_another_reader_of_the_bot_stops_it_at_once(self):
        http = Telegram(getUpdates=refused("Conflict: terminated by other getUpdates request", 409))
        chat, _offset, text = run_listen(http, seconds=100000)
        self.assertIsNone(chat)
        self.assertEqual(http.methods().count("getUpdates"), 1)
        self.assertIn("something else is reading", text)

    def test_a_dead_network_stops_it_after_a_few_tries_and_a_short_gap_does_not(self):
        http = Telegram(getUpdates=requests.exceptions.ConnectionError("down"))
        chat, _offset, text = run_listen(http, seconds=100000)
        self.assertIsNone(chat)
        self.assertEqual(http.methods().count("getUpdates"), channel.LISTEN_MAX_FAILURES)
        self.assertIn("failed calls in a row", text)

        answers = [requests.exceptions.ConnectionError("down"), refused("Bad Gateway", 502), ok([channel_post(9, MORROW)])]
        http = Telegram(getUpdates=lambda _kwargs: answers.pop(0), getChatMember=ok(FULL))
        chat, _offset, _text = run_listen(http, seconds=100000)
        self.assertEqual(chat, MORROW)

    def test_a_webhook_that_cannot_be_removed_means_no_listening(self):
        http = Telegram(deleteWebhook=refused("Unauthorized", 401))
        chat, offset, text = run_listen(http)
        self.assertEqual((chat, offset), (None, None))
        self.assertNotIn("getUpdates", http.methods())
        self.assertIn("deleteWebhook failed", text)

    def test_the_feed_is_read_again_during_a_long_wait(self):
        newer = {"bot": {"/help": "the menu", "/today": "tomorrow's five"}, "stories": []}
        http = Telegram(getUpdates=batches([text_message(1, "/today")]))
        _chat, _offset, _text = run_listen(http, seconds=3000, step=500, refresh=lambda: newer)
        self.assertEqual(http.sent("sendMessage")[0]["text"], "tomorrow's five")


class SettleTest(unittest.TestCase):
    def test_late_messages_are_answered_and_acknowledged(self):
        http = Telegram(getUpdates=batches([text_message(5, "/today")]))
        self.assertEqual(channel.settle(http, TOKEN, FEED, 5), 1)
        polls = http.sent("getUpdates")
        self.assertEqual([poll["offset"] for poll in polls], [5, 6])
        self.assertTrue(all(poll["timeout"] == 0 for poll in polls))

    def test_the_channel_service_lines_from_setup_are_cleared_without_an_answer(self):
        renamed = {"update_id": 8, "channel_post": {"message_id": 9, "new_chat_title": "Morrow Brief", "chat": MORROW}}
        http = Telegram(getUpdates=batches([renamed]))
        self.assertEqual(channel.settle(http, TOKEN, FEED, 8), 0)
        self.assertNotIn("sendMessage", http.methods())
        self.assertEqual(http.sent("getUpdates")[-1]["offset"], 9)

    def test_nothing_received_means_nothing_to_settle(self):
        http = Telegram()
        self.assertEqual(channel.settle(http, TOKEN, FEED, None), 0)
        self.assertEqual(http.calls, [])

    def test_a_busy_bot_is_handed_back_after_a_few_rounds(self):
        counter = iter(range(100, 200))
        http = Telegram(getUpdates=lambda _kwargs: ok([text_message(next(counter), "/today")]))
        channel.settle(http, TOKEN, FEED, 100)
        polls = http.sent("getUpdates")
        self.assertEqual(len(polls), channel.SETTLE_ROUNDS + 1)
        self.assertEqual(polls[-1]["limit"], 1)


class ListenCommandTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.output = os.path.join(self.folder.name, "github_output.txt")

    def run_main(self, argv: list[str], env: dict, http: Telegram) -> tuple[int, str]:
        printed = io.StringIO()
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "GITHUB_OUTPUT": self.output, **env}
        with mock.patch.dict(os.environ, env, clear=False), contextlib.redirect_stdout(printed), \
                mock.patch.object(channel, "requests", http), \
                mock.patch.object(channel, "avatar_jpeg", lambda: JPEG), \
                mock.patch.object(channel.time, "sleep", lambda _seconds: None):
            for name in ("TELEGRAM_CHAT_ID", "CHANNEL_HANDOFF_KEY"):
                if name not in env:
                    os.environ.pop(name, None)
            code = channel.main(argv)
        return code, printed.getvalue()

    def written(self) -> str:
        with open(self.output, encoding="utf-8") as output:
            return output.read()

    def test_a_found_channel_is_sealed_set_up_tested_and_read(self):
        http = Telegram(getUpdates=batches([channel_post(1, MORROW)]), getChat=ok(MORROW), getChatMember=ok(FULL),
                        getChatMemberCount=ok(1))
        code, text = self.run_main(["listen", "--feed", "missing.json", "--seconds", "600"],
                                   {"CHANNEL_HANDOFF_KEY": KEY}, http)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.written(), "found=true\n")
        sealed = [line for line in text.splitlines() if line.startswith("sealed id: ")][0].split(": ")[1]
        self.assertEqual(channel.unseal(sealed, KEY), str(MORROW["id"]))
        self.assertNotIn("5550001111", text)
        self.assertNotIn(TOKEN, text)
        self.assertNotIn(KEY, text)
        self.assertEqual(http.sent("setChatTitle")[0], {"chat_id": str(MORROW["id"]), "title": "Morrow Brief"})
        self.assertIn("pin the welcome post: done", text)
        self.assertIn("checks passed", text)
        self.assertIn("the bot @Morrow_brief_bot is: administrator", text)
        self.assertEqual(http.sent("getUpdates")[-1]["offset"], 2)

    def test_a_setup_that_fails_fails_the_run_but_still_says_it_was_found(self):
        http = Telegram(getUpdates=batches([channel_post(1, MORROW)]), getChat=ok(MORROW), getChatMember=ok(FULL),
                        setChatTitle=refused("Bad Request: not enough rights"))
        code, text = self.run_main(["listen", "--feed", "missing.json"], {"CHANNEL_HANDOFF_KEY": KEY}, http)
        self.assertEqual(code, 1)
        self.assertEqual(self.written(), "found=true\n")
        self.assertIn("name: FAILED", text)

    def test_no_channel_is_not_a_failure_and_touches_nothing(self):
        http = Telegram()
        code, text = self.run_main(["listen", "--feed", "missing.json", "--seconds", "0"],
                                   {"CHANNEL_HANDOFF_KEY": KEY}, http)
        self.assertEqual(code, 0, text)
        self.assertEqual(self.written(), "found=false\n")
        self.assertNotIn("sealed id", text)
        self.assertNotIn("setChatTitle", http.methods())

    def test_without_the_key_the_id_is_not_handed_over(self):
        http = Telegram(getUpdates=batches([channel_post(1, MORROW)]), getChat=ok(MORROW), getChatMember=ok(FULL))
        code, text = self.run_main(["listen", "--feed", "missing.json"], {}, http)
        self.assertEqual(code, 0, text)
        self.assertIn("CHANNEL_HANDOFF_KEY is not set", text)
        self.assertNotIn("sealed id", text)
        self.assertNotIn("5550001111", text)


class PublicPage:
    """Stands in for `requests` when the channel's public page is read."""

    def __init__(self, text: str = "", status: int = 200, error: Exception | None = None):
        self.text, self.status_code, self.error = text, status, error
        self.urls: list[str] = []

    def get(self, url: str, **_kwargs):
        self.urls.append(url)
        if self.error:
            raise self.error
        return self


def page_post(number: int, inner: str) -> str:
    return (f'<div class="tgme_widget_message" data-post="morrowbrief/{number}">{inner}'
            f'<time datetime="2026-11-17T01:0{number % 10}:00+00:00"></time></div>')


class ViewTest(unittest.TestCase):
    def test_the_newest_posts_are_described_with_their_picture(self):
        text = '<div class="tgme_widget_message_text">One <a href="https://example.com/a">story</a></div>'
        page = PublicPage("".join([
            page_post(1, '<a class="tgme_widget_message_photo_wrap"></a>' + text),
            page_post(2, text),
            page_post(3, text + '<a class="tgme_widget_message_link_preview"><i class="link_preview_image"></i></a>'),
            page_post(4, text + '<a class="tgme_widget_message_link_preview"></a>'),
        ]))
        log, seen = channel.view(page, "morrowbrief", count=3)
        self.assertEqual(page.urls, ["https://t.me/s/morrowbrief"])
        self.assertEqual(seen, 4)
        self.assertEqual(len(log), 4, "a heading and the three newest posts")
        self.assertIn("post 2 · 2026-11-17T01:02:00+00:00 · 9 characters, 1 links · no picture", log[1])
        self.assertIn("link preview with a picture", log[2])
        self.assertIn("link preview without a picture", log[3])
        self.assertIn("sent as a photo", channel.view(page, "morrowbrief")[0][1])

    def test_a_page_without_posts_or_out_of_reach_is_said_plainly(self):
        self.assertEqual(channel.view(PublicPage("<html></html>"), "morrowbrief")[1], 0)
        self.assertIn("HTTP 404", channel.view(PublicPage(status=404), "morrowbrief")[0][0])
        down = PublicPage(error=requests.exceptions.ConnectionError("no route"))
        self.assertIn("could not be read (ConnectionError)", channel.view(down, "morrowbrief")[0][0])

    def test_view_needs_no_token_and_reads_the_brief_channel_by_default(self):
        page = PublicPage(page_post(1, ""))
        output = io.StringIO()
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(channel, "requests", page), \
                contextlib.redirect_stdout(output):
            page.exceptions = requests.exceptions
            self.assertEqual(channel.main(["view"]), 0)
            self.assertEqual(channel.main(["view", "--chat", "https://t.me/s/other_name"]), 0)
        self.assertEqual(page.urls, ["https://t.me/s/morrowbrief", "https://t.me/s/other_name"])


class PageAndTelegram(Telegram):
    """Stands in for `requests` when a command asks Telegram and also reads the public page."""

    def __init__(self, page: PublicPage, **answers):
        super().__init__(**answers)
        self.page = page
        self.exceptions = requests.exceptions

    def get(self, url: str, **kwargs):
        return self.page.get(url, **kwargs)


NOW = datetime.datetime(2026, 11, 20, 2, 0, tzinfo=datetime.timezone.utc)


def counted_post(number: int, sent: str, views: str) -> str:
    return (f'<div class="tgme_widget_message" data-post="morrowbrief/{number}">'
            f'<span class="tgme_widget_message_views">{views}</span><time datetime="{sent}"></time></div>')


class MetricsTest(unittest.TestCase):
    def test_view_counters_are_read_as_the_page_prints_them(self):
        self.assertEqual(channel.view_count("78"), 78)
        self.assertEqual(channel.view_count(" 1.2K "), 1200)
        self.assertEqual(channel.view_count("3.4M"), 3_400_000)
        self.assertIsNone(channel.view_count("many"))
        self.assertIsNone(channel.view_count(""))

    def test_only_posts_a_day_to_eight_days_old_are_counted(self):
        page = PublicPage("".join([
            counted_post(1, "2026-11-10T01:00:00+00:00", "900"),   # ten days old: too old
            counted_post(2, "2026-11-15T01:00:00+00:00", "40"),
            counted_post(3, "2026-11-17T01:00:00+00:00", "60"),
            counted_post(4, "2026-11-18T01:00:00+00:00", "80"),
            counted_post(5, "2026-11-19T23:00:00+00:00", "5"),     # three hours old: still collecting views
            '<div class="tgme_widget_message" data-post="morrowbrief/6"><time datetime="2026-11-18T02:00:00+00:00">'
            "</time></div>",                                       # a service post has no view counter
        ]))
        posts, why = channel.post_views(page, "morrowbrief")
        self.assertIsNone(why)
        self.assertEqual(len(posts), 5)
        self.assertEqual(channel.metrics_row(NOW, 200, posts), "2026-11-20,200,3,60,30")

    def test_the_day_is_the_jakarta_day_and_an_even_count_gives_the_middle(self):
        late = datetime.datetime(2026, 11, 20, 18, 30, tzinfo=datetime.timezone.utc)
        posts = [(late - datetime.timedelta(days=2), 10), (late - datetime.timedelta(days=3), 15)]
        self.assertEqual(channel.metrics_row(late, 50, posts), "2026-11-21,50,2,12.5,25")

    def test_without_settled_posts_the_subscribers_are_still_recorded(self):
        self.assertEqual(channel.metrics_row(NOW, 2, []), "2026-11-20,2,0,,")
        self.assertEqual(channel.metrics_row(NOW, 0, [(NOW - datetime.timedelta(days=2), 7)]), "2026-11-20,0,1,7,")

    def test_one_line_a_day_is_kept(self):
        with tempfile.TemporaryDirectory() as folder:
            path = pathlib.Path(folder) / "data" / "metrics.csv"
            channel.record(path, "2026-11-19,2,0,,")
            channel.record(path, "2026-11-20,3,1,4,133")
            channel.record(path, "2026-11-20,5,1,6,120")
            self.assertEqual(path.read_text(encoding="utf-8").splitlines(),
                             [channel.METRICS_HEADER, "2026-11-19,2,0,,", "2026-11-20,5,1,6,120"])

    def test_the_command_reads_both_and_saves_the_line(self):
        page = PublicPage(counted_post(3, "2026-11-17T01:00:00+00:00", "1.2K"))
        http = PageAndTelegram(page, getChatMemberCount=ok(4000), getChat=ok(PUBLIC))
        log, row = channel.metrics(http, TOKEN, "@morrowbrief", NOW)
        self.assertEqual(row, "2026-11-20,4000,1,1200,30")
        self.assertEqual(log, [channel.METRICS_HEADER, row])
        self.assertEqual(page.urls, ["https://t.me/s/morrowbrief"])
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "metrics.csv")
            with mock.patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "@morrowbrief"},
                                 clear=True), \
                    mock.patch.object(channel, "requests", http), contextlib.redirect_stdout(output):
                self.assertEqual(channel.main(["metrics", "--out", path]), 0)
            with open(path, encoding="utf-8") as saved:
                lines = saved.read().splitlines()
        self.assertEqual(lines[0], channel.METRICS_HEADER)
        self.assertTrue(lines[1].endswith(",4000,0,,") or lines[1].endswith(",4000,1,1200,30"), lines[1])
        self.assertNotIn(TOKEN, output.getvalue())

    def test_a_private_channel_or_an_unreadable_page_still_gives_the_subscribers(self):
        http = PageAndTelegram(PublicPage(status=404), getChatMemberCount=ok(12), getChat=ok(PRIVATE))
        log, row = channel.metrics(http, TOKEN, "-1009876543210", NOW)
        self.assertEqual(row, "2026-11-20,12,0,,")
        self.assertIn("views not read: the channel has no public page", log)
        http = PageAndTelegram(PublicPage(status=404), getChatMemberCount=ok(12), getChat=ok(PUBLIC))
        log, row = channel.metrics(http, TOKEN, "@morrowbrief", NOW)
        self.assertEqual(row, "2026-11-20,12,0,,")
        self.assertIn("HTTP 404", log[-1])

    def test_no_subscriber_count_means_no_line(self):
        http = PageAndTelegram(PublicPage(), getChatMemberCount=refused("Bad Request: chat not found"))
        log, row = channel.metrics(http, TOKEN, "@nowhere", NOW)
        self.assertIsNone(row)
        self.assertIn("subscribers could not be read", log[0])
        self.assertNotIn(TOKEN, " ".join(log))


if __name__ == "__main__":
    unittest.main()
