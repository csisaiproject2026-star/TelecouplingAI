/**
 * ImageRenderer — displays a QGIS-rendered spatial preview image.
 */
export default function ImageRenderer({ url, filename, extent }) {
  return (
    <div className="rounded-2xl overflow-hidden border border-gray-200 shadow-sm">
      <img
        src={url}
        alt={filename}
        className="w-full object-cover"
        loading="lazy"
      />
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
