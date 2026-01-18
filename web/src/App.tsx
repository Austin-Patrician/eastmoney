import { ThemeProvider, CssBaseline } from '@mui/material';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { theme } from './theme/theme';
import Layout from './components/layout/Layout';
import DashboardPage from './pages/Dashboard';
import ReportsPage from './pages/Reports';
import FundsPage from './pages/Funds';
import StocksPage from './pages/Stocks';
import SentimentPage from './pages/Sentiment';
import CommoditiesPage from './pages/Commodities';
import SettingsPage from './pages/Settings';
import LoginPage from './pages/Login';
import RecommendationsPage from './pages/Recommendations';
import DocumentationPage from './pages/Documentation';

// Auth Guard
const PrivateRoute = () => {
    const token = localStorage.getItem('token');
    return token ? <Outlet /> : <Navigate to="/login" replace />;
};

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/doc" element={<DocumentationPage />} />

          {/* Protected Routes */}
          <Route element={<PrivateRoute />}>
              <Route path="/" element={<Layout />}>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="funds" element={<FundsPage />} />
                <Route path="stocks" element={<StocksPage />} />
                <Route path="recommendations" element={<RecommendationsPage />} />
                <Route path="sentiment" element={<SentimentPage />} />
                <Route path="reports" element={<ReportsPage />} />
                <Route path="commodities" element={<CommoditiesPage />} />
                <Route path="settings" element={<SettingsPage />} />
              </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;