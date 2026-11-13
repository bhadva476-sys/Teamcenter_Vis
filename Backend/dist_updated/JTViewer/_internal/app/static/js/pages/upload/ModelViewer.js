import { MODEL_VIEWER_URL } from '../../config.js';

let viewerPromise;

export function loadModelViewer() {
  if (!viewerPromise) {
    viewerPromise = import(MODEL_VIEWER_URL).catch(error => {
      viewerPromise = null;
      throw error;
    });
  }
  return viewerPromise;
}
