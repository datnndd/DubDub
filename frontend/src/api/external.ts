/**
 * openExternal — open a URL in a new browser tab.
 */
export async function openExternal(url: string) {
  window.open(url, '_blank', 'noopener,noreferrer');
}

