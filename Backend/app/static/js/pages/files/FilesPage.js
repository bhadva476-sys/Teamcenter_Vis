import {
  fetchUploadedFiles,
  openRegisteredFile,
  downloadRegisteredFile
} from '../../common/services/api.js';
import { createFileRow } from '../../common/components/DataTable.js';
import { setStatus } from '../../common/components/StatusMessage.js';
import { getErrorMessage } from '../../common/utils/errorUtils.js';
import { getElement } from '../../common/utils/domUtils.js';
import { getMyFiles } from '../my-files/MyFilesPage.js';
import { appState } from '../../state.js';

let filesPageInitialized = false;
let activeView = 'all';
let sidebar;
const FILES_PAGE_SIZE = 10;

let filesHasMore = true;
let filesLoadingMore = false;
let filesRequestVersion = 0;

function getVisibleFiles() {
  const files = activeView === 'mine' ? getMyFiles(appState.files) : appState.files;
  const query = getElement('fileSearch').value.trim().toLocaleLowerCase();
  return {
    files,
    filteredFiles: files.filter(file => [
      file.id,
      file.filename,
      file.file_location,
      file.type,
      file.size,
      file.attribute_owner,
      file.download_url
      
    ].some(value => String(value ?? '').toLocaleLowerCase().includes(query))),
    query
  };
}

function renderFiles() {
  if (!filesPageInitialized) return;
  const { files, filteredFiles, query } = getVisibleFiles();
  const body = getElement('uploadedFilesBody');
  const rows = document.createDocumentFragment();
  filteredFiles.forEach(file => {
    rows.appendChild(
      createFileRow(file, activeView, openInTeamcenterVisualization, downloadFile)
    );
  });
  body.replaceChildren(rows);

  const status = getElement('fileListStatus');
  if (!files.length) {
    setStatus(
      status,
      activeView === 'mine'
        ? 'No files are registered to local-user yet.'
        : 'No JT files have been uploaded to the server yet.'
    );
  } else if (!filteredFiles.length) {
    setStatus(status, `No uploaded files match "${getElement('fileSearch').value.trim()}".`);
  } else {
    setStatus(
      status,
      query
        ? `Showing ${filteredFiles.length} of ${files.length} uploaded file(s).`
        : `Showing ${filteredFiles.length} most recent uploaded file(s).`
    );
  }
}

async function openInTeamcenterVisualization(file, button) {
  button.disabled = true;
  const status = getElement('fileListStatus');
  setStatus(status, `Opening ${file.filename} in Teamcenter Visualization...`);
  try {
    await openRegisteredFile(file.id);
    setStatus(status, `${file.filename} opened in Teamcenter Visualization.`);
  } catch (error) {
    setStatus(status, getErrorMessage(error), true);
  } finally {
    button.disabled = false;
  }
}

async function downloadFile(file, button) {
  alert(`Downloading ${file.filename}...`);
  button.disabled = true;
  const status = getElement('fileListStatus');
  setStatus(status, `Downloading ${file.filename}...`);
  try {
    await downloadRegisteredFile(file.id);
    setStatus(status, `${file.filename} downloaded.`);
  } catch (error) {
    setStatus(status, getErrorMessage(error), true);
  } finally {
    button.disabled = false;
  }
}

// export async function refreshFiles(forceRefresh = false) {
//   if (appState.filesRequest) {
//     if (forceRefresh) appState.refreshQueued = true;
//     return appState.filesRequest;
//   }
//   if (appState.filesLoaded && !forceRefresh) return;

//   const refreshButton = getElement('refreshFilesBtn');
//   const status = getElement('fileListStatus');
//   refreshButton.disabled = true;
//   setStatus(status, 'Loading uploaded files...');

