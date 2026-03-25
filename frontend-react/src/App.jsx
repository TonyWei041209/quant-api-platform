import { useState, useCallback } from 'react';
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

export default function App() {
  const [activePage, setActivePage] = useState('dashboard');
  const [refreshKey, setRefreshKey] = useState(0);

  const handleNavigate = useCallback((page) => {
    setActivePage(page);
    window.scrollTo(0, 0);
  }, []);

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  const PageComponent = PAGES[activePage] || Dashboard;

  return (
    <>
      <Sidebar activePage={activePage} onNavigate={handleNavigate} />
      <div className="ml-[240px] flex flex-col min-h-screen">
        <Header onRefresh={handleRefresh} />
        <main className="flex-1 px-8 py-6">
          <PageComponent key={`${activePage}-${refreshKey}`} onNavigate={handleNavigate} />
        </main>
      </div>
    </>
  );
}
