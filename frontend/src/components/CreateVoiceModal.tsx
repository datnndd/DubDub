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
} from 'lucide-react';

export const CreateVoiceModal: React.FC = () => {
  const isOpen = useDubDubStore((s) => s.isCreateVoiceModalOpen);
  const setIsOpen = useDubDubStore((s) => s.setCreateVoiceModalOpen);
  const activeTtsType = useDubDubStore((s) => s.backend?.config?.ttsType ?? 2);
  const createVoice = useDubDubStore((s) => s.createVoice);

  const [name, setName] = useState('');
  const [provider, setProvider] = useState<number>(activeTtsType);
  const [description, setDescription] = useState('');
  const [language, setLanguage] = useState('vi');
  const [refText, setRefText] = useState('');
  const [instruct, setInstruct] = useState('');

  // Audio source state
  const [sourceMode, setSourceMode] = useState<'upload' | 'record'>('upload');
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioDuration, setAudioDuration] = useState<number | null>(null);

  // Recording state
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordingTimerRef = useRef<number | null>(null);

  // Playback & submission state
  const [isPlaying, setIsPlaying] = useState(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setProvider(activeTtsType);
      setName('');
      setDescription('');
      setLanguage('vi');
      setRefText('');
      setInstruct('');
      setAudioBlob(null);
      setAudioFile(null);
      setAudioUrl(null);
      setAudioDuration(null);
      setErrorMsg(null);
      setSourceMode('upload');
    }
  }, [isOpen, activeTtsType]);

  // Clean up object URLs
  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  if (!isOpen) return null;

  const handleFileChange = (file: File) => {
    setErrorMsg(null);
    if (audioUrl) URL.revokeObjectURL(audioUrl);

    const url = URL.createObjectURL(file);
    setAudioFile(file);
    setAudioBlob(file);
    setAudioUrl(url);

    // Measure audio duration
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
      // Browser cannot decode format natively (e.g. FLAC or OGG in Safari).
      // Fall back to assuming valid duration so backend FFmpeg will validate authoritatively.
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

        // Stop all audio tracks to release the microphone
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanName = name.trim();
    if (!cleanName) {
      setErrorMsg('Please enter a voice name.');
      return;
    }

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
        ref_text: refText.trim(),
        instruct: instruct.trim(),
        audio: audioBlob,
      });
      setIsOpen(false);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create voice.');
    } finally {
      setIsSubmitting(false);
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
              <h3 className="font-bold text-sm text-stone-900">Clone Custom Neural Voice</h3>
              <p className="text-[11px] text-stone-500">Create a reproducible voice profile from a short speech sample</p>
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{errorMsg}</div>
            </div>
          )}

          {/* Voice Name & Language Row */}
          <div className="grid grid-cols-12 gap-3">
            <div className="col-span-8 space-y-1.5">
              <label className="block text-xs font-bold text-stone-700">
                Voice Name <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Minh Thư (Storyteller)"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full text-xs px-3 py-2 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] focus:ring-1 focus:ring-[#8D4B00] outline-hidden font-medium"
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

          {/* TTS Engine Provider Selector */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-stone-700">Cloning Model Backbone</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 2, label: 'VieNeu-TTS', desc: '48kHz NeuTTS Air (Default)' },
                { id: 1, label: 'OmniVoice', desc: '24kHz Built-in' },
                { id: 0, label: 'ElevenLabs', desc: 'Cloud Instant Cloning' },
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

          {/* Reference Audio Source Tabs */}
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

            {/* Upload Zone */}
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

            {/* Microphone Recording Zone */}
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

            {/* Audio Duration Status Indicator & Audition Player */}
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

          {/* Reference Audio Transcript (Crucial for OmniVoice) */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-bold text-stone-700">
                Reference Audio Transcript
                {provider === 1 && <span className="text-rose-500 ml-1">(Required for OmniVoice)</span>}
              </label>
              {provider === 1 && (
                <span className="text-[10px] text-amber-700 font-semibold flex items-center gap-0.5">
                  <Info className="w-3 h-3" /> Prevents hallucinations
                </span>
              )}
            </div>
            <textarea
              rows={2}
              placeholder="Exact words spoken in the reference audio sample..."
              value={refText}
              onChange={(e) => setRefText(e.target.value)}
              className="w-full text-xs p-2.5 bg-white rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
            />
          </div>

          {/* Style & Timbre Instruction Prompt */}
          <div className="space-y-1.5">
            <label className="block text-xs font-bold text-stone-700">
              Style / Timbre Tags <span className="text-stone-400 font-normal">(Optional)</span>
            </label>
            <input
              type="text"
              placeholder="e.g. Warm, calm documentary narrator with low resonance"
              value={instruct}
              onChange={(e) => setInstruct(e.target.value)}
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
              disabled={isSubmitting || !name.trim() || !audioBlob || !isDurationValid}
              className="px-5 py-2 rounded-xl bg-[#8D4B00] hover:bg-[#733D00] text-white text-xs font-bold transition-all shadow-sm flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  Transcoding & Saving...
                </>
              ) : (
                'Save Voice Profile'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
