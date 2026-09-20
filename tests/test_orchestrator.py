from pathlib import Path

import pytest

from videotrans.task import orchestrator
from videotrans.task.orchestrator import (
    CancellationToken,
    EventKind,
    TaskRequest,
    TaskStatus,
)


class FakeTask:
    enabled = {}
    fail_stage = None
    cancel_stage = None
    calls = []

    def __init__(self, cfg, event_sink=None, cancellation_token=None):
        self.cfg = cfg
        self.event_sink = event_sink
        self.cancellation_token = cancellation_token
        self.should_recogn = self.enabled.get("recogn", False)
        self.should_trans = self.enabled.get("trans", False)
        self.should_dubbing = self.enabled.get("dubbing", False)
        self.should_recogn2 = self.enabled.get("recogn2pass", False)
        self.should_hebing = self.enabled.get("assembling", False)
        self.cfg.source_sub = str(Path(cfg.target_dir) / "source.srt")
        self.cfg.target_sub = str(Path(cfg.target_dir) / "target.srt")
        self.cfg.source_wav_output = str(Path(cfg.target_dir) / "source.m4a")
        self.cfg.target_wav_output = str(Path(cfg.target_dir) / "target.m4a")
        self.cfg.targetdir_mp4 = str(Path(cfg.target_dir) / "result.mp4")

    def __getattr__(self, name):
        if name not in {
            "prepare", "recogn", "diariz", "trans", "dubbing", "align",
            "recogn2pass", "assembling", "task_done",
        }:
            raise AttributeError(name)

        def execute():
            self.calls.append(name)
            if name == self.fail_stage:
                raise ValueError("broken stage")
            if name == self.cancel_stage:
                self.cancellation_token.cancel()
            if name == "task_done":
                Path(self.cfg.targetdir_mp4).write_bytes(b"video")

        return execute


@pytest.fixture
def runner_env(tmp_path, monkeypatch):
    temp_root = tmp_path / "temp"
    temp_root.mkdir()
    source = tmp_path / "input.mp4"
    source.write_bytes(b"input")
    output = tmp_path / "output"
    monkeypatch.setattr(orchestrator, "TEMP_DIR", str(temp_root))
    monkeypatch.setattr(orchestrator, "TransCreate", FakeTask)
    FakeTask.enabled = {}
    FakeTask.fail_stage = None
    FakeTask.cancel_stage = None
    FakeTask.calls = []
    return source, output, temp_root


def request(source, output, temp_root, **params):
    return TaskRequest({
        "name": str(source),
        "target_dir": str(output),
        "cache_folder": str(temp_root / "job"),
        "source_language_code": "en",
        "target_language_code": "fr",
        **params,
    })


@pytest.mark.parametrize(
    ("enabled", "expected"),
    [
        ({}, ["prepare", "task_done"]),
        ({"recogn": True}, ["prepare", "recogn", "diariz", "task_done"]),
        ({"trans": True}, ["prepare", "trans", "task_done"]),
        ({"dubbing": True}, ["prepare", "dubbing", "align", "task_done"]),
        ({"assembling": True}, ["prepare", "assembling", "task_done"]),
        ({"recogn2pass": True}, ["prepare", "recogn2pass", "task_done"]),
    ],
)
def test_runner_owns_conditional_stage_routing(runner_env, enabled, expected):
    source, output, temp_root = runner_env
    FakeTask.enabled = enabled

    result = orchestrator.run(request(source, output, temp_root))

    assert result.status == TaskStatus.SUCCEEDED
    assert FakeTask.calls == expected
    assert result.outputs == (output.resolve() / "result.mp4",)


def test_runner_can_stop_after_review_checkpoint(runner_env):
    source, output, temp_root = runner_env
    FakeTask.enabled = {
        "recogn": True,
        "trans": True,
        "dubbing": True,
        "assembling": True,
    }

    result = orchestrator.run(
        request(source, output, temp_root),
        stop_after_stage="diariz",
    )

    assert result.status == TaskStatus.SUCCEEDED
    assert FakeTask.calls == ["prepare", "recogn", "diariz"]
    assert "trans" not in FakeTask.calls
    assert "dubbing" not in FakeTask.calls
    assert "assembling" not in FakeTask.calls


def test_events_are_ordered_and_have_one_terminal_event(runner_env):
    source, output, temp_root = runner_env
    events = []

    orchestrator.run(request(source, output, temp_root), events.append)

    assert events[0].kind == EventKind.QUEUED
    assert events[1].kind == EventKind.RUNNING
    assert [event.kind for event in events].count(EventKind.SUCCEEDED) == 1
    assert events[-1].kind == EventKind.SUCCEEDED


def test_validation_happens_before_task_construction_or_output_mutation(runner_env, monkeypatch):
    _source, output, temp_root = runner_env
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    constructed = False

    def factory(**_kwargs):
        nonlocal constructed
        constructed = True

    monkeypatch.setattr(orchestrator, "TransCreate", factory)
    result = orchestrator.run(request(temp_root / "missing.mp4", output, temp_root))

    assert result.status == TaskStatus.FAILED
    assert result.failure.stage == "validation"
    assert not constructed
    assert marker.read_text(encoding="utf-8") == "keep"


def test_clear_cache_never_deletes_output_directory(runner_env):
    source, output, temp_root = runner_env
    output.mkdir()
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    cache = temp_root / "job"
    cache.mkdir()
    (cache / "old.txt").write_text("old", encoding="utf-8")

    result = orchestrator.run(request(source, output, temp_root, clear_cache=True))

    assert result.status == TaskStatus.SUCCEEDED
    assert marker.exists()
    assert not (cache / "old.txt").exists()


def test_cancellation_is_a_distinct_terminal_state(runner_env):
    source, output, temp_root = runner_env
    FakeTask.cancel_stage = "prepare"
    events = []

    result = orchestrator.run(
        request(source, output, temp_root), events.append, CancellationToken()
    )

    assert result.status == TaskStatus.CANCELLED
    assert FakeTask.calls == ["prepare"]
    assert [event.kind for event in events].count(EventKind.CANCELLED) == 1
    assert EventKind.FAILED not in [event.kind for event in events]


def test_failure_identifies_stage_and_preserves_diagnostic_cause(runner_env):
    source, output, temp_root = runner_env
    FakeTask.fail_stage = "prepare"
    events = []

    result = orchestrator.run(request(source, output, temp_root), events.append)

    assert result.status == TaskStatus.FAILED
    assert result.failure.code == "prepare_failed"
    assert result.failure.stage == "prepare"
    assert "ValueError: broken stage" in result.failure.cause
    assert [event.kind for event in events].count(EventKind.FAILED) == 1
