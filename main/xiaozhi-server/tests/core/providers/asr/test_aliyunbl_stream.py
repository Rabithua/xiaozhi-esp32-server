"""Offline checks for the Aliyun ASR provider; no server dependencies or network calls."""

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


PROVIDER_PATH = (
    Path(__file__).resolve().parents[4]
    / "core" / "providers" / "asr" / "aliyunbl_stream.py"
)
QWEN_MODEL = "qwen-audio-3.1-asr-flash-streaming"
DEFAULT_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"


def load_provider():
    """Stub external imports so these checks cannot connect to a cloud service."""
    logger_module = ModuleType("config.logger")
    logger_module.setup_logging = lambda: Mock()
    base_module = ModuleType("core.providers.asr.base")
    base_module.ASRProviderBase = type("ASRProviderBase", (), {})
    dto_module = ModuleType("core.providers.asr.dto.dto")
    dto_module.InterfaceType = SimpleNamespace(STREAM="stream")
    websocket_module = ModuleType("websockets")
    websocket_module.ConnectionClosed = type("ConnectionClosed", (Exception,), {})
    modules = {
        "config.logger": logger_module,
        "core.providers.asr.base": base_module,
        "core.providers.asr.dto.dto": dto_module,
        "websockets": websocket_module,
    }
    spec = importlib.util.spec_from_file_location("aliyunbl_stream_under_test", PROVIDER_PATH)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, modules):
        spec.loader.exec_module(module)
    return module.ASRProvider


ASRProvider = load_provider()


def final_result(text, sentence_id=1):
    return {
        "header": {"event": "result-generated"},
        "payload": {
            "output": {
                "sentence": {
                    "sentence_id": sentence_id,
                    "text": text,
                    "sentence_end": True,
                    "end_time": 1000 * sentence_id,
                }
            }
        },
    }


TASK_FINISHED = {"header": {"event": "task-finished"}, "payload": {}}


class FakeWebSocket:
    def __init__(self, events):
        self.events = list(events)

    async def recv(self):
        event = self.events.pop(0)
        if callable(event):
            event = event()
        return json.dumps(event)


class RequestTests(unittest.TestCase):
    def test_paraformer_parameters_remain_unchanged(self):
        provider = ASRProvider(
            {"vocabulary_id": "offline-vocabulary", "language_hints": ["zh"]}, True
        )
        request = provider._build_run_task_message()
        self.assertEqual(request["payload"]["model"], "paraformer-realtime-v2")
        self.assertEqual(
            request["payload"]["parameters"],
            {
                "format": "pcm",
                "sample_rate": 16000,
                "disfluency_removal_enabled": False,
                "semantic_punctuation_enabled": False,
                "max_sentence_silence": 200,
                "multi_threshold_mode_enabled": False,
                "punctuation_prediction_enabled": True,
                "inverse_text_normalization_enabled": True,
                "vocabulary_id": "offline-vocabulary",
                "language_hints": ["zh"],
            },
        )

    def test_qwen_31_and_snapshots_use_only_new_parameters(self):
        for model in (QWEN_MODEL, QWEN_MODEL + "-2026-09-21"):
            with self.subTest(model=model):
                provider = ASRProvider(
                    {
                        "model": model,
                        "format": "pcm",
                        "sample_rate": 16000,
                        "semantic_punctuation_enabled": True,
                        "language_hints": ["zh"],
                        "vocabulary_id": "offline-vocabulary",
                    },
                    True,
                )
                request = provider._build_run_task_message()
                self.assertEqual(request["payload"]["model"], model)
                self.assertEqual(request["payload"]["input"], {})
                self.assertEqual(
                    request["payload"]["parameters"],
                    {"format": "pcm", "sample_rate": 16000, "vad_model": "near_meeting_16k"},
                )

    def test_other_qwen_models_keep_legacy_parameters(self):
        provider = ASRProvider({"model": "qwen3-asr-flash-realtime"}, True)
        parameters = provider._build_run_task_message()["payload"]["parameters"]
        self.assertNotIn("vad_model", parameters)
        self.assertEqual(parameters["max_sentence_silence"], 200)
        self.assertIn("semantic_punctuation_enabled", parameters)

    def test_optional_websocket_url(self):
        custom_url = "wss://offline-workspace.cn-beijing.maas.aliyuncs.com/api-ws/v1/inference"
        for config, expected in (({}, DEFAULT_WS_URL), ({"ws_url": ""}, DEFAULT_WS_URL),
                                 ({"ws_url": custom_url}, custom_url)):
            with self.subTest(config=config):
                self.assertEqual(ASRProvider(config, True).ws_url, expected)


class ManualCompletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.provider = ASRProvider({"model": QWEN_MODEL}, True)
        self.conn = SimpleNamespace(
            client_listen_mode="manual",
            client_voice_stop=False,
            asr_audio=[b"offline-pcm"],
            stop_event=SimpleNamespace(is_set=lambda: False),
            reset_audio_states=Mock(),
        )
        self.submissions = []

        async def submit(conn, audio):
            text, _ = await self.provider.speech_to_text(audio, "offline-session")
            self.submissions.append((text, list(audio)))

        self.provider.handle_voice_stop = AsyncMock(side_effect=submit)
        self.provider._cleanup = AsyncMock()

    def stop_then_finish(self):
        self.conn.client_voice_stop = True
        return TASK_FINISHED

    async def run_events(self, events):
        self.provider.asr_ws = FakeWebSocket(events)
        await self.provider._forward_results(self.conn)
        self.provider._cleanup.assert_awaited_once()
        self.conn.reset_audio_states.assert_called_once()

    async def start_next_session(self):
        websocket_module = self.provider._start_recognition.__globals__["websockets"]
        websocket = SimpleNamespace(send=AsyncMock())
        with (
            patch.object(websocket_module, "connect", AsyncMock(return_value=websocket), create=True),
            patch.object(self.provider, "_forward_results", new_callable=AsyncMock),
        ):
            await self.provider._start_recognition(self.conn)
            await self.provider.forward_task
        self.provider._cleanup.reset_mock()
        self.conn.reset_audio_states.reset_mock()

    async def test_final_before_stop_is_submitted_on_task_finished(self):
        await self.run_events([final_result("你好。"), self.stop_then_finish])
        self.assertEqual(self.submissions, [("你好。", [b"offline-pcm"])])
        self.provider.handle_voice_stop.assert_awaited_once()

    async def test_final_after_stop_is_submitted_once(self):
        self.conn.client_voice_stop = True
        await self.run_events([final_result("你好。"), TASK_FINISHED])
        self.assertEqual(self.submissions, [("你好。", [b"offline-pcm"])])
        self.provider.handle_voice_stop.assert_awaited_once()
        self.assertEqual(self.provider.asr_ws.events, [TASK_FINISHED])

    async def test_multiple_finals_before_stop_are_combined_once(self):
        await self.run_events([
            final_result("你好。"), final_result("再见。", 2), self.stop_then_finish
        ])
        self.assertEqual(self.submissions, [("你好。再见。", [b"offline-pcm"])])
        self.provider.handle_voice_stop.assert_awaited_once()

    async def test_empty_task_does_not_submit(self):
        await self.run_events([self.stop_then_finish])
        self.provider.handle_voice_stop.assert_not_awaited()

    async def test_finish_without_stop_does_not_submit(self):
        await self.run_events([final_result("你好。"), TASK_FINISHED])
        self.provider.handle_voice_stop.assert_not_awaited()

    async def test_task_failure_does_not_submit_cached_text(self):
        await self.run_events([
            final_result("你好。"),
            {"header": {"event": "task-failed", "error_code": "OFFLINE_TEST"}},
        ])
        self.provider.handle_voice_stop.assert_not_awaited()

    async def test_failed_task_text_is_not_submitted_by_next_empty_task(self):
        await self.run_events([
            final_result("旧文本。"),
            {"header": {"event": "task-failed", "error_code": "OFFLINE_TEST"}},
        ])
        await self.start_next_session()
        await self.run_events([self.stop_then_finish])
        self.provider.handle_voice_stop.assert_not_awaited()

    async def test_failed_task_text_is_not_prefixed_to_next_sentence(self):
        await self.run_events([
            final_result("旧文本。"),
            {"header": {"event": "task-failed", "error_code": "OFFLINE_TEST"}},
        ])
        await self.start_next_session()
        self.conn.client_voice_stop = True
        await self.run_events([final_result("新文本。"), TASK_FINISHED])
        self.assertEqual(self.submissions, [("新文本。", [b"offline-pcm"])])
        self.provider.handle_voice_stop.assert_awaited_once()

    async def test_automatic_completion_still_submits_once(self):
        self.conn.client_listen_mode = "auto"
        await self.run_events([final_result("你好。"), TASK_FINISHED])
        self.assertEqual(self.submissions, [("你好。", [b"offline-pcm"])])
        self.provider.handle_voice_stop.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
