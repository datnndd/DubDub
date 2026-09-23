import React, { useState, useRef, useEffect } from 'react';
import { useDubDubStore } from '../store';
import {
  X,
  Plus,
  Play,
  Pause,
  Trash2,
  Edit2,
  Check,
  Search,
  Volume2,
  RefreshCw,
  Sparkles,
  Layers,
  Loader2,
} from 'lucide-react';
import {
  previewCustomVoice,
  getCustomVoiceAudioUrl,
  getCustomVoicePreviewAudioUrl,
  type CustomVoice,
} from '../api/voices';

export const VoiceManagerDrawer: React.FC = () => {
  const isOpen = useDubDubStore((s) => s.isVoiceManagerDrawerOpen);
  const setIsOpen = useDubDubStore((s) => s.setVoiceManagerDrawerOpen);
  const openCreateModal = useDubDubStore((s) => s.setCreateVoiceModalOpen);
  const customVoices = useDubDubStore((s) => s.customVoices);
  const loadCustomVoices = useDubDubStore((s) => s.loadCustomVoices);
  const updateVoice = useDubDubStore((s) => s.updateVoice);
  const deleteVoice = useDubDubStore((s) => s.deleteVoice);

  const [search, setSearch] = useState('');
  const [editingVoiceId, setEditingVoiceId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [editingDesc, setEditingDesc] = useState('');

  // Audio preview playback state
  const [playingVoiceId, setPlayingVoiceId] = useState<string | null>(null);
  const [loadingPreviewId, setLoadingPreviewId] = useState<string | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Deletion confirmation state
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadCustomVoices();
    } else {
      // Pause any ongoing playback when closing
      if (audioRef.current) {
        audioRef.current.pause();
        setPlayingVoiceId(null);
      }
      setEditingVoiceId(null);
      setConfirmDeleteId(null);
    }
  }, [isOpen, loadCustomVoices]);

  if (!isOpen) return null;

  const filteredVoices = (customVoices || []).filter((v) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return (
      v.name.toLowerCase().includes(q) ||
      (v.description || '').toLowerCase().includes(q) ||
      (v.ref_text || '').toLowerCase().includes(q)
    );
  });

  const handleStartEdit = (v: CustomVoice) => {
    setEditingVoiceId(v.id);
    setEditingName(v.name);
    setEditingDesc(v.description || '');
  };

  const handleSaveEdit = async (voiceId: string) => {
    const clean = editingName.trim();
    if (!clean) return;
    try {
      await updateVoice(voiceId, {
        name: clean,
        description: editingDesc.trim(),
      });
      setEditingVoiceId(null);
    } catch (err) {
      console.error('Failed to update voice:', err);
    }
  };

  const handleTogglePlay = async (voice: CustomVoice) => {
    if (!audioRef.current) return;

    if (playingVoiceId === voice.id) {
      audioRef.current.pause();
      setPlayingVoiceId(null);
      return;
    }

    try {
      // If preview exists or fallback to reference audio
      const audioUrl = voice.preview_audio_path
        ? getCustomVoicePreviewAudioUrl(voice.id)
        : getCustomVoiceAudioUrl(voice.id);

      audioRef.current.src = audioUrl;
      await audioRef.current.play();
      setPlayingVoiceId(voice.id);
    } catch (err) {
      console.warn('Playback failed, attempting preview synthesis:', err);
      setLoadingPreviewId(voice.id);
      try {
        await previewCustomVoice(voice.id);
        if (audioRef.current) {
          audioRef.current.src = getCustomVoicePreviewAudioUrl(voice.id);
          await audioRef.current.play();
          setPlayingVoiceId(voice.id);
        }
      } catch (synthErr) {
        console.error('Synthesis failed:', synthErr);
      } finally {
        setLoadingPreviewId(null);
      }
    }
  };

  const handleDelete = async (voiceId: string) => {
    try {
      await deleteVoice(voiceId, false);
      setConfirmDeleteId(null);
    } catch (err) {
      console.error('Failed to delete voice:', err);
    }
  };

  const getProviderBadge = (provider: number) => {
    switch (provider) {
      case 2:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-100 text-amber-900 border border-amber-200">
            VieNeu 48k
          </span>
        );
      case 1:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-sky-100 text-sky-900 border border-sky-200">
            OmniVoice 24k
          </span>
        );
      case 0:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-900 border border-purple-200">
            ElevenLabs
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-stone-100 text-stone-700">
            Neural Voice
          </span>
        );
    }
  };

  return (
    <div
      data-voice-manager-drawer="true"
      className="fixed inset-0 z-50 flex justify-end bg-black/40 backdrop-blur-xs transition-opacity"
      onClick={(e) => {
        if (e.target === e.currentTarget) setIsOpen(false);
      }}
    >
      <div className="w-full max-w-md bg-[#FAF9F6] h-full shadow-2xl border-l border-[#E7E4DC] flex flex-col animate-in slide-in-from-right duration-200">
        {/* Drawer Header */}
        <div className="h-14 px-4 border-b border-[#E7E4DC] flex items-center justify-between bg-white shrink-0">
          <div className="flex items-center gap-2">
            <Volume2 className="w-5 h-5 text-[#8D4B00]" />
            <h3 className="font-bold text-sm text-stone-900">Custom Voice Library</h3>
            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-stone-100 text-stone-600">
              {customVoices.length}
            </span>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={() => {
                setIsOpen(false);
                openCreateModal(true);
              }}
              className="px-2.5 py-1.5 rounded-lg bg-[#8D4B00] hover:bg-[#733D00] text-white font-bold text-xs flex items-center gap-1 shadow-xs transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              New Voice
            </button>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 rounded-lg text-stone-400 hover:text-stone-700 hover:bg-stone-100 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Search Bar */}
        <div className="p-3 border-b border-[#E7E4DC] bg-white shrink-0">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-stone-400" />
            <input
              type="text"
              placeholder="Search custom voices..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full text-xs pl-8 pr-3 py-1.5 bg-stone-50 rounded-lg border border-[#E7E4DC] focus:border-[#8D4B00] outline-hidden font-medium"
            />
          </div>
        </div>

        {/* Voice List */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {filteredVoices.length === 0 ? (
            <div className="py-12 px-4 text-center">
              <div className="w-12 h-12 rounded-2xl bg-amber-50 border border-amber-200 flex items-center justify-center mx-auto mb-3 text-[#8D4B00]">
                <Sparkles className="w-6 h-6" />
              </div>
              <h4 className="font-bold text-xs text-stone-800 mb-1">No Custom Voices Found</h4>
              <p className="text-[11px] text-stone-500 max-w-xs mx-auto mb-4">
                Clone a reference voice to personalize narration and maintain consistent speaker profiles across dubbing jobs.
              </p>
              <button
                onClick={() => {
                  setIsOpen(false);
                  openCreateModal(true);
                }}
                className="px-4 py-2 rounded-xl bg-[#8D4B00] hover:bg-[#733D00] text-white font-bold text-xs inline-flex items-center gap-1.5 shadow-sm"
              >
                <Plus className="w-4 h-4" />
                Create Cloned Voice
              </button>
            </div>
          ) : (
            filteredVoices.map((voice) => {
              const isEditing = editingVoiceId === voice.id;
              const isPlaying = playingVoiceId === voice.id;
              const isLoading = loadingPreviewId === voice.id;
              const isConfirmingDelete = confirmDeleteId === voice.id;

              return (
                <div
                  key={voice.id}
                  className="p-3 rounded-xl border border-[#E7E4DC] bg-white hover:border-amber-300 transition-all space-y-2 shadow-2xs"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-start gap-2.5 min-w-0">
                      {/* Audition Play / Pause button */}
                      <button
                        type="button"
                        onClick={() => handleTogglePlay(voice)}
                        disabled={isLoading}
                        className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 transition-colors ${
                          isPlaying
                            ? 'bg-[#8D4B00] text-white'
                            : 'bg-stone-100 hover:bg-stone-200 text-stone-700'
                        }`}
                        title="Audition voice sample"
                      >
                        {isLoading ? (
                          <Loader2 className="w-4 h-4 animate-spin text-amber-700" />
                        ) : isPlaying ? (
                          <Pause className="w-4 h-4" />
                        ) : (
                          <Play className="w-4 h-4 ml-0.5" />
                        )}
                      </button>

                      <div className="min-w-0 flex-1">
                        {isEditing ? (
                          <div className="space-y-1">
                            <input
                              type="text"
                              value={editingName}
                              onChange={(e) => setEditingName(e.target.value)}
                              className="text-xs font-bold px-2 py-0.5 bg-stone-50 border border-stone-200 rounded w-full outline-hidden"
                            />
                            <input
                              type="text"
                              placeholder="Description..."
                              value={editingDesc}
                              onChange={(e) => setEditingDesc(e.target.value)}
                              className="text-[10px] px-2 py-0.5 bg-stone-50 border border-stone-200 rounded w-full outline-hidden text-stone-600"
                            />
                          </div>
                        ) : (
                          <>
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <span className="font-bold text-xs text-stone-900 truncate">
                                {voice.name}
                              </span>
                              {getProviderBadge(voice.provider)}
                            </div>
                            {voice.description && (
                              <p className="text-[10px] text-stone-500 truncate mt-0.5">
                                {voice.description}
                              </p>
                            )}
                          </>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-1 shrink-0">
                      {isEditing ? (
                        <button
                          onClick={() => handleSaveEdit(voice.id)}
                          className="p-1 rounded hover:bg-emerald-50 text-emerald-600"
                          title="Save changes"
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleStartEdit(voice)}
                          className="p-1 rounded hover:bg-stone-100 text-stone-400 hover:text-stone-700"
                          title="Rename voice"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                      )}

                      {!isConfirmingDelete ? (
                        <button
                          onClick={() => setConfirmDeleteId(voice.id)}
                          className="p-1 rounded hover:bg-rose-50 text-stone-400 hover:text-rose-600"
                          title="Delete voice"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      ) : (
                        <div className="flex items-center gap-1 bg-rose-50 p-1 rounded-lg border border-rose-200">
                          <span className="text-[10px] text-rose-700 font-bold px-1">Sure?</span>
                          <button
                            onClick={() => handleDelete(voice.id)}
                            className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-rose-600 text-white hover:bg-rose-700"
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="px-1.5 py-0.5 rounded text-[9px] font-bold bg-stone-200 text-stone-700 hover:bg-stone-300"
                          >
                            No
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Ref text snippet if present */}
                  {voice.ref_text && (
                    <div className="text-[10px] text-stone-500 bg-stone-50 p-1.5 rounded-lg border border-stone-100 line-clamp-2">
                      <span className="font-semibold text-stone-600">Ref Text: </span>
                      {voice.ref_text}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Global Audio Player Element for Audition */}
        <audio
          ref={audioRef}
          onEnded={() => setPlayingVoiceId(null)}
          onError={() => setPlayingVoiceId(null)}
          className="hidden"
        />
      </div>
    </div>
  );
};
