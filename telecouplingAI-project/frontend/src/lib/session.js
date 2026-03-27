/**
 * Session ID management for CSIS frontend.
 */

/**
 * Get or create a session ID stored in sessionStorage.
 * @returns {string} Session ID of the form "csis_<uuid>"
 */
export function getOrCreateSessionId() {
  const key = "csis_session_id";
  let id = sessionStorage.getItem(key);
  if (!id) {
    id = `csis_${crypto.randomUUID()}`;
    sessionStorage.setItem(key, id);
  }
  return id;
}
