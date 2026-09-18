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
        currentTime: 0,
        formattedTime: "00:00.000",
        isPlaying: false,
        playbackSpeed: 1.0,
        audioChannel: "dub" // 'orig' or 'dub'
      },
      languages: {
        source: { code: "zh-cn", name: "Simplified Chinese", flag: "", autoDetected: false },
        target: { code: "vi", name: "Vietnamese" },
        timingMode: "voice"
      },
      engines: {
        speakerDiarization: false,
        speakerCount: 0,
        removeNoise: false,
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
        options: { languages: [], asrProviders: [], translationProviders: [], translationModes: [], voices: [] },
        config: { recognType: 1, translateType: 0, translationMode: "srt", ttsType: 2, modelName: "nova-3", voiceRole: "", useCuda: false },
        asrSettingsProviderId: null,
        asrSettingsSaving: false,
        asrSettingsError: null,
        asrTesting: false,
        asrTestProviderId: null,
        asrTestMessage: null,
        asrTestOk: null,
        translationSettingsProviderId: null,
        translationSettingsSaving: false,
        translationSettingsError: null,
        translationTesting: false,
        translationTestProviderId: null,
        translationTestMessage: null,
        translationTestOk: null,
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

  syncPreviewPlayback(media) {
    const seconds = Number.isFinite(media.currentTime) ? media.currentTime : 0;
    this.state.playback.currentTime = seconds;
    this.state.playback.formattedTime = this.formatTime(seconds);
    this.state.playback.isPlaying = !media.paused;
    const timeline = document.querySelector('[data-preview-timeline]');
    if (timeline) timeline.value = String(seconds);
    document.querySelectorAll('[data-preview-current]').forEach(node => {
      node.textContent = this.state.playback.formattedTime;
    });
    const icon = document.querySelector('[data-preview-action-icon]');
    if (icon) icon.textContent = media.paused ? 'play_arrow' : 'pause';
  }

  seekPreview(seconds) {
    const media = document.querySelector('[data-source-preview]');
    if (!media) return;
    const duration = Number.isFinite(media.duration) ? media.duration : this.state.project.durationSec;
    media.currentTime = Math.min(Math.max(Number(seconds) || 0, 0), duration || 0);
    this.syncPreviewPlayback(media);
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

  updateEngineConfig(key, value) {
    this.state.engines[key] = value;
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

  updateTimingMode(mode) {
    if (['voice', 'video', 'align'].includes(mode)) {
      this.state.languages.timingMode = mode;
      this.notify();
    }
  }

  updateBackendConfig(field, value) {
    if (field === 'recognType') {
      const provider = this.state.backend.options.asrProviders.find(item => item.recognType === Number(value));
      if (!provider) return;
      this.state.backend.config.recognType = provider.recognType;
      this.state.backend.config.modelName = provider.models[0] || '';
      this.state.backend.asrTestMessage = null;
      this.notify();
      return;
    }
    if (field === 'translateType') {
      const provider = this.state.backend.options.translationProviders.find(item => item.translateType === Number(value));
      if (!provider) return;
      this.state.backend.config.translateType = provider.translateType;
      this.state.backend.translationTestMessage = null;
      this.notify();
      return;
    }
    this.state.backend.config[field] = value;
    if (field === 'ttsType') this.loadVoices();
    this.notify();
  }

  async initialize() {
    try {
      const response = await fetch('/api/options');
      if (!response.ok) throw new Error(await response.text());
      this.state.backend.options = await response.json();
      const defaults = this.state.backend.options.defaults || {};
      const defaultProvider = this.state.backend.options.asrProviders.find(item => item.recognType === defaults.recognType)
        || this.state.backend.options.asrProviders[0];
      if (defaultProvider) {
        this.state.backend.config.recognType = defaultProvider.recognType;
        this.state.backend.config.modelName = defaultProvider.models.includes(defaults.modelName)
          ? defaults.modelName
          : (defaultProvider.models[0] || '');
      }
      if (defaults.sourceLanguage) {
        const source = this.state.backend.options.languages.find(item => item.code === defaults.sourceLanguage);
        if (source) this.state.languages.source = { ...source, flag: "", autoDetected: false };
      }
      if (defaults.targetLanguage) {
        const target = this.state.backend.options.languages.find(item => item.code === defaults.targetLanguage);
        if (target) this.state.languages.target = { ...target };
      }
      if (['voice', 'video', 'align'].includes(defaults.timingMode)) {
        this.state.languages.timingMode = defaults.timingMode;
      }
      const defaultTranslation = this.state.backend.options.translationProviders.find(
        item => item.translateType === defaults.translateType
      ) || this.state.backend.options.translationProviders[0];
      if (defaultTranslation) this.state.backend.config.translateType = defaultTranslation.translateType;
      if (this.state.backend.options.translationModes.some(item => item.id === defaults.translationMode)) {
        this.state.backend.config.translationMode = defaults.translationMode;
      }
      if (this.state.backend.options.voices.some(([value]) => value === defaults.ttsType)) {
        this.state.backend.config.ttsType = defaults.ttsType;
      }
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
    this.state.playback.currentTime = 0;
    this.state.playback.formattedTime = '00:00.000';
    this.state.playback.isPlaying = false;
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
      this.state.project.format = media.container || this.state.project.format;
      this.state.project.bitrate = media.bitrate ? `${(Number(media.bitrate) / 1_000_000).toFixed(2)} Mbps` : 'Not reported';
      this.state.project.audioCodec = media.audioCodec
        ? [media.audioCodec, media.audioSampleRate ? `${Math.round(media.audioSampleRate / 1000)}kHz` : '', media.audioChannels ? `${media.audioChannels}ch` : ''].filter(Boolean).join(' · ')
        : '—';
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

  openAsrSettings(providerId) {
    const provider = this.state.backend.options.asrProviders.find(item => item.id === providerId);
    if (!provider?.requiresSettings) return;
    this.state.backend.asrSettingsProviderId = providerId;
    this.state.backend.asrSettingsError = null;
    this.state.backend.asrTestMessage = null;
    this.notify();
  }

  closeAsrSettings() {
    if (this.state.backend.asrSettingsSaving || this.state.backend.asrTesting) return;
    this.state.backend.asrSettingsProviderId = null;
    this.state.backend.asrSettingsError = null;
    this.state.backend.asrTestMessage = null;
    this.notify();
  }

  getAsrSettingsPayload(provider, useForm) {
    const payload = {
      model: provider.recognType === Number(this.state.backend.config.recognType)
        ? this.state.backend.config.modelName
        : (provider.models[0] || '')
    };
    if (provider.requiresSettings && useForm) {
      payload.apiKey = document.getElementById('asr-api-key')?.value.trim() || '';
    }
    return payload;
  }

  async saveAsrSettings() {
    const backend = this.state.backend;
    const provider = backend.options.asrProviders.find(item => item.id === backend.asrSettingsProviderId);
    const apiKey = document.getElementById('asr-api-key')?.value.trim() || '';
    if (!provider || (!apiKey && !provider.configured)) {
      backend.asrSettingsError = 'Enter an API key before saving.';
      this.notify();
      return;
    }
    backend.asrSettingsSaving = true;
    backend.asrSettingsError = null;
    this.notify();
    try {
      const response = await fetch(`/api/asr-settings/${encodeURIComponent(provider.id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey })
      });
      if (!response.ok) throw new Error(await response.text());
      provider.configured = true;
      backend.asrSettingsProviderId = null;
      backend.message = `${provider.label} API settings saved`;
    } catch (error) {
      backend.asrSettingsError = error.message;
    } finally {
      backend.asrSettingsSaving = false;
      this.notify();
    }
  }

  async testAsrConnection(providerId = null, useForm = false) {
    const backend = this.state.backend;
    const id = providerId || backend.asrSettingsProviderId;
    const provider = backend.options.asrProviders.find(item => item.id === id);
    if (!provider?.testable || backend.asrTesting) return;
    const payload = this.getAsrSettingsPayload(provider, useForm);
    backend.asrTesting = true;
    backend.asrSettingsError = null;
    backend.asrTestProviderId = provider.id;
    backend.asrTestMessage = 'Testing connection and model…';
    backend.asrTestOk = null;
    this.notify();
    try {
      const response = await fetch(`/api/asr-settings/${encodeURIComponent(provider.id)}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      if (provider.requiresSettings) provider.configured = true;
      backend.asrTestMessage = `${result.message} — ${result.model}: ${result.result}`;
      backend.asrTestOk = true;
    } catch (error) {
      backend.asrSettingsError = error.message;
      backend.asrTestMessage = error.message;
      backend.asrTestOk = false;
    } finally {
      backend.asrTesting = false;
      this.notify();
    }
  }

  openTranslationSettings(providerId) {
    const provider = this.state.backend.options.translationProviders.find(item => item.id === providerId);
    if (!provider?.requiresSettings) return;
    const backend = this.state.backend;
    backend.translationSettingsProviderId = providerId;
    backend.translationSettingsError = null;
    backend.translationTestMessage = null;
    this.notify();
  }

  closeTranslationSettings() {
    const backend = this.state.backend;
    if (backend.translationSettingsSaving || backend.translationTesting) return;
    backend.translationSettingsProviderId = null;
    backend.translationSettingsError = null;
    backend.translationTestMessage = null;
    this.notify();
  }

  getTranslationSettingsPayload(provider, useForm) {
    const payload = { translationMode: this.state.backend.config.translationMode };
    if (!provider?.requiresSettings) return payload;
    if (!useForm) return { ...payload, baseUrl: provider.baseUrl, model: provider.model };
    return {
      ...payload,
      baseUrl: document.getElementById('translation-base-url')?.value.trim() || '',
      apiKey: document.getElementById('translation-api-key')?.value.trim() || '',
      model: document.getElementById('translation-model')?.value.trim() || ''
    };
  }

  async saveTranslationSettings() {
    const backend = this.state.backend;
    const provider = backend.options.translationProviders.find(item => item.id === backend.translationSettingsProviderId);
    if (!provider) return;
    const payload = this.getTranslationSettingsPayload(provider, true);
    backend.translationSettingsSaving = true;
    backend.translationSettingsError = null;
    this.notify();
    try {
      const response = await fetch(`/api/translation-settings/${encodeURIComponent(provider.id)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(await response.text());
      Object.assign(provider, await response.json());
      backend.translationSettingsProviderId = null;
      backend.message = `${provider.label} settings saved`;
    } catch (error) {
      backend.translationSettingsError = error.message;
    } finally {
      backend.translationSettingsSaving = false;
      this.notify();
    }
  }

  async testTranslationConnection(providerId = null, useForm = false) {
    const backend = this.state.backend;
    const id = providerId || backend.translationSettingsProviderId;
    const provider = backend.options.translationProviders.find(item => item.id === id);
    if (!provider || backend.translationTesting) return;
    const payload = this.getTranslationSettingsPayload(provider, useForm);
    backend.translationTesting = true;
    backend.translationSettingsError = null;
    backend.translationTestProviderId = provider.id;
    backend.translationTestMessage = 'Testing connection…';
    backend.translationTestOk = null;
    this.notify();
    try {
      const response = await fetch(`/api/translation-settings/${encodeURIComponent(provider.id)}/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      provider.configured = true;
      if (provider.requiresSettings) {
        provider.baseUrl = payload.baseUrl;
        provider.model = payload.model;
      }
      backend.translationTestMessage = `${result.message}: ${result.result}`;
      backend.translationTestOk = true;
    } catch (error) {
      backend.translationSettingsError = error.message;
      backend.translationTestMessage = error.message;
      backend.translationTestOk = false;
    } finally {
      backend.translationTesting = false;
      this.notify();
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
        timingMode: this.state.languages.timingMode,
        removeNoise: this.state.engines.removeNoise,
        speakerDiarization: this.state.engines.speakerDiarization,
        speakerCount: this.state.engines.speakerCount,
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
    const provider = backend.options.asrProviders.find(item => item.recognType === Number(backend.config.recognType));
    if (!provider) return 'Select a supported ASR engine';
    if (!provider.models.includes(backend.config.modelName)) return `Select a ${provider.label} model`;
    if (provider.requiresSettings && !provider.configured) return `Configure ${provider.label} API settings first`;
    if (!Number.isInteger(Number(backend.config.translateType))) return 'Select a translation engine';
    const translationProvider = backend.options.translationProviders.find(
      item => item.translateType === Number(backend.config.translateType)
    );
    if (!translationProvider) return 'Select a supported translation engine';
    if (translationProvider.requiresSettings && !translationProvider.configured) {
      return `Configure ${translationProvider.label} settings first`;
    }
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
