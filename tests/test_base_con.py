from videotrans.configure import base


def test_signal_without_consumer_logs_without_desktop_dispatch(monkeypatch):
    logged = []

    monkeypatch.setattr(base.app_cfg, "exec_mode", "gui")
    monkeypatch.setattr(base.logger, "info", lambda message: logged.append(message))
    base.BaseCon().signal(text="provider progress")

    assert logged == ["provider progress"]


def test_signal_sends_structured_message_to_job_event_sink():
    events = []

    base.BaseCon(event_sink=events.append).signal(text="provider progress")

    assert events == [{"text": "provider progress", "uuid": None, "type": "logs"}]
