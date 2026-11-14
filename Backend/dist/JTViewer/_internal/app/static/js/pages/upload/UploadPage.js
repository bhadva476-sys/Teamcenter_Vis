import {
  addJTFileToTeamcenterVisualization,
  convertJTFile,
  registerJTFile
} from '../../common/services/api.js';
import { setStatus } from '../../common/components/StatusMessage.js';
import { getErrorMessage } from '../../common/utils/errorUtils.js';
import { getElement } from '../../common/utils/domUtils.js';
import { refreshFiles } from '../files/FilesPage.js';
import { appState } from '../../state.js';
import { loadModelViewer } from './ModelViewer.js';

let previewState = 'idle';
let thumbnailUrl = null;

function setRegistrationStatus(text, isError = false) {
  setStatus(getElement('registrationStatus'), text, isError);
}

function updateRegistrationButton() {
  const hasThumbnail = getElement('thumbnailFile').files.length > 0;
  getElement('registerBtn').disabled =
    previewState === 'checking' ||
    (previewState === 'available' && !hasThumbnail);
}

function setEmptyState(title, message) {
  getElement('emptyState').querySelector('h2').textContent = title;
  getElement('emptyState').querySelector('p').textContent = message;
}

function clearSelectedFile() {
  getElement('registerBtn').style.display = 'none';
  getElement('registerBtn').disabled = false;
  getElement('addBtn').style.display = 'none';
  getElement('downloadBtn').style.display = 'none';
  getElement('selectedFile').style.display = 'none';
  getElement('previewStage').classList.remove('has-model');
  getElement('previewBadge').classList.remove('ready');
  getElement('previewBadge').textContent = 'Waiting for a file';
  setEmptyState(
    'Your preview starts here',
    'Select a JT file to convert it and preview the 3D model in this workspace.'
  );
  getElement('moreOptions').hidden = true;
  getElement('moreOptions').open = false;
  getElement('thumbnailFile').value = '';
  getElement('thumbnailFile').required = false;
  getElement('thumbnailSelection').textContent = '';
  getElement('thumbnailPreview').hidden = true;
  getElement('thumbnailPreview').removeAttribute('src');
  previewState = 'idle';
  if (thumbnailUrl) {
    URL.revokeObjectURL(thumbnailUrl);
    thumbnailUrl = null;
  }
  setRegistrationStatus('');
  getElement('viewer').removeAttribute('src');

  if (appState.downloadUrl) {
    URL.revokeObjectURL(appState.downloadUrl);
    appState.downloadUrl = null;
  }
}

async function handleFileChange() {
  const input = getElement('file');
  const file = input.files[0];
  clearSelectedFile();
  if (!file) return;

  if (!file.name.toLowerCase().endsWith('.jt')) {
    setStatus(getElement('status'), 'Please choose a .jt file.', true);
    input.value = '';
    return;
  }

  getElement('registerBtn').style.display = 'inline-flex';
  getElement('registerBtn').disabled = true;
  getElement('addBtn').style.display = 'inline-flex';
  const selectedFile = getElement('selectedFile');
  selectedFile.textContent = file.name;
  selectedFile.title = file.name;
  selectedFile.style.display = 'block';
  appState.downloadUrl = URL.createObjectURL(file);
  const downloadButton = getElement('downloadBtn');
  downloadButton.href = appState.downloadUrl;
  downloadButton.download = file.name;
  downloadButton.style.display = 'inline-flex';

  setStatus(getElement('status'), 'Uploading and converting... this can take a while for large files.');
  previewState = 'checking';

  try {
    const data = await convertJTFile(file);
    if (data.preview_available === false) {
      previewState = 'unavailable';
      getElement('previewBadge').textContent = 'No preview data';
      setEmptyState(
        'No preview data',
        'This JT file has no usable 3D geometry. You can still upload the original file.'
      );
      setStatus(getElement('status'), 'No preview data is available for this JT file.');
      updateRegistrationButton();
      return;
    }

    previewState = 'available';
    getElement('moreOptions').hidden = false;
    getElement('thumbnailFile').required = true;
    updateRegistrationButton();

    const viewerError = await loadModelViewer().then(() => null, error => error);
    if (viewerError) {
      getElement('previewBadge').textContent = 'Preview unavailable';
      setStatus(
        getElement('status'),
        `The model converted, but the 3D viewer could not be loaded: ${viewerError.message}`,
        true
      );
      return;
    }
    const previewStage = getElement('previewStage');
    const previewBadge = getElement('previewBadge');
    previewStage.classList.add('has-model');
    previewBadge.classList.remove('ready');
    previewBadge.textContent = 'Loading preview...';
    getElement('viewer').src = new URL(data.url, window.location.origin).href;
  } catch (error) {
    previewState = 'unavailable';
    const converterUnavailable = error.message.includes(
      'Aspose.3D could not be loaded'
    );
    const previewMessage = converterUnavailable
      ? 'No preview is available because the Aspose.3D converter is unavailable.'
      : getErrorMessage(error);
    getElement('previewBadge').textContent = 'No preview';
    setEmptyState(
      'No preview',
      'The original JT file can still be uploaded without a thumbnail.'
    );
    setStatus(
      getElement('status'),
      previewMessage,
      !converterUnavailable
    );
    updateRegistrationButton();
  }
}

