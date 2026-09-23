import React, { useState, useRef, useEffect, useMemo } from 'react';
import { useDubDubStore } from '../store';
import {
  Sparkles,
  Volume2,
  Play,
  Pause,
  Plus,
  Sliders,
  Search,
  Check,
  ChevronDown,
  User,
  AudioWaveform,
} from 'lucide-react';

export interface VoiceSelectorProps {
  value: string;
  onChange: (voiceId: string) => void;
  size?: 'sm' | 'md';
  className?: string;
  disabled?: boolean;
  placeholder?: string;
}

interface SelectorOption {
  id: string;
  name: string;
  kind: 'custom' | 'preset' | 'system' | 'clone';
  provider?: number;
  sampleUrl?: string;
  description?: string;
}

const getProviderBadge = (provider?: number) => {
  switch (provider) {
    case 0:
      return 'ElevenLabs';
    case 1:
      return 'OmniVoice';
    case 2:
      return 'VieNeu';
    case 3:
      return 'Gemini';
    default:
      return null;
  }
};

export const VoiceSelector: React.FC<VoiceSelectorProps> = ({
  value,
  onChange,
  size = 'md',
  className = '',
  disabled = false,
  placeholder = 'Select Voice',
}) => {
  const voices = useDubDubStore((s) => s.voices);
  const customVoices = useDubDubStore((s) => s.customVoices);
  const setCreateVoiceModalOpen = useDubDubStore((s) => s.setCreateVoiceModalOpen);
  const setVoiceManagerDrawerOpen = useDubDubStore((s) => s.setVoiceManagerDrawerOpen);

  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [openUpwards, setOpenUpwards] = useState(false);
  const [playingUrl, setPlayingUrl] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Stop audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Handle outside click and Escape key
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        closeDropdown();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeDropdown();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  // Focus search input on open
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const closeDropdown = () => {
    setIsOpen(false);
    setSearch('');
    if (audioRef.current) {
      audioRef.current.pause();
      setPlayingUrl(null);
    }
  };

  const handleToggleOpen = () => {
    if (disabled) return;
    if (!isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      setOpenUpwards(spaceBelow < 320);
    }
    if (isOpen) {
      closeDropdown();
    } else {
      setIsOpen(true);
    }
  };

  // Build unified deduplicated options map
  const optionsMap = useMemo(() => {
    const map = new Map<string, SelectorOption>();

    // 1. Add all custom voices from store
    (customVoices || []).forEach((cv) => {
      map.set(cv.id, {
        id: cv.id,
        name: cv.name,
        kind: 'custom',
        provider: cv.provider,
        sampleUrl: `/api/custom-voices/${cv.id}/audio`,
        description: cv.description,
      });
    });

    // 2. Add voices from voices list (presets, systems, or additional customs)
    (voices || []).forEach((v) => {
      const isCustom = v.kind === 'custom' || v.id.startsWith('voice_');
      const isSystem =
        v.id === 'No' ||
        v.id.toLowerCase() === 'clone' ||
        v.kind === 'clone' ||
        v.kind === 'system';

      if (!map.has(v.id)) {
        map.set(v.id, {
          id: v.id,
          name: v.name || v.id,
          kind: isCustom ? 'custom' : isSystem ? 'system' : 'preset',
          provider: v.provider,
          sampleUrl: v.sampleUrl || (isCustom ? `/api/custom-voices/${v.id}/audio` : undefined),
        });
      }
    });

    return map;
  }, [voices, customVoices]);

  // Find currently active option
  const activeOption = useMemo(() => {
    if (!value) return null;
    if (optionsMap.has(value)) return optionsMap.get(value);
    // Fallback: check by name or stripped prefix
    const stripped = value.startsWith('Custom: ') ? value.replace('Custom: ', '') : value;
    for (const opt of optionsMap.values()) {
      if (opt.name === stripped || opt.name === value) return opt;
    }
    return null;
  }, [optionsMap, value]);

  // Group and filter options
  const { customGroup, presetGroup, systemGroup, hasMatches } = useMemo(() => {
    const q = search.trim().toLowerCase();
    const all = Array.from(optionsMap.values());

    const filtered = all.filter((opt) => {
      if (!q) return true;
      return (
        opt.name.toLowerCase().includes(q) ||
        opt.id.toLowerCase().includes(q) ||
        (opt.description && opt.description.toLowerCase().includes(q))
      );
    });

    const custom = filtered.filter((o) => o.kind === 'custom');
    const preset = filtered.filter((o) => o.kind === 'preset');
    const system = filtered.filter((o) => o.kind === 'system' || o.kind === 'clone');

    return {
      customGroup: custom,
      presetGroup: preset,
      systemGroup: system,
      hasMatches: filtered.length > 0,
    };
  }, [optionsMap, search]);

  const handleSelect = (optionId: string) => {
    onChange(optionId);
    closeDropdown();
  };

  const handleTogglePlay = (e: React.MouseEvent, sampleUrl?: string) => {
    e.stopPropagation();
    if (!sampleUrl) return;

    if (!audioRef.current) {
      audioRef.current = new Audio();
      audioRef.current.onended = () => setPlayingUrl(null);
      audioRef.current.onerror = () => setPlayingUrl(null);
    }

    if (playingUrl === sampleUrl) {
      audioRef.current.pause();
      setPlayingUrl(null);
    } else {
      audioRef.current.src = sampleUrl;
      audioRef.current.play().catch(() => setPlayingUrl(null));
      setPlayingUrl(sampleUrl);
    }
  };

  const isSelected = (optId: string) => {
    if (value === optId) return true;
    if (activeOption && activeOption.id === optId) return true;
    return false;
  };

  const displayLabel = activeOption ? activeOption.name : (value || placeholder);
  const isCustomActive = activeOption?.kind === 'custom' || value?.startsWith('voice_');

  const sizeClasses =
    size === 'sm'
      ? 'h-7 px-2 text-[11px] gap-1.5'
      : 'h-8 px-2.5 text-xs gap-2';

  return (
    <div ref={containerRef} className={`relative inline-block text-left ${className}`}>
      {/* Trigger Button */}
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        onClick={handleToggleOpen}
        className={`w-full flex items-center justify-between rounded-lg border border-stone-200 bg-white hover:border-amber-400 focus:outline-none focus:ring-1 focus:ring-amber-500 font-semibold text-stone-800 transition-colors shadow-2xs cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed ${sizeClasses}`}
        title={displayLabel}
      >
        <div className="flex items-center gap-1.5 min-w-0 truncate">
          {isCustomActive ? (
            <Sparkles className="w-3 h-3 text-[#8D4B00] shrink-0" />
          ) : (
            <Volume2 className="w-3 h-3 text-stone-400 shrink-0" />
          )}
          <span className="truncate">{displayLabel}</span>
          {isCustomActive && (
            <span className="px-1 py-0.2 rounded text-[9px] font-bold bg-amber-100 text-[#8D4B00] shrink-0">
              Custom
            </span>
          )}
        </div>
        <ChevronDown
          className={`w-3.5 h-3.5 text-stone-400 shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Dropdown Popover */}
      {isOpen && (
        <div
          className={`absolute right-0 w-72 bg-white rounded-xl shadow-xl border border-stone-200 z-50 flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-100 ${
            openUpwards ? 'bottom-full mb-1' : 'top-full mt-1'
          }`}
        >
          {/* Search Header */}
          <div className="p-2 border-b border-stone-100 bg-stone-50/50">
            <div className="relative flex items-center">
              <Search className="w-3.5 h-3.5 text-stone-400 absolute left-2.5 pointer-events-none" />
              <input
                ref={searchInputRef}
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search voices..."
                className="w-full pl-8 pr-2.5 py-1 text-xs bg-white rounded-lg border border-stone-200 focus:outline-none focus:border-amber-400 text-stone-800 placeholder-stone-400"
              />
            </div>
          </div>

          {/* Scrollable Options List */}
          <div className="max-h-60 overflow-y-auto p-1.5 space-y-2">
            {/* 1. Cloned Voices Group */}
            {customGroup.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-amber-900/60 flex items-center gap-1">
                  <Sparkles className="w-2.5 h-2.5 text-[#8D4B00]" />
                  <span>My Cloned Voices ({customGroup.length})</span>
                </div>
                <div className="space-y-0.5 mt-0.5">
                  {customGroup.map((opt) => {
                    const selected = isSelected(opt.id);
                    const providerTag = getProviderBadge(opt.provider);
                    const isAudioPlaying = playingUrl === opt.sampleUrl;

                    return (
                      <div
                        key={opt.id}
                        onClick={() => handleSelect(opt.id)}
                        className={`group px-2 py-1.5 rounded-lg flex items-center justify-between gap-2 cursor-pointer transition-colors ${
                          selected
                            ? 'bg-amber-500/10 text-[#8D4B00] font-bold'
                            : 'hover:bg-stone-100 text-stone-800 text-xs'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-5 h-5 rounded-full bg-amber-100 text-[#8D4B00] flex items-center justify-center text-[10px] shrink-0">
                            <Sparkles className="w-2.5 h-2.5" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-xs truncate font-medium">{opt.name}</div>
                            {providerTag && (
                              <div className="text-[9px] text-stone-400 leading-tight">
                                {providerTag}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                          {opt.sampleUrl && (
                            <button
                              type="button"
                              onClick={(e) => handleTogglePlay(e, opt.sampleUrl)}
                              className={`p-1 rounded-md transition-colors ${
                                isAudioPlaying
                                  ? 'bg-[#8D4B00] text-white'
                                  : 'text-stone-400 hover:text-stone-700 hover:bg-stone-200/60'
                              }`}
                              title={isAudioPlaying ? 'Stop Audition' : 'Audition Voice'}
                            >
                              {isAudioPlaying ? (
                                <Pause className="w-3 h-3" />
                              ) : (
                                <Play className="w-3 h-3" />
                              )}
                            </button>
                          )}
                          {selected && <Check className="w-3.5 h-3.5 text-[#8D4B00]" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 2. Preset Voices Group */}
            {presetGroup.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-stone-400">
                  Preset Voices ({presetGroup.length})
                </div>
                <div className="space-y-0.5 mt-0.5">
                  {presetGroup.map((opt) => {
                    const selected = isSelected(opt.id);
                    return (
                      <div
                        key={opt.id}
                        onClick={() => handleSelect(opt.id)}
                        className={`px-2 py-1.5 rounded-lg flex items-center justify-between cursor-pointer transition-colors text-xs ${
                          selected
                            ? 'bg-amber-500/10 text-[#8D4B00] font-bold'
                            : 'hover:bg-stone-100 text-stone-700'
                        }`}
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <Volume2 className="w-3 h-3 text-stone-400 shrink-0" />
                          <span className="truncate">{opt.name}</span>
                        </div>
                        {selected && <Check className="w-3.5 h-3.5 text-[#8D4B00] shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* 3. System / Control Group */}
            {systemGroup.length > 0 && (
              <div>
                <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-stone-400">
                  Control
                </div>
                <div className="space-y-0.5 mt-0.5">
                  {systemGroup.map((opt) => {
                    const selected = isSelected(opt.id);
                    return (
                      <div
                        key={opt.id}
                        onClick={() => handleSelect(opt.id)}
                        className={`px-2 py-1.5 rounded-lg flex items-center justify-between cursor-pointer transition-colors text-xs italic ${
                          selected
                            ? 'bg-amber-500/10 text-[#8D4B00] font-bold'
                            : 'hover:bg-stone-100 text-stone-500'
                        }`}
                      >
                        <span className="truncate">{opt.name}</span>
                        {selected && <Check className="w-3.5 h-3.5 text-[#8D4B00] shrink-0" />}
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* No matches */}
            {!hasMatches && (
              <div className="p-4 text-center text-xs text-stone-500">
                No voices found matching "{search}"
              </div>
            )}
          </div>

          {/* Dropdown Footer Actions */}
          <div className="p-2 border-t border-stone-100 bg-stone-50/80 flex flex-col gap-1 shrink-0">
            <button
              type="button"
              onClick={() => {
                closeDropdown();
                setCreateVoiceModalOpen(true);
              }}
              className="w-full flex items-center justify-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-[#8D4B00] text-white hover:bg-[#723c00] transition-colors cursor-pointer shadow-2xs"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Create New Voice</span>
            </button>
            <button
              type="button"
              onClick={() => {
                closeDropdown();
                setVoiceManagerDrawerOpen(true);
              }}
              className="w-full flex items-center justify-center gap-1.5 px-2 py-1 rounded-md text-[11px] font-medium text-stone-600 hover:text-stone-900 hover:bg-stone-200/60 transition-colors cursor-pointer"
            >
              <Sliders className="w-3 h-3 text-stone-500" />
              <span>Manage Voice Library</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
