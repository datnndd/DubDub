from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

import soundfile as sf

from videotrans.tts._base import BaseTTS
from videotrans.util.help_role import get_vieneu_custom_voice_path


@dataclass
class VieNeuTTS(BaseTTS):
    engine: Any = field(init=False, repr=False)

    def __post_init__(self):
        super().__post_init__()
        self.engine = self._create_engine()

    def _create_engine(self):
        from vieneu import Vieneu

        device = "cuda" if self.is_cuda else "cpu"
        backend = "pytorch" if self.is_cuda else "onnx"
        return Vieneu(
            mode="v3turbo",
            device=device,
            backend=backend,
            max_batch_size=4,
        )

    def _inference_options(
        self, item: Dict[str, Any]
    ) -> Tuple[Tuple[str, str], Dict[str, Any]]:
        role = str(item.get("role") or "").strip()
        if role.lower() == "clone":
            ref_wav, _ = self.get_ref_wav(item)
            return ("clone", ref_wav), {"ref_audio": ref_wav}

        custom_voice_path = get_vieneu_custom_voice_path(role)
        if custom_voice_path:
            reference_audio = Path(custom_voice_path)
            if not reference_audio.is_file():
                raise FileNotFoundError(f"VieNeu reference audio does not exist: {reference_audio}")
            return ("custom", reference_audio.as_posix()), {"ref_audio": reference_audio.as_posix()}

        return ("preset", role), {"voice": self.engine.get_preset_voice(role)}

    def _exec(self) -> None:
        queue_by_voice: Dict[
            Tuple[str, str], List[Tuple[Dict[str, Any], Dict[str, Any]]]
        ] = defaultdict(list)
        for item in self.queue_tts:
            if not item.get("text", "").strip() or Path(item["filename"]).is_file():
                continue
            voice_key, options = self._inference_options(item)
            queue_by_voice[voice_key].append((item, options))

        try:
            completed = 0
            for items in queue_by_voice.values():
                queue = [item for item, _ in items]
                options = items[0][1]
                audios = self.engine.infer_batch(
                    [item["text"] for item in queue],
                    **options,
                )
                if len(audios) != len(queue):
                    raise RuntimeError(
                        "VieNeu-TTS returned an unexpected number of audio segments"
                    )
                for item, audio in zip(queue, audios):
                    sf.write(item["filename"], audio, self.engine.sample_rate)
                    completed += 1
                    self.signal(text=f"TTS[{completed}/{self.len}]")
            self.signal(text="TTS ended")
        finally:
            self.engine.close()
