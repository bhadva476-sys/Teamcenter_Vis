export function getMyFiles(files) {
  return files.filter(file => file.attribute_owner === 'local-user');
}
