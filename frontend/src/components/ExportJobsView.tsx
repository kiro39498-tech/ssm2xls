import React, { useEffect, useState } from 'react';
import { Download, XCircle, RefreshCw, AlertCircle, FileSpreadsheet } from 'lucide-react';
import { api } from '../services/api';
import type { ExportJobResponse } from '../types';

export const ExportJobsView: React.FC = () => {
  const [jobs, setJobs] = useState<ExportJobResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const res = await api.listExportJobs(50, 0);
      setJobs(res.jobs);
      setErrorMsg(null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch export jobs');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
    // Poll every 3 seconds if any jobs are pending or running
    const interval = setInterval(() => {
      fetchJobs();
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleCancel = async (jobId: string) => {
    try {
      await api.cancelExportJob(jobId);
      fetchJobs();
    } catch (err: any) {
      alert(`Failed to cancel job: ${err.message}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Pending':
        return <span className="badge badge-pending">Pending</span>;
      case 'Running':
        return <span className="badge badge-running">Running</span>;
      case 'Completed':
        return <span className="badge badge-completed">Completed</span>;
      case 'Failed':
        return <span className="badge badge-failed">Failed</span>;
      case 'Cancelled':
        return <span className="badge badge-cancelled">Cancelled</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  const formatFileSize = (bytes: number) => {
    if (!bytes) return '0 B';
    const mb = bytes / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${(bytes / 1024).toFixed(1)} KB`;
  };

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: 'var(--surface-card)',
        padding: '16px 20px',
        borderRadius: '8px',
        border: '1px solid var(--surface-border)',
      }}>
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Export Jobs Queue</h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Database-backed background queue. Files are kept for 7 days before automatic purging.
          </p>
        </div>

        <button onClick={fetchJobs} className="secondary" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {errorMsg && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid #ef4444',
          borderRadius: '6px',
          padding: '12px',
          color: '#f87171',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <AlertCircle size={16} />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Jobs Table */}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Report Title</th>
              <th>Status</th>
              <th>Rows Exported</th>
              <th>File Size</th>
              <th>Duration</th>
              <th>Requested By</th>
              <th>Submitted At</th>
              <th>Expires At</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {jobs.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                  No export jobs queued yet. Create one from the Query Workspace.
                </td>
              </tr>
            ) : (
              jobs.map((job) => (
                <tr key={job.id}>
                  <td style={{ fontWeight: 500 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <FileSpreadsheet size={15} color="#34d399" />
                      <span>{job.report_title}</span>
                    </div>
                    {job.error_message && (
                      <div style={{ fontSize: '11px', color: '#f87171', marginTop: '2px' }} title={job.error_message}>
                        {job.error_message.slice(0, 80)}...
                      </div>
                    )}
                  </td>
                  <td>{getStatusBadge(job.status)}</td>
                  <td>{job.rows_exported.toLocaleString()}</td>
                  <td>{formatFileSize(job.file_size_bytes)}</td>
                  <td>{job.execution_duration_ms > 0 ? `${(job.execution_duration_ms / 1000).toFixed(1)}s` : '-'}</td>
                  <td>{job.requested_by}</td>
                  <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {new Date(job.created_at).toLocaleString()}
                  </td>
                  <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {new Date(job.expires_at).toLocaleDateString()}
                  </td>
                  <td>
                    {job.download_available ? (
                      <a
                        href={api.getDownloadUrl(job.id)}
                        download
                        style={{
                          backgroundColor: '#10b981',
                          color: '#fff',
                          padding: '6px 12px',
                          borderRadius: '6px',
                          textDecoration: 'none',
                          fontSize: '12px',
                          fontWeight: 500,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <Download size={13} />
                        <span>Download</span>
                      </a>
                    ) : job.status === 'Pending' || job.status === 'Running' ? (
                      <button
                        onClick={() => handleCancel(job.id)}
                        className="danger"
                        style={{ padding: '4px 10px', fontSize: '11px' }}
                      >
                        <XCircle size={12} />
                        <span>Cancel</span>
                      </button>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
