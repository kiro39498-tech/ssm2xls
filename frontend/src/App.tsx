import { useState } from 'react';
import { Navbar } from './components/Navbar';
import { QueryWorkspace } from './components/QueryWorkspace';
import { ExportJobsView } from './components/ExportJobsView';
import { SavedReportsView } from './components/SavedReportsView';
import { AuditTrailView } from './components/AuditTrailView';

export function App() {
  const [activeTab, setActiveTab] = useState<'workspace' | 'exports' | 'reports' | 'audit'>('workspace');
  const [loadedSql, setLoadedSql] = useState<string | null>(null);

  const handleLoadQueryIntoEditor = (sql: string) => {
    setLoadedSql(sql);
    setActiveTab('workspace');
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      <main style={{ flex: 1 }}>
        {activeTab === 'workspace' && (
          <QueryWorkspace
            key={loadedSql ? `loaded-${loadedSql.length}` : 'default'}
            onJobCreated={() => setActiveTab('exports')}
          />
        )}
        {activeTab === 'exports' && <ExportJobsView />}
        {activeTab === 'reports' && (
          <SavedReportsView onLoadQueryIntoEditor={handleLoadQueryIntoEditor} />
        )}
        {activeTab === 'audit' && <AuditTrailView />}
      </main>
    </div>
  );
}

export default App;
