import { toast } from 'react-hot-toast';
import i18n from '../i18n';
import { browserDownload } from './download';
import { exportRecord } from '../api/exports';

const VIDEO_EXTS = ['mp4', 'mov', 'mkv', 'webm'];
const AUDIO_EXTS = ['wav', 'mp3', 'flac', 'm4b', 'm4a', 'aac', 'ogg', 'opus'];

function guessMode(ext) {
  if (VIDEO_EXTS.includes(ext)) return 'video';
  if (AUDIO_EXTS.includes(ext)) return 'audio';
  return 'file';
}

export async function downloadMedia(url, fallbackName, opts = {}) {
  const { onValueMoment = null, onHistoryChanged = null } = opts;
  try {
    toast.loading(i18n.t('app.toast_processing', { name: fallbackName }), { id: fallbackName });
    const finalName = await browserDownload(url, fallbackName);
    toast.success(i18n.t('app.toast_downloaded', { name: finalName }), { id: fallbackName });
    onValueMoment?.();
    const ext = (finalName.split('.').pop() || 'bin').toLowerCase();
    try {
      await exportRecord({
        filename: finalName,
        destination_path: `~/Downloads/${finalName}`,
        mode: guessMode(ext),
      });
      onHistoryChanged?.();
    } catch (error) {
      console.warn('exportRecord failed:', error);
    }
  } catch (error) {
    console.error(error);
    toast.error(i18n.t('app.toast_download_error', { message: error.message }), {
      id: fallbackName,
    });
  }
}
