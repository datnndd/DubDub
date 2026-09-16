from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QMainWindow
import pytest

app = QApplication.instance() or QApplication([])

from videotrans.configure.config import app_cfg
from videotrans.ui.en import Ui_MainWindow
from videotrans.mainwin._actions import WinAction
from videotrans.winform.ocr import RoiDialog


class _TestMainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)
        self.win_action = WinAction(self)
        self.subtitle_source.currentIndexChanged.connect(self.win_action.subtitle_source_change)


def test_subtitle_source_dropdown_exists():
    win = _TestMainWindow()
    assert hasattr(win, "subtitle_source")
    assert win.subtitle_source.count() == 2
    assert win.subtitle_source.currentIndex() == 0


def test_toggling_subtitle_source_locks_stt_controls():
    win = _TestMainWindow()
    win.show()
    assert win.recogn_type.isVisible() is True
    assert win.btn_ocr_roi.isVisible() is False

    # Switch to Hard-Subtitle OCR
    win.subtitle_source.setCurrentIndex(1)

    assert win.recogn_type.isVisible() is False
    assert win.model_name.isVisible() is False
    assert win.remove_noise.isVisible() is False
    assert win.recogn2pass.isVisible() is False
    assert win.btn_ocr_roi.isVisible() is True

    # Switch back to Audio STT
    win.subtitle_source.setCurrentIndex(0)

    assert win.recogn_type.isVisible() is True
    assert win.model_name.isVisible() is True
    assert win.btn_ocr_roi.isVisible() is False


def test_roi_dialog_confirm_updates_main_window_and_app_cfg():
    win = _TestMainWindow()
    app_cfg.main_win = win
    app_cfg.ocr_roi = None

    dialog = RoiDialog()
    dialog.video = "test.mp4"
    dialog.frame_view.set_roi((0.1, 0.7, 0.8, 0.2))

    dialog._confirm()

    assert dialog.confirmed is True
    assert app_cfg.ocr_roi == (0.1, 0.7, 0.8, 0.2)
    assert app_cfg.ocr_roi_confirmed is True
    assert app_cfg.subtitle_source == "video_ocr"
    assert win.subtitle_source.currentIndex() == 1
    assert win.win_action.queue_mp4 == ["test.mp4"]


def test_openwin_and_update_ui_autoloads_video_from_main_window(monkeypatch):
    win = _TestMainWindow()
    win.win_action.queue_mp4 = ["C:/media/video.mp4"]
    app_cfg.main_win = win

    loaded = []
    monkeypatch.setattr(RoiDialog, "load_video", lambda self, p: loaded.append(p))

    from videotrans.winform.ocr import openwin
    dialog = openwin()
    assert loaded == ["C:/media/video.mp4"]

    # Test update_ui when queue_mp4 changes later
    win.win_action.queue_mp4 = ["C:/media/video2.mp4"]
    dialog.update_ui()
    assert loaded == ["C:/media/video.mp4", "C:/media/video2.mp4"]


def test_recogn_mixin_imports_scan_video_to_srt():
    from videotrans.task._stage_recogn import RecognMixin, scan_video_to_srt
    assert callable(scan_video_to_srt)
