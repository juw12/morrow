"""The channel commands: finding it, reading the bot's rights, setting its profile, and the capability test."""
import contextlib
import io
import json
import os
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
        self.assertIn(str(feed.DIGEST_SIZE), text)
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
        for command in ("find", "status", "setup", "test"):
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


if __name__ == "__main__":
    unittest.main()
