const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const MIN_SIZE = 0.02;

/** All coordinates are relative to the visible video, including portrait video. */
export function dragOcrRegion(rect, start, point, action = 'draw') {
  const x = clamp(point.x, 0, 1), y = clamp(point.y, 0, 1);
  if (action === 'draw' || !rect) {
    const result = { left: Math.min(start.x, x), top: Math.min(start.y, y),
      right: Math.max(start.x, x), bottom: Math.max(start.y, y) };
    return result.right - result.left >= MIN_SIZE && result.bottom - result.top >= MIN_SIZE ? result : null;
  }
  if (action === 'move') {
    const width = rect.right - rect.left, height = rect.bottom - rect.top;
    const left = clamp(rect.left + x - start.x, 0, 1 - width);
    const top = clamp(rect.top + y - start.y, 0, 1 - height);
    return { left, top, right: left + width, bottom: top + height };
  }
  return {
    left: action.includes('w') ? clamp(x, 0, rect.right - MIN_SIZE) : rect.left,
    right: action.includes('e') ? clamp(x, rect.left + MIN_SIZE, 1) : rect.right,
    top: action.includes('n') ? clamp(y, 0, rect.bottom - MIN_SIZE) : rect.top,
    bottom: action.includes('s') ? clamp(y, rect.top + MIN_SIZE, 1) : rect.bottom,
  };
}

export function editOcrCoordinate(rect, edge, percent) {
  if (!Number.isFinite(percent)) return rect;
  const low = edge === 'right' ? rect.left + MIN_SIZE : edge === 'bottom' ? rect.top + MIN_SIZE : 0;
  const high = edge === 'left' ? rect.right - MIN_SIZE : edge === 'top' ? rect.bottom - MIN_SIZE : 1;
  return { ...rect, [edge]: clamp(percent / 100, low, high) };
}

export function formatOcrTime(seconds) {
  const s = Math.max(0, Math.round(Number(seconds) || 0));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}
