from videotrans.task._rate import SpeedRate


def test_alignment_progress_uses_job_event_sink(tmp_path):
    events = []
    rate = SpeedRate(
        queue_tts=[],
        cache_folder=tmp_path.as_posix(),
        event_sink=events.append,
    )

    rate.signal("Preparing data")

    assert events == [{"text": "Preparing data", "type": "logs", "uuid": None}]
