export function getElement(id) {
  const element = document.getElementById(id);
  if (!element) throw new Error(`Required page element #${id} was not found.`);
  return element;
}

export function addTableCell(row, value, className = '') {
  const cell = document.createElement('td');
  if (className) cell.className = className;
  cell.textContent = value ?? '';
  row.appendChild(cell);
  return cell;
}
