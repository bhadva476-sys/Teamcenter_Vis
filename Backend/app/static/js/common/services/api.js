import { API_BASE } from '../../config.js';

async function requestJson(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || 'The request could not be completed.');
  }
  return data;
}

export function fetchUploadedFiles() {
  return requestJson('/list', {
    headers: { Accept: 'application/json' }
  });
}

export function openRegisteredFile(fileId) {
  return requestJson(`/api/jt-files/${encodeURIComponent(fileId)}/open-in-teamcenter-visualization`, {
    method: 'POST',
    headers: { Accept: 'application/json' }
  });
}

// export function downloadRegisteredFile(fileId) {
//   return requestJson(`/api/jt-files/${encodeURIComponent(fileId)}/download`, {
//     method: 'POST',
//     headers: { Accept: 'application/json' }
//   });
// }
export async function downloadRegisteredFile(fileId, filename) {
  if (window.pywebview?.api?.download_file) {
    return window.pywebview.api.download_file(fileId, filename);
  }

  const response = await fetch(
    `${API_BASE}/api/jt-files/${encodeURIComponent(fileId)}/download`
  );
  if (!response.ok) {
    let message = 'File download failed.';
    try {
      const data = await response.json();
      message = data.error || message;
    } catch {
      // Keep the generic error when the response is not JSON.
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;

  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { cancelled: false, filename };
}

export function convertJTFile(file) {
  const form = new FormData();
  form.append('file', file);
  return requestJson('/upload', { method: 'POST', body: form });
}

export function registerJTFile(file, { thumbnail, previewAvailable = false } = {}) {
  const form = new FormData();
  form.append('file', file);
  form.append('preview_available', String(previewAvailable));
  if (thumbnail) form.append('thumbnail', thumbnail);
  return requestJson('/api/jt-files/upload', { method: 'POST', body: form });
}

export function addJTFileToTeamcenterVisualization(file) {
  const form = new FormData();
  form.append('file', file);
  return requestJson('/add-to-teamcenter-visualization', { method: 'POST', body: form });
}
