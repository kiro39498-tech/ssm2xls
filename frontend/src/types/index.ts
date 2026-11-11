export interface ColumnMetadata {
  name: string;
  type_name: string;
  precision?: number | null;
  scale?: number | null;
  nullable?: boolean | null;
}

export interface QueryValidationResponse {
  is_valid: boolean;
  errors: string[];
  statement_type?: string | null;
  tables_referenced: string[];
  normalized_sql?: string | null;
}

export interface QueryExecutionResponse {
  execution_id: string;
  status: 'success' | 'cancelled' | 'failed';
  row_count: number;
  duration_ms: number;
  columns: ColumnMetadata[];
  rows: Record<string, any>[];
  error_message?: string | null;
}

export interface ExportJobResponse {
  id: string;
  report_title: string;
  database_name: string;
  status: 'Pending' | 'Running' | 'Completed' | 'Failed' | 'Cancelled';
  progress_pct: number;
  rows_exported: number;
  file_size_bytes: number;
  error_message?: string | null;
  execution_duration_ms: number;
  requested_by: string;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  expires_at: string;
  download_available: boolean;
}

export interface QueryVersionResponse {
  id: string;
  query_id: string;
  version_number: number;
  sql_text: string;
  parameters_schema_json?: string | null;
  status: 'Draft' | 'Tested' | 'Approved' | 'Active' | 'Archived';
  change_summary?: string | null;
  created_by: string;
  tested_by?: string | null;
  tested_at?: string | null;
  test_results_summary?: string | null;
  approved_by?: string | null;
  approved_at?: string | null;
  activated_by?: string | null;
  activated_at?: string | null;
  created_at: string;
}

export interface ReportResponse {
  id: string;
  title: string;
  description?: string | null;
  database_name: string;
  category: string;
  is_active: boolean;
  current_version_id?: string | null;
  current_version?: QueryVersionResponse | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface AuditLogResponse {
  id: number;
  query_id?: string | null;
  query_version_id?: string | null;
  executed_by: string;
  execution_type: string;
  database_name: string;
  duration_ms: number;
  rows_returned: number;
  status: string;
  error_message?: string | null;
  parameters_json?: string | null;
  executed_at: string;
}

export interface DatabaseHealthResponse {
  timestamp: string;
  sqlite: {
    status: string;
    connected: boolean;
    database_path?: string;
    journal_mode?: string;
    foreign_keys_enabled?: boolean;
    busy_timeout_ms?: number;
    error?: string;
  };
  sql_server: {
    status: string;
    connected: boolean;
    server?: string;
    server_instance?: string;
    database?: string;
    version?: string;
    driver?: string;
    error?: string;
  };
}
