/**
 * SSE streaming client for CSIS chat API.
 *
 * Uses @microsoft/fetch-event-source so we can POST multipart/form-data with a
 * custom X-Session-ID header (the browser's native EventSource only supports
 * GET and no custom headers). The library also handles transparent reconnects
 * on transient network errors — those happen silently and never surface to the
 * UI; the user just keeps seeing the existing loading state.
 *
 * Combined with the backend's sse-starlette ping=15, this defeats the MSU WAF
 * idle timeout: the connection always has bytes flowing, so the WAF never
 * decides it's stale and never severs it.
 *
 * Upload-progress design: when the caller attaches files, we don't send them
 * together with the chat POST. Instead we first PUSH them to /api/upload via
 * a plain XMLHttpRequest (because fetch() has no upload-progress API) and
 * report bytes-uploaded to the UI as they go out. Once the upload finishes,
 * /api/chat is invoked with the message text only — backend reads the
 * already-uploaded files out of the session_manager. The user sees a real
 * progress bar while bytes are flowing instead of staring at a frozen spinner
 * for several minutes during big multipart POSTs through the MSU WAF.
 */

import { fetchEventSource } from '@microsoft/fetch-event-source';

class RetriableError extends Error {}
class FatalError extends Error {}

/**
 * Push a batch of File objects to /api/upload with byte-level progress.
 * @param {File[]} files
 * @param {string} sessionId
 * @param {(p: {loaded:number,total:number,percent:number}) => void} onProgress
 * @returns {Promise<void>}
 */
function uploadFilesWithProgress(files, sessionId, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    files.forEach((f) => {
      formData.append('files', f);
      // For folder uploads, webkitRelativePath holds the path within the chosen
      // folder (e.g. "Input/habitat_layers/eelgrass.tif"); the backend recreates
      // that structure so CSVs referencing sibling files still resolve. Plain
      // file picks / drag-drop have an empty webkitRelativePath → just the name.
      formData.append('paths', f.webkitRelativePath || f.name);
    });

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/upload');
    xhr.setRequestHeader('X-Session-ID', sessionId);

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable || !onProgress) return;
      const percent = (evt.loaded / evt.total) * 100;
      // status === 'uploading' while bytes still leaving the browser; once the
      // browser has pushed the last byte into the TCP socket the percent jumps
      // to 100, but the server hasn't necessarily received / parsed / committed
      // the upload yet (especially through the MSU WAF, where deep inspection
      // can run for minutes after the browser thinks it's "done"). Flip to
      // 'processing' so the UI keeps showing something instead of disappearing
      // at the very moment the slow wait actually starts.
      onProgress({
        loaded: evt.loaded,
        total: evt.total,
        percent,
        status: percent >= 100 ? 'processing' : 'uploading',
      });
    };

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        // Server has acknowledged the upload — hand off to the chat phase.
        // 'done' tells the UI it's safe to hide the upload bar; the chat
        // loading spinner takes over from here.
        if (onProgress) {
          onProgress({ loaded: 1, total: 1, percent: 100, status: 'done' });
        }
        resolve();
      } else {
        reject(new Error(`Upload failed: HTTP ${xhr.status}`));
      }
    };
    xhr.onerror = () => reject(new Error('Upload network error'));
    xhr.onabort = () => reject(new Error('Upload aborted'));

    xhr.send(formData);
  });
}

/**
 * Stream a chat message and receive SSE events. If files are attached they
 * are uploaded first via /api/upload (with progress) and then the chat call
 * carries only the message text.
 *
 * @param {string} message - User message text
 * @param {File[]} uploadedFiles - Optional files to upload
 * @param {string} sessionId - Session ID header
 * @param {string|null} model - Gemini model name (e.g. 'gemini-2.5-flash')
 * @param {function(Object): void} onEvent - Callback for each SSE event
 * @param {{onUploadProgress?: (p:{loaded:number,total:number,percent:number}) => void}} [opts]
 */
export async function streamChat(message, uploadedFiles, sessionId, model, onEvent, opts = {}) {
  // Phase 1: upload files (if any). This is the slow part for big rasters; we
  // run it as a separate XHR so xhr.upload.onprogress gives us byte-level
  // progress for the UI.
  if (uploadedFiles && uploadedFiles.length > 0) {
    await uploadFilesWithProgress(uploadedFiles, sessionId, opts.onUploadProgress);
  }

  // Phase 2: kick off the chat. The body is now tiny (just the message text)
  // so retries are cheap and safe, and the SSE stream can keep-alive freely.
  const formData = new FormData();
  formData.append('message', message);
  if (model) {
    formData.append('model', model);
  }
  // NOTE: files are intentionally NOT appended — backend pulls them from the
  // session_manager (where /api/upload above stashed them).

  // Track whether we've ever received a real event. Retrying after the agent
  // has already started producing output would re-trigger the whole agent run
  // on the server (until Tier 3 buffer+resume lands), so we only retry while
  // the stream is still in its "warm up" phase.
  let receivedAnyEvent = false;

  await fetchEventSource('/api/chat', {
    method: 'POST',
    headers: { 'X-Session-ID': sessionId },
    body: formData,
    openWhenHidden: true,  // keep streaming when tab is backgrounded

    async onopen(response) {
      if (response.ok && response.headers.get('content-type')?.includes('text/event-stream')) {
        return; // connection established
      }
      // Non-streaming response — server returned an HTML error page or similar.
      // 4xx is final, 5xx might be transient.
      if (response.status >= 400 && response.status < 500 && response.status !== 429) {
        throw new FatalError(`HTTP ${response.status}`);
      }
      throw new RetriableError(`HTTP ${response.status}`);
    },

    onmessage(ev) {
      // sse-starlette emits keep-alive comment frames (": ping") that the
      // library filters out, so anything that reaches us is a real event.
      if (!ev.data) return;
      receivedAnyEvent = true;
      try {
        onEvent(JSON.parse(ev.data));
      } catch (e) {
        console.warn('SSE parse error:', e, ev.data);
      }
    },

    onerror(err) {
      // Stop retrying if it's clearly fatal or we already started receiving
      // events (re-running the agent from scratch would be worse). With the
      // upload split out into its own XHR, the chat POST body is just text,
      // so we no longer need the "skip retry when files attached" guard.
      if (err instanceof FatalError) throw err;
      if (receivedAnyEvent) throw err;
      console.warn('[stream] transient error, will retry silently:', err?.message || err);
      // returning undefined lets fetch-event-source retry with its default backoff
    },
  });
}
