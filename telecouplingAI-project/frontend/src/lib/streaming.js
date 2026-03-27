/**
 * SSE streaming client for CSIS chat API.
 */

/**
 * Stream a chat message and receive SSE events.
 * @param {string} message - User message text
 * @param {File[]} uploadedFiles - Optional files to upload
 * @param {string} sessionId - Session ID header
 * @param {string|null} model - Gemini model name (e.g. 'gemini-2.5-flash')
 * @param {function(Object): void} onEvent - Callback for each SSE event
 */
export async function streamChat(message, uploadedFiles, sessionId, model, onEvent) {
  const formData = new FormData();
  formData.append("message", message);
  if (model) {
    formData.append("model", model);
  }
  if (uploadedFiles && uploadedFiles.length > 0) {
    uploadedFiles.forEach((f) => formData.append("files", f));
  }

  // Use relative path — nginx proxies to backend (no hardcoded localhost)
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "X-Session-ID": sessionId },
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop(); // keep incomplete line in buffer
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(line.slice(6)));
        } catch (e) {
          console.warn("SSE parse error:", e, line);
        }
      }
    }
  }
}
