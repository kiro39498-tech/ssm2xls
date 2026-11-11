import React, { useState } from 'react';
import Editor from '@monaco-editor/react';
import { Play, CheckSquare, FileSpreadsheet, BookmarkPlus, XCircle, Clock, Table, AlertTriangle, CheckCircle } from 'lucide-react';
import { api } from '../services/api';
import type { QueryExecutionResponse, QueryValidationResponse } from '../types';

interface QueryWorkspaceProps {
  onJobCreated?: () => void;
}

const DEFAULT_SQL = `-- Write your T-SQL query below.
-- Only SELECT or CTE queries are permitted. Preview returns up to 1,000 rows.

SELECT 
    name AS database_name,
    database_id,
    create_date,
    compatibility_level,
    collation_name
FROM sys.databases
ORDER BY name ASC;
`;

export const QueryWorkspace: React.FC<QueryWorkspaceProps> = ({ onJobCreated }) => {
  const [sql, setSql] = useState<string>(DEFAULT_SQL);
  const [loading, setLoading] = useState<boolean>(false);
  const [validation, setValidation] = useState<QueryValidationResponse | null>(null);
  const [execution, setExecution] = useState<QueryExecutionResponse | null>(null);
  const [activeExecId, setActiveExecId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Export Modal state
  const [showExportModal, setShowExportModal] = useState<boolean>(false);
  const [exportTitle, setExportTitle] = useState<string>('My SQL Export');
  const [includeSqlInExport, setIncludeSqlInExport] = useState<boolean>(false);
  const [exportSubmitting, setExportSubmitting] = useState<boolean>(false);

  // Save Report Modal state
  const [showSaveModal, setShowSaveModal] = useState<boolean>(false);
  const [reportTitle, setReportTitle] = useState<string>('');
  const [reportDesc, setReportDesc] = useState<string>('');
  const [reportCat, setReportCat] = useState<string>('General');
  const [saveSubmitting, setSaveSubmitting] = useState<boolean>(false);

  // 1. Validate SQL
  const handleValidate = async () => {
    try {
      setErrorMsg(null);
      const res = await api.validateQuery(sql);
      setValidation(res);
      if (!res.is_valid) {
        setErrorMsg(res.errors.join('; '));
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Validation request failed');
    }
  };

  // 2. Run Limited Preview (Max 1000 rows)
  const handleRunPreview = async () => {
    try {
      setLoading(true);
      setErrorMsg(null);
      setExecution(null);

      // Pre-validate first
      const val = await api.validateQuery(sql);
      setValidation(val);
      if (!val.is_valid) {
        setErrorMsg(`SQL Validation Error: ${val.errors.join('; ')}`);
        setLoading(false);
        return;
      }

      const res = await api.executePreview(sql, undefined, 1000);
      setExecution(res);
      setActiveExecId(res.execution_id);

      if (res.status === 'failed') {
        setErrorMsg(res.error_message || 'Query execution failed on SQL Server');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to execute query preview');
    } finally {
      setLoading(false);
    }
  };

  // 3. Cancel Running Query
  const handleCancelQuery = async () => {
    if (!activeExecId) return;
    try {
      await api.cancelQuery(activeExecId);
      setErrorMsg('Cancellation signal delivered to ODBC driver.');
    } catch (err: any) {
      setErrorMsg(`Cancellation failed: ${err.message}`);
    }
  };

  // 4. Submit Export Job
  const handleCreateExport = async () => {
    try {
      setExportSubmitting(true);
      await api.createExportJob({
        report_title: exportTitle,
        sql,
        include_sql: includeSqlInExport,
      });
      setShowExportModal(false);
      if (onJobCreated) onJobCreated();
      alert(`Export job '${exportTitle}' created successfully! Check the Export Jobs tab.`);
    } catch (err: any) {
      alert(`Export creation failed: ${err.message}`);
    } finally {
      setExportSubmitting(false);
    }
  };

  // 5. Save as Report
  const handleSaveReport = async () => {
    if (!reportTitle.trim()) {
      alert('Please enter a report title.');
      return;
    }
    try {
      setSaveSubmitting(true);
      await api.createReport({
        title: reportTitle,
        description: reportDesc,
        category: reportCat,
        initial_sql: sql,
      });
      setShowSaveModal(false);
      alert(`Report '${reportTitle}' saved successfully with initial Draft v1!`);
    } catch (err: any) {
      alert(`Failed to save report: ${err.message}`);
    } finally {
      setSaveSubmitting(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', padding: '20px' }}>
      {/* Editor & Controls Card */}
      <div style={{
        backgroundColor: 'var(--surface-card)',
        borderRadius: '8px',
        border: '1px solid var(--surface-border)',
        overflow: 'hidden',
      }}>
        {/* Toolbar */}
        <div style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--surface-border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={handleRunPreview}
              disabled={loading}
              className="primary"
            >
              <Play size={14} />
              <span>{loading ? 'Executing...' : 'Run Preview (1,000 max)'}</span>
            </button>

            {loading && activeExecId && (
              <button onClick={handleCancelQuery} className="danger">
                <XCircle size={14} />
                <span>Cancel</span>
              </button>
            )}

            <button onClick={handleValidate} className="secondary" disabled={loading}>
              <CheckSquare size={14} />
              <span>Validate SQL</span>
            </button>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              onClick={() => setShowExportModal(true)}
              className="secondary"
              style={{ color: '#34d399', borderColor: '#059669' }}
            >
              <FileSpreadsheet size={14} />
              <span>Export to Excel</span>
            </button>

            <button
              onClick={() => setShowSaveModal(true)}
              className="secondary"
            >
              <BookmarkPlus size={14} />
              <span>Save as Report</span>
            </button>
          </div>
        </div>

        {/* Monaco Editor */}
        <div style={{ height: '320px', borderBottom: '1px solid var(--surface-border)' }}>
          <Editor
            height="100%"
            defaultLanguage="sql"
            theme="vs-dark"
            value={sql}
            onChange={(val) => setSql(val || '')}
            options={{
              minimap: { enabled: false },
              fontSize: 13,
              scrollBeyondLastLine: false,
              wordWrap: 'on',
              lineNumbers: 'on',
              automaticLayout: true,
            }}
          />
        </div>

        {/* Validation / Execution Status Bar */}
        <div style={{
          padding: '8px 16px',
          backgroundColor: '#0f172a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
          color: 'var(--text-muted)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            {validation && (
              <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                {validation.is_valid ? (
                  <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <CheckCircle size={14} /> SQL Valid (AST verified)
                  </span>
                ) : (
                  <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <AlertTriangle size={14} /> Invalid SQL
                  </span>
                )}
              </span>
            )}

            {execution && execution.status === 'success' && (
              <>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Clock size={13} /> {execution.duration_ms} ms
                </span>
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <Table size={13} /> {execution.row_count} rows ({execution.columns.length} columns)
                </span>
              </>
            )}
          </div>

          <div>Target: <strong>Local SQL Server (MSSQLSERVER)</strong></div>
        </div>
      </div>

      {/* Error Message Box */}
      {errorMsg && (
        <div style={{
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid #ef4444',
          borderRadius: '6px',
          padding: '12px 16px',
          color: '#f87171',
          fontSize: '13px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '8px',
        }}>
          <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: '2px' }} />
          <div>{errorMsg}</div>
        </div>
      )}

      {/* Preview Data Grid */}
      {execution && execution.status === 'success' && (
        <div style={{
          backgroundColor: 'var(--surface-card)',
          borderRadius: '8px',
          border: '1px solid var(--surface-border)',
          padding: '16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Query Preview Results</h3>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Showing {execution.rows.length} rows (capped at 1,000 for preview)
            </span>
          </div>

          <div className="data-table-container">
            <table className="data-table">
              <thead>
                <tr>
                  {execution.columns.map((col, idx) => (
                    <th key={idx}>
                      <div>{col.name}</div>
                      <span className="badge-type">{col.type_name}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {execution.rows.map((row, rIdx) => (
                  <tr key={rIdx}>
                    {execution.columns.map((col, cIdx) => {
                      const val = row[col.name];
                      return (
                        <td key={cIdx}>
                          {val === null ? (
                            <span className="badge-null">NULL</span>
                          ) : typeof val === 'boolean' ? (
                            val ? 'TRUE' : 'FALSE'
                          ) : (
                            String(val)
                          )}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Export to Excel Modal */}
      {showExportModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3 style={{ marginBottom: '16px' }}>Export SQL Results to Excel</h3>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '16px' }}>
              Submits a background export job. Large datasets (up to 1,000,000 rows) are streamed sequentially in constant-memory mode.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 500 }}>
                  Report Title
                </label>
                <input
                  type="text"
                  value={exportTitle}
                  onChange={(e) => setExportTitle(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <input
                  type="checkbox"
                  id="includeSql"
                  checked={includeSqlInExport}
                  onChange={(e) => setIncludeSqlInExport(e.target.checked)}
                />
                <label htmlFor="includeSql" style={{ fontSize: '12px', cursor: 'pointer' }}>
                  Include SQL query on Report Information sheet (Developer Export)
                </label>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowExportModal(false)} className="secondary">
                Cancel
              </button>
              <button onClick={handleCreateExport} disabled={exportSubmitting} className="primary">
                {exportSubmitting ? 'Queueing...' : 'Start Export Job'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Save as Report Modal */}
      {showSaveModal && (
        <div className="modal-overlay">
          <div className="modal-card">
            <h3 style={{ marginBottom: '16px' }}>Save Query as Managed Report</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 500 }}>
                  Report Title *
                </label>
                <input
                  type="text"
                  placeholder="e.g. Monthly Active Users by Region"
                  value={reportTitle}
                  onChange={(e) => setReportTitle(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 500 }}>
                  Category
                </label>
                <select
                  value={reportCat}
                  onChange={(e) => setReportCat(e.target.value)}
                  style={{ width: '100%' }}
                >
                  <option value="General">General</option>
                  <option value="Finance">Finance</option>
                  <option value="Operations">Operations</option>
                  <option value="Sales">Sales</option>
                  <option value="Analytics">Analytics</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', marginBottom: '4px', fontWeight: 500 }}>
                  Description
                </label>
                <textarea
                  rows={3}
                  placeholder="Briefly describe the purpose of this report..."
                  value={reportDesc}
                  onChange={(e) => setReportDesc(e.target.value)}
                  style={{ width: '100%', resize: 'vertical' }}
                />
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button onClick={() => setShowSaveModal(false)} className="secondary">
                Cancel
              </button>
              <button onClick={handleSaveReport} disabled={saveSubmitting} className="primary">
                {saveSubmitting ? 'Saving...' : 'Save Draft v1'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
