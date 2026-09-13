/**
 * Mark the browser CSS scale engine as active.
 *
 * @param {number} scale
 */
export async function applyUiScale(scale) {
  const root = document.documentElement;
  void scale;
  root.dataset.uiScaleEngine = 'css';
  return 'css';
}
