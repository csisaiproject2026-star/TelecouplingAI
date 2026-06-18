/**
 * ResultFiles — displays downloadable result files from tool output.
 *
 * Output files live server-side under /data/outputs/{session_id}/ and are
 * cleaned up by the backend (24h session TTL + LRU eviction past MAX_SESSIONS).
 * Chat history, however, is persisted client-side in localStorage forever, so
 * when an old conversation is reopened its download links may point at files
 * the server has already removed. To avoid silently broken links we probe each
 * URL with a HEAD request and render an "expired" hint when the file is gone.
 */
import { useState, useEffect } from 'react';
import { Download, AlertCircle, Archive } from 'lucide-react';

const ICON = {
  download: '📦',
  csv:      '📊',
  image:    '🖼️',
  default:  '📄',
};

// 'checking' | 'ok' | 'expired' — optimistic: only flips to 'expired' on a
// definitive 404/403 from the server, never on transient network errors.
function useAvailability(url) {
  const [state, setState] = useState('ok');
  useEffect(() => {
    if (!url) { setState('expired'); return; }
    let cancelled = false;
    fetch(url, { method: 'HEAD' })
      .then((res) => {
        if (cancelled) return;
        setState(res.status === 404 || res.status === 403 ? 'expired' : 'ok');
      })
      .catch(() => { /* transient/network error — stay optimistic */ });
    return () => { cancelled = true; };
  }, [url]);
  return state;
}

function FileRow({ file }) {
  const state = useAvailability(file.url);
  const icon = ICON[file.render_type] || ICON.default;

  if (state === 'expired') {
    return (
      <li className="flex items-center gap-2 text-gray-400">
        <span className="opacity-50">{icon}</span>
        <span className="text-sm truncate flex-1 line-through" title={file.filename}>
          {file.filename}
        </span>
        <span className="flex items-center gap-1 text-xs text-amber-600 shrink-0">
          <AlertCircle size={12} /> expired — re-run to regenerate
        </span>
      </li>
    );
  }

  return (
    <li className="flex items-center gap-2">
      <span>{icon}</span>
      <a
        href={file.url}
        download={file.filename}
        className="text-sm text-blue-600 hover:underline truncate flex-1"
      >
        {file.filename}
      </a>
      <a href={file.url} download={file.filename}
        className="p-1 hover:bg-blue-100 rounded-full text-blue-400 hover:text-blue-600 shrink-0">
        <Download size={14} />
      </a>
    </li>
  );
}

export default function ResultFiles({ files, sessionId }) {
  const [zipping, setZipping] = useState(false);
  if (!files || files.length === 0) return null;

  // Bundle ONLY this card's files (one tool run) — not the whole session. We
  // POST the exact internal paths of these files; the server re-validates each
  // is under this session's dir, zips them, and streams the blob back.
  const downloadZip = async () => {
    const paths = files.map((f) => f.path).filter(Boolean);
    if (paths.length === 0 || zipping) return;
    setZipping(true);
    try {
      const res = await fetch(`/api/download_zip/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ paths }),
      });
      if (!res.ok) {
        alert('These result files are no longer available (they may have expired). Re-run the tool to regenerate them.');
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'results.zip';
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert('Could not build the ZIP — please try downloading the files individually.');
    } finally {
      setZipping(false);
    }
  };

  return (
    <div className="p-4 bg-gray-50 rounded-2xl border border-gray-200">
      <div className="flex items-center justify-between mb-3 gap-2">
        <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          Result Files
        </div>
        {sessionId && files.some((f) => f.path) && (
          <button
            onClick={downloadZip}
            disabled={zipping}
            className="flex items-center gap-1 text-xs font-medium text-blue-600 hover:text-blue-700 bg-white border border-blue-200 hover:border-blue-400 px-2.5 py-1 rounded-full shadow-sm shrink-0 disabled:opacity-50"
            title="Download these result files as a single ZIP"
          >
            <Archive size={13} /> {zipping ? 'Zipping…' : 'Download all (.zip)'}
          </button>
        )}
      </div>
      <ul className="space-y-2">
        {files.map((file, i) => (
          <FileRow key={i} file={file} />
        ))}
      </ul>
    </div>
  );
}
