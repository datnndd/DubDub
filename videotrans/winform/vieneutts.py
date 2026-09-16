from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from videotrans.configure import contants
from videotrans.configure.config import app_cfg, tr
from videotrans.util.help_misc import set_process, show_error
from videotrans.util.help_role import (
    get_vieneu_custom_voice_map,
    remove_vieneu_custom_voice,
    save_vieneu_custom_voice,
)


class VieNeuVoicesDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowModality(Qt.NonModal)
        self.setMinimumSize(620, 420)
        self.setWindowTitle(tr("Manage VieNeu voices"))

        layout = QVBoxLayout(self)
        hint = QLabel(tr("Add a name and reference audio file. The original file must remain available."))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.voice_list = QListWidget(self)
        layout.addWidget(self.voice_list)

        form_layout = QFormLayout()
        self.name_input = QLineEdit(self)
        self.audio_input = QLineEdit(self)
        self.audio_input.setReadOnly(True)
        browse_button = QPushButton(tr("Select reference audio"), self)
        audio_layout = QHBoxLayout()
        audio_layout.addWidget(self.audio_input)
        audio_layout.addWidget(browse_button)
        form_layout.addRow(tr("Voice name"), self.name_input)
        form_layout.addRow(tr("Reference audio"), audio_layout)
        layout.addLayout(form_layout)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton(tr("Add or update voice"), self)
        self.remove_button = QPushButton(tr("Remove selected voice"), self)
        self.close_button = QPushButton(tr("Close"), self)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)

        browse_button.clicked.connect(self._select_reference_audio)
        self.save_button.clicked.connect(self._save_voice)
        self.remove_button.clicked.connect(self._remove_voice)
        self.close_button.clicked.connect(self.close)
        self.voice_list.currentItemChanged.connect(self._select_voice)
        self.update_ui()

    def update_ui(self, selected_name=None):
        if selected_name is None and self.voice_list.currentItem():
            selected_name = self.voice_list.currentItem().data(Qt.ItemDataRole.UserRole)

        custom_voices = get_vieneu_custom_voice_map()
        self.voice_list.blockSignals(True)
        self.voice_list.clear()
        for voice_name in sorted(custom_voices, key=str.casefold):
            item = QListWidgetItem(voice_name)
            item.setData(Qt.ItemDataRole.UserRole, voice_name)
            item.setToolTip(custom_voices[voice_name])
            self.voice_list.addItem(item)
            if voice_name == selected_name:
                self.voice_list.setCurrentItem(item)
        self.voice_list.blockSignals(False)

        if self.voice_list.currentItem():
            self._select_voice(self.voice_list.currentItem(), None)
        else:
            self.name_input.clear()
            self.audio_input.clear()

    def _select_reference_audio(self):
        patterns = " ".join(f"*.{extension}" for extension in contants.AUDIO_EXITS)
        audio_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select reference audio"),
            "",
            f"Audio files ({patterns})",
        )
        if audio_path:
            self.audio_input.setText(Path(audio_path).as_posix())

    def _select_voice(self, current_item, _previous_item):
        if not current_item:
            return
        voice_name = current_item.data(Qt.ItemDataRole.UserRole)
        self.name_input.setText(voice_name)
        self.audio_input.setText(get_vieneu_custom_voice_map().get(voice_name, ""))

    def _save_voice(self):
        try:
            voice_name = save_vieneu_custom_voice(
                self.name_input.text(),
                self.audio_input.text(),
            )
        except ValueError as error:
            show_error(str(error))
            return
        set_process(text="", type="refreshtts")
        self.update_ui(voice_name)

    def _remove_voice(self):
        current_item = self.voice_list.currentItem()
        if not current_item:
            show_error(tr("Select a custom VieNeu voice first"))
            return
        voice_name = current_item.data(Qt.ItemDataRole.UserRole)
        if remove_vieneu_custom_voice(voice_name):
            set_process(text="", type="refreshtts")
            self.update_ui()


def openwin():
    existing_dialog = app_cfg.child_forms.get("vieneutts")
    if existing_dialog:
        existing_dialog.update_ui()
        existing_dialog.show()
        existing_dialog.activateWindow()
        return existing_dialog

    dialog = VieNeuVoicesDialog()
    app_cfg.child_forms["vieneutts"] = dialog
    dialog.show()
    dialog.activateWindow()
    return dialog
