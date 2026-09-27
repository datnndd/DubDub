import { useState, useEffect, useCallback } from 'react';
import { previewTTS } from '../api/voices';

export interface AuditionState {
  activeKey: string | null;
  isPlaying: boolean;
  loadingKey: string | null;
}

type AuditionListener = (state: AuditionState) => void;

/**
 * Standard sample phrase by language for preview synthesis.
 * Vietnamese and English phrases as required by R3.
 */
export function getStandardSamplePhrase(langCode?: string): string {
  const code = (langCode || 'vi').trim().toLowerCase();
  if (code.startsWith('vi')) {
    return 'Chào bạn, đây là bản nghe thử giọng nói trí tuệ nhân tạo được tổng hợp thành công.';
  }
  return 'Hello, this is a sample preview of this voice.';
}

/**
 * Cache key generator matching client state requirements: provider + voice + language
 */
export function getVoicePreviewCacheKey(
  provider: number | string,
  voice: string,
  language: string
): string {
  const normVoice = (voice || '').trim();
  const normLang = (language || 'vi').trim().toLowerCase();
  return `${provider}:${normVoice}:${normLang}`;
}

/**
 * Unified Voice Audition Manager maintaining a single active audio player instance
 * and client memory cache across all audition buttons.
 */
export class VoiceAuditionManager {
  private static instance: VoiceAuditionManager | null = null;
  private audio: HTMLAudioElement | null = null;
  private activeKey: string | null = null;
  private isPlaying: boolean = false;
  private loadingKey: string | null = null;
  private cache = new Map<string, string>();
  private listeners = new Set<AuditionListener>();
  private pendingToken: number = 0;
  private pendingAbortController: AbortController | null = null;
  private pendingLoadingCallback: ((loading: boolean) => void) | null = null;

  public static getInstance(): VoiceAuditionManager {
    if (!VoiceAuditionManager.instance) {
      VoiceAuditionManager.instance = new VoiceAuditionManager();
    }
    return VoiceAuditionManager.instance;
  }

  public getCacheKey(provider: number | string, voice: string, language: string): string {
    return getVoicePreviewCacheKey(provider, voice, language);
  }

  public getCachedUrl(provider: number | string, voice: string, language: string): string | undefined {
    return this.cache.get(this.getCacheKey(provider, voice, language));
  }

  public setCachedUrl(provider: number | string, voice: string, language: string, url: string): void {
    this.cache.set(this.getCacheKey(provider, voice, language), url);
  }

  public hasCachedUrl(provider: number | string, voice: string, language: string): boolean {
    return this.cache.has(this.getCacheKey(provider, voice, language));
  }

  public clearCache(): void {
    this.cache.clear();
  }

  public getActiveKey(): string | null {
    return this.isPlaying ? this.activeKey : null;
  }

  public isPlayingState(): boolean {
    return this.isPlaying;
  }

  public getLoadingKey(): string | null {
    return this.loadingKey;
  }

  public isKeyPlaying(key: string): boolean {
    return this.isPlaying && this.activeKey === key;
  }

  public isKeyLoading(key: string): boolean {
    return this.loadingKey === key;
  }

  public subscribe(listener: AuditionListener): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify(): void {
    const state: AuditionState = {
      activeKey: this.isPlaying ? this.activeKey : null,
      isPlaying: this.isPlaying,
      loadingKey: this.loadingKey,
    };
    this.listeners.forEach((listener) => {
      try {
        listener(state);
      } catch (err) {
        console.error('Error in audition listener:', err);
      }
    });
  }

  public cancelPending(shouldNotify: boolean = true): void {
    this.pendingToken++;
    if (this.pendingAbortController) {
      try {
        this.pendingAbortController.abort();
      } catch (_) {}
      this.pendingAbortController = null;
    }
    if (this.pendingLoadingCallback) {
      try {
        this.pendingLoadingCallback(false);
      } catch (_) {}
      this.pendingLoadingCallback = null;
    }
    if (this.loadingKey !== null) {
      this.loadingKey = null;
      if (shouldNotify) {
        this.notify();
      }
    }
  }

