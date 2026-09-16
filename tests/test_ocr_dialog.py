import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app

def test_roi_dialog_confirms_only_with_valid_roi(qapp):
    from videotrans.ocr import OcrConfig, crop_roi
    from videotrans.winform.ocr import RoiDialog, RoiFrameView

    dialog = RoiDialog()
    # default ROI is the bottom strip (valid)
    roi = dialog.frame_view.roi()
    assert OcrConfig(roi=roi).is_valid_roi()
    assert roi[2] > 0 and roi[3] > 0

    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    view = RoiFrameView()
    view.set_frame(frame)
    crop = crop_roi(frame, view.roi())
    assert crop is not None

def test_roi_dialog_openwin_registers_child(qapp):
    from videotrans.winform.ocr import openwin
    dlg = openwin()
    from videotrans.configure.config import app_cfg
    assert app_cfg.child_forms.get("ocr") is not None
    dlg.close()

def test_crop_roi_none_on_empty_area():
    from videotrans.ocr import crop_roi
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    # zero-size ROI -> None
    assert crop_roi(frame, (0.0, 0.0, 0.0, 0.0)) is None
    assert crop_roi(None, (0.0, 0.0, 0.0, 0.0)) is None
