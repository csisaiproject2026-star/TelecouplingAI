/**
 * CsvRenderer — displays CSV output as a scrollable table with row count.
 */
export default function CsvRenderer({ filename, rows, columns }) {
  if (!rows || !columns || rows.length === 0) return null;
  return (
    <div className="rounded-2xl border border-gray-200 overflow-hidden shadow-sm">
      <div className="bg-gray-50 px-4 py-2 flex items-center justify-between border-b border-gray-200">
        <span className="text-sm font-medium text-gray-700">📊 {filename}</span>
        <span className="text-xs text-gray-400">{rows.length} rows × {columns.length} cols</span>
      </div>
      <div className="overflow-x-auto max-h-72">
        <table className="min-w-full text-xs">
          <thead className="bg-gray-100 sticky top-0">
            <tr>
              {columns.map((col, i) => (
                <th key={i} className="px-3 py-2 text-left font-semibold text-gray-600 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, ri) => (
              <tr key={ri} className={ri % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                {columns.map((col, ci) => (
                  <td key={ci} className="px-3 py-1.5 text-gray-700 whitespace-nowrap">
                    {row[col] ?? ''}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
