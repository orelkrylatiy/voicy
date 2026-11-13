"""Pure unit tests: external APIs and text models are mocked."""
import io
import json
import os
import sys
import types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import transcribe_bot as voicy


def settings(**overrides):
    defaults = dict(telegram_token="123:fake", owner_ids=frozenset({"42"}), allow_public=False,
                    openai_key="test-key", transcribe_mode="auto", transcribe_model="gpt-transcribe",
                    transcribe_edit="humanizer", humanizer_backend="auto", humanizer_openai_model="gpt-4.1-mini",
                    transport="bot_api")
    defaults.update(overrides)
    return voicy.Settings(**defaults)


class FakeHumanizer:
    def __init__(self):
        self.conversations = []
        self.edits = []

    def reply(self, messages):
        self.conversations.append(messages)
        return "Привет!"

    def edit_transcript(self, text, names):
        self.edits.append((text, names))
        return "Исправлено: " + text


class SettingsTests(unittest.TestCase):
    def test_default_is_private(self):
        self.assertTrue(settings().authorized(42))
        self.assertFalse(settings().authorized(43))
        with self.assertRaisesRegex(ValueError, "OWNER_IDS"):
            settings(owner_ids=frozenset()).validate()

    def test_audio_key_not_required_in_text_only_mode(self):
        settings(openai_key="", transcribe_mode="off").validate()
        with self.assertRaisesRegex(ValueError, "OPENAI_API_KEY"):
            settings(openai_key="").validate()

    def test_invalid_settings_rejected(self):
        with self.assertRaises(ValueError):
            settings(humanizer_backend="unknown").validate()


