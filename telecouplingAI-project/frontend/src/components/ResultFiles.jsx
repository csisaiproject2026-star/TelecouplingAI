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
import { Download, AlertCircle } from 'lucide-react';

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

export default function ResultFiles({ files }) {
  if (!files || files.length === 0) return null;
  return (
    <div className="p-4 bg-gray-50 rounded-2xl border border-gray-200">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Result Files
      </div>
      <ul className="space-y-2">
        {files.map((file, i) => (
          <FileRow key={i} file={file} />
        ))}
      </ul>
    </div>
  );
}