  public startLoading(
    key: string,
    abortController: AbortController,
    onLoadingChange?: (loading: boolean) => void
  ): number {
    this.cancelPending();
    this.loadingKey = key;
    this.pendingAbortController = abortController;
    this.pendingLoadingCallback = onLoadingChange || null;
    const token = ++this.pendingToken;
    try {
      onLoadingChange?.(true);
    } catch (_) {}
    this.notify();
    return token;
  }

  public finishLoading(token: number): void {
    if (this.pendingToken === token) {
      let changed = false;
      if (this.pendingLoadingCallback) {
        try {
          this.pendingLoadingCallback(false);
        } catch (_) {}
        this.pendingLoadingCallback = null;
        changed = true;
      }
      this.pendingAbortController = null;
      if (this.loadingKey !== null) {
        this.loadingKey = null;
        changed = true;
      }
      if (changed) {
        this.notify();
      }
    }
  }

  public stop(): void {
    this.cancelPending(false);
    if (this.audio) {
      try {
        this.audio.pause();
        this.audio.currentTime = 0;
        this.audio.onended = null;
        this.audio.onerror = null;
        this.audio.src = '';
      } catch (_) {}
    }
    this.isPlaying = false;
    this.activeKey = null;
    this.notify();
  }

  public stopIfKey(key: string): void {
    if (this.activeKey === key) {
      this.stop();
    } else if (this.loadingKey === key) {
      this.cancelPending();
    }
  }

  public stopIfKeyPrefix(prefix: string): void {
    let shouldNotify = false;
    if (this.activeKey && this.activeKey.startsWith(prefix)) {
      if (this.audio) {
        try {
          this.audio.pause();
          this.audio.currentTime = 0;
          this.audio.onended = null;
          this.audio.onerror = null;
          this.audio.src = '';
        } catch (_) {}
      }
      this.isPlaying = false;
      this.activeKey = null;
      shouldNotify = true;
    }
    if (this.loadingKey && this.loadingKey.startsWith(prefix)) {
      this.cancelPending();
      shouldNotify = false; // cancelPending already notified
    }
    if (shouldNotify) {
      this.notify();
    }
  }

  public nextToken(): number {
    this.pendingToken++;
    return this.pendingToken;
  }

  public isTokenCurrent(token: number): boolean {
    return this.pendingToken === token;
  }

  public play(key: string, url: string): void {
    // If clicking currently playing audio key, toggle halt
    if (this.isPlaying && this.activeKey === key) {
      this.stop();
      return;
    }

    // Single active audio player instance across all buttons:
    // halt any currently playing audio immediately and cancel any pending loading
    this.stop();

    if (typeof Audio === 'undefined') {
      this.isPlaying = false;
      this.activeKey = null;
      return;
    }

    this.activeKey = key;
    this.isPlaying = true;

    try {
      if (!this.audio) {
        this.audio = new Audio();
      }
      this.audio.src = url;
      const currentKey = key;

      this.audio.onended = () => {
        if (this.activeKey === currentKey) {
          this.isPlaying = false;
          this.activeKey = null;
          this.notify();
        }
      };
      this.audio.onerror = () => {
        if (this.activeKey === currentKey) {
          this.isPlaying = false;
          this.activeKey = null;
          this.notify();
        }
      };
      const playPromise = this.audio.play();
      if (playPromise && typeof playPromise.catch === 'function') {
        playPromise.catch(() => {
          if (this.activeKey === currentKey) {
            this.isPlaying = false;
            this.activeKey = null;
            this.notify();
          }
        });
      }
    } catch (err) {
      console.error('Failed to play audio:', err);
      this.isPlaying = false;
      this.activeKey = null;
    }

    this.notify();
  }

  public setAudioForTesting(audio: any): void {
    this.audio = audio;
  }
}

export const voiceAuditionManager = VoiceAuditionManager.getInstance();