class MediaTests(unittest.TestCase):
    def test_voice_audio_and_document(self):
        self.assertEqual(voicy.choose_media({"voice": {"file_id": "x"}})["filename"], "voice.ogg")
        self.assertEqual(voicy.choose_media({"audio": {"file_name": "memo.m4a"}})["filename"], "memo.m4a")
        self.assertIsNotNone(voicy.choose_media({"document": {"mime_type": "audio/ogg", "file_name": "f.ogg"}}))
        self.assertIsNone(voicy.choose_media({"document": {"mime_type": "application/pdf", "file_name": "x.pdf"}}))

    def test_audio_filename_sanitized(self):
        self.assertEqual(voicy.safe_audio_name("../../hello.oga"), "recording.ogg")
        with self.assertRaises(ValueError):
            voicy.safe_audio_name('injected"\r\nname="x.txt')

    def test_long_text_is_preserved(self):
        original = "Пример " * 1500
        chunks = voicy.split_text(original, size=200)
        self.assertTrue(all(0 < len(x) <= 200 for x in chunks))
        self.assertEqual(" ".join(chunks), original.strip())

    def test_emoji_chunks_fit_telegram_utf16_limit(self):
        for chunk in voicy.split_text("😀" * 3000):
            self.assertLessEqual(len(chunk.encode("utf-16-le")) // 2, 4096)

    def test_caption_hint(self):
        self.assertEqual(voicy.name_hints_from_caption("Имена: Мария, Роман"), "Мария, Роман")
        self.assertEqual(voicy.name_hints_from_caption("любые слова"), "")

    def test_transcription_api_uses_correct_model_and_hint(self):
        reqs = []

        def fake_open(request, timeout=None):
            reqs.append((request, timeout))
            return io.BytesIO(b'{"text": " hello "}')

        with patch.object(voicy.urllib.request, "urlopen", fake_open):
            self.assertEqual(voicy.transcribe_openai(b"audio", "v.ogg", settings(), "Анна"), "hello")
        req, _ = reqs[0]
        self.assertIn(b'gpt-transcribe', req.data)
        self.assertIn("audio/transcriptions", req.full_url)
        self.assertIn(b'\xd0\x90\xd0\xbd\xd0\xbd\xd0\xb0', req.data)
        self.assertIn(b'filename="recording.ogg"', req.data)


class BotTests(unittest.TestCase):
    def test_unauthorized_not_processed(self):
        answers = []
        bot = voicy.Bot(settings(), FakeHumanizer())
        bot.handle(100, 99, {"text": "test"}, answers.append, lambda _: (_ for _ in ()).throw(Exception()))
        self.assertEqual(answers, [])

    def test_transcribe_and_edit(self):
        answers = []
        hz = FakeHumanizer()
        bot = voicy.Bot(settings(), hz)
        with patch.object(voicy, "transcribe_openai", return_value="Мама мыла раму.") as openai:
            bot.handle(100, 42, {"voice": {"file_id": "f", "file_size": 12}, "caption": "Имена: Маша"},
                       answers.append, lambda _: (b"audio", "voice.ogg"))
        self.assertEqual(answers, ["Расшифровываю аудио…", "Исправлено: Мама мыла раму."])
        self.assertEqual(hz.edits, [("Мама мыла раму.", "Маша")])
        self.assertEqual(openai.call_count, 1)

    def test_raw_audio_never_calls_humanizer(self):
        answers = []
        hz = FakeHumanizer()
        with patch.object(voicy, "transcribe_openai", return_value="original"):
            voicy.Bot(settings(transcribe_edit="raw"), hz).handle(
                100, 42, {"audio": {"file_id": "x"}}, answers.append,
                lambda _: (b"audio", "voice.ogg"))
        self.assertEqual(answers[-1], "original")
        self.assertEqual(hz.edits, [])

    def test_disabled_audio_and_large_file(self):
        answers = []
        voicy.Bot(settings(transcribe_mode="off")).handle(100, 42, {"voice": {"file_id": "x"}},
                                                         answers.append, lambda _: None)
        self.assertIn("выключено", answers[-1])
        voicy.Bot(settings()).handle(100, 42, {"voice": {"file_id": "x", "file_size": voicy.MAX_AUDIO_BYTES + 1}},
                                     answers.append, lambda _: None)
        self.assertIn("20 МБ", answers[-1])

    def test_text_uses_humanizer_and_isolates_users(self):
        hz = FakeHumanizer()
        bot = voicy.Bot(settings(allow_public=True), hz)
        answers = []
        bot.handle(100, 42, {"text": "один"}, answers.append, lambda _: None)
        bot.handle(100, 50, {"text": "другой"}, answers.append, lambda _: None)
        bot.handle(100, 42, {"text": "два"}, answers.append, lambda _: None)
        self.assertEqual(len(hz.conversations[0]), 1)
        self.assertEqual(len(hz.conversations[1]), 1)
        self.assertEqual(len(hz.conversations[2]), 3)
        self.assertEqual(answers, ["Привет!"] * 3)


class BridgeTests(unittest.TestCase):
    def test_chat_calls_full_framework_generate(self):
        calls = []
        class Message:
            def __init__(self, role, content):
                self.role, self.content = role, content
        class Request:
            def __init__(self, **kwargs):
                self.kwargs = kwargs
        class Framework:
            def __init__(self, provider=None):
                self.provider = provider
            def generate(self, request):
                calls.append(request)
                return types.SimpleNamespace(text="ok")
        mod = types.ModuleType("humanizer_framework")
        mod.CommunicationFramework = Framework
        mod.CommunicationRequest = Request
        mod.Message = Message
        mod.MessageType = types.SimpleNamespace(CHAT_REPLY="chat_reply")
        with patch.dict(sys.modules, {"humanizer_framework": mod}):
            with patch.dict(os.environ, {"ZAI_API_KEY": "dummy"}):
                bridge = voicy.HumanizerBridge(settings())
                self.assertEqual(bridge.reply([("user", "Как дела?")]), "ok")
        self.assertEqual(calls[0].kwargs["domain"], "generic")
        self.assertEqual(calls[0].kwargs["channel"], "telegram")


if __name__ == "__main__":
    unittest.main()
