import React, { useState, useRef, useEffect } from 'react';
import { useDubDubStore } from '../store';
import {
  X,
  Mic,
  Upload,
  Square,
  Play,
  Pause,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  Info,
  Loader2,
  Sliders,
  Volume2,
  Wand2,
} from 'lucide-react';
import { requestVoiceDesignAssist, previewTTS } from '../api/voices';

const VIENEU_PRESET_VOICES = [
  { id: 'Bình (nam miền Bắc)', name: 'Bình', region: 'Nam Bắc', gender: 'Nam', desc: 'Truyền cảm, ấm áp' },
  { id: 'Ly (nữ miền Bắc)', name: 'Ly', region: 'Nữ Bắc', gender: 'Nữ', desc: 'Tự nhiên, nhẹ nhàng' },
  { id: 'Ngọc (nữ miền Bắc)', name: 'Ngọc', region: 'Nữ Bắc', gender: 'Nữ', desc: 'Trong trẻo, rõ nét' },
  { id: 'Tuyên (nam miền Bắc)', name: 'Tuyên', region: 'Nam Bắc', gender: 'Nam', desc: 'Trầm ấm, đĩnh đạc' },
  { id: 'Vĩnh (nam miền Nam)', name: 'Vĩnh', region: 'Nam Nam', gender: 'Nam', desc: 'Tự nhiên, phóng khoáng' },
  { id: 'Đoan (nữ miền Nam)', name: 'Đoan', region: 'Nữ Nam', gender: 'Nữ', desc: 'Dịu dàng, ngọt ngào' },
];

