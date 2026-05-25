/**
 * ImageRenderer — displays a QGIS-rendered spatial preview image.
 *
 * Preview images live server-side and are cleaned up the same way result files
 * are (session TTL + LRU eviction), while chat history persists in the browser.
 * When an old conversation is reopened the image may be gone, so we catch the
 * <img> load error and show a graceful "expired" placeholder instead of the
 * browser's broken-image icon.
 */
import { useState } from 'react';
import { AlertCircle } from 'lucide-react';

export default function ImageRenderer({ url, filename, extent }) {
  const [broken, setBroken] = useState(false);

  return (
    <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-sm">
      {broken ? (
        <div className="flex flex-col items-center justify-center gap-2 py-10 bg-gray-50 text-gray-400">
          <AlertCircle size={28} className="text-amber-500" />
          <p className="text-sm">Preview expired</p>
          <p className="text-xs text-gray-400">Re-run the tool to regenerate this image</p>
        </div>
      ) : (
        <img
          src={url}
          alt={filename}
          className="w-full object-cover"
          loading="lazy"
          onError={() => setBroken(true)}
        />
      )}
      <div className="bg-gray-50 px-3 py-2 flex items-center justify-between">
        <span className="text-xs text-gray-500 truncate">{filename}</span>
        {extent && (
          <span className="text-xs text-gray-400 ml-2 shrink-0">
            [{extent.map(v => v.toFixed(2)).join(', ')}]
          </span>
        )}
      </div>
    </div>
  );
}
