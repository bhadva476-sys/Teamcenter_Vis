import { setPageTitle } from '../common/components/Topbar.js';
import { initializeSidebar } from '../common/components/Sidebar.js';
import { initializeFilesPage, setFilesView } from '../pages/files/FilesPage.js';
import { initializeUploadPage } from '../pages/upload/UploadPage.js';
import { getElement } from '../common/utils/domUtils.js';
import { appState } from '../state.js';

export function initializeRouter() {
  let sidebar;
  sidebar = initializeSidebar(view => navigate(view, sidebar));
  initializeFilesPage(sidebar);
  initializeUploadPage();
  navigate('all', sidebar);
}

function navigate(view, sidebar) {
  if (!['all', 'mine', 'upload'].includes(view)) return;
  appState.activeView = view;
  const title = view === 'upload' ? 'Upload File' : view === 'mine' ? 'My Files' : 'All Files';
  setPageTitle(title);
  sidebar.setActiveView(view);
  setFilesView(view);
}
