import React from 'react';
import { FileText, Download } from 'lucide-react';
import { API_URL as API } from '../../config';
import { useToast } from '../../context/ToastContext';

interface Props {
  token: string | null;
}

const DashboardExport = React.memo(({ token }: Props) => {
  const { toast } = useToast();
  const headers = { Authorization: `Bearer ${token}` };

  const exportQueries = async (format: string) => {
    try {
      const r = await fetch(`${API}/api/user/export?format=${format}`, { headers });
      if (format === 'csv') {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'ecoquery-export.csv'; a.click();
        URL.revokeObjectURL(url);
      } else {
        const d = await r.json();
        const blob = new Blob([JSON.stringify(d, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'ecoquery-export.json'; a.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) { toast.error('Export failed. Please try again.'); }
  };

  const downloadReport = async () => {
    try {
      const r = await fetch(`${API}/api/user/sustainability-report`, { headers });
      const d = await r.json();
      const blob = new Blob([d.text_report || JSON.stringify(d, null, 2)], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = 'ecoquery-sustainability-report.txt'; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { toast.error('Failed to download report'); }
  };

  return (
    <div className="dashboard-section">
      <h2><FileText size={20} /> Data Export</h2>
      <p className="dashboard-hint" style={{ marginBottom: '0.75rem' }}>Download your query history for offline analysis.</p>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button className="btn btn-secondary" onClick={() => exportQueries('csv')}><Download size={16} /> Export CSV</button>
        <button className="btn btn-secondary" onClick={() => exportQueries('json')}><Download size={16} /> Export JSON</button>
        <button className="btn btn-primary" onClick={downloadReport}><FileText size={16} /> Sustainability Report</button>
      </div>
    </div>
  );
});

export default DashboardExport;
