import { API_BASE } from '../../config.js';

export function getErrorMessage(error) {
  return error instanceof TypeError
    ? `Cannot reach the backend old at ${API_BASE}. Is it running?`
    : error.message;
}