function handleThumbnailChange() {
  const input = getElement('thumbnailFile');
  const thumbnail = input.files[0];
  if (thumbnailUrl) {
    URL.revokeObjectURL(thumbnailUrl);
    thumbnailUrl = null;
  }

  const preview = getElement('thumbnailPreview');
  if (!thumbnail) {
    preview.hidden = true;
    preview.removeAttribute('src');
    getElement('thumbnailSelection').textContent = '';
    updateRegistrationButton();
    return;
  }

  const allowedExtensions = ['.jpg', '.jpeg', '.png', '.webp'];
  const extension = thumbnail.name.slice(thumbnail.name.lastIndexOf('.')).toLowerCase();
  if (!allowedExtensions.includes(extension)) {
    input.value = '';
    getElement('thumbnailSelection').textContent = 'Choose a PNG, JPG, or WebP image.';
    updateRegistrationButton();
    return;
  }

  thumbnailUrl = URL.createObjectURL(thumbnail);
  preview.src = thumbnailUrl;
  preview.hidden = false;
  getElement('thumbnailSelection').textContent = thumbnail.name;
  updateRegistrationButton();
}

async function handleRegistration() {
  const file = getElement('file').files[0];
  const button = getElement('registerBtn');
  if (!file || button.disabled) return;

  const thumbnail = getElement('thumbnailFile').files[0] || null;
  if (previewState === 'available' && !thumbnail) {
    setRegistrationStatus(
      'Choose a thumbnail image before uploading this previewed model.',
      true
    );
    return;
  }

  button.disabled = true;
  getElement('registerBtnLabel').textContent = 'Uploading to server...';
  setRegistrationStatus('Saving the original JT file and registering its metadata...');
  try {
    const data = await registerJTFile(file, {
      thumbnail,
      previewAvailable: previewState === 'available'
    });
    setRegistrationStatus(
      `Registered successfully: ${data.filename} (${Number(data.file_size).toLocaleString()} bytes, record #${data.id}).`
    );
    await refreshFiles(true);
  } catch (error) {
    setRegistrationStatus(getErrorMessage(error), true);
  } finally {
    updateRegistrationButton();
    getElement('registerBtnLabel').textContent = 'Upload to server';
  }
}

async function handleOpenInTeamcenterVisualization() {
  const file = getElement('file').files[0];
  const button = getElement('addBtn');
  if (!file) return;

  button.disabled = true;
  setStatus(getElement('status'), 'Opening in Teamcenter Visualization...');
  try {
    await addJTFileToTeamcenterVisualization(file);
    setStatus(getElement('status'), 'Opened in Teamcenter Visualization.');
  } catch (error) {
    setStatus(getElement('status'), getErrorMessage(error), true);
  } finally {
    button.disabled = false;
  }
}

export function initializeUploadPage() {
  getElement('viewer').addEventListener('load', () => {
    getElement('previewBadge').classList.add('ready');
    getElement('previewBadge').textContent = 'Preview ready';
    setStatus(getElement('status'), 'Done. Drag to rotate, scroll to zoom.');
  });
  getElement('viewer').addEventListener('error', () => {
    getElement('previewBadge').classList.remove('ready');
    getElement('previewBadge').textContent = 'Preview unavailable';
    setStatus(
      getElement('status'),
      'The converted model could not be displayed. Try selecting the file again.',
      true
    );
  });
  getElement('file').addEventListener('change', handleFileChange);
  getElement('thumbnailFile').addEventListener('change', handleThumbnailChange);
  getElement('registerBtn').addEventListener('click', handleRegistration);
  getElement('addBtn').addEventListener('click', handleOpenInTeamcenterVisualization);
}
