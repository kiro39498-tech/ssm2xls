import React, { useEffect, useState } from 'react';
import { History, Copy, CheckCircle, ShieldCheck, Power, RefreshCw, ArrowUpRight } from 'lucide-react';
import { api } from '../services/api';
import type { ReportResponse, QueryVersionResponse } from '../types';

interface SavedReportsViewProps {
  onLoadQueryIntoEditor: (sql: string) => void;
}

export const SavedReportsView: React.FC<SavedReportsViewProps> = ({ onLoadQueryIntoEditor }) => {
  const [reports, setReports] = useState<ReportResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportResponse | null>(null);
  const [versions, setVersions] = useState<QueryVersionResponse[]>([]);
  const [showVersionModal, setShowVersionModal] = useState(false);
  const [cloning, setCloning] = useState(false);

  const fetchReports = async () => {
    try {
      setLoading(true);
      const res = await api.listReports();
      setReports(res.reports);
    } catch (err: any) {
      alert(`Failed to load reports: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  const openVersions = async (report: ReportResponse) => {
    try {
      setSelectedReport(report);
      const vers = await api.listVersions(report.id);
      setVersions(vers);
      setShowVersionModal(true);
    } catch (err: any) {
      alert(`Failed to load version history: ${err.message}`);
    }
  };

  const handleTest = async (versionId: string) => {
    try {
      await api.testVersion(versionId);
      if (selectedReport) openVersions(selectedReport);
      fetchReports();
    } catch (err: any) {
      alert(`Test transition failed: ${err.message}`);
    }
  };

  const handleApprove = async (versionId: string) => {
    try {
      await api.approveVersion(versionId);
      if (selectedReport) openVersions(selectedReport);
      fetchReports();
    } catch (err: any) {
      alert(`Approval failed: ${err.message}`);
    }
  };

  const handleActivate = async (versionId: string) => {
    try {
      await api.activateVersion(versionId);
      if (selectedReport) openVersions(selectedReport);
      fetchReports();
    } catch (err: any) {
      alert(`Activation failed: ${err.message}`);
    }
  };

  const handleCloneDraft = async (reportId: string, versionId: string) => {
    try {
      setCloning(true);
      const newDraft = await api.cloneToNewDraft(reportId, versionId, 'Cloned from version history');
      alert(`New Draft v${newDraft.version_number} created successfully!`);
      if (selectedReport) openVersions(selectedReport);
      fetchReports();
    } catch (err: any) {
      alert(`Failed to clone draft: ${err.message}`);
    } finally {
      setCloning(false);
    }
  };

  const handleToggleActive = async (reportId: string, currentActive: boolean) => {
    try {
      await api.toggleReportActive(reportId, !currentActive);
      fetchReports();
    } catch (err: any) {
      alert(`Toggle failed: ${err.message}`);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Draft':
        return <span className="badge badge-pending">Draft</span>;
      case 'Tested':
        return <span className="badge badge-running">Tested</span>;
      case 'Approved':
        return <span className="badge badge-completed">Approved</span>;
      case 'Active':
        return <span className="badge" style={{ backgroundColor: '#2563eb', color: '#fff' }}>Active</span>;
      case 'Archived':
        return <span className="badge badge-cancelled">Archived</span>;
      default:
        return <span className="badge">{status}</span>;
    }
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
          <h2 style={{ fontSize: '16px', fontWeight: 600 }}>Saved Reports & Version Catalog</h2>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Immutable versioning lifecycle: Draft → Tested → Approved → Active. Approved queries cannot be edited in place.
          </p>
        </div>

        <button onClick={fetchReports} className="secondary" disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Reports Table */}
      <div className="data-table-container">
        <table className="data-table">
          <thead>
            <tr>
              <th>Title</th>
              <th>Category</th>
              <th>Current Version</th>
              <th>Status</th>
              <th>Database</th>
              <th>Created By</th>
              <th>Active</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {reports.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '32px', color: 'var(--text-muted)' }}>
                  No saved reports yet. Save a query draft from the Query Workspace!
                </td>
              </tr>
            ) : (
              reports.map((rep) => (
                <tr key={rep.id}>
                  <td style={{ fontWeight: 500 }}>
                    <div>{rep.title}</div>
                    {rep.description && (
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{rep.description}</div>
                    )}
                  </td>
                  <td>
                    <span className="badge-type">{rep.category}</span>
                  </td>
                  <td>v{rep.current_version?.version_number ?? 1}</td>
                  <td>{getStatusBadge(rep.current_version?.status ?? 'Draft')}</td>
                  <td>{rep.database_name}</td>
                  <td>{rep.created_by}</td>
                  <td>
                    <button
                      onClick={() => handleToggleActive(rep.id, rep.is_active)}
                      className={rep.is_active ? 'secondary' : 'danger'}
                      style={{ padding: '2px 8px', fontSize: '11px' }}
                      title={rep.is_active ? 'Click to disable report' : 'Click to enable report'}
                    >
                      <Power size={11} />
                      <span>{rep.is_active ? 'Enabled' : 'Disabled'}</span>
                    </button>
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        onClick={() => openVersions(rep)}
                        className="secondary"
                        style={{ padding: '4px 8px', fontSize: '11px' }}
                      >
                        <History size={12} />
                        <span>Versions ({rep.current_version?.version_number ?? 1})</span>
                      </button>

                      {rep.current_version?.sql_text && (
                        <button
                          onClick={() => onLoadQueryIntoEditor(rep.current_version!.sql_text)}
                          className="primary"
                          style={{ padding: '4px 8px', fontSize: '11px' }}
                          title="Load SQL into Query Workspace"
                        >
                          <ArrowUpRight size={12} />
                          <span>Edit</span>
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Version History Modal */}
      {showVersionModal && selectedReport && (
        <div className="modal-overlay">
          <div className="modal-card" style={{ maxWidth: '800px', maxHeight: '85vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div>
                <h3 style={{ fontSize: '16px' }}>Version History: {selectedReport.title}</h3>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Immutability: Approved/Active queries are immutable. Use "Clone to Draft" to make changes.
                </div>
              </div>
              <button onClick={() => setShowVersionModal(false)} className="secondary">Close</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {versions.map((ver) => (
                <div
                  key={ver.id}
                  style={{
                    backgroundColor: '#0f172a',
                    border: '1px solid var(--surface-border)',
                    borderRadius: '6px',
                    padding: '14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ fontWeight: 700, fontSize: '14px' }}>Version {ver.version_number}</span>
                      {getStatusBadge(ver.status)}
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Created by {ver.created_by} on {new Date(ver.created_at).toLocaleDateString()}
                      </span>
                    </div>

                    {/* Workflow State Buttons */}
                    <div style={{ display: 'flex', gap: '6px' }}>
                      {ver.status === 'Draft' && (
                        <button
                          onClick={() => handleTest(ver.id)}
                          className="secondary"
                          style={{ padding: '3px 8px', fontSize: '11px' }}
                        >
                          <CheckCircle size={11} /> Mark Tested
                        </button>
                      )}

                      {ver.status === 'Tested' && (
                        <button
                          onClick={() => handleApprove(ver.id)}
                          className="secondary"
                          style={{ padding: '3px 8px', fontSize: '11px', color: '#34d399', borderColor: '#10b981' }}
                        >
                          <ShieldCheck size={11} /> Approve
                        </button>
                      )}

                      {ver.status === 'Approved' && (
                        <button
                          onClick={() => handleActivate(ver.id)}
                          className="primary"
                          style={{ padding: '3px 8px', fontSize: '11px' }}
                        >
                          Activate (Production)
                        </button>
                      )}

                      <button
                        onClick={() => handleCloneDraft(selectedReport.id, ver.id)}
                        disabled={cloning}
                        className="secondary"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                        title="Clone this version into a new Draft"
                      >
                        <Copy size={11} /> Clone to Draft
                      </button>

                      <button
                        onClick={() => {
                          onLoadQueryIntoEditor(ver.sql_text);
                          setShowVersionModal(false);
                        }}
                        className="secondary"
                        style={{ padding: '3px 8px', fontSize: '11px' }}
                      >
                        Load SQL
                      </button>
                    </div>
                  </div>

                  {ver.change_summary && (
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
                      Change note: {ver.change_summary}
                    </div>
                  )}

                  <pre style={{
                    backgroundColor: '#1e293b',
                    padding: '8px',
                    borderRadius: '4px',
                    fontSize: '11px',
                    overflowX: 'auto',
                    fontFamily: 'monospace',
                  }}>
                    {ver.sql_text}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
