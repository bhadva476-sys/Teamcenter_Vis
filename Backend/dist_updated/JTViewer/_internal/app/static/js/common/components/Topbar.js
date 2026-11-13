import { getElement } from '../utils/domUtils.js';

export function setPageTitle(title) {
  getElement('pageTitle').textContent = title;
}
