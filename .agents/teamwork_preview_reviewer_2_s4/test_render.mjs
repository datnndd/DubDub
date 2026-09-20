globalThis.window = globalThis;
globalThis.document = {
  querySelector: () => null,
  querySelectorAll: () => []
};

const { renderStage4EditVideo } = await import('../../frontend/js/screens/Stage4EditVideo.js');
const { store } = await import('../../frontend/js/state.js');

const state = store.getState();
state.currentStep = 4;
state.activeSegmentId = 1;
state.project = { durationSec: 30, duration: "00:30", title: "Demo Video", resolution: "1920x1080" };
state.editVideo = {
  audioMix: { original: 20, dubbed: 100, background: 40 },
  backgroundAudio: { name: "test_bgm.mp3", previewUrl: "blob:bgm" },
  thumbnail: { name: "test_thumb.png", previewUrl: "blob:thumb" },
  activeTab: "audio"
};
state.segments = [
  { id: 1, startSec: 0, endSec: 3.5, targetText: "Node rendered subtitle" }
];

const htmlAudio = renderStage4EditVideo(state);
console.log("Audio tab toggle-mute-original:", htmlAudio.includes('data-action="toggle-mute-original"'));
console.log("Audio tab toggle-mute-dubbed:", htmlAudio.includes('data-action="toggle-mute-dubbed"'));
console.log("Audio tab toggle-mute-background:", htmlAudio.includes('data-action="toggle-mute-background"'));
console.log("Audio tab mix slider original:", htmlAudio.includes('data-mix-slider="original"'));
console.log("Audio tab mix slider dubbed:", htmlAudio.includes('data-mix-slider="dubbed"'));
console.log("Audio tab mix slider background:", htmlAudio.includes('data-mix-slider="background"'));
