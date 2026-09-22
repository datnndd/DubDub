from videotrans.configure.config import app_cfg
from videotrans.util import help_misc


def test_novoice_wait_reports_progress_to_job_sink(tmp_path, monkeypatch):
    video = tmp_path / "novoice.mp4"
    video.write_bytes(b"video")
    job_id = "novoice-progress-test"
    events = []
    app_cfg.queue_novice[job_id] = "ing"
    monkeypatch.setattr(app_cfg, "current_status", "ing")

    def finish(_seconds):
        app_cfg.queue_novice[job_id] = "end"

    monkeypatch.setattr(help_misc.time, "sleep", finish)
    try:
        assert help_misc.is_novoice_mp4(
            video.as_posix(),
            job_id,
            event_sink=events.append,
        ) is True
    finally:
        app_cfg.queue_novice.pop(job_id, None)

    assert events and events[0]["uuid"] == job_id


def test_novoice_wait_honors_job_cancellation(tmp_path):
    class Cancelled:
        @staticmethod
        def is_cancelled():
            return True

    assert help_misc.is_novoice_mp4(
        (tmp_path / "missing.mp4").as_posix(),
        "cancelled-job",
        cancellation_token=Cancelled(),
    ) is False
