/**
 * ToolStatusCard — displays tool execution status with progress bar.
 */
export default function ToolStatusCard({ tool, message, progress }) {
  const isComplete = progress >= 100;
  return (
    <div className={`p-4 rounded-2xl border ${isComplete ? 'bg-green-50 border-green-200' : 'bg-blue-50 border-blue-200'}`}>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-sm font-semibold ${isComplete ? 'text-green-700' : 'text-blue-700'}`}>
          {isComplete ? '✅' : '⚙️'} {tool}
        </span>
        {progress !== undefined && (
          <span className={`text-xs font-bold ${isComplete ? 'text-green-600' : 'text-blue-600'}`}>
            {progress}%
          </span>
        )}
      </div>
      <div className={`text-sm ${isComplete ? 'text-green-600' : 'text-blue-600'}`}>{message}</div>
      {progress !== undefined && (
        <div className="mt-2 h-1.5 bg-blue-100 rounded-full overflow-hidden">
          <div
            className={`h-1.5 rounded-full transition-all duration-500 ${isComplete ? 'bg-green-500' : 'bg-blue-500'}`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