//   appState.filesRequest = (async () => {
//     try {
//       const data = await fetchUploadedFiles();
//       appState.files = data.files;
//       appState.filesLoaded = true;
//       sidebar.setCounts(appState.files.length, getMyFiles(appState.files).length);
//       renderFiles();
//     } catch (error) {
//       setStatus(status, getErrorMessage(error), true);
//     } finally {
//       refreshButton.disabled = false;
//       appState.filesRequest = null;
//       if (appState.refreshQueued) {
//         appState.refreshQueued = false;
//         refreshFiles(true);
//       }
//     }
//   })();
//   return appState.filesRequest;
// }

export async function refreshFiles(forceRefresh = false) {
  if (appState.filesRequest) {
    if (forceRefresh) appState.refreshQueued = true;
    return appState.filesRequest;
  }

  if (appState.filesLoaded && !forceRefresh) return;

  const refreshButton = getElement('refreshFilesBtn');
  const status = getElement('fileListStatus');

  refreshButton.disabled = true;
  setStatus(status, 'Loading uploaded files...');

  const requestVersion = ++filesRequestVersion;

  appState.filesRequest = (async () => {
    try {
      const data = await fetchUploadedFiles(FILES_PAGE_SIZE, 0);

      if (requestVersion !== filesRequestVersion) return;

      appState.files = data.files || [];
      appState.filesLoaded = true;
      filesHasMore = Boolean(data.has_more);

      sidebar.setCounts(
        appState.files.length,
        getMyFiles(appState.files).length
      );

      renderFiles();
    } catch (error) {
      if (requestVersion === filesRequestVersion) {
        setStatus(status, getErrorMessage(error), true);
      }
    } finally {
      appState.filesRequest = null;
      refreshButton.disabled = false;

      if (appState.refreshQueued) {
        appState.refreshQueued = false;
        refreshFiles(true);
      }
    }
  })();

  return appState.filesRequest;
}

async function loadMoreFiles() {
  if (
    filesLoadingMore ||
    !filesHasMore ||
    appState.filesRequest ||
    !appState.filesLoaded ||
    !filesPageInitialized
  ) {
    return;
  }

  filesLoadingMore = true;
  const requestVersion = filesRequestVersion;

  try {
    const offset = appState.files.length;

    const data = await fetchUploadedFiles(
      FILES_PAGE_SIZE,
      offset
    );

    // Ignore results from an older request after a refresh.
    if (requestVersion !== filesRequestVersion) return;

    const newFiles = data.files || [];

    // Append instead of replacing existing records.
    appState.files = [...appState.files, ...newFiles];
    filesHasMore = Boolean(data.has_more);

    sidebar.setCounts(
      appState.files.length,
      getMyFiles(appState.files).length
    );

    renderFiles();
  } catch (error) {
    console.error('Could not load more JT files:', error);
  } finally {
    filesLoadingMore = false;
  }
}


export function initializeFilesPage(sidebarController) {
  if (filesPageInitialized) return;
  sidebar = sidebarController;
  getElement('fileSearch').addEventListener('input', renderFiles);
  getElement('refreshFilesBtn').addEventListener('click', () => refreshFiles(true));
  filesPageInitialized = true;
  refreshFiles();
}

export function setFilesView(view) {
  activeView = view;
  const page = getElement('filesPage');
  page.classList.toggle('active', view !== 'upload');
  getElement('uploadPage').classList.toggle('active', view === 'upload');
  getElement('teamcenterVisualizationActionHeader').hidden = view !== 'mine';
  getElement('uploadedFilesTitle').textContent = view === 'mine' ? 'My Files' : 'All Files';
  getElement('filesSubtitle').textContent = view === 'mine'
    ? 'Files tagged local-user (authentication is not enabled)'
    : 'Files registered in your MySQL database';
  getElement('fileSearch').placeholder = view === 'mine'
    ? 'Search your files by name, path, type or ID...'
    : 'Search filename, path, owner, type or ID...';
  renderFiles();
   
}


document.addEventListener('scroll', event => {
  const container = event.target;

  if (!container.matches?.('.file-list-scroll')) return;

  const nearBottom =
    container.scrollTop + container.clientHeight >=
    container.scrollHeight - 100;

  if (nearBottom) {
    loadMoreFiles();
  }
}, true);
