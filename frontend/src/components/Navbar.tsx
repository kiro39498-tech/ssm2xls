import React, { useEffect, useState } from 'react';
import { Database, Terminal, FileSpreadsheet, BookmarkCheck, History, RefreshCw, AlertCircle, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';
import type { DatabaseHealthResponse } from '../types';

interface NavbarProps {
  activeTab: 'workspace' | 'exports' | 'reports' | 'audit';
  setActiveTab: (tab: 'workspace' | 'exports' | 'reports' | 'audit') => void;
  pendingJobsCount?: number;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab, pendingJobsCount = 0 }) => {
  const [health, setHealth] = useState<DatabaseHealthResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const data = await api.getDbHealth();
      setHealth(data);
    } catch {
      // Ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const isSqlConnected = health?.sql_server?.connected ?? false;

  return (
    <header style={{
      backgroundColor: 'var(--surface-card)',
      borderBottom: '1px solid var(--surface-border)',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: '60px',
      position: 'sticky',
      top: 0,
      zIndex: 100,
    }}>
      {/* Brand & Connectivity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            background: 'linear-gradient(135deg, #2563eb, #1d4ed8)',
            padding: '6px',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
          }}>
            <Database size={20} color="#ffffff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '15px', letterSpacing: '-0.3px' }}>SSMS2XLS</div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Internal SQL & Excel Portal</div>
          </div>
        </div>

        {/* Database Health Pill */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          padding: '4px 10px',
          borderRadius: '9999px',
          fontSize: '11px',
          fontWeight: 500,
          backgroundColor: isSqlConnected ? 'rgba(16, 185, 129, 0.15)' : 'rgba(245, 158, 11, 0.15)',
          color: isSqlConnected ? '#34d399' : '#fbbf24',
          border: `1px solid ${isSqlConnected ? '#10b981' : '#f59e0b'}`,
        }} title={health?.sql_server?.error || 'Connected to SQL Server instance'}>
          {isSqlConnected ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
          <span>{isSqlConnected ? 'SQL Server Connected' : 'SQL Server Degraded (Stopped)'}</span>
          <button
            onClick={fetchHealth}
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              color: 'inherit',
              display: 'flex',
              alignItems: 'center',
            }}
            title="Refresh database connectivity"
          >
            <RefreshCw size={11} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Tabs */}
      <nav style={{ display: 'flex', gap: '8px' }}>
        <button
          onClick={() => setActiveTab('workspace')}
          className={activeTab === 'workspace' ? 'primary' : 'secondary'}
        >
          <Terminal size={15} />
          <span>Query Workspace</span>
        </button>

        <button
          onClick={() => setActiveTab('exports')}
          className={activeTab === 'exports' ? 'primary' : 'secondary'}
          style={{ position: 'relative' }}
        >
          <FileSpreadsheet size={15} />
          <span>Export Jobs</span>
          {pendingJobsCount > 0 && (
            <span style={{
              background: '#f59e0b',
              color: '#000',
              borderRadius: '9999px',
              padding: '0 6px',
              fontSize: '10px',
              fontWeight: 700,
              marginLeft: '4px',
            }}>
              {pendingJobsCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('reports')}
          className={activeTab === 'reports' ? 'primary' : 'secondary'}
        >
          <BookmarkCheck size={15} />
          <span>Saved Reports</span>
        </button>

        <button
          onClick={() => setActiveTab('audit')}
          className={activeTab === 'audit' ? 'primary' : 'secondary'}
        >
          <History size={15} />
          <span>Audit Trail</span>
        </button>
      </nav>

      {/* Identity */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
        <span>User:</span>
        <span style={{ color: 'var(--text-main)', fontWeight: 600 }}>developer (Windows Auth)</span>
      </div>
    </header>
  );
};
