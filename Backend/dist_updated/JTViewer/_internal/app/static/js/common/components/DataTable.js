import { formatDate } from '../utils/dateUtils.js';
import { formatFileSize } from '../utils/fileUtils.js';
import { addTableCell } from '../utils/domUtils.js';

export function createFileRow(file, view, onOpenInTeamcenterVisualization, onDownloadFile) {
  const row = document.createElement('tr');
  addTableCell(row, `#${file.id}`, 'file-id');
  addTableCell(row, file.filename, 'file-name-cell');

  const thumbnailCell = document.createElement('td');
  thumbnailCell.className = 'file-thumbnail-cell';
  if (file.thumbnail_url) {
    const thumbnail = document.createElement('img');
    thumbnail.className = 'file-thumbnail';
    thumbnail.src = file.thumbnail_url;
    thumbnail.alt = `Thumbnail for ${file.filename}`;
    thumbnail.loading = 'lazy';
    thumbnail.addEventListener('error', () => {
      thumbnail.replaceWith(document.createTextNode('Thumbnail unavailable'));
    }, { once: true });
    thumbnailCell.appendChild(thumbnail);
  } else {
    thumbnailCell.textContent = 'No Thumbnail';
  }
  row.appendChild(thumbnailCell);

  const typeCell = document.createElement('td');
  const typeBadge = document.createElement('span');
  typeBadge.className = 'file-type-badge';
  typeBadge.textContent = file.type;
  typeCell.appendChild(typeBadge);
  row.appendChild(typeCell);

  addTableCell(row, formatFileSize(file.size), 'file-size-cell');
  addTableCell(row, formatDate(file.createdat));
  addTableCell(row, file.attribute_owner, 'file-owner-cell');


  if (view === 'mine') {
    const actionCell = document.createElement('td');
    const openButton = document.createElement('button');
    openButton.className = 'teamcenter-visualization-button';
    openButton.type = 'button';
    openButton.title = 'Open in Teamcenter Visualization';
    openButton.textContent = 'Teamcenter Visualization';
    openButton.setAttribute('aria-label', `Open ${file.filename} in Teamcenter Visualization`);
    openButton.addEventListener(
      'click',
      () => onOpenInTeamcenterVisualization(file, openButton)
    );
    actionCell.appendChild(openButton);
    row.appendChild(actionCell);
  }
  const downloadCell = document.createElement('td');
  const downloadButton = document.createElement('button');
  downloadButton.type = 'button';
  downloadButton.textContent = 'Download File';
  downloadButton.className = 'btn btn-download';
  downloadButton.addEventListener('click', () => onDownloadFile(file, downloadButton));
  downloadCell.appendChild(downloadButton);
  row.appendChild(downloadCell);

  return row;
}
