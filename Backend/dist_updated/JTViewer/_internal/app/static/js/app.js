import { FILES_PAGE_URL, UPLOAD_PAGE_URL } from './config.js';
import { initializeRouter } from './navigation/router.js';
import { getElement } from './common/utils/domUtils.js';

async function loadPageTemplates() {
  const [uploadResponse, filesResponse] = await Promise.all([
    fetch(UPLOAD_PAGE_URL),
    fetch(FILES_PAGE_URL)
  ]);
  if (!uploadResponse.ok || !filesResponse.ok) {
    throw new Error('The application page templates could not be loaded.');
  }
  const [uploadPage, filesPage] = await Promise.all([
    uploadResponse.text(),
    filesResponse.text()
  ]);
  getElement('pageMount').innerHTML = `${uploadPage}\n${filesPage}`;
}

loadPageTemplates()
  .then(initializeRouter)
  .catch(error => {
    const mount = getElement('pageMount');
    mount.textContent = error.message;
    mount.classList.add('error');
  });
