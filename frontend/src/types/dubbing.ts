export interface Speaker {
  id: string;
  code: string;
  name: string;
  role?: string;
  preset?: string;
  clarity?: string;
  coverage?: string;
  color?: string;
}

export interface VoiceOption {
  id: string;
  name: string;
  gender?: string;
  lang?: string;
  sampleUrl?: string;
  provider?: number;
  kind?: string;
}

export interface DubbingTuning {
  pace: number;
  timbreWarmth: number;
  ducking: string;
}
