/**
 * ResultFiles — displays downloadable result files from tool output.
 */
import { Download } from 'lucide-react';

const ICON = {
  download: '📦',
  csv:      '📊',
  image:    '🖼️',
  default:  '📄',
};

export default function ResultFiles({ files }) {
  if (!files || files.length === 0) return null;
  return (
    <div className="p-4 bg-gray-50 rounded-2xl border border-gray-200">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3">
        Result Files
      </div>
      <ul className="space-y-2">
        {files.map((file, i) => (
          <li key={i} className="flex items-center gap-2">
            <span>{ICON[file.render_type] || ICON.default}</span>
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
        ))}
      </ul>
    </div>
  );
}
