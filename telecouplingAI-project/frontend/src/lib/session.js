/**
 * Session ID management for CSIS frontend.
 */

/**
 * Generate a UUID v4 — works in both HTTP and HTTPS contexts.
 * crypto.randomUUID() requires a secure context (HTTPS/localhost),
 * so we fall back to a manual implementation for plain HTTP.
 */
function generateUUID() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  // Fallback: manual UUID v4 using Math.random
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

/**
 * Get or create a session ID stored in sessionStorage.
 * @returns {string} Session ID of the form "csis_<uuid>"
 */
export function getOrCreateSessionId() {
  const key = "csis_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `csis_${generateUUID()}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}