export const CreateVoiceModal: React.FC = () => {
  const isOpen = useDubDubStore((s) => s.isCreateVoiceModalOpen);
  const setIsOpen = useDubDubStore((s) => s.setCreateVoiceModalOpen);
  const activeTtsType = useDubDubStore((s) => s.backend?.config?.ttsType ?? 2);
  const createVoice = useDubDubStore((s) => s.createVoice);
  const customVoices = useDubDubStore((s) => s.customVoices || []);

  // Creation mode
  const [creationMode, setCreationMode] = useState<'clone' | 'design'>('clone');

  // Common voice attributes
  const [name, setName] = useState('');
  const [provider, setProvider] = useState<number>(activeTtsType);
  const [description, setDescription] = useState('');
  const [language, setLanguage] = useState('vi');
  const [refText, setRefText] = useState('');
  const [instruct, setInstruct] = useState('');

  // Cloning specific
  const [denoise, setDenoise] = useState(true);
  const [sourceMode, setSourceMode] = useState<'upload' | 'record'>('upload');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioDuration, setAudioDuration] = useState<number | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingTimerRef = useRef<number | null>(null);

  // Design specific
  const [baseVoice, setBaseVoice] = useState('Bình (nam miền Bắc)');
  const [style, setStyle] = useState<'tu_nhien' | 'tin_tuc' | 'doc_truyen'>('tu_nhien');
  const [temperature, setTemperature] = useState<number>(0.8);
  const [repetitionPenalty, setRepetitionPenalty] = useState<number>(1.2);
  const [silenceP, setSilenceP] = useState<number>(0.15);
  const [designPrompt, setDesignPrompt] = useState('');
  const [isAssisting, setIsAssisting] = useState(false);
  const [previewText, setPreviewText] = useState('Xin chào, đây là bản nghe thử phong cách giọng nói vừa được thiết kế.');

  // Playback & audition
  const [isPlaying, setIsPlaying] = useState(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const [isAuditioning, setIsAuditioning] = useState(false);
  const [auditionAudioUrl, setAuditionAudioUrl] = useState<string | null>(null);
  const [isAuditionPlaying, setIsAuditionPlaying] = useState(false);
  const auditionAudioRef = useRef<HTMLAudioElement | null>(null);

  // Status
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setCreationMode('clone');
      setProvider(activeTtsType);
      setName('');
      setDescription('');
      setLanguage('vi');
      setRefText('');
      setInstruct('');
      setDenoise(true);
      setAudioBlob(null);
      setAudioFile(null);
      setAudioUrl(null);
      setAudioDuration(null);
      setErrorMsg(null);
      setSourceMode('upload');
      setBaseVoice('Bình (nam miền Bắc)');
      setStyle('tu_nhien');
      setTemperature(0.8);
      setRepetitionPenalty(1.2);
      setSilenceP(0.15);
      setDesignPrompt('');
      setPreviewText('Xin chào, đây là bản nghe thử phong cách giọng nói vừa được thiết kế.');
      setAuditionAudioUrl(null);
      setIsAuditionPlaying(false);
    }
  }, [isOpen, activeTtsType]);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (auditionAudioUrl && auditionAudioUrl.startsWith('blob:')) URL.revokeObjectURL(auditionAudioUrl);
    };
  }, [audioUrl, auditionAudioUrl]);

  if (!isOpen) return null;

  const handleFileChange = (file: File) => {
    setErrorMsg(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);

    const url = URL.createObjectURL(file);
    setAudioFile(file);
    setAudioBlob(file);
    setAudioUrl(url);

    const tempAudio = new Audio(url);
    tempAudio.onloadedmetadata = () => {
      const dur = tempAudio.duration;
      setAudioDuration(dur);
      if (dur < 2.0) {
        setErrorMsg(`Audio duration (${dur.toFixed(1)}s) is too short. Minimum duration is 2.0s.`);
      } else if (dur > 30.0) {
        setErrorMsg(`Audio duration (${dur.toFixed(1)}s) exceeds 30s limit. Please select a shorter sample.`);
      }
    };
    tempAudio.onerror = () => {
      setAudioDuration(5.0);
    };
  };

  const startRecording = async () => {
    setErrorMsg(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const supportedTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg'];
      const mimeType = supportedTypes.find((t) => typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported?.(t)) || '';
      const mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      const chunks: BlobPart[] = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const actualType = mediaRecorder.mimeType || mimeType || 'audio/webm';
        const blob = new Blob(chunks, { type: actualType });
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        const url = URL.createObjectURL(blob);
        setAudioBlob(blob);
        setAudioFile(null);
        setAudioUrl(url);

        const tempAudio = new Audio(url);
        tempAudio.onloadedmetadata = () => {
          const dur = tempAudio.duration;
          setAudioDuration(dur);
          if (dur < 2.0) {
            setErrorMsg(`Recording (${dur.toFixed(1)}s) is too short. Speak for at least 2.0 seconds.`);
          } else if (dur > 30.0) {
            setErrorMsg(`Recording (${dur.toFixed(1)}s) exceeds 30.0s. Please keep it concise.`);
          }
        };

        stream.getTracks().forEach((track) => track.stop());
      };

      mediaRecorder.start(250);
      setIsRecording(true);
      setRecordingSeconds(0);

      recordingTimerRef.current = window.setInterval(() => {
        setRecordingSeconds((prev) => {
          if (prev >= 29) {
            stopRecording();
            return 30;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err: any) {
      setErrorMsg(`Microphone access error: ${err.message || 'Permission denied'}`);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (recordingTimerRef.current) {
        clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
      }
    }
  };

  const togglePlayback = () => {
    if (!audioPlayerRef.current) return;
    if (isPlaying) {
      audioPlayerRef.current.pause();
      setIsPlaying(false);
    } else {
      audioPlayerRef.current.play();
      setIsPlaying(true);
    }
  };

  const insertEmotionTag = (tag: string) => {
    setPreviewText((prev) => `${prev.trim()} ${tag} `);
  };

  const handleApplyDesignAssist = async () => {
    if (!designPrompt.trim()) return;
    setIsAssisting(true);
    setErrorMsg(null);
    try {
      const res = await requestVoiceDesignAssist({ prompt: designPrompt });
      if (res.style === 'tin_tuc' || res.style === 'doc_truyen' || res.style === 'tu_nhien') {
        setStyle(res.style);
      }
      if (res.temperature) setTemperature(res.temperature);
      if (res.repetition_penalty) setRepetitionPenalty(res.repetition_penalty);
      if (!name.trim() && res.suggested_name) setName(res.suggested_name);
      if (res.description) setDescription(res.description);
      if (res.suggested_tags && res.suggested_tags.length > 0) {
        setPreviewText((prev) => `${prev.trim()} ${res.suggested_tags[0]}`);
      }
    } catch (err: any) {
      setErrorMsg(`AI Assistant error: ${err.message || 'Failed to analyze prompt'}`);
    } finally {
      setIsAssisting(false);
    }
  };

  const handleAuditionDesign = async () => {
    if (!previewText.trim()) return;
    setIsAuditioning(true);
    setErrorMsg(null);
    try {
      const res = await previewTTS({
        voice: baseVoice,
        provider: 2,
        language,
        text: previewText,
        style,
        tuningParams: {
          style,
          temperature,
          repetition_penalty: repetitionPenalty,
          silence_p: silenceP,
        },
      });
      if (res.audio_url || res.preview_url) {
        const url = res.audio_url || res.preview_url;
        setAuditionAudioUrl(url);
        setIsAuditionPlaying(true);
        if (auditionAudioRef.current) {
          auditionAudioRef.current.src = url;
          auditionAudioRef.current.play().catch(() => {});
        }
      }
    } catch (err: any) {
      setErrorMsg(`Audition synthesis error: ${err.message || 'Failed to synthesize sample'}`);
    } finally {
      setIsAuditioning(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanName = name.trim();
    if (!cleanName) {
      setErrorMsg('Please enter a voice name.');
      return;
    }

    if (creationMode === 'clone') {
      if (!audioBlob) {
        setErrorMsg('Please upload or record reference audio for voice cloning.');
        return;
      }

      if (audioDuration !== null && (audioDuration < 2.0 || audioDuration > 30.0)) {
        setErrorMsg(`Audio duration must be between 2.0s and 30.0s (currently ${audioDuration.toFixed(1)}s).`);
        return;
      }

      if (provider === 1 && !refText.trim()) {
        setErrorMsg('OmniVoice requires reference text transcript to prevent acoustic hallucinations.');
        return;
      }

      setIsSubmitting(true);
      try {
        await createVoice({
          name: cleanName,
          provider,
          description: description.trim(),
          language,
          kind: 'clone',
          ref_text: refText.trim(),
          instruct: instruct.trim(),
          audio: audioBlob,
          denoise,
          tuning_params: { denoise },
        });
        setIsOpen(false);
      } catch (err: any) {
        setErrorMsg(err.message || 'Failed to clone voice.');
      } finally {
        setIsSubmitting(false);
      }
    } else {
      // Voice Design
      setIsSubmitting(true);
      try {
        await createVoice({
          name: cleanName,
          provider: 2, // VieNeu-TTS
          description: description.trim() || `Thiết kế từ ${baseVoice} (${style})`,
          language,
          kind: 'design',
          external_voice_id: baseVoice,
          tuning_params: {
            base_voice: baseVoice,
            style,
            temperature,
            repetition_penalty: repetitionPenalty,
            silence_p: silenceP,
          },
        });
        setIsOpen(false);
      } catch (err: any) {
        setErrorMsg(err.message || 'Failed to design voice.');
      } finally {
        setIsSubmitting(false);
      }
    }
  };

  const isDurationValid = audioDuration !== null && audioDuration >= 2.0 && audioDuration <= 30.0;

  return (
    <div
      data-modal="create-voice"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-xs p-4 overflow-y-auto"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) setIsOpen(false);
      }}
    >
      <div className="w-full max-w-lg bg-[#FAF9F6] rounded-2xl border border-[#E7E4DC] shadow-2xl overflow-hidden flex flex-col my-auto animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="h-14 px-5 border-b border-[#E7E4DC] flex items-center justify-between bg-white shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-amber-100 flex items-center justify-center text-[#8D4B00]">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-stone-900">
                {creationMode === 'clone' ? 'Clone Custom Voice' : 'Design New Voice Persona'}
              </h3>
              <p className="text-[11px] text-stone-500">
                {creationMode === 'clone'
                  ? 'Replicate a real voice from 3-15 seconds of audio'
                  : 'Customize speaking style, emotions, and prosody with VieNeu-TTS'}
              </p>
            </div>
          </div>
          <button
            onClick={() => setIsOpen(false)}
            disabled={isSubmitting}
            className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher: Voice Cloning vs Voice Design */}
        <div className="grid grid-cols-2 p-1.5 bg-stone-100 border-b border-[#E7E4DC] text-xs font-bold">
          <button
            type="button"
            onClick={() => setCreationMode('clone')}
            className={`py-2 px-3 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
              creationMode === 'clone'
                ? 'bg-white text-stone-900 shadow-xs'
                : 'text-stone-500 hover:text-stone-800'
            }`}
          >
            <Mic className="w-3.5 h-3.5 text-[#8D4B00]" />
            Voice Cloning
          </button>
          <button
            type="button"
            onClick={() => setCreationMode('design')}
            className={`py-2 px-3 rounded-xl flex items-center justify-center gap-1.5 transition-all ${
              creationMode === 'design'
                ? 'bg-white text-stone-900 shadow-xs'
                : 'text-stone-500 hover:text-stone-800'
            }`}
          >
            <Sliders className="w-3.5 h-3.5 text-[#8D4B00]" />
            Voice Design
            <span className="px-1.5 py-0.2 rounded-full text-[9px] bg-amber-100 text-[#8D4B00]">VieNeu</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMsg}</div>
            </div>
          )}

          {/* Common: Voice Name & Language Row */}
          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-8 space-y-1.5">
              <label className="block text-xs font-bold text-stone-700">
                Voice Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder={creationMode === 'clone' ? 'e.g. Minh Thư (Studio)' : 'e.g. Hoàng Long (Storyteller)'}
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
              />
            </div>

            <div className="col-span-4 space-y-1.5">
              <label className="block text-xs font-bold text-stone-700">Language</label>
              <select
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
              >
                <option value="vi">Vietnamese (vi)</option>
                <option value="en">English (en)</option>
                <option value="Auto">Auto Detect</option>
              </select>
            </div>
          </div>

          {/* ============================================================== */}
          {/* TAB 1: VOICE CLONING                                           */}
          {/* ============================================================== */}
          {creationMode === 'clone' && (
            <>
              {/* TTS Provider */}
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-stone-700">Cloning Model Backbone</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 2, label: 'VieNeu-TTS', desc: '48kHz Turbo (Recommended)' },
                    { id: 1, label: 'OmniVoice', desc: '24kHz Built-in' },
                    { id: 0, label: 'ElevenLabs', desc: 'Cloud Instant' },
                  ].map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => setProvider(item.id)}
                      className={`p-2.5 rounded-xl border text-left transition-all ${
                        provider === item.id
                          ? 'border-[#8D4B00] bg-amber-50/60 ring-1 ring-[#8D4B00]'
                          : 'border-stone-200 bg-white hover:border-stone-300'
                      }`}
                    >
                      <div className="font-bold text-xs text-stone-900">{item.label}</div>
                      <div className="text-[10px] text-stone-500">{item.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Denoise Toggle for VieNeu */}
              {provider === 2 && (
                <div className="flex items-center justify-between p-2.5 bg-amber-50/40 rounded-xl border border-amber-200/50">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="denoise-toggle"
                      checked={denoise}
                      onChange={(e) => setDenoise(e.target.checked)}
                      className="w-4 h-4 rounded text-[#8D4B00] focus:ring-[#8D4B00] border-stone-300 cursor-pointer"
                    />
                    <label htmlFor="denoise-toggle" className="text-xs font-bold text-stone-800 cursor-pointer">
                      ONNX Auto-Denoise
                    </label>
                  </div>
                  <span className="text-[10px] text-stone-500">Cleans room reverb and background hiss</span>
                </div>
              )}

              {/* Audio Upload or Record */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-stone-700">
                    Reference Audio Sample <span className="text-rose-500">*</span>
                  </label>
                  <div className="flex items-center gap-1 bg-stone-100 p-0.5 rounded-lg border border-stone-200">
                    <button
                      type="button"
                      onClick={() => setSourceMode('upload')}
                      className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                        sourceMode === 'upload' ? 'bg-white shadow-xs text-stone-900' : 'text-stone-500'
                      }`}
                    >
                      <Upload className="w-3 h-3 inline mr-1" />
                      Upload File
                    </button>
                    <button
                      type="button"
                      onClick={() => setSourceMode('record')}
                      className={`px-2.5 py-1 text-[11px] font-semibold rounded-md transition-all ${
                        sourceMode === 'record' ? 'bg-white shadow-xs text-stone-900' : 'text-stone-500'
                      }`}
                    >
                      <Mic className="w-3 h-3 inline mr-1" />
                      Record Mic
                    </button>
                  </div>
                </div>

                {sourceMode === 'upload' && (
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={(e) => {
                      e.preventDefault();
                      if (e.dataTransfer.files?.[0]) handleFileChange(e.dataTransfer.files[0]);
                    }}
                    className={`border-2 border-dashed rounded-xl p-5 text-center transition-all ${
                      audioBlob ? 'border-emerald-300 bg-emerald-50/20' : 'border-stone-300 bg-white hover:border-amber-400'
                    }`}
                  >
                    <input
                      type="file"
                      id="voice-audio-file"
                      accept="audio/wav,audio/mp3,audio/mpeg,audio/m4a,audio/webm,audio/ogg,audio/flac,.wav,.mp3,.m4a,.webm,.ogg,.flac"
                      className="hidden"
                      onChange={(e) => {
                        if (e.target.files?.[0]) handleFileChange(e.target.files[0]);
                      }}
                    />
                    <label htmlFor="voice-audio-file" className="cursor-pointer block">
                      <div className="w-10 h-10 rounded-full bg-stone-100 flex items-center justify-center mx-auto mb-2 text-stone-500">
                        <Upload className="w-5 h-5" />
                      </div>
                      <div className="text-xs font-bold text-stone-800">
                        {audioFile ? audioFile.name : 'Click to select or drag audio here'}
                      </div>
                      <div className="text-[10px] text-stone-500 mt-1">
                        WAV, MP3, M4A, WebM (Optimal: 3-15 seconds, mono 48kHz / 24kHz)
                      </div>
                    </label>
                  </div>
                )}

                {sourceMode === 'record' && (
                  <div className="p-5 rounded-xl border border-stone-200 bg-white text-center space-y-3">
                    <div className="flex items-center justify-center gap-3">
                      {!isRecording ? (
                        <button
                          type="button"
                          onClick={startRecording}
                          className="px-4 py-2 rounded-xl bg-[#8D4B00] text-white font-bold text-xs flex items-center gap-2 hover:bg-[#733D00] shadow-sm transition-all"
                        >
                          <Mic className="w-4 h-4" />
                          Start Recording
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={stopRecording}
                          className="px-4 py-2 rounded-xl bg-rose-600 text-white font-bold text-xs flex items-center gap-2 animate-pulse shadow-sm"
                        >
                          <Square className="w-4 h-4 fill-white" />
                          Stop Recording ({recordingSeconds}s / 30s)
                        </button>
                      )}
                    </div>
                    <div className="text-[11px] text-stone-500">
                      {isRecording ? 'Speak clearly into your microphone...' : 'Record 3-10 seconds of clear speech.'}
                    </div>
                  </div>
                )}

                {audioUrl && (
                  <div className="p-3 rounded-xl border border-stone-200 bg-white flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 min-w-0">
                      <button
                        type="button"
                        onClick={togglePlayback}
                        className="w-8 h-8 rounded-full bg-stone-100 hover:bg-stone-200 flex items-center justify-center text-stone-700 shrink-0"
                      >
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 ml-0.5" />}
                      </button>
                      <div className="min-w-0">
                        <div className="text-xs font-bold text-stone-800 truncate">Reference Sample Ready</div>
                        <div className="text-[10px] text-stone-500">
                          Duration: {audioDuration !== null ? `${audioDuration.toFixed(1)}s` : 'Analyzing...'}
                        </div>
                      </div>
                    </div>

                    <div className="shrink-0">
                      {isDurationValid ? (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" /> Valid Duration
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 text-amber-800 flex items-center gap-1">
                          <AlertCircle className="w-3 h-3" /> Must be 2-30s
                        </span>
                      )}
                    </div>

                    <audio
                      ref={audioPlayerRef}
                      src={audioUrl}
                      onEnded={() => setIsPlaying(false)}
                      className="hidden"
                    />
                  </div>
                )}
              </div>

              {/* Reference Audio Transcript for OmniVoice */}
              {provider === 1 && (
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="block text-xs font-bold text-stone-700">
                      Reference Audio Transcript <span className="text-rose-500">*</span>
                    </label>
                    <span className="text-[10px] text-amber-700 font-semibold flex items-center gap-0.5">
                      <Info className="w-3 h-3" /> Prevents hallucinations
                    </span>
                  </div>
                  <textarea
                    rows={2}
                    placeholder="Exact words spoken in the reference audio sample..."
                    value={refText}
                    onChange={(e) => setRefText(e.target.value)}
                    className="w-full text-xs p-2.5 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
                  />
                </div>
              )}
            </>
          )}

          {/* ============================================================== */}
          {/* TAB 2: VOICE DESIGN (VIENEU-TTS)                               */}
          {/* ============================================================== */}
          {creationMode === 'design' && (
            <>
              {/* AI Prompt Assistant */}
              <div className="p-3 rounded-xl bg-gradient-to-r from-amber-50 to-orange-50 border border-amber-200/70 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-[#8D4B00] flex items-center gap-1.5">
                    <Wand2 className="w-3.5 h-3.5" />
                    AI Prompt Assistant
                  </span>
                  <span className="text-[10px] text-stone-500">Auto-tunes styles & emotions</span>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="e.g. Giọng kể chuyện đêm khuya truyền cảm có tiếng thở dài..."
                    value={designPrompt}
                    onChange={(e) => setDesignPrompt(e.target.value)}
                    className="flex-1 text-xs px-2.5 py-1.5 bg-white rounded-lg border border-amber-200 focus:border-[#8D4B00] outline-hidden"
                  />
                  <button
                    type="button"
                    onClick={handleApplyDesignAssist}
                    disabled={isAssisting || !designPrompt.trim()}
                    className="px-3 py-1.5 bg-[#8D4B00] hover:bg-[#733D00] text-white text-xs font-bold rounded-lg shadow-xs flex items-center gap-1 disabled:opacity-50"
                  >
                    {isAssisting ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Apply'}
                  </button>
                </div>
              </div>

              {/* Base Voice Selector */}
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-stone-700">Base Voice Timbre</label>
                <select
                  value={baseVoice}
                  onChange={(e) => setBaseVoice(e.target.value)}
                  className="w-full text-xs px-3 py-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
                >
                  <optgroup label="VieNeu Built-in Presets">
                    {VIENEU_PRESET_VOICES.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name} — {v.region} ({v.desc})
                      </option>
                    ))}
                  </optgroup>
                  {customVoices.filter((v) => v.kind !== 'design').length > 0 && (
                    <optgroup label="Your Custom Cloned Voices">
                      {customVoices
                        .filter((v) => v.kind !== 'design')
                        .map((cv) => (
                          <option key={cv.id} value={cv.id}>
                            {cv.name} (Custom Cloned)
                          </option>
                        ))}
                    </optgroup>
                  )}
                </select>
              </div>

              {/* Speaking Style Cards */}
              <div className="space-y-1.5">
                <label className="block text-xs font-bold text-stone-700">Speaking Style</label>
                <div className="grid grid-cols-3 gap-2">
                  {[
                    { id: 'tu_nhien', label: 'Tự nhiên', desc: 'Hội thoại đời thường, tự nhiên' },
                    { id: 'tin_tuc', label: 'Tin tức', desc: 'Trang trọng, dõng dạc, rõ ràng' },
                    { id: 'doc_truyen', label: 'Đọc truyện', desc: 'Diễn cảm, giàu cảm xúc drama' },
                  ].map((item) => (
                    <button
                      type="button"
                      key={item.id}
                      onClick={() => setStyle(item.id as any)}
                      className={`p-2.5 rounded-xl border text-left transition-all ${
                        style === item.id
                          ? 'border-[#8D4B00] bg-amber-50/70 ring-1 ring-[#8D4B00]'
                          : 'border-stone-200 bg-white hover:border-stone-300'
                      }`}
                    >
                      <div className="font-bold text-xs text-stone-900">{item.label}</div>
                      <div className="text-[10px] text-stone-500 leading-tight mt-0.5">{item.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Emotion Expression Palette */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="block text-xs font-bold text-stone-700">Non-verbal Emotion Cues</label>
                  <span className="text-[10px] text-stone-400">Click to insert into test phrase</span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => insertEmotionTag('[cười]')}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                  >
                    + [cười] (Chuckle)
                  </button>
                  <button
                    type="button"
                    onClick={() => insertEmotionTag('[thở dài]')}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-sky-50 text-sky-700 border border-sky-200 hover:bg-sky-100 transition-colors"
                  >
                    + [thở dài] (Sigh)
                  </button>
                  <button
                    type="button"
                    onClick={() => insertEmotionTag('[hắng giọng]')}
                    className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-purple-50 text-purple-700 border border-purple-200 hover:bg-purple-100 transition-colors"
                  >
                    + [hắng giọng] (Throat clear)
                  </button>
                </div>
              </div>

              {/* Acoustic Tuning Sliders */}
              <div className="p-3 bg-white rounded-xl border border-stone-200 space-y-3">
                <div className="text-xs font-bold text-stone-800 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Sliders className="w-3.5 h-3.5 text-stone-500" />
                    Acoustic Prosody Sliders
                  </span>
                </div>

                {/* Temperature */}
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-stone-600 font-medium">Expressiveness (Temperature)</span>
                    <span className="font-bold text-stone-900">{temperature.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0.5"
                    max="1.2"
                    step="0.05"
                    value={temperature}
                    onChange={(e) => setTemperature(parseFloat(e.target.value))}
                    className="w-full accent-[#8D4B00] cursor-pointer"
                  />
                  <div className="flex justify-between text-[9px] text-stone-400">
                    <span>Calm (0.5)</span>
                    <span>Standard (0.8)</span>
                    <span>High Dynamic (1.2)</span>
                  </div>
                </div>

                {/* Repetition penalty */}
                <div className="space-y-1">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-stone-600 font-medium">Anti-Repetition Penalty</span>
                    <span className="font-bold text-stone-900">{repetitionPenalty.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="1.0"
                    max="1.5"
                    step="0.05"
                    value={repetitionPenalty}
                    onChange={(e) => setRepetitionPenalty(parseFloat(e.target.value))}
                    className="w-full accent-[#8D4B00] cursor-pointer"
                  />
                </div>
              </div>

              {/* Sample Audition Box */}
              <div className="space-y-2 p-3 bg-stone-50 rounded-xl border border-stone-200">
                <label className="block text-xs font-bold text-stone-700">Test Phrase & Live Audition</label>
                <textarea
                  rows={2}
                  value={previewText}
                  onChange={(e) => setPreviewText(e.target.value)}
                  className="w-full text-xs p-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
                />
                <div className="flex items-center justify-between pt-1">
                  <button
                    type="button"
                    onClick={handleAuditionDesign}
                    disabled={isAuditioning || !previewText.trim()}
                    className="px-3 py-1.5 rounded-lg bg-stone-800 hover:bg-stone-900 text-white text-xs font-bold flex items-center gap-1.5 shadow-xs disabled:opacity-50"
                  >
                    {isAuditioning ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Synthesizing...
                      </>
                    ) : (
                      <>
                        <Volume2 className="w-3.5 h-3.5" />
                        Audition Designed Voice
                      </>
                    )}
                  </button>

                  {auditionAudioUrl && (
                    <audio
                      ref={auditionAudioRef}
                      src={auditionAudioUrl}
                      controls
                      autoPlay
                      className="h-7 w-48"
                      onPlay={() => setIsAuditionPlaying(true)}
                      onPause={() => setIsAuditionPlaying(false)}
                      onEnded={() => setIsAuditionPlaying(false)}
                    />
                  )}
                </div>
              </div>
            </>
          )}

          {/* Description */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-stone-700">
              Description <span className="text-stone-400 font-normal">(Optional)</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Dành cho video tài liệu lịch sử hoặc kể chuyện"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full text-xs px-3 py-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
            />
          </div>

          {/* Action Buttons */}
          <div className="pt-3 border-t border-[#E7E4DC] flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              disabled={isSubmitting}
              className="px-4 py-2 rounded-xl border border-stone-200 bg-white hover:bg-stone-50 text-xs font-bold text-stone-700 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                isSubmitting ||
                !name.trim() ||
                (creationMode === 'clone' && (!audioBlob || !isDurationValid))
              }
              className="px-5 py-2 rounded-xl bg-[#8D4B00] hover:bg-[#733D00] text-white text-xs font-bold transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Saving Profile...
                </>
              ) : creationMode === 'clone' ? (
                'Save Cloned Voice'
              ) : (
                'Save Designed Voice'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
