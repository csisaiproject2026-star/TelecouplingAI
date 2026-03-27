/**
 * WarningCard — displays a warning message from the agent.
 */
export default function WarningCard({ message }) {
  return (
    <div className="flex gap-2 p-4 bg-amber-50 border border-amber-200 rounded-2xl">
      <span className="text-amber-500 text-lg shrink-0">⚠️</span>
      <p className="text-sm text-amber-800">{message}</p>
    </div>
  );
}
