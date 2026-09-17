/**
 * DubDub Studio Central Synchronized State Store
 * Keeps all workflow stages and UI components 100% in lockstep.
 */

class WorkflowStore {
  constructor() {
    this.listeners = new Set();
    this.selectedFile = null;
    this.mediaSelectionVersion = 0;
    this.pollTimer = null;
    this.state = {
      currentStep: 1, // 1: Prepare, 2: Review Transcript, 3: Voice & Dubbing, 4: Edit Video
      maxUnlockedStep: 4,
      project: {
        filename: "Select a video to begin",
        format: "—",
        resolution: "—",
        fps: "—",
        duration: "00:00.000",
        durationSec: 0,
        fileSize: "—",
        videoCodec: "—",
        audioCodec: "—",
        bitrate: "Not reported",
        hasAudio: false,
        hasVideo: false,
        verified: false,
        lastSaved: "Just now"
      },
      playback: {
        currentTime: 86.5, // 01:26.500
        formattedTime: "01:26.500",
        isPlaying: false,
        playbackSpeed: 1.0,
        audioChannel: "dub" // 'orig' or 'dub'
      },
      languages: {
        source: { code: "en", name: "English", flag: "", autoDetected: false },
        target: { code: "es", name: "Spanish" },
        timingMode: "idiomatic" // 'idiomatic' or 'direct'
      },
      engines: {
        asr: "whisper_v3_turbo",
        llm: "gpt_4o_dub",
        tone: "conversational",
        speakerDiarization: true,
        removeBackgroundNoise: true,
        ocrSlideEngine: true
      },
      speakers: [
        {
          id: "spk_1",
          code: "AC",
          name: "Alex Carter",
          role: "Keynote Speaker",
          preset: "Studio Warmth v4.2",
          clarity: "98%",
          coverage: "86%",
          color: "amber"
        },
        {
          id: "spk_2",
          code: "ER",
          name: "Elena Rostova",
          role: "Guest / Interviewer",
          preset: "Crisp Broadcast",
          clarity: "99%",
          coverage: "14%",
          color: "secondary"
        }
      ],
      tuning: {
        pace: 1.00,
        timbreWarmth: 62,
        ducking: "85/15"
      },
      lockedTerms: [
        { id: 1, source: "AI", target: "inteligencia artificial" },
        { id: 2, source: "vocoder", target: "vocoder" },
        { id: 3, source: "neural mesh", target: "malla neuronal" }
      ],
      segments: [
        {
          id: 1,
          speakerId: "spk_1",
          speakerName: "Alex Carter",
          speakerCode: "AC",
          startTime: "01:21.000",
          endTime: "01:26.400",
          startSec: 81.0,
          endSec: 86.4,
          cps: 14.2,
          cpsStatus: "Optimal",
          confidence: 99.1,
          sourceText: "We are entering an era where artificial intelligence truly understands human nuances.",
          targetText: "Estamos entrando en una era donde la inteligencia artificial realmente comprende los matices humanos.",
          hasOcrDiff: false
        },
        {
          id: 2,
          speakerId: "spk_1",
          speakerName: "Alex Carter",
          speakerCode: "AC",
          startTime: "01:26.500",
          endTime: "01:31.200",
          startSec: 86.5,
          endSec: 91.2,
          cps: 15.1,
          cpsStatus: "Good",
          confidence: 94.8,
          sourceText: "It's no longer just word-for-word translation, but cultural emotion.",
          targetText: "Ya no se trata solo de una traducción palabra por palabra, sino de emoción cultural.",
          hasOcrDiff: true,
          ocrBoxNumber: "#01",
          ocrConfidence: 99.4,
          ocrSlideText: "Translation must bridge cultural resonance, not merely literal syntax.",
          ocrResolved: false
        },
        {
          id: 3,
          speakerId: "spk_2",
          speakerName: "Elena Rostova",
          speakerCode: "ER",
          startTime: "01:31.500",
          endTime: "01:38.000",
          startSec: 91.5,
          endSec: 98.0,
          cps: 13.8,
          cpsStatus: "Optimal",
          confidence: 99.5,
          sourceText: "How does neural voice synthesis preserve the speaker's original emotional cadence?",
          targetText: "¿Cómo preserva la síntesis de voz neuronal la cadencia emocional original del orador?",
          hasOcrDiff: false
        },
        {
          id: 4,
          speakerId: "spk_1",
          speakerName: "Alex Carter",
          speakerCode: "AC",
          startTime: "01:38.200",
          endTime: "01:44.800",
          startSec: 98.2,
          endSec: 104.8,
          cps: 14.5,
          cpsStatus: "Optimal",
          confidence: 98.7,
          sourceText: "By isolating harmonic overtones while re-synthesizing phonemes in real-time.",
          targetText: "Aislando los armónicos superiores mientras se re-sintetizan los fonemas en tiempo real.",
          hasOcrDiff: false
        }
      ],
      subtitleStyles: {
        preset: "warm_glow",
        fontFamily: "Plus Jakarta Sans",
        fontSize: 24,
        color: "#FBBF24",
        aiLipSync: true,
        deReverb: true,
        faceRetouch: false,
        superRes4K: true,
        activeTab: "text" // 'text' or 'bgm'
      },
      gpuStatus: {
        warmDuration: "42m",
        status: "Online",
        memoryUsed: "4.8 / 16.0 GB",
        utilization: "38%"
      },
      backend: {
        ready: false,
        mediaId: null,
        options: { languages: [], recognizers: [], translators: [], voices: [], models: [] },
        config: { recognType: 0, translateType: 0, ttsType: 0, modelName: "large-v3-turbo", voiceRole: "", useCuda: false },
        status: "idle",
        jobId: null,
        stage: null,
        progress: null,
        message: "Choose a video to start",
        error: null,
        outputs: []
      }
    };
  }

