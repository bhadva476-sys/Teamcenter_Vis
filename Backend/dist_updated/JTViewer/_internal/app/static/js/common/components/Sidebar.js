import { getElement } from '../utils/domUtils.js';

export function initializeSidebar(onNavigate) {
  const buttons = document.querySelectorAll('.sidebar-nav-button');
  buttons.forEach(button => {
    button.addEventListener('click', () => onNavigate(button.dataset.view));
  });

  return {
    setActiveView(view) {
      buttons.forEach(button => {
        button.setAttribute('aria-current', button.dataset.view === view ? 'page' : 'false');
      });
    },
    setCounts(allCount, myCount) {
      getElement('allFilesCount').textContent = String(allCount);
      getElement('myFilesCount').textContent = String(myCount);
    }
  };
}
