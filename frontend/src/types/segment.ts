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
  targetText: string;
  hasOcrDiff?: boolean;
  ocrBoxNumber?: string;
  ocrConfidence?: number;
  ocrSlideText?: string;
  ocrResolved?: boolean;
}

export interface OcrCropState {
  active: boolean;
  segmentId: number | null;
  roi: [number, number, number, number]; // [x, y, width, height] normalized 0-1
  loading: boolean;
  error: string | null;
}