export async function auditionVoice(options: {
  key: string;
  voice: string;
  provider: number | string;
  language: string;
  staticSampleUrl?: string;
  speed?: number;
  onLoadingChange?: (loading: boolean) => void;
}): Promise<string | null> {
  const manager = VoiceAuditionManager.getInstance();
  const { key, voice, provider, language, staticSampleUrl, speed, onLoadingChange } = options;

  // 1. Clicking audition on currently playing key halts playback
  if (manager.isKeyPlaying(key)) {
    manager.stop();
    return null;
  }

  // 2. Clicking audition on currently loading key halts/cancels generation
  if (manager.isKeyLoading(key)) {
    manager.stop();
    return null;
  }

  // 3. R4: maintain single active audio player - halt any currently playing audio immediately
  manager.stop();

  // 4. Static sample URL takes precedence when present
  if (staticSampleUrl) {
    manager.play(key, staticSampleUrl);
    return staticSampleUrl;
  }

  // 5. Validate voice when synthesizing via backend
  const normVoice = (voice || '').trim();
  if (!normVoice || normVoice === 'No' || normVoice.toLowerCase() === 'clone') {
    return null;
  }

  // 6. Check client memory cache (keyed by provider + voice + language)
  const cachedUrl = manager.getCachedUrl(provider, normVoice, language);
  if (cachedUrl) {
    manager.play(key, cachedUrl);
    return cachedUrl;
  }

  // 6. Delegate to /api/tts/preview endpoint
  const abortController = new AbortController();
  const token = manager.startLoading(key, abortController, onLoadingChange);

  try {
    const phrase = getStandardSamplePhrase(language);
    const res = await previewTTS(
      {
        text: phrase,
        voice: normVoice,
        provider,
        language,
        speed,
        force_refresh: false,
      },
      { signal: abortController.signal }
    );

    const audioUrl = res.audio_url || res.preview_url;
    if (audioUrl) {
      manager.setCachedUrl(provider, normVoice, language, audioUrl);
      // Only start playing if this request wasn't cancelled or superseded
      if (manager.isTokenCurrent(token)) {
        manager.finishLoading(token);
        manager.play(key, audioUrl);
      }
      return audioUrl;
    }
  } catch (err: any) {
    if (err?.name !== 'AbortError') {
      console.error(`Failed to audition voice preview for ${voice}:`, err);
    }
  } finally {
    manager.finishLoading(token);
  }

  return null;
}

export function useVoiceAudition() {
  const manager = VoiceAuditionManager.getInstance();
  const [activeKey, setActiveKey] = useState<string | null>(() => manager.getActiveKey());
  const [isPlaying, setIsPlaying] = useState<boolean>(() => manager.isPlayingState());
  const [loadingKey, setLoadingKey] = useState<string | null>(() => manager.getLoadingKey());

  useEffect(() => {
    setActiveKey(manager.getActiveKey());
    setIsPlaying(manager.isPlayingState());
    setLoadingKey(manager.getLoadingKey());

    return manager.subscribe((state) => {
      setActiveKey(state.activeKey);
      setIsPlaying(state.isPlaying);
      setLoadingKey(state.loadingKey);
    });
  }, [manager]);

  const isKeyPlaying = useCallback(
    (key: string) => isPlaying && activeKey === key,
    [isPlaying, activeKey]
  );
  const isKeyLoading = useCallback(
    (key: string) => loadingKey === key,
    [loadingKey]
  );
  const stop = useCallback(() => manager.stop(), [manager]);
  const stopIfKey = useCallback((key: string) => manager.stopIfKey(key), [manager]);
  const stopIfKeyPrefix = useCallback(
    (prefix: string) => manager.stopIfKeyPrefix(prefix),
    [manager]
  );
  const play = useCallback((key: string, url: string) => manager.play(key, url), [manager]);

  return {
    activeKey,
    isPlaying,
    loadingKey,
    isKeyPlaying,
    isKeyLoading,
    stop,
    stopIfKey,
    stopIfKeyPrefix,
    play,
    manager,
  };
}
