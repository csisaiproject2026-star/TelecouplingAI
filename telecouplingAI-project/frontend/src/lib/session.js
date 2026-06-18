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

const SESSION_KEY = "csis_session_id";

/**
 * Get or create a session ID stored in sessionStorage.
 * @returns {string} Session ID of the form "csis_<uuid>"
 */
export function getOrCreateSessionId() {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = `csis_${generateUUID()}`;
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

/**
 * Force-mint a fresh session ID and persist it. Used when the user starts a
 * new chat — without this the backend would keep replaying the previous
 * chat_history under the same session_id and the LLM would loop on stale
 * tool errors instead of actually re-dispatching tools.
 * @returns {string} The new session ID
 */
export function resetSessionId() {
  const id = `csis_${generateUUID()}`;
  sessionStorage.setItem(SESSION_KEY, id);
  return id;
}
