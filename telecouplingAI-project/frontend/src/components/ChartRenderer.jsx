/**
 * ChartRenderer — renders a bar/line chart from config.
 * config shape: { type, x_field, y_field, title, data }
 */
import { useEffect, useRef } from 'react';

export default function ChartRenderer({ config }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    if (!config || !canvasRef.current) return;
    let chartInstance = null;

    // Dynamically load Chart.js from CDN if not already loaded
    const renderChart = () => {
      const { Chart } = window;
      if (!Chart) return;

      const ctx = canvasRef.current.getContext('2d');
      if (chartInstance) chartInstance.destroy();

      const labels = (config.data || []).map(d => d[config.x_field] ?? '');
      const values = (config.data || []).map(d => parseFloat(d[config.y_field]) || 0);

      chartInstance = new Chart(ctx, {
        type: config.type || 'bar',
        data: {
          labels,
          datasets: [{
            label: config.y_field || 'Value',
            data: values,
            backgroundColor: 'rgba(66, 133, 244, 0.7)',
            borderColor: 'rgba(66, 133, 244, 1)',
            borderWidth: 1,
          }],
        },
        options: {
          responsive: true,
          plugins: {
            title: { display: !!config.title, text: config.title },
            legend: { display: false },
          },
        },
      });
    };

    if (window.Chart) {
      renderChart();
    } else {
      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js';
      script.onload = renderChart;
      document.head.appendChild(script);
    }

    return () => { if (chartInstance) chartInstance.destroy(); };
  }, [config]);

  if (!config) return null;
  return (
    <div className="p-4 bg-gray-50 rounded-2xl border border-gray-200">
      {config.title && <div className="text-sm font-medium text-gray-700 mb-3">{config.title}</div>}
      <canvas ref={canvasRef} />
    </div>
  );
}
