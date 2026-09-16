"""ROI preview + test-recognition dialog for the Hard-Subtitle OCR source.

The dialog uses the media player only for navigation; the exact decoded frame
comes from the ffmpeg decoding layer (frame_at), never from capturing the
displayed video widget. The user draws a normalized ROI, sees a magnified crop
preview, runs a test recognition, and confirms before starting the task.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from videotrans.configure.config import app_cfg, tr
from videotrans.ocr import OcrConfig, PADDLE_OCR, crop_roi, run
from videotrans.ocr._frame_source import frame_at, probe_duration
from videotrans.util.help_misc import set_process, show_error


class RoiFrameView(QWidget):
    """Paints the decoded frame with a draggable/resizable ROI overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame = None
        self._roi = (0.0, 0.85, 1.0, 0.15)  # normalized (x, y, w, h)
        self._boxes = []  # list of normalized (x, y, w, h)
        self.setMinimumSize(320, 180)
        self.setMouseTracking(True)
        self._drag = None  # (mode, start_ndc) mode in {"move", "nw", "ne", "sw", "se", "new"}

    def set_frame(self, frame):
        self._frame = frame
        self.update()

    def set_roi(self, roi):
        self._roi = tuple(roi)
        self.update()

    def roi(self):
        return self._roi

    def set_boxes(self, boxes):
        self._boxes = list(boxes or [])
        self.update()

    # -- painting ---------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(20, 20, 20))
        if self._frame is None:
            painter.setPen(QColor(200, 200, 200))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("Open a video to preview"))
            return
        h, w = self._frame.shape[:2]
        pix = self._to_pixmap(self._frame)
        pix = pix.scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(0, 0, pix)

        # Map normalized ROI/boxes to widget coords.
        off_x = (self.width() - pix.width()) / 2
        off_y = (self.height() - pix.height()) / 2
        scale_x = pix.width() / w
        scale_y = pix.height() / h
        x, y, rw, rh = self._roi
        rx0 = off_x + x * scale_x * w
        ry0 = off_y + y * scale_y * h
        rx1 = off_x + (x + rw) * scale_x * w
        ry1 = off_y + (y + rh) * scale_y * h
        pen = QPen(QColor(0, 255, 0), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(int(rx0), int(ry0), int(rx1 - rx0), int(ry1 - ry0))
        for (bx, by, bw, bh) in self._boxes:
            painter.setPen(QPen(QColor(255, 80, 80), 1))
            b0 = off_x + bx * scale_x * w
            b1 = off_y + by * scale_y * h
            painter.drawRect(int(b0), int(b1), int(bw * scale_x * w), int(bh * scale_y * h))

    # -- interaction ------------------------------------------------------
    def _to_ndc(self, widget_pos):
        if self._frame is None:
            return None
        h, w = self._frame.shape[:2]
        pix = self._to_pixmap(self._frame).scaled(
            self.width(), self.height(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        off_x = (self.width() - pix.width()) / 2
        off_y = (self.height() - pix.height()) / 2
        px = (widget_pos.x() - off_x) / pix.width()
        py = (widget_pos.y() - off_y) / pix.height()
        if not (0.0 <= px <= 1.0 and 0.0 <= py <= 1.0):
            return None
        return (max(0.0, min(1.0, px)), max(0.0, min(1.0, py)))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._frame is not None:
            ndc = self._to_ndc(event.position())
            if ndc is None:
                return
            x, y, rw, rh = self._roi
            inside = x <= ndc[0] <= x + rw and y <= ndc[1] <= y + rh
            self._drag = ("move" if inside else "new", ndc)
            if not inside:
                self._roi = (ndc[0], ndc[1], 0.0, 0.0)
            self.update()

    def mouseMoveEvent(self, event):
        if self._drag is None or self._frame is None:
            return
        ndc = self._to_ndc(event.position())
        if ndc is None:
            return
        mode, start = self._drag
        if mode == "new":
            self._roi = (
                min(start[0], ndc[0]),
                min(start[1], ndc[1]),
                abs(ndc[0] - start[0]),
                abs(ndc[1] - start[1]),
            )
        elif mode == "move":
            dx = ndc[0] - start[0]
            dy = ndc[1] - start[1]
            x, y, rw, rh = self._roi
            self._roi = (
                max(0.0, min(1.0 - rw, x + dx)),
                max(0.0, min(1.0 - rh, y + dy)),
                rw,
                rh,
            )
            self._drag = (mode, ndc)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag = None
        self.update()
        self._emit_roi_changed()

    def _emit_roi_changed(self):
        parent_dialog = self.window()
        if parent_dialog and hasattr(parent_dialog, "_on_roi_changed"):
            parent_dialog._on_roi_changed()

    @staticmethod
    def _to_pixmap(frame):
        h, w = frame.shape[:2]
        if frame.ndim == 2:
            img = QImage(frame.data, w, h, w, QImage.Format.Format_Grayscale8)
        else:
            # BGR -> RGB for display.
            rgb = frame[:, :, ::-1].copy()
            img = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img.copy())


class RoiDialog(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.video = None
        self.duration_ms = 0
        self.confirmed = False
        self.language = None
        self.device = "auto"
        self._build_ui()
        self.setWindowTitle(tr("Hard-subtitle OCR: set region"))
        self.setMinimumSize(760, 560)

    def _build_ui(self):
        root = QVBoxLayout(self)
        self.frame_view = RoiFrameView()

        controls = QHBoxLayout()
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 10000)
        self.seek_slider.valueChanged.connect(self._on_seek)
        self.ms_input = QSpinBox()
        self.ms_input.setRange(0, 2**31 - 1)
        self.ms_input.setSuffix(" ms")
        self.ms_input.valueChanged.connect(self._on_ts_entry)
        self.video_input = QLineEdit()
        self.video_input.setReadOnly(True)
        self.video_input.setPlaceholderText(tr("Select a video to preview"))
        open_btn = QPushButton(tr("Open video"))
        open_btn.clicked.connect(self._open_video)
        controls.addWidget(self.video_input)
        controls.addWidget(open_btn)
        controls.addWidget(self.ms_input)
        controls.addWidget(self.seek_slider)

        self.crop_label = QLabel(tr("Crop preview"))
        self.crop_label.setFixedWidth(220)
        self.crop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        bottom = QHBoxLayout()
        self.status_label = QLabel("")
        test_btn = QPushButton(tr("Test OCR"))
        test_btn.clicked.connect(self._test_ocr)
        reset_btn = QPushButton(tr("Clear ROI"))
        reset_btn.clicked.connect(self._reset_roi)
        confirm_btn = QPushButton(tr("Confirm"))
        confirm_btn.clicked.connect(self._confirm)
        bottom.addWidget(self.status_label, 1)
        bottom.addWidget(reset_btn)
        bottom.addWidget(test_btn)
        bottom.addWidget(confirm_btn)

        root.addWidget(self.video_input)
        root.addWidget(self.frame_view, 1)
        root.addWidget(self.crop_label)
        root.addLayout(controls)
        root.addLayout(bottom)

    # -- actions ----------------------------------------------------------
    def _open_video(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select video"), "", tr("Video files") + " (*.mp4 *.mkv *.avi *.mov *.webm)"
        )
        if path:
            self.load_video(path)

    def load_video(self, video):
        self.video = str(Path(video))
        self.duration_ms = probe_duration("ffmpeg", self.video)
        self.ms_input.setRange(0, max(1, self.duration_ms))
        self.video_input.setText(self.video)
        self._decode_at(0)
        self.confirmed = False

    def _decode_at(self, ts_ms):
        frame, w, h = frame_at("ffmpeg", self.video, ts_ms)
        if frame is None:
            show_error(tr("Could not decode a frame at this timestamp"))
            return
        self.frame_view.set_frame(frame)
        self._update_crop()
        self._refresh_boxes()

    def _on_seek(self, value):
        ratio = value / 10000.0
        target = int(ratio * self.duration_ms)
        if abs(target - self.ms_input.value()) > 20 and self.video:
            self.ms_input.blockSignals(True)
            self.ms_input.setValue(target)
            self.ms_input.blockSignals(False)
            self._decode_at(target)

    def _on_ts_entry(self, value):
        if self.video and self.duration_ms:
            self.seek_slider.blockSignals(True)
            self.seek_slider.setValue(int(value / self.duration_ms * 10000))
            self.seek_slider.blockSignals(False)
            self._decode_at(value)

    def _on_roi_changed(self):
        self._update_crop()
        self.confirmed = False

    def _update_crop(self):
        crop = crop_roi(self.frame_view._frame, self.frame_view.roi())
        if crop is None:
            self.crop_label.setText(tr("Crop preview"))
            return
        pix = RoiFrameView._to_pixmap(crop)
        self.crop_label.setPixmap(pix.scaled(
            self.crop_label.width(), 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))

    def _refresh_boxes(self):
        self.frame_view.set_boxes(self._last_boxes if hasattr(self, "_last_boxes") else [])

    def _reset_roi(self):
        self.frame_view.set_roi((0.0, 0.85, 1.0, 0.15))
        self._last_boxes = []
        self._update_crop()
        self.confirmed = False
        self.status_label.setText("")

    def _test_ocr(self):
        if not self.video:
            show_error(tr("Open a video first"))
            return
        roi = self.frame_view.roi()
        cfg = OcrConfig(provider="paddle", roi=roi, language=self.language, device=self.device)
        if not cfg.is_valid_roi():
            show_error(tr("Draw a valid region first"))
            return
        frame, _, _ = frame_at("ffmpeg", self.video, self.ms_input.value())
        if frame is None:
            show_error(tr("Could not decode a frame"))
            return
        crop = crop_roi(frame, roi)
        try:
            result = run(provider=PADDLE_OCR, image=crop, language=self.language, device=self.device)
        except RuntimeError as error:
            show_error(str(error))
            return
        self._last_boxes = [
            (b.box[0], b.box[1], b.box[2], b.box[3]) for b in result.lines if b.box
        ]
        self.frame_view.set_boxes(self._last_boxes)
        self.status_label.setText(
            f"{tr('Text')}: {result.text or '—'}   {tr('Confidence')}: {result.confidence:.2f}"
        )

    def _confirm(self):
        if not self.video:
            show_error(tr("Open a video first"))
            return
        roi = self.frame_view.roi()
        if not OcrConfig(roi=roi).is_valid_roi() or (roi[2] * roi[3]) <= 0:
            show_error(tr("Confirm a valid region first"))
            return
        self.confirmed = True
        app_cfg.ocr_roi = roi
        app_cfg.ocr_roi_confirmed = True
        app_cfg.subtitle_source = "video_ocr"
        main_win = getattr(app_cfg, "main_win", None)
        if main_win:
            if hasattr(main_win, "win_action") and self.video:
                if not main_win.win_action.queue_mp4 or main_win.win_action.queue_mp4[0] != self.video:
                    main_win.win_action.queue_mp4 = [self.video]
                    if hasattr(main_win, "source_mp4"):
                        main_win.source_mp4.setText(Path(self.video).name)
                    if hasattr(main_win, "output_dir"):
                        output_path = Path(self.video).parent / "_video_out"
                        main_win.output_dir.setText(output_path.as_posix())
            if hasattr(main_win, "subtitle_source"):
                main_win.subtitle_source.setCurrentIndex(1)
            if hasattr(main_win, "show_tips"):
                main_win.show_tips.setText("")
        self.close()

    def update_ui(self):
        main_win = getattr(app_cfg, "main_win", None)
        if main_win and hasattr(main_win, "win_action") and main_win.win_action.queue_mp4:
            if len(main_win.win_action.queue_mp4) > 0:
                video_path = main_win.win_action.queue_mp4[0]
                if self.video != video_path:
                    self.load_video(video_path)


def openwin():
    existing = app_cfg.child_forms.get("ocr")
    if existing:
        existing.update_ui()
        existing.show()
        existing.activateWindow()
        return existing
    dialog = RoiDialog()
    dialog.update_ui()
    app_cfg.child_forms["ocr"] = dialog
    dialog.show()
    dialog.activateWindow()
    return dialog
