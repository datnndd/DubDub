export async function askConfirm(message, title = 'Confirm') {
  void title;
  return Promise.resolve(window.confirm(message));
}
