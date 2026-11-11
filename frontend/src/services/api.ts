import type {
  QueryValidationResponse,
  QueryExecutionResponse,
  ExportJobResponse,
  ReportResponse,
  QueryVersionResponse,
  AuditLogResponse,
  DatabaseHealthResponse,
} from '../types';

const API_BASE = '/api';

export const api = {
  // Health
  async getDbHealth(): Promise<DatabaseHealthResponse> {
    const res = await fetch(`${API_BASE}/health/db`);
    if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
    return res.json();
  },

  // Query Workspace
  async validateQuery(sql: string, database?: string): Promise<QueryValidationResponse> {
    const res = await fetch(`${API_BASE}/queries/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, database }),
    });
    if (!res.ok) throw new Error(`Validation failed: ${res.statusText}`);
    return res.json();
  },

  async executePreview(sql: string, database?: string, maxRows = 1000): Promise<QueryExecutionResponse> {
    const res = await fetch(`${API_BASE}/queries/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, database, max_rows: maxRows }),
    });
    if (!res.ok) throw new Error(`Execution failed: ${res.statusText}`);
    return res.json();
  },

  async cancelQuery(executionId: string): Promise<{ cancelled: boolean; message: string }> {
    const res = await fetch(`${API_BASE}/queries/cancel/${executionId}`, {
      method: 'POST',
    });
    return res.json();
  },

  // Export Jobs
  async createExportJob(payload: {
    report_title: string;
    sql: string;
    database?: string;
    include_sql?: boolean;
    query_id?: string;
    query_version_id?: string;
  }): Promise<ExportJobResponse> {
    const res = await fetch(`${API_BASE}/exports/jobs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Export creation failed: ${res.statusText}`);
    }
    return res.json();
  },

  async getExportJob(jobId: string): Promise<ExportJobResponse> {
    const res = await fetch(`${API_BASE}/exports/jobs/${jobId}`);
    if (!res.ok) throw new Error(`Failed to load job ${jobId}`);
    return res.json();
  },

  async listExportJobs(limit = 50, offset = 0, myJobsOnly = false): Promise<{ jobs: ExportJobResponse[]; total: number }> {
    const res = await fetch(`${API_BASE}/exports/jobs?limit=${limit}&offset=${offset}&my_jobs_only=${myJobsOnly}`);
    if (!res.ok) throw new Error(`Failed to list jobs`);
    return res.json();
  },

  async cancelExportJob(jobId: string): Promise<any> {
    const res = await fetch(`${API_BASE}/exports/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
    return res.json();
  },

  getDownloadUrl(jobId: string): string {
    return `${API_BASE}/exports/jobs/${jobId}/download`;
  },

  // Reports & Versioning
  async listReports(search?: string, category?: string, isActive?: boolean): Promise<{ reports: ReportResponse[]; total: number }> {
    const params = new URLSearchParams();
    if (search) params.set('search', search);
    if (category) params.set('category', category);
    if (isActive !== undefined) params.set('is_active', String(isActive));
    const res = await fetch(`${API_BASE}/reports?${params.toString()}`);
    if (!res.ok) throw new Error('Failed to load reports');
    return res.json();
  },

  async getReport(queryId: string): Promise<ReportResponse> {
    const res = await fetch(`${API_BASE}/reports/${queryId}`);
    if (!res.ok) throw new Error('Failed to load report');
    return res.json();
  },

  async createReport(payload: {
    title: string;
    description?: string;
    database?: string;
    category?: string;
    initial_sql: string;
  }): Promise<ReportResponse> {
    const res = await fetch(`${API_BASE}/reports`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create report');
    }
    return res.json();
  },

  async updateDraftVersion(versionId: string, sql: string, changeSummary?: string): Promise<QueryVersionResponse> {
    const res = await fetch(`${API_BASE}/reports/versions/${versionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sql, change_summary: changeSummary }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to update draft version');
    }
    return res.json();
  },

  async cloneToNewDraft(queryId: string, fromVersionId?: string, changeSummary?: string): Promise<QueryVersionResponse> {
    const res = await fetch(`${API_BASE}/reports/${queryId}/new-draft`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from_version_id: fromVersionId, change_summary: changeSummary }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to create new draft');
    }
    return res.json();
  },

  async testVersion(versionId: string, testSummary?: string): Promise<QueryVersionResponse> {
    const summary = testSummary || 'Preview execution validated successfully';
    const res = await fetch(`${API_BASE}/reports/versions/${versionId}/test?test_summary=${encodeURIComponent(summary)}`, {
      method: 'POST',
    });
    return res.json();
  },

  async approveVersion(versionId: string): Promise<QueryVersionResponse> {
    const res = await fetch(`${API_BASE}/reports/versions/${versionId}/approve`, {
      method: 'POST',
    });
    return res.json();
  },

  async activateVersion(versionId: string): Promise<QueryVersionResponse> {
    const res = await fetch(`${API_BASE}/reports/versions/${versionId}/activate`, {
      method: 'POST',
    });
    return res.json();
  },

  async toggleReportActive(queryId: string, isActive: boolean): Promise<ReportResponse> {
    const res = await fetch(`${API_BASE}/reports/${queryId}/toggle-active?is_active=${isActive}`, {
      method: 'POST',
    });
    return res.json();
  },

  async listVersions(queryId: string): Promise<QueryVersionResponse[]> {
    const res = await fetch(`${API_BASE}/reports/${queryId}/versions`);
    return res.json();
  },

  async getAuditHistory(queryId?: string): Promise<AuditLogResponse[]> {
    const url = queryId ? `${API_BASE}/reports/${queryId}/audit` : `${API_BASE}/reports/audit/all`;
    const res = await fetch(url);
    return res.json();
  },
};
