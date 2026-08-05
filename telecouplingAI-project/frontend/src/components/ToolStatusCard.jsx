/**
 * ToolStatusCard — displays tool execution status with progress bar.
 */
export default function ToolStatusCard({ tool, message, progress, status }) {
  const isComplete = progress >= 100;
  const isWarning = status === 'warning';
  const cardClass = isWarning
    ? 'bg-amber-50 border-amber-200'
    : isComplete
      ? 'bg-green-50 border-green-200'
      : 'bg-blue-50 border-blue-200';
  const textClass = isWarning
    ? 'text-amber-700'
    : isComplete
      ? 'text-green-700'
      : 'text-blue-700';
  const progressClass = isWarning
    ? 'bg-amber-500'
    : isComplete
      ? 'bg-green-500'
      : 'bg-blue-500';
  return (
    <div className={`p-4 rounded-2xl border ${cardClass}`}>
      <div className="flex items-center justify-between mb-1">
        <span className={`text-sm font-semibold ${textClass}`}>
          {isWarning ? '⚠️' : isComplete ? '✅' : '⚙️'} {tool}
        </span>
        {progress !== undefined && (
          <span className={`text-xs font-bold ${textClass}`}>
            {progress}%
          </span>
        )}
      </div>
      <div className={`text-sm ${textClass}`}>{message}</div>
      {progress !== undefined && (
        <div className="mt-2 h-1.5 bg-blue-100 rounded-full overflow-hidden">
          <div
            className={`h-1.5 rounded-full transition-all duration-500 ${progressClass}`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  );
}
