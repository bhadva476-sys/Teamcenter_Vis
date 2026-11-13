export function setStatus(element, text, isError = false) {
  element.textContent = text;
  element.classList.toggle('error', isError);
}
