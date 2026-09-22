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
    this.translationPollTimer = null;
    this.translationJobId = null;
    this.activeEditor = null;
    this.state = {
      currentStep: 1, // 1: Prepare, 2: Review Transcript, 3: Voice & Dubbing, 4: Edit Video
      maxUnlockedStep: 4,
      activeSegmentId: 1,
      translationModal: {
        active: false,
        status: "idle",
        progress: 0,
        message: "Translating transcript...",
        error: null,
      },
      translationError: null,
      ocrCrop: {
        active: false,
        segmentId: null,
        roi: [0.05, 0.75, 0.9, 0.2],
        loading: false,
        error: null
      },
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
      speakerVoiceMap: {},
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
        preset: "clean",
        fontFamily: "Arial",
        fontSize: 22,
        color: "#FFFFFF",
        outlineColor: "#000000",
        outlineWidth: 2,
        shadowColor: "rgba(0,0,0,.75)",
        shadowSize: 2,
        aiLipSync: true,
        deReverb: true,
        faceRetouch: false,
        superRes4K: true,
        activeTab: "text" // 'text' or 'bgm'
      },
      editVideo: {
        audioMix: { original: 0, dubbed: 100, background: 35 },
        backgroundAudio: null,
        thumbnail: null,
        exporting: false,
        error: null,
        activeTab: "audio"
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
        outputs: [],
        asrDuration: null,
        startTime: null,
        elapsedSeconds: 0
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

  notify(scope = 'full') {
    for (const listener of this.listeners) {
      try {
        listener(this.state, scope);
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
    if (this.state.currentStep === 2) {
      this.proceedToVoiceDubbing();
      return;
    }
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
    const sec = Math.max(0, Number(seconds) || 0);
    this.state.playback.currentTime = sec;
    this.state.playback.formattedTime = this.formatTime(sec);
    const curSeg = this.state.segments.find(s => s.startSec <= sec && sec <= s.endSec);
    if (curSeg) {
      this.state.activeSegmentId = curSeg.id;
    }
    this.notify();
  }

  async togglePlay() {
    const media = document.querySelector('[data-source-preview]');
    if (!media) return;
    if (media.paused) {
      try {
        await media.play();
        this.state.playback.isPlaying = true;
      } catch (err) {
        console.warn('Play was prevented:', err);
      }
    } else {
      media.pause();
      this.state.playback.isPlaying = false;
    }
    const icon = document.querySelector('[data-preview-action-icon]');
    if (icon) icon.textContent = this.state.playback.isPlaying ? 'pause' : 'play_arrow';
    this.notify();
  }

  seekAndPlay(seconds, segmentId = null) {
    const sec = Math.max(0, Number(seconds) || 0);
    this.state.playback.currentTime = sec;
    this.state.playback.formattedTime = this.formatTime(sec);
    if (segmentId != null) {
      this.state.activeSegmentId = segmentId;
    }
    const media = document.querySelector('[data-source-preview]');
    if (media) {
      media.currentTime = sec;
      const playPromise = media.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          this.state.playback.isPlaying = true;
          this.syncPreviewPlayback(media);
        }).catch(err => {
          console.warn('Playback error / autoplay prevented:', err);
        });
      }
    }
    this.notify();
  }

  syncPreviewPlayback(media) {
    const seconds = Number.isFinite(media.currentTime) ? media.currentTime : 0;
    this.state.playback.currentTime = seconds;
    this.state.playback.formattedTime = this.formatTime(seconds);
    this.state.playback.isPlaying = !media.paused;
    const currentActive = this.state.segments.find(s => s.startSec <= seconds && seconds <= s.endSec);
    if (currentActive && this.state.activeSegmentId !== currentActive.id) {
      this.state.activeSegmentId = currentActive.id;
      document.querySelectorAll('[data-segment-card]').forEach(card => {
        const id = card.getAttribute('data-segment-card');
        const isActive = String(id) === String(currentActive.id);
        if (isActive) {
          card.classList.add('border-2', 'border-[#8D4B00]', 'bg-amber-50/50', 'shadow-xs');
          card.classList.remove('border-stone-200', 'bg-white');
        } else {
          card.classList.remove('border-2', 'border-[#8D4B00]', 'bg-amber-50/50', 'shadow-xs');
          card.classList.add('border-stone-200', 'bg-white');
        }
      });
    }

    const canvasSub = document.querySelector('[data-canvas-subtitle]');
    const canvasBadge = document.querySelector('[data-canvas-speaker-badge]');
    if (canvasSub) {
      canvasSub.textContent = currentActive
        ? (currentActive.targetText || currentActive.sourceText || currentActive.text || '')
        : '';
    }
    if (canvasBadge) {
      if (currentActive) {
        canvasBadge.textContent = currentActive.speakerName || currentActive.speakerLabel || currentActive.speaker || 'Speaker 1';
        canvasBadge.style.display = 'inline-flex';
      } else {
        canvasBadge.textContent = '';
        canvasBadge.style.display = 'none';
      }
    }

    const timeline = document.querySelector('[data-preview-timeline]');
    if (timeline) timeline.value = String(seconds);
    document.querySelectorAll('[data-preview-current]').forEach(node => {
      node.textContent = this.state.playback.formattedTime;
    });
    document.querySelectorAll('[data-playhead-timecode]').forEach(node => {
      node.textContent = this.state.playback.formattedTime;
    });
    const duration = this.state.project.durationSec || (media.duration || 1);
    const percent = Math.min(100, Math.max(0, (seconds / duration) * 100));
    const scrubberMarker = document.querySelector('[data-scrubber-marker]');
    const scrubberProgress = document.querySelector('[data-scrubber-progress]');
    if (scrubberMarker) scrubberMarker.style.left = `${percent}%`;
    if (scrubberProgress) scrubberProgress.style.width = `${percent}%`;
    const timelinePlayhead = document.querySelector('[data-timeline-playhead]');
    if (timelinePlayhead) timelinePlayhead.style.left = `${percent}%`;
    const icon = document.querySelector('[data-preview-action-icon]');
    if (icon) icon.textContent = media.paused ? 'play_arrow' : 'pause';

    // Synchronize Stage 4 Audio Mixing and Background Music
    if (this.state.currentStep === 4 && this.state.editVideo?.audioMix) {
      const origVol = Number(this.state.editVideo.audioMix.original) || 0;
      media.volume = Math.max(0, Math.min(1, origVol / 100));
      media.muted = (origVol === 0);

      const bgm = document.getElementById('stage4-bgm-preview');
      if (bgm && bgm.src && !bgm.src.endsWith('#') && bgm.src !== window.location.href) {
        const bgmVol = Number(this.state.editVideo.audioMix.background) || 0;
        bgm.volume = Math.max(0, Math.min(1, bgmVol / 100));
        bgm.muted = (bgmVol === 0);
        if (media.paused && !bgm.paused) {
          bgm.pause();
        } else if (!media.paused && bgm.paused) {
          bgm.play().catch(() => {});
        }
        const expectedTime = bgm.duration ? (seconds % bgm.duration) : seconds;
        if (Math.abs(bgm.currentTime - expectedTime) > 0.35) {
          bgm.currentTime = expectedTime;
        }
      }
    }
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

      if (!this.state.speakerVoiceMap) this.state.speakerVoiceMap = {};
      const defaultVoice = config.voiceRole || (data.voices && data.voices.length > 0 ? data.voices[0] : 'default');
      const distinctSpeakers = this.getDistinctSpeakers();
      distinctSpeakers.forEach(spk => {
        if (!this.state.speakerVoiceMap[spk.speakerId] || !data.voices.includes(this.state.speakerVoiceMap[spk.speakerId])) {
          this.state.speakerVoiceMap[spk.speakerId] = defaultVoice;
        }
      });

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

  async startDub() {
    const validationError = this.getPrepareValidationError();
    if (validationError || ['analyzing', 'submitting', 'queued', 'running'].includes(this.state.backend.status)) {
      if (validationError) {
        this.state.backend.error = validationError;
        this.state.backend.message = validationError;
        this.notify();
      }
      return;
    }
    const backend = this.state.backend;
    backend.status = 'submitting';
    backend.message = 'Initiating speech recognition & diarization…';
    backend.error = null;
    backend.outputs = [];
    backend.asrDuration = null;
    backend.startTime = Date.now();
    backend.elapsedSeconds = 0;
    this.notify();
    const body = {
      mediaId: backend.mediaId,
      jobType: 'asr',
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
      if (job.status === 'succeeded') {
        if (Array.isArray(job.segments)) {
          this.setSegments(job.segments);
        }
        if (this.state.currentStep === 1) {
          this.setStep(2);
        }
      } else {
        if (this.pollTimer) window.clearInterval(this.pollTimer);
        this.pollTimer = window.setInterval(() => this.pollJob(), 500);
      }
    } catch (error) {
      backend.status = 'failed';
      backend.error = error.message;
      backend.message = error.message;
    }
    this.notify();
  }

  async startProcessing() {
    return this.startDub();
  }

  async pollJob() {
    if (!this.state.backend.jobId) return;
    try {
      if (this.state.backend.startTime) {
        this.state.backend.elapsedSeconds = Math.round((Date.now() - this.state.backend.startTime) / 1000);
      }
      const response = await fetch(`/api/jobs/${this.state.backend.jobId}`);
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      this.applyJob(job);
      const terminal = ['succeeded', 'failed', 'cancelled'].includes(job.status) || Boolean(job.error);
      if (job.status === 'succeeded' && !job.error) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
        if (Array.isArray(job.segments)) {
          this.setSegments(job.segments);
        }
        if (this.state.currentStep === 1) {
          this.setStep(2);
        }
      } else if (terminal) {
        window.clearInterval(this.pollTimer);
        this.pollTimer = null;
        if (job.error && !['failed', 'cancelled'].includes(this.state.backend.status)) {
          this.state.backend.status = 'failed';
        }
      } else {
        // Do not remount the entire app while polling. Replacing root.innerHTML
        // recreates the <video> element and resets playback every 500 ms.
        this.notify('status');
        return;
      }
      // Progress polling must not remount the whole application. A full render
      // replaces the <video> element and resets playback on every poll.
      this.notify(terminal ? 'full' : 'status');
      return;
    } catch (error) {
      this.state.backend.status = 'failed';
      this.state.backend.error = error.message;
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
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
      outputs: job.outputs || [],
      asrDuration: job.asrDuration ?? this.state.backend.asrDuration
    });
    if (job.segments && job.segments.length > 0) {
      this.state.segments = job.segments;
    }
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
    if (this.pollTimer) {
      window.clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
    this.state.backend.status = 'cancelled';
    this.state.backend.message = 'Processing cancelled';
    try {
      await fetch(`/api/jobs/${id}/cancel`, { method: 'POST' });
    } catch (e) {
      // Ignore network error on cancel
    }
    this.notify();
  }

  syncSpeakerVoices() {
    if (!this.state.speakerVoiceMap) {
      this.state.speakerVoiceMap = {};
    }
    const defaultVoice = (this.state.backend?.config?.voiceRole && this.state.backend.config.voiceRole !== 'No' ? this.state.backend.config.voiceRole : null) ||
      (this.state.backend?.options?.voiceRoles && this.state.backend.options.voiceRoles.find(v => v !== 'No')) ||
      (this.state.backend?.options?.voiceRoles && this.state.backend.options.voiceRoles[0]) ||
      'default';
    const distinctSpeakers = this.getDistinctSpeakers();
    distinctSpeakers.forEach(spk => {
      if (!this.state.speakerVoiceMap[spk.speakerId]) {
        this.state.speakerVoiceMap[spk.speakerId] = defaultVoice;
      }
    });
  }

  async proceedToVoiceDubbing() {
    if (this.state.translationModal && this.state.translationModal.active) {
      return;
    }

    this.state.translationError = null;

    const src = (this.state.languages?.source?.code || '').toLowerCase().trim();
    const tgt = (this.state.languages?.target?.code || '').toLowerCase().trim();
    const sameLanguage = Boolean(src && tgt && src === tgt);

    const segments = this.state.segments || [];
    const allSegmentsHaveTarget = segments.length > 0 && segments.every(
      s => typeof s.targetText === 'string' && s.targetText.trim().length > 0
    );

    if (sameLanguage || allSegmentsHaveTarget) {
      if (sameLanguage) {
        this.state.segments = segments.map(seg => {
          const targetText = (seg.targetText && seg.targetText.trim().length > 0)
            ? seg.targetText
            : (seg.sourceText !== undefined && seg.sourceText !== null ? seg.sourceText : (seg.text || ''));
          const dur = Math.max(0.1, (seg.endSec || 0) - (seg.startSec || 0));
          const cps = Number((String(targetText).trim().length / dur).toFixed(1));
          return {
            ...seg,
            targetText,
            targetCps: cps,
            cps,
            cpsStatus: cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Fast',
          };
        });
      }
      this.syncSpeakerVoices();
      this.setStep(3);
      return;
    }

    if (segments.length === 0) {
      this.syncSpeakerVoices();
      this.setStep(3);
      return;
    }

    this.state.translationModal = {
      active: true,
      status: 'starting',
      progress: 0,
      message: 'Initiating LLM translation...',
      error: null,
    };
    this.notify();

    const payload = {
      mediaId: this.state.backend.mediaId,
      jobType: 'translation',
      options: {
        ...this.state.backend.config,
        sourceLanguage: this.state.languages.source.code,
        targetLanguage: this.state.languages.target.code,
        translateType: Number(this.state.backend.config.translateType) || 0,
        translationMode: this.state.backend.config.translationMode || 'srt',
        segments: segments.map(seg => ({
          id: seg.id,
          startSec: seg.startSec,
          endSec: seg.endSec,
          startTime: seg.startTime,
          endTime: seg.endTime,
          sourceText: seg.sourceText !== undefined && seg.sourceText !== null ? seg.sourceText : (seg.text || ''),
          text: seg.sourceText !== undefined && seg.sourceText !== null ? seg.sourceText : (seg.text || ''),
          speakerId: seg.speakerId,
          speakerName: seg.speakerName,
          speakerCode: seg.speakerCode,
          speakerColor: seg.speakerColor,
          voiceOverride: seg.voiceOverride,
          targetText: seg.targetText || '',
        })),
      },
    };

    try {
      const response = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errText = await response.text();
        throw new Error(errText || 'Failed to start translation job');
      }

      const job = await response.json();
      this.translationJobId = job.id;
      this.state.translationModal.status = job.status || 'running';
      this.state.translationModal.message = job.message || 'Translating transcript...';
      this.state.translationModal.progress = typeof job.progress === 'number' ? job.progress : 0;
      this.notify();

      if (job.status === 'succeeded') {
        const transSegs = (job.result && job.result.segments) || job.segments || [];
        this.completeTranslation(transSegs);
        return;
      }

      if (job.status === 'failed') {
        this.handleTranslationError(job.error || job.message || 'Translation failed');
        return;
      }

      if (this.translationPollTimer) {
        clearInterval(this.translationPollTimer);
      }
      this.translationPollTimer = setInterval(() => this.pollTranslationJob(job.id), 500);
    } catch (err) {
      this.handleTranslationError(err.message || String(err));
    }
  }

  async pollTranslationJob(jobId) {
    if (!this.state.translationModal.active || this.translationJobId !== jobId) {
      if (this.translationPollTimer) {
        clearInterval(this.translationPollTimer);
        this.translationPollTimer = null;
      }
      return;
    }

    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      if (this.translationJobId !== jobId) return;

      this.state.translationModal.status = job.status;
      this.state.translationModal.message = job.message || 'Translating transcript...';
      if (typeof job.progress === 'number') {
        this.state.translationModal.progress = job.progress;
      }

      if (job.status === 'succeeded') {
        if (this.translationPollTimer) {
          clearInterval(this.translationPollTimer);
          this.translationPollTimer = null;
        }
        const transSegs = (job.result && job.result.segments) || job.segments || [];
        this.completeTranslation(transSegs);
      } else if (job.status === 'failed' || job.status === 'cancelled') {
        if (this.translationPollTimer) {
          clearInterval(this.translationPollTimer);
          this.translationPollTimer = null;
        }
        if (job.status === 'cancelled') {
          this.state.translationModal.active = false;
          this.state.translationModal.status = 'cancelled';
          this.notify();
        } else {
          this.handleTranslationError(job.error || job.message || 'Translation failed');
        }
      } else {
        this.notify();
      }
    } catch (err) {
      console.warn('Translation poll error:', err);
    }
  }

  async cancelTranslation() {
    const jobId = this.translationJobId;
    if (this.translationPollTimer) {
      clearInterval(this.translationPollTimer);
      this.translationPollTimer = null;
    }
    this.translationJobId = null;
    this.state.translationModal.active = false;
    this.state.translationModal.status = 'cancelled';
    this.notify();

    if (jobId) {
      try {
        await fetch(`/api/jobs/${jobId}/cancel`, { method: 'POST' });
      } catch (_) {}
    }
  }

  completeTranslation(translatedSegments) {
    if (this.translationPollTimer) {
      clearInterval(this.translationPollTimer);
      this.translationPollTimer = null;
    }
    this.translationJobId = null;

    if (Array.isArray(translatedSegments) && translatedSegments.length > 0) {
      this.state.segments = (this.state.segments || []).map((seg, index) => {
        const match = translatedSegments.find(ts => String(ts.id) === String(seg.id)) || translatedSegments[index];
        const newTargetText = match
          ? (match.targetText !== undefined && match.targetText !== null ? match.targetText : (match.text !== undefined && match.text !== null ? match.text : seg.targetText))
          : (seg.targetText || '');
        const dur = Math.max(0.1, (seg.endSec || 0) - (seg.startSec || 0));
        const cps = Number((String(newTargetText).trim().length / dur).toFixed(1));
        const cpsStatus = cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Fast';
        return {
          ...seg,
          targetText: newTargetText,
          targetCps: cps,
          cps,
          cpsStatus,
        };
      });
    }

    this.state.translationModal.active = false;
    this.state.translationModal.status = 'succeeded';
    this.syncSpeakerVoices();
    this.setStep(3);
  }

  handleTranslationError(errorMessage) {
    if (this.translationPollTimer) {
      clearInterval(this.translationPollTimer);
      this.translationPollTimer = null;
    }
    this.translationJobId = null;
    this.state.translationModal.active = false;
    this.state.translationModal.status = 'failed';
    this.state.translationError = errorMessage || 'Translation failed';
    this.notify();
  }

  dismissTranslationError() {
    this.state.translationError = null;
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
    const seg = this.state.segments.find(s => String(s.id) === String(id));
    if (seg) {
      seg[field] = value;
      this.notify();
    }
  }

  updateSegmentText(id, text, forceNotify = false) {
    const seg = this.state.segments.find(s => String(s.id) === String(id));
    if (seg) {
      seg.sourceText = text;
      seg.text = text;
      const dur = Math.max(0.1, (seg.endSec || 0) - (seg.startSec || 0));
      const cps = Number((text.trim().length / dur).toFixed(1));
      seg.cps = cps;
      seg.cpsStatus = cps <= 14.5 ? 'Optimal' : cps <= 18.0 ? 'Good' : 'Fast';

      // Update the CPS badge in DOM directly
      const card = document.querySelector(`[data-segment-card="${id}"]`);
      if (card) {
        const cpsNode = card.querySelector('[data-cps-badge]');
        if (cpsNode) {
          cpsNode.textContent = `${cps} CPS • ${seg.cpsStatus}`;
          cpsNode.className = `px-1.5 py-0.2 rounded ${cps <= 14.5 ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : cps <= 18.0 ? 'bg-amber-50 text-[#8D4B00] border-amber-200' : 'bg-red-50 text-red-700 border-red-200'} border text-[9px] font-bold font-mono`;
        }
      }

      // If user is actively typing in this textarea, avoid full DOM teardown to preserve smooth typing and IME
      const activeEl = typeof document !== 'undefined' ? document.activeElement : null;
      const isActivelyTyping = activeEl && activeEl.getAttribute('data-segment-input') === String(id);
      if (!isActivelyTyping || forceNotify) {
        this.notify();
      }
    }
  }

  getDistinctSpeakers() {
    const segments = this.state.segments || [];
    const colorPalette = ['amber', 'secondary', 'emerald', 'rose', 'purple'];
    const speakerMap = new Map();

    segments.forEach((seg, index) => {
      const spkId = seg.speakerId || seg.speakerLabel || seg.speaker || (seg.speakerName ? String(seg.speakerName).toLowerCase().replace(/\s+/g, '_') : `spk_${index + 1}`);
      if (!speakerMap.has(spkId)) {
        const fallbackIndex = speakerMap.size;
        const metaSpeaker = (this.state.speakers || []).find(s => s.id === spkId) || {};
        speakerMap.set(spkId, {
          speakerId: spkId,
          speakerName: seg.speakerName || metaSpeaker.name || (seg.speakerLabel ? `Speaker ${seg.speakerLabel}` : `Speaker ${fallbackIndex + 1}`),
          speakerCode: seg.speakerCode || metaSpeaker.code || `S${fallbackIndex + 1}`,
          speakerColor: seg.speakerColor || metaSpeaker.color || colorPalette[fallbackIndex % colorPalette.length],
        });
      }
    });

    if (speakerMap.size === 0) {
      return [{
        speakerId: 'spk_1',
        speakerName: 'Speaker 1',
        speakerCode: 'S1',
        speakerColor: 'amber'
      }];
    }

    return Array.from(speakerMap.values());
  }

  updateSpeakerVoice(speakerId, voice) {
    if (!this.state.speakerVoiceMap) {
      this.state.speakerVoiceMap = {};
    }
    this.state.speakerVoiceMap[speakerId] = voice;
    this.notify();
  }

  setSegmentVoiceOverride(segmentId, voice) {
    const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
    if (seg) {
      seg.voiceOverride = voice;
      this.notify();
    }
  }

  clearSegmentVoiceOverride(segmentId) {
    const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
    if (seg) {
      delete seg.voiceOverride;
      this.notify();
    }
  }

  updateSegmentTargetText(segmentId, targetText, forceNotify = false) {
    const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
    if (seg) {
      seg.targetText = targetText;
      const dur = Math.max(0.1, (seg.endSec || 0) - (seg.startSec || 0));
      const cps = Number((targetText.trim().length / dur).toFixed(1));
      seg.targetCps = cps;

      if (String(this.state.activeSegmentId) === String(segmentId)) {
        const canvasSub = typeof document !== 'undefined' ? document.querySelector('[data-canvas-subtitle]') : null;
        if (canvasSub) {
          canvasSub.textContent = targetText || seg.sourceText || '';
        }
      }

      const activeEl = typeof document !== 'undefined' ? document.activeElement : null;
      const inputAttr = activeEl ? activeEl.getAttribute('data-segment-input') : null;
      const isActivelyTyping = inputAttr === `stage3-${segmentId}` || inputAttr === `stage4-${segmentId}` || inputAttr === String(segmentId);
      if (!isActivelyTyping || forceNotify) {
        this.notify();
      }
    }
  }

  getResolvedVoice(segment) {
    if (!segment) return 'default';
    return segment.voiceOverride
      || (this.state.speakerVoiceMap && this.state.speakerVoiceMap[segment.speakerId])
      || (this.state.backend && this.state.backend.options && this.state.backend.options.voiceRoles && this.state.backend.options.voiceRoles[0])
      || 'default';
  }

  setActiveEditor(id, cursorPosition) {
    this.activeEditor = { segmentId: id, cursorPosition: Number(cursorPosition) || 0 };
  }

  clearActiveEditor(segmentId = null) {
    if (segmentId === null || (this.activeEditor && String(this.activeEditor.segmentId) === String(segmentId))) {
      this.activeEditor = null;
    }
  }

  captureEditorBeforeSplit(segmentId) {
    const textarea = document.querySelector(`[data-segment-input="${segmentId}"]`);
    if (textarea && document.activeElement === textarea) {
      this.activeEditor = { segmentId, cursorPosition: textarea.selectionStart };
    }
  }

  splitSegment(segmentId, splitTime = null, cursorPosition = null) {
    const index = this.state.segments.findIndex(s => String(s.id) === String(segmentId));
    if (index === -1) return;
    const seg = this.state.segments[index];

    let t = splitTime;
    if (t === null || t === undefined) {
      const media = document.querySelector('[data-source-preview]');
      const cur = (media && Number.isFinite(media.currentTime)) ? media.currentTime : this.state.playback.currentTime;
      if (cur > seg.startSec && cur < seg.endSec) {
        t = cur;
      } else {
        t = Number(((seg.startSec + seg.endSec) / 2).toFixed(3));
      }
    }
    const minGap = Math.min(0.05, (seg.endSec - seg.startSec) * 0.1);
    t = Math.max(seg.startSec + minGap, Math.min(seg.endSec - minGap, Number(t)));

    let curPos = cursorPosition;
    if (curPos === null && this.activeEditor && String(this.activeEditor.segmentId) === String(segmentId)) {
      curPos = this.activeEditor.cursorPosition;
    }

    const text = (seg.sourceText !== undefined ? seg.sourceText : seg.text) || '';
    let text1, text2;

    if (curPos !== null && curPos !== undefined && curPos >= 0 && curPos <= text.length) {
      text1 = text.substring(0, curPos).trim();
      text2 = text.substring(curPos).trim();
    } else {
      const trimmed = text.trim();
      if (!trimmed) {
        text1 = "";
        text2 = "";
      } else {
        const ratio = (t - seg.startSec) / (seg.endSec - seg.startSec);
        const targetChar = Math.round(trimmed.length * ratio);
        const punctChars = new Set(["，", "。", "！", "？", "、", "；", "：", ",", "!", "?", ";", ":", "."]);
        const candidates = [];
        for (let i = 0; i < trimmed.length; i++) {
          if (i > 0 && i < trimmed.length - 1) {
            if (/\s/.test(trimmed[i])) {
              candidates.push({ idx: i, isSpace: true });
            } else if (punctChars.has(trimmed[i])) {
              candidates.push({ idx: i + 1, isSpace: false });
            }
          }
        }
        if (candidates.length > 0) {
          let best = candidates[0];
          let minDist = Math.abs(best.idx - targetChar);
          for (const cand of candidates) {
            const dist = Math.abs(cand.idx - targetChar);
            if (dist < minDist || (dist === minDist && !cand.isSpace && best.isSpace)) {
              minDist = dist;
              best = cand;
            }
          }
          if (best.isSpace) {
            text1 = trimmed.substring(0, best.idx).trim();
            text2 = trimmed.substring(best.idx + 1).trim();
          } else {
            text1 = trimmed.substring(0, best.idx).trim();
            text2 = trimmed.substring(best.idx).trim();
          }
        } else {
          const splitIdx = Math.max(1, Math.min(targetChar, Math.max(1, trimmed.length - 1)));
          text1 = trimmed.substring(0, splitIdx).trim();
          text2 = trimmed.substring(splitIdx).trim();
        }
      }
    }

    const dur1 = Math.max(0.1, t - seg.startSec);
    const dur2 = Math.max(0.1, seg.endSec - t);
    const cps1 = Number((text1.length / dur1).toFixed(1));
    const cps2 = Number((text2.length / dur2).toFixed(1));

    const maxNum = this.state.segments.reduce((m, s) => {
      const n = typeof s.id === 'number' ? s.id : parseInt(String(s.id).replace(/\D/g, '')) || 0;
      return Math.max(m, n);
    }, 0);
    const newId = (typeof seg.id === 'string' && seg.id.startsWith('seg-')) ? `seg-${maxNum + 1}` : (maxNum + 1);

    const seg1 = {
      ...seg,
      id: seg.id,
      startSec: Number(seg.startSec.toFixed(3)),
      endSec: Number(t.toFixed(3)),
      startTime: seg.startTime || this.formatTime(seg.startSec),
      endTime: this.formatTime(t),
      sourceText: text1,
      text: text1,
      cps: cps1,
      cpsStatus: cps1 <= 14.5 ? 'Optimal' : cps1 <= 18.0 ? 'Good' : 'Fast',
      hasOcrDiff: false,
    };

    const seg2 = {
      ...seg,
      id: newId,
      startSec: Number(t.toFixed(3)),
      endSec: Number(seg.endSec.toFixed(3)),
      startTime: this.formatTime(t),
      endTime: seg.endTime || this.formatTime(seg.endSec),
      sourceText: text2,
      text: text2,
      cps: cps2,
      cpsStatus: cps2 <= 14.5 ? 'Optimal' : cps2 <= 18.0 ? 'Good' : 'Fast',
      hasOcrDiff: false,
    };

    this.state.segments.splice(index, 1, seg1, seg2);
    this.activeEditor = null;
    this.notify();
  }

  splitSegmentCard(segmentId) {
    this.splitSegment(segmentId);
  }

  openOcrCrop(segmentId) {
    const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
    if (!seg) return;
    this.seekPreview(seg.startSec);
    this.state.activeSegmentId = seg.id;
    this.state.ocrCrop = {
      active: true,
      segmentId: seg.id,
      roi: [0.05, 0.75, 0.9, 0.2],
      loading: false,
      error: null,
    };
    this.notify();
  }

  closeOcrCrop() {
    this.state.ocrCrop.active = false;
    this.state.ocrCrop.error = null;
    this.notify();
  }

  updateOcrRoi(roi) {
    if (this.state.ocrCrop) {
      this.state.ocrCrop.roi = roi;
      this.notify();
    }
  }

  async confirmOcrCrop() {
    const crop = this.state.ocrCrop;
    if (!crop || !crop.active) return;
    const seg = this.state.segments.find(s => String(s.id) === String(crop.segmentId));
    if (!seg) return;

    crop.loading = true;
    crop.error = null;
    this.notify();

    try {
      const response = await fetch('/api/ocr/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mediaId: this.state.backend.mediaId,
          startSec: seg.startSec,
          endSec: seg.endSec,
          roi: crop.roi,
          language: this.state.languages.source.code,
        }),
      });

      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      if (data.text) {
        seg.sourceText = data.text;
        seg.text = data.text;
        seg.hasOcrDiff = false;
        seg.ocrResolved = true;
        const dur = Math.max(0.1, (seg.endSec || 0) - (seg.startSec || 0));
        seg.cps = Number((data.text.trim().length / dur).toFixed(1));
        seg.cpsStatus = seg.cps <= 14.5 ? 'Optimal' : seg.cps <= 18.0 ? 'Good' : 'Fast';
        crop.active = false;
        crop.loading = false;
      } else {
        crop.loading = false;
        crop.error = "No text detected in selected ROI region";
      }
    } catch (err) {
      crop.loading = false;
      crop.error = err.message;
    }
    this.notify();
  }

  initRoiDrag(e, handle = 'move') {
    if (!this.state.ocrCrop || !this.state.ocrCrop.active) return;
    e.preventDefault();
    e.stopPropagation();

    const overlay = document.querySelector('[data-crop-overlay]');
    const cropBox = document.querySelector('[data-crop-box]');
    if (!overlay || !cropBox) return;

    const overlayRect = overlay.getBoundingClientRect();
    if (overlayRect.width <= 0 || overlayRect.height <= 0) return;

    const startX = e.clientX;
    const startY = e.clientY;
    const initialRoi = [...this.state.ocrCrop.roi]; // [x, y, w, h]

    const onPointerMove = (moveEv) => {
      const dx = (moveEv.clientX - startX) / overlayRect.width;
      const dy = (moveEv.clientY - startY) / overlayRect.height;
      let [x, y, w, h] = initialRoi;

      if (handle === 'move') {
        x = Math.max(0, Math.min(1 - w, x + dx));
        y = Math.max(0, Math.min(1 - h, y + dy));
      } else if (handle === 'se') {
        w = Math.max(0.05, Math.min(1 - x, w + dx));
        h = Math.max(0.05, Math.min(1 - y, h + dy));
      } else if (handle === 'sw') {
        const newX = Math.max(0, Math.min(x + w - 0.05, x + dx));
        w = w + (x - newX);
        x = newX;
        h = Math.max(0.05, Math.min(1 - y, h + dy));
      } else if (handle === 'ne') {
        const newY = Math.max(0, Math.min(y + h - 0.05, y + dy));
        h = h + (y - newY);
        y = newY;
        w = Math.max(0.05, Math.min(1 - x, w + dx));
      } else if (handle === 'nw') {
        const newX = Math.max(0, Math.min(x + w - 0.05, x + dx));
        const newY = Math.max(0, Math.min(y + h - 0.05, y + dy));
        w = w + (x - newX);
        h = h + (y - newY);
        x = newX;
        y = newY;
      }

      this.state.ocrCrop.roi = [
        Number(x.toFixed(3)),
        Number(y.toFixed(3)),
        Number(w.toFixed(3)),
        Number(h.toFixed(3)),
      ];

      cropBox.style.left = `${(x * 100).toFixed(1)}%`;
      cropBox.style.top = `${(y * 100).toFixed(1)}%`;
      cropBox.style.width = `${(w * 100).toFixed(1)}%`;
      cropBox.style.height = `${(h * 100).toFixed(1)}%`;
    };

    const onPointerUp = () => {
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
      this.notify();
    };

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
  }

  setSegments(segments) {
    if (Array.isArray(segments)) {
      this.state.segments = segments;
      this.notify();
    }
  }

  resolveOcrDiff(segmentId, useOcrText) {
    const seg = this.state.segments.find(s => String(s.id) === String(segmentId));
    if (seg && seg.hasOcrDiff) {
      if (useOcrText && seg.ocrSlideText) {
        seg.sourceText = seg.ocrSlideText;
        seg.text = seg.ocrSlideText;
      }
      seg.ocrResolved = true;
      this.notify();
    }
  }

  updateSubtitleStyle(field, value, notify = true) {
    this.state.subtitleStyles[field] = value;
    if (field === 'fontSize') {
      const sub = typeof document !== 'undefined' ? document.querySelector('[data-canvas-subtitle]') : null;
      if (sub) {
        sub.style.fontSize = `${Number(value) || 22}px`;
      }
    }
    if (notify) {
      this.notify();
    }
  }

  updateAudioMix(source, value, notify = true) {
    if (!(source in this.state.editVideo.audioMix)) return;
    this.state.editVideo.audioMix[source] = Math.max(0, Math.min(150, Number(value) || 0));
    if (notify) this.notify();
  }

  async uploadEditAsset(kind, file) {
    if (!file) return null;
    const form = new FormData();
    form.append('file', file);
    const response = await fetch(`/api/assets/${kind}`, { method: 'POST', body: form });
    if (!response.ok) throw new Error(await response.text());
    return response.json();
  }

  async selectBackgroundAudio(file) {
    if (!file) return;
    const edit = this.state.editVideo;
    const previewUrl = URL.createObjectURL(file);
    edit.error = null;
    edit.backgroundAudio = { name: file.name, previewUrl, uploading: true };
    this.notify();
    try {
      const asset = await this.uploadEditAsset('background-audio', file);
      edit.backgroundAudio = { ...asset, previewUrl };
    } catch (error) {
      URL.revokeObjectURL(previewUrl);
      edit.backgroundAudio = null;
      edit.error = error.message;
    }
    this.notify();
  }

  removeBackgroundAudio() {
    const edit = this.state.editVideo;
    if (edit.backgroundAudio?.previewUrl) {
      URL.revokeObjectURL(edit.backgroundAudio.previewUrl);
    }
    edit.backgroundAudio = null;
    this.notify();
  }

  removeThumbnail() {
    const edit = this.state.editVideo;
    if (edit.thumbnail?.previewUrl) {
      URL.revokeObjectURL(edit.thumbnail.previewUrl);
    }
    edit.thumbnail = null;
    this.notify();
  }

  toggleAudioMute(source) {
    const edit = this.state.editVideo;
    if (!(source in edit.audioMix)) return;
    if (!edit.prevMix) edit.prevMix = {};
    if (edit.audioMix[source] > 0) {
      edit.prevMix[source] = edit.audioMix[source];
      edit.audioMix[source] = 0;
    } else {
      edit.audioMix[source] = edit.prevMix[source] || (source === 'dubbed' ? 100 : source === 'background' ? 35 : 100);
    }
    this.notify();
  }

  setStage4InspectorTab(tab) {
    if (['audio', 'subtitles', 'thumbnail'].includes(tab)) {
      this.state.editVideo.activeTab = tab;
      this.notify();
    }
  }

  async selectThumbnail(file) {
    if (!file) return;
    const edit = this.state.editVideo;
    const previewUrl = URL.createObjectURL(file);
    edit.error = null;
    edit.thumbnail = { name: file.name, previewUrl, uploading: true };
    this.notify();
    try { edit.thumbnail = { ...(await this.uploadEditAsset('thumbnail', file)), previewUrl }; }
    catch (error) { URL.revokeObjectURL(previewUrl); edit.thumbnail = null; edit.error = error.message; }
    this.notify();
  }

  updateStage4Subtitle(segmentId, text, forceNotify = false) {
    this.updateSegmentTargetText(segmentId, text, forceNotify);
  }

  updateStage4Timing(segmentId, field, value) {
    const index = this.state.segments.findIndex(seg => String(seg.id) === String(segmentId));
    const seg = this.state.segments[index];
    const seconds = Number(value);
    if (!seg || !['startSec', 'endSec'].includes(field) || !Number.isFinite(seconds)) return;
    if (field === 'startSec') seg.startSec = Math.max(index ? this.state.segments[index - 1].endSec : 0, Math.min(seconds, seg.endSec - .001));
    else seg.endSec = Math.min(index < this.state.segments.length - 1 ? this.state.segments[index + 1].startSec : Math.max(seconds, seg.startSec + .001), Math.max(seconds, seg.startSec + .001));
    seg.startTime = this.formatTime(seg.startSec);
    seg.endTime = this.formatTime(seg.endSec);
    this.notify();
  }

  focusStage4Cue(segmentId) {
    const input = document.querySelector(`[data-stage4-subtitle="${segmentId}"]`) || document.querySelector(`[data-segment-input="stage4-${segmentId}"]`);
    input?.focus();
    input?.select();
  }

  serializeEditedSrt() {
    const stamp = value => {
      const ms = Math.max(0, Math.round((Number(value) || 0) * 1000));
      const h = Math.floor(ms / 3600000), m = Math.floor((ms % 3600000) / 60000), s = Math.floor((ms % 60000) / 1000);
      return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}`;
    };
    return this.state.segments.map((seg, index) => `${index + 1}\n${stamp(seg.startSec)} --> ${stamp(seg.endSec)}\n${seg.targetText || seg.sourceText || seg.text || ''}`).join('\n\n');
  }

  async exportEditedVideo() {
    const { backend, editVideo } = this.state;
    if (!backend.mediaId || editVideo.exporting) return;
    editVideo.exporting = true;
    editVideo.error = null;
    backend.status = 'submitting';
    backend.message = 'Preparing final audio mix and subtitles…';
    this.notify();
    const mix = editVideo.audioMix;
    try {
      const response = await fetch('/api/jobs', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mediaId: backend.mediaId, jobType: 'render', options: {
          ...backend.config,
          sourceLanguage: this.state.languages.source.code,
          targetLanguage: this.state.languages.target.code,
          timingMode: this.state.languages.timingMode,
          subtitles: this.serializeEditedSrt(),
          volume: `${mix.dubbed - 100 >= 0 ? '+' : ''}${mix.dubbed - 100}%`,
          originalAudioVolume: mix.original / 100,
          backgroundAudioVolume: mix.background / 100,
          backgroundAudioId: editVideo.backgroundAudio?.id || null,
          thumbnailId: editVideo.thumbnail?.id || null,
          subtitleStyle: this.state.subtitleStyles
        }})
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      backend.jobId = job.id;
      this.applyJob(job);
      if (this.pollTimer) clearInterval(this.pollTimer);
      this.pollTimer = setInterval(() => this.pollJob(), 500);
    } catch (error) {
      backend.status = 'failed'; backend.error = error.message; editVideo.error = error.message;
    } finally { editVideo.exporting = false; this.notify(); }
  }
}

export const store = new WorkflowStore();
if (typeof window !== 'undefined') {
  window.dubDubStore = store;
}