  getState() {
    return this.state;
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this.state);
      } catch (err) {
        console.error("State listener error:", err);
      }
    }
  }

  setStep(stepNumber) {
    if (stepNumber >= 1 && stepNumber <= 4) {
      this.state.currentStep = stepNumber;
      this.notify();
    }
  }

  nextStep() {
    if (this.state.currentStep < 4) {
      this.setStep(this.state.currentStep + 1);
    }
  }

  prevStep() {
    if (this.state.currentStep > 1) {
      this.setStep(this.state.currentStep - 1);
    }
  }

  setPlaybackTime(seconds) {
    this.state.playback.currentTime = seconds;
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    this.state.playback.formattedTime = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
    this.notify();
  }

  async togglePlay() {
    const media = document.querySelector('[data-source-preview]');
    if (!media) return;
    if (media.paused) {
      await media.play();
      this.state.playback.isPlaying = true;
    } else {
      media.pause();
      this.state.playback.isPlaying = false;
    }
    const icon = document.querySelector('[data-preview-action-icon]');
    if (icon) icon.textContent = this.state.playback.isPlaying ? 'pause' : 'play_arrow';
  }

  setAudioChannel(channel) {
    if (channel === 'orig' || channel === 'dub') {
      this.state.playback.audioChannel = channel;
      this.notify();
    }
  }

  updateTuning(key, value) {
    this.state.tuning[key] = value;
    this.notify();
  }

  updateTargetLanguage(code, name) {
    this.state.languages.target = { code, name };
    this.loadVoices();
    this.notify();
  }

  updateSourceLanguage(code, name) {
    this.state.languages.source = { code, name, flag: "", autoDetected: false };
    this.notify();
  }

  updateBackendConfig(field, value) {
    this.state.backend.config[field] = value;
    if (field === 'ttsType') this.loadVoices();
    this.notify();
  }

  async initialize() {
    try {
      const response = await fetch('/api/options');
      if (!response.ok) throw new Error(await response.text());
      this.state.backend.options = await response.json();
      this.state.backend.ready = true;
      const languages = this.state.backend.options.languages;
      if (!languages.some(item => item.code === this.state.languages.source.code) && languages[0]) {
        this.state.languages.source = { ...languages[0], flag: "", autoDetected: false };
      }
      if (!languages.some(item => item.code === this.state.languages.target.code) && languages[0]) {
        this.state.languages.target = { ...languages[0] };
      }
      await this.loadVoices();
    } catch (error) {
      this.state.backend.error = `Backend unavailable: ${error.message}`;
    }
    this.notify();
  }

  chooseMedia() {
    if (['analyzing', 'submitting', 'queued', 'running'].includes(this.state.backend.status)) return;
    document.getElementById('media-input')?.click();
  }

  async selectMedia(file) {
    if (!file) return;
    if (['submitting', 'queued', 'running'].includes(this.state.backend.status)) return;
    const selectionVersion = ++this.mediaSelectionVersion;
    this.selectedFile = file;
    const backend = this.state.backend;
    backend.mediaId = null;
    backend.jobId = null;
    backend.status = 'analyzing';
    backend.message = 'Uploading and inspecting source media…';
    backend.error = null;
    backend.outputs = [];
    this.state.project.verified = false;
    if (this.state.project.previewUrl) URL.revokeObjectURL(this.state.project.previewUrl);
    this.state.project.filename = this.escapeText(file.name);
    this.state.project.fileSize = this.formatBytes(file.size);
    this.state.project.format = file.name.includes('.') ? file.name.split('.').pop().toUpperCase() : 'Media';
    this.state.project.previewUrl = URL.createObjectURL(file);
    this.notify();
    const form = new FormData();
    form.append('file', file);
    try {
      const response = await fetch('/api/media', { method: 'POST', body: form });
      if (!response.ok) throw new Error(await response.text());
      const media = await response.json();
      if (selectionVersion !== this.mediaSelectionVersion) return;
      backend.mediaId = media.id;
      this.state.project.filename = this.escapeText(media.filename);
      this.state.project.fileSize = this.formatBytes(media.sizeBytes);
      this.state.project.durationSec = media.durationMs / 1000;
      this.state.project.duration = this.formatTime(media.durationMs / 1000);
      this.state.project.resolution = media.resolution || 'Audio only';
      this.state.project.fps = media.fps ? `${Number(media.fps).toFixed(2)} fps` : '—';
      this.state.project.videoCodec = media.videoCodec || '—';
      this.state.project.audioCodec = media.audioCodec || '—';
      this.state.project.hasAudio = media.hasAudio;
      this.state.project.hasVideo = media.hasVideo;
      this.state.project.verified = true;
      backend.status = 'ready';
      backend.message = 'Media verified — ready to process';
    } catch (error) {
      if (selectionVersion !== this.mediaSelectionVersion) return;
      backend.status = 'failed';
      backend.error = error.message;
      backend.message = 'Media inspection failed';
    }
    this.notify();
  }

  async loadVoices() {
    const config = this.state.backend.config;
    try {
      const query = new URLSearchParams({ ttsType: config.ttsType, language: this.state.languages.target.code });
      const response = await fetch(`/api/voices?${query}`);
      if (!response.ok) return;
      const data = await response.json();
      this.state.backend.options.voiceRoles = data.voices;
      if (!data.voices.includes(config.voiceRole)) config.voiceRole = data.voices.find(v => v !== 'No') || 'No';
      this.notify();
    } catch (_) {
      // Voice discovery is optional; the server applies a safe fallback.
    }
  }

  async startProcessing() {
    const validationError = this.getPrepareValidationError();
    if (validationError || ['analyzing', 'queued', 'running'].includes(this.state.backend.status)) {
      if (validationError) {
        this.state.backend.error = validationError;
        this.state.backend.message = validationError;
        this.notify();
      }
      return;
    }
    const backend = this.state.backend;
    backend.status = 'submitting';
    backend.message = 'Starting processing workflow…';
    backend.error = null;
    backend.outputs = [];
    this.notify();
    const body = {
      mediaId: backend.mediaId,
      options: {
        ...backend.config,
        sourceLanguage: this.state.languages.source.code,
        targetLanguage: this.state.languages.target.code,
        removeNoise: this.state.engines.removeBackgroundNoise,
        speakerDiarization: this.state.engines.speakerDiarization,
        voiceRate: `${Math.round((this.state.tuning.pace - 1) * 100) >= 0 ? '+' : ''}${Math.round((this.state.tuning.pace - 1) * 100)}%`
      }
    };
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      backend.jobId = job.id;
      this.applyJob(job);
      this.pollTimer = window.setInterval(() => this.pollJob(), 750);
    } catch (error) {
      backend.status = 'failed';
      backend.error = error.message;
      backend.message = error.message;
    }
    this.notify();
  }

  async pollJob() {
    if (!this.state.backend.jobId) return;
    try {
      const response = await fetch(`/api/jobs/${this.state.backend.jobId}`);
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      this.applyJob(job);
      if (['succeeded', 'failed', 'cancelled'].includes(job.status)) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
      }
    } catch (error) {
      this.state.backend.status = 'failed';
      this.state.backend.error = error.message;
      window.clearInterval(this.pollTimer);
    }
    this.notify();
  }

  applyJob(job) {
    Object.assign(this.state.backend, {
      status: job.status,
      stage: job.stage,
      progress: job.progress,
      message: job.message,
      error: job.error,
      outputs: job.outputs || []
    });
  }

  getPrepareValidationError() {
    const backend = this.state.backend;
    if (!backend.ready) return 'Backend options are still loading';
    if (!backend.mediaId || !this.state.project.verified) return 'Select a valid video file first';
    if (!this.state.languages.source.code) return 'Select the source language';
    if (!this.state.languages.target.code) return 'Select the target language';
    if (!Number.isInteger(Number(backend.config.recognType))) return 'Select an ASR engine';
    if (!Number.isInteger(Number(backend.config.translateType))) return 'Select a translation engine';
    return null;
  }

  formatBytes(bytes) {
    if (!Number.isFinite(Number(bytes))) return '—';
    const value = Number(bytes);
    if (value < 1024) return `${value} B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
    if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
    return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }

  async cancelProcessing() {
    const id = this.state.backend.jobId;
    if (!id) return;
    await fetch(`/api/jobs/${id}/cancel`, { method: 'POST' });
    this.state.backend.message = 'Cancellation requested…';
    this.notify();
  }

  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.floor((seconds % 1) * 1000);
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}.${String(ms).padStart(3, '0')}`;
  }

  escapeText(value) {
    return String(value).replace(/[&<>"']/g, char => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    })[char]);
  }

  updateSegment(id, field, value) {
    const seg = this.state.segments.find(s => s.id === id);
    if (seg) {
      seg[field] = value;
      this.notify();
    }
  }

  resolveOcrDiff(segmentId, useOcrText) {
    const seg = this.state.segments.find(s => s.id === segmentId);
    if (seg && seg.hasOcrDiff) {
      if (useOcrText && seg.ocrSlideText) {
        seg.sourceText = seg.ocrSlideText;
      }
      seg.ocrResolved = true;
      this.notify();
    }
  }

  updateSubtitleStyle(field, value) {
    this.state.subtitleStyles[field] = value;
    this.notify();
  }
}

export const store = new WorkflowStore();
window.dubDubStore = store;
