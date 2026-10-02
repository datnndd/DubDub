export interface Segment {
  id: number;
  speakerId: string;
  speakerName?: string;
  speakerCode?: string;
  speakerLabel?: string;
  startTime: string;
  endTime: string;
  startSec: number;
  endSec: number;
  cps?: number;
  cpsStatus?: 'Optimal' | 'Good' | 'Warning' | 'Critical';
  confidence?: number;
  sourceText: string;
  text?: string;
  targetText: string;
  speakerColor?: string;
  voiceOverride?: string;
  previewAudioUrl?: string;
  previewAudioId?: string;
  previewSpeedFactor?: number;
  previewVoice?: string;
  hasOcrDiff?: boolean;
  ocrBoxNumber?: string;
  ocrConfidence?: number;
  ocrSlideText?: string;
  ocrResolved?: boolean;
  sourceType?: 'asr' | 'ocr';
}

export interface OcrSubtitleEntry {
  startSec: number;
  endSec: number;
  startTime: string;
  endTime: string;
  text: string;
  confidence?: number;
}

export interface OcrCropState {
  active: boolean;
  segmentId: number | null;
  roi: [number, number, number, number]; // [x, y, width, height] normalized 0-1
  loading: boolean;
  error: string | null;
}
