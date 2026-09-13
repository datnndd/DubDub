import { detectPlatform } from './micError';

export { detectPlatform };
export async function checkMicrophone() {
  try {
    const result = await navigator.permissions?.query?.({ name: 'microphone' });
    return result?.state || 'unknown';
  } catch {
    return 'unknown';
  }
}
