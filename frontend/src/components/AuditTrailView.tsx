import React, { useEffect, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import type { AuditLogResponse } from '../types';

export const AuditTrailView: React.FC = () => {
  const [logs, setLogs] = useState<AuditLogResponse[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchLogs = async () => {
    try {
      setLoading(true);
      const res = await api.getAuditHistory();
      setLogs(res);
    } catch (err: any) {
      alert(`Failed to load audit history: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

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
          <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Execution Audit Trail</h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Compliance history tracking all Preview and Export executions, durations, returned row counts, and masked parameters.
          </p>
        </div>

        <button onClick={fetchLogs} className="secondary" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp (UTC)</th>
              <th>Executed By</th>
              <th>Type</th>
              <th>Database</th>
              <th>Status</th>
              <th>Duration</th>
              <th>Rows</th>
              <th>Parameters</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                  No execution audit logs recorded yet.
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={log.id}>
                  <td style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {new Date(log.executed_at).toLocaleString()}
                  </td>
                  <td style={{ fontWeight: 500 }}>{log.executed_by}</td>
                  <td>
                    <span className="badge-type">{log.execution_type}</span>
                  </td>
                  <td>{log.database_name}</td>
                  <td>
                    {log.status === 'Success' ? (
                      <span className="badge badge-completed">Success</span>
                    ) : log.status === 'Cancelled' ? (
                      <span className="badge badge-cancelled">Cancelled</span>
                    ) : (
                      <span className="badge badge-failed" title={log.error_message || ''}>
                        Failed
                      </span>
                    )}
                  </td>
                  <td>{log.duration_ms} ms</td>
                  <td>{log.rows_returned.toLocaleString()}</td>
                  <td style={{ fontSize: '11px', color: 'var(--text-muted)', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {log.parameters_json || '-'}
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
