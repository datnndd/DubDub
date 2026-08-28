// Column config for the dub segment table — shared with the IdleSkeleton
// ghost preview so the skeleton can never drift from the real table.
export const COLUMNS = [
  { key: 'time', width: 50 },
  { key: 'spkr', width: 45 },
  { key: 'text', flex: 1 },
  { key: 'lang', width: 42 },
  { key: 'voice', width: 60 },
  { key: 'vol', width: 40 },
  { key: 'act', width: 42 },
];
