import { useState, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import Instruments from './pages/Instruments';
import Research from './pages/Research';
import Backtest from './pages/Backtest';
import Execution from './pages/Execution';
import DataQuality from './pages/DataQuality';
import SettingsPage from './pages/SettingsPage';

const PAGES = {
  dashboard: Dashboard,
  instruments: Instruments,
  research: Research,
  backtest: Backtest,
  execution: Execution,
  dq: DataQuality,
  settings: SettingsPage,
};

// Pages that should keep state alive when navigating away
const PERSISTENT_PAGES = ['dashboard', 'research', 'backtest', 'execution'];

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [refreshKey, setRefreshKey] = useState(0);
  const visitedRef = useRef(new Set(['dashboard']));

  const handleNavigate = useCallback((page) => {
    setActivePage(page);
    visitedRef.current.add(page);
    window.scrollTo(0, 0);
  }, []);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  return (
    <>
      <Sidebar activePage={activePage} onNavigate={handleNavigate} />
      <div className="ml-[240px] flex-1 flex flex-col min-h-screen">
        <Header onRefresh={handleRefresh} onNavigate={handleNavigate} />
        <main className="flex-1 px-8 py-6">
          {Object.entries(PAGES).map(([pageName, PageComponent]) => {
            const isActive = pageName === activePage;
            const isPersistent = PERSISTENT_PAGES.includes(pageName);
            const wasVisited = visitedRef.current.has(pageName);

            // Persistent pages: render once visited, keep alive via display:none
            // Non-persistent pages: only render when active (fresh mount each time)
            if (isPersistent && wasVisited) {
              return (
                <div key={pageName} style={{ display: isActive ? 'block' : 'none' }}>
                  <PageComponent onNavigate={handleNavigate} />
                </div>
              );
            }

            if (!isPersistent && isActive) {
              return (
                <div key={`${pageName}-${refreshKey}`}>
                  <PageComponent onNavigate={handleNavigate} />
                </div>
              );
            }

            return null;
          })}
        </main>
      </div>
    </>
  );
}
