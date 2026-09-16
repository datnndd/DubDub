from types import SimpleNamespace

from videotrans.ui import _setup_rows


class _Signal:
    def __init__(self):
        self.callbacks = []

    def connect(self, callback):
        self.callbacks.append(callback)

    def emit(self, value):
        for callback in self.callbacks:
            callback(value)


class _Widget:
    def __init__(self, *_args):
        self._checked = False
        self.toggled = _Signal()

    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None

    def setChecked(self, value):
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        self.toggled.emit(value)

    def isChecked(self):
        return self._checked


class _Layout:
    def __getattr__(self, _name):
        return lambda *_args, **_kwargs: None


def test_output_only_options_are_mutually_exclusive(monkeypatch):
    widgets = SimpleNamespace(
        QHBoxLayout=_Layout,
        QPushButton=_Widget,
        QLabel=_Widget,
        QCheckBox=_Widget,
    )
    core = SimpleNamespace(QSize=lambda *args: args)
    size_policy = SimpleNamespace(Policy=SimpleNamespace(Minimum=0))
    monkeypatch.setattr(_setup_rows, 'QtWidgets', widgets)
    monkeypatch.setattr(_setup_rows, 'QtCore', core)
    monkeypatch.setattr(_setup_rows, 'QSizePolicy', size_policy)
    monkeypatch.setattr(_setup_rows, 'tr', lambda text: text)
    ui = SimpleNamespace()

    _setup_rows._create_file_row(ui, object())

    ui.only_out_mp4.setChecked(True)
    assert ui.only_out_dubbed_audio.isChecked() is False

    ui.only_out_dubbed_audio.setChecked(True)
    assert ui.only_out_mp4.isChecked() is False
