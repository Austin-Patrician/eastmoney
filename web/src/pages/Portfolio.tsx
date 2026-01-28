import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  IconButton,
  Button,
  CircularProgress,
  Alert,
  Tabs,
  Tab,
  Tooltip,
  Snackbar,
  Paper,
  Dialog,
  useTheme,
  alpha,
} from '@mui/material';
import Grid from '@mui/material/Grid';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import CloseIcon from '@mui/icons-material/Close';
import ReceiptIcon from '@mui/icons-material/Receipt';
import DataMigrationIcon from '@mui/icons-material/CloudSync';
import GridViewIcon from '@mui/icons-material/GridView';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import {
  fetchPortfolios,
  fetchDefaultPortfolio,
  fetchPortfolioSummaryNew,
  fetchTransactions,
  fetchPortfolioAlerts,
  fetchPortfolioDiagnosis,
  fetchRebalanceSuggestions,
  createPortfolio,
  deletePortfolio,
  setDefaultPortfolio,
  createTransaction,
  deleteTransaction,
  deleteUnifiedPosition,
  updateUnifiedPosition,
  recalculatePosition,
  markAlertRead,
  dismissAlertApi,
  migrateOldPositions,
  // New institutional-grade APIs
  fetchStressTestScenarios,
  runStressTest,
  fetchPortfolioCorrelation,
  fetchPortfolioSignals,
  fetchSignalDetail,
  fetchRiskSummary,
  fetchPortfolioSparkline,
  fetchCorrelationExplanation,
  // Returns Analysis APIs
  fetchReturnsSummary,
  fetchReturnsCalendar,
  fetchDailyReturnsDetail,
  fetchReturnsExplanation,
} from '../api';
import type {
  Portfolio,
  UnifiedPosition,
  Transaction,
  PortfolioAlert,
  PortfolioDiagnosis,
  RebalanceSuggestion,
  PortfolioCreateData,
  StressTestScenario,
  StressTestSlider,
  StressTestResult,
  CorrelationResult,
  PortfolioSignal,
  PortfolioSignalDetail,
  RiskSummary,
  SparklineData,
  // Returns Analysis Types
  ReturnsSummary,
  ReturnsCalendarData,
  DailyReturnsDetail,
  ReturnsExplanation,
} from '../api';
import {
  PortfolioSwitcher,
  TransactionForm,
  TransactionHistory,
  AssetSearchDialog,
  PortfolioDiagnosisCard,
  RebalanceSuggestions,
  AlertBanner,
  // New institutional-grade components
  PortfolioHeader,
  StressTestSandbox,
  CorrelationHeatmap,
  SmartPositionTable,
  // Returns Analysis components
  ReturnsOverview,
  ReturnsCalendar,
  DailyReturnsDetail as DailyReturnsDetailComponent,
} from '../components/portfolio';
import type { TransactionFormData } from '../components/portfolio';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';

type TabValue = 'overview' | 'positions' | 'transactions' | 'returns';

export default function PortfolioPage() {
  const { t } = useTranslation();
  const theme = useTheme();

  // Abort controller ref for canceling requests on portfolio switch
  const abortControllerRef = useRef<AbortController | null>(null);
  // Mounted ref to prevent state updates after unmount
  const isMountedRef = useRef(true);

  // State - Core data
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [currentPortfolio, setCurrentPortfolio] = useState<Portfolio | null>(null);
  const [positions, setPositions] = useState<UnifiedPosition[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [alerts, setAlerts] = useState<PortfolioAlert[]>([]);
  const [diagnosis, setDiagnosis] = useState<PortfolioDiagnosis | null>(null);
  const [rebalanceSuggestions, setRebalanceSuggestions] = useState<RebalanceSuggestion[]>([]);
  const [currentAllocation, setCurrentAllocation] = useState<Record<string, number>>({});

  // State - New institutional-grade data
  const [riskSummary, setRiskSummary] = useState<RiskSummary | null>(null);
  const [sparklineData, setSparklineData] = useState<SparklineData | null>(null);
  const [stressTestScenarios, setStressTestScenarios] = useState<StressTestScenario[]>([]);
  const [stressTestSliders, setStressTestSliders] = useState<StressTestSlider[]>([]);
  const [correlationData, setCorrelationData] = useState<CorrelationResult | null>(null);
  const [signals, setSignals] = useState<PortfolioSignal[]>([]);

  // State - Returns Analysis data
  const [returnsSummary, setReturnsSummary] = useState<ReturnsSummary | null>(null);
  const [returnsCalendar, setReturnsCalendar] = useState<ReturnsCalendarData | null>(null);
  const [dailyReturnsDetail, setDailyReturnsDetail] = useState<DailyReturnsDetail | null>(null);
  const [returnsExplanation, setReturnsExplanation] = useState<ReturnsExplanation | null>(null);
  const [returnsLoading, setReturnsLoading] = useState(false);
  const [returnsExplanationLoading, setReturnsExplanationLoading] = useState(false);

  // Summary state
  const [summary, setSummary] = useState({
    totalValue: 0,
    totalCost: 0,
    totalPnl: 0,
    totalPnlPct: 0,
    positionsCount: 0,
    allocationByType: {} as Record<string, number>,
    allocationBySector: {} as Record<string, number>,
  });

  // UI state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabValue>('returns');
  const [diagnosisLoading, setDiagnosisLoading] = useState(false);
  const [riskLoading, setRiskLoading] = useState(false);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [signalsLoading, setSignalsLoading] = useState(false);
  const [stressTestLoading, setStressTestLoading] = useState(false);
  const [correlationExplanation, setCorrelationExplanation] = useState<string | null>(null);
  const [correlationExplanationLoading, setCorrelationExplanationLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
    open: false,
    message: '',
    severity: 'success',
  });

  // Dialog state
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const [transactionFormOpen, setTransactionFormOpen] = useState(false);
  const [diagnosisDialogOpen, setDiagnosisDialogOpen] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState<{
    code: string;
    name: string;
    type: 'stock' | 'fund';
    sector?: string;
  } | null>(null);

  // Load portfolios on mount
  useEffect(() => {
    loadPortfolios();
  }, []);

  // Load portfolio data when current portfolio changes
  useEffect(() => {
    if (currentPortfolio) {
      loadPortfolioData(currentPortfolio.id);
      loadInstitutionalData(currentPortfolio.id);
    }
  }, [currentPortfolio?.id]);

  const loadPortfolios = async () => {
    try {
      const [portfoliosRes, defaultRes] = await Promise.all([
        fetchPortfolios(),
        fetchDefaultPortfolio(),
      ]);
      setPortfolios(portfoliosRes.portfolios);
      setCurrentPortfolio(defaultRes);
    } catch (err: any) {
      setError(err.message || t('portfolio.error_load'));
    }
  };

  const loadPortfolioData = async (portfolioId: number) => {
    setLoading(true);
    setError(null);
    try {
      const [summaryRes, alertsRes] = await Promise.all([
        fetchPortfolioSummaryNew(portfolioId),
        fetchPortfolioAlerts(portfolioId, true),
      ]);

      if (!isMountedRef.current) return;
      setPositions(summaryRes.positions || []);
      setSummary({
        totalValue: summaryRes.total_value,
        totalCost: summaryRes.total_cost,
        totalPnl: summaryRes.total_pnl,
        totalPnlPct: summaryRes.total_pnl_pct,
        positionsCount: summaryRes.positions_count,
        allocationByType: summaryRes.allocation?.by_type || {},
        allocationBySector: summaryRes.allocation?.by_sector || {},
      });
      setAlerts(alertsRes.alerts);
    } catch (err: any) {
      if (isMountedRef.current) setError(err.message || t('portfolio.error_load'));
    } finally {
      if (isMountedRef.current) setLoading(false);
    }
  };

  // Load institutional-grade data - SEQUENTIALLY to reduce memory pressure
  const loadInstitutionalData = async (portfolioId: number) => {
    // Cancel any pending requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    // Step 1: Load only essential data first (risk summary + sparkline)
    setRiskLoading(true);
    try {
      const [riskRes, sparklineRes] = await Promise.all([
        // fetchRiskSummary(portfolioId),
        null,
        fetchPortfolioSparkline(portfolioId, 7),
      ]);
      if (!isMountedRef.current) return;
      setRiskSummary(riskRes);
      setSparklineData(sparklineRes);
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Failed to load risk data:', err);
      }
    } finally {
      if (isMountedRef.current) setRiskLoading(false);
    }

    // Step 2: Load signals after a small delay
    await new Promise(resolve => setTimeout(resolve, 100));
    if (!isMountedRef.current) return;
    loadSignals(portfolioId);

    // Step 3: Load stress test scenarios after another delay (heavy component)
    await new Promise(resolve => setTimeout(resolve, 300));
    if (!isMountedRef.current) return;
    loadStressTestScenarios(portfolioId);

    // Correlation data is loaded lazily when the correlation tab is selected
  };

  const loadStressTestScenarios = async (portfolioId: number) => {
    setStressTestLoading(true);
    try {
      const scenariosRes = await fetchStressTestScenarios(portfolioId);
      if (!isMountedRef.current) return;
      setStressTestScenarios(scenariosRes.scenarios);
      setStressTestSliders(scenariosRes.sliders);
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Failed to load stress test scenarios:', err);
      }
    } finally {
      if (isMountedRef.current) setStressTestLoading(false);
    }
  };

  const loadCorrelation = useCallback(async (portfolioId: number) => {
    setCorrelationLoading(true);
    try {
      const res = await fetchPortfolioCorrelation(portfolioId, 90);
      if (!isMountedRef.current) return;
      setCorrelationData(res);
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Failed to load correlation:', err);
      }
    } finally {
      if (isMountedRef.current) setCorrelationLoading(false);
    }
  }, []);

  const loadSignals = async (portfolioId: number) => {
    setSignalsLoading(true);
    try {
      const res = await fetchPortfolioSignals(portfolioId);
      if (!isMountedRef.current) return;
      setSignals(res.signals);
    } catch (err: any) {
      if (err?.name !== 'AbortError') {
        console.error('Failed to load signals:', err);
      }
    } finally {
      if (isMountedRef.current) setSignalsLoading(false);
    }
  };

  const loadCorrelationExplanation = useCallback(async () => {
    if (!currentPortfolio || !correlationData) return;
    setCorrelationExplanationLoading(true);
    try {
      const res = await fetchCorrelationExplanation(currentPortfolio.id, correlationData);
      if (!isMountedRef.current) return;
      setCorrelationExplanation(res.explanation);
    } catch (err: any) {
      console.error('Failed to generate correlation explanation:', err);
      if (isMountedRef.current) {
        showSnackbar(t('portfolio.explanationError', '生成解读失败'), 'error');
      }
    } finally {
      if (isMountedRef.current) setCorrelationExplanationLoading(false);
    }
  }, [currentPortfolio?.id, correlationData]);

  const loadTransactions = useCallback(async () => {
    if (!currentPortfolio) return;
    try {
      const res = await fetchTransactions(currentPortfolio.id, undefined, 100, 0);
      setTransactions(res.transactions);
    } catch (err: any) {
      console.error('Failed to load transactions:', err);
    }
  }, [currentPortfolio?.id]);

  const loadDiagnosis = useCallback(async () => {
    if (!currentPortfolio) return;
    setDiagnosisLoading(true);
    try {
      const [diagRes, rebalanceRes] = await Promise.all([
        fetchPortfolioDiagnosis(currentPortfolio.id),
        fetchRebalanceSuggestions(currentPortfolio.id),
      ]);
      setDiagnosis(diagRes);
      setRebalanceSuggestions(rebalanceRes.suggestions);
      setCurrentAllocation(rebalanceRes.current_allocation);
    } catch (err: any) {
      console.error('Failed to load diagnosis:', err);
    } finally {
      setDiagnosisLoading(false);
    }
  }, [currentPortfolio?.id]);

  // Returns Analysis loading functions
  const loadReturnsData = useCallback(async (calendarView: 'day' | 'month' | 'year' = 'day') => {
    if (!currentPortfolio) return;
    setReturnsLoading(true);
    try {
      const [summaryRes, calendarRes, dailyRes] = await Promise.all([
        fetchReturnsSummary(currentPortfolio.id),
        fetchReturnsCalendar(currentPortfolio.id, calendarView),
        fetchDailyReturnsDetail(currentPortfolio.id),
      ]);
      if (!isMountedRef.current) return;
      setReturnsSummary(summaryRes);
      setReturnsCalendar(calendarRes);
      setDailyReturnsDetail(dailyRes);
    } catch (err: any) {
      console.error('Failed to load returns data:', err);
    } finally {
      if (isMountedRef.current) setReturnsLoading(false);
    }
  }, [currentPortfolio?.id]);

  const loadReturnsCalendar = useCallback(async (view: 'day' | 'month' | 'year') => {
    if (!currentPortfolio) return;
    try {
      const res = await fetchReturnsCalendar(currentPortfolio.id, view);
      if (!isMountedRef.current) return;
      setReturnsCalendar(res);
    } catch (err: any) {
      console.error('Failed to load returns calendar:', err);
    }
  }, [currentPortfolio?.id]);

  const loadReturnsExplanation = useCallback(async () => {
    if (!currentPortfolio) return;
    setReturnsExplanationLoading(true);
    try {
      const res = await fetchReturnsExplanation(currentPortfolio.id);
      if (!isMountedRef.current) return;
      setReturnsExplanation(res);
    } catch (err: any) {
      console.error('Failed to generate returns explanation:', err);
      if (isMountedRef.current) {
        showSnackbar(t('portfolio.explanationError', '生成解读失败'), 'error');
      }
    } finally {
      if (isMountedRef.current) setReturnsExplanationLoading(false);
    }
  }, [currentPortfolio?.id]);

  // Load tab-specific data
  useEffect(() => {
    if (tab === 'transactions') {
      loadTransactions();
    } else if (tab === 'returns' && !returnsSummary && !returnsLoading) {
      loadReturnsData();
    } else if (tab === 'positions' && !diagnosis && !diagnosisLoading) {
      // Lazily load diagnosis when switching to positions tab
      loadDiagnosis();
    }
  }, [tab, loadTransactions, loadReturnsData, returnsSummary, returnsLoading, loadDiagnosis, diagnosis, diagnosisLoading]);

  // Lazy load correlation data when on overview tab
  useEffect(() => {
    if (tab === 'overview' && currentPortfolio && !correlationData && !correlationLoading) {
      loadCorrelation(currentPortfolio.id);
    }
  }, [tab, currentPortfolio?.id, correlationData, correlationLoading, loadCorrelation]);

  // Cleanup abort controller on unmount
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // Handlers
  const handleSwitchPortfolio = (portfolioId: number) => {
    const portfolio = portfolios.find((p) => p.id === portfolioId);
    if (portfolio) {
      setCurrentPortfolio(portfolio);
      setDiagnosis(null);
      setRebalanceSuggestions([]);
      setRiskSummary(null);
      setCorrelationData(null);
      setCorrelationExplanation(null);
      setSignals([]);
    }
  };

  const handleCreatePortfolio = async (data: PortfolioCreateData) => {
    await createPortfolio(data);
    await loadPortfolios();
    showSnackbar(t('common.created'), 'success');
  };

  const handleDeletePortfolio = async (portfolioId: number) => {
    await deletePortfolio(portfolioId);
    await loadPortfolios();
    showSnackbar(t('common.deleted'), 'success');
  };

  const handleSetDefault = async (portfolioId: number) => {
    await setDefaultPortfolio(portfolioId);
    await loadPortfolios();
    showSnackbar(t('common.saved'), 'success');
  };

  const handleAssetSelect = (asset: { code: string; name: string; type: 'stock' | 'fund'; sector?: string }) => {
    setSelectedAsset(asset);
    setSearchDialogOpen(false);
    setTransactionFormOpen(true);
  };

  const handleCreateTransaction = async (data: TransactionFormData) => {
    if (!currentPortfolio) return;
    await createTransaction(currentPortfolio.id, data);
    await loadPortfolioData(currentPortfolio.id);
    await loadInstitutionalData(currentPortfolio.id);
    if (tab === 'transactions') {
      await loadTransactions();
    }
    showSnackbar(t('portfolio.add_transaction') + ' - ' + t('common.success'), 'success');
  };

  const handleDeleteTransaction = async (transactionId: number) => {
    if (!currentPortfolio) return;
    if (!window.confirm(t('portfolio.confirm_delete'))) return;
    await deleteTransaction(currentPortfolio.id, transactionId);
    await loadTransactions();
    showSnackbar(t('common.deleted'), 'success');
  };

  const handleDeletePosition = async (positionId: number) => {
    if (!currentPortfolio) return;
    if (!window.confirm(t('portfolio.confirm_delete'))) return;
    await deleteUnifiedPosition(currentPortfolio.id, positionId);
    await loadPortfolioData(currentPortfolio.id);
    await loadInstitutionalData(currentPortfolio.id);
    showSnackbar(t('common.deleted'), 'success');
  };

  const handleEditPosition = async (positionId: number, updates: { total_shares?: number; average_cost?: number; notes?: string }) => {
    if (!currentPortfolio) return;
    await updateUnifiedPosition(currentPortfolio.id, positionId, updates);
    await loadPortfolioData(currentPortfolio.id);
    showSnackbar(t('common.saved'), 'success');
  };

  const handleRecalculatePosition = async (positionId: number) => {
    if (!currentPortfolio) return;
    await recalculatePosition(currentPortfolio.id, positionId);
    await loadPortfolioData(currentPortfolio.id);
    showSnackbar(t('portfolio.recalculate') + ' - ' + t('common.success'), 'success');
  };

  const handleMarkAlertRead = async (alertId: number) => {
    await markAlertRead(alertId);
    if (currentPortfolio) {
      const alertsRes = await fetchPortfolioAlerts(currentPortfolio.id, true);
      setAlerts(alertsRes.alerts);
    }
  };

  const handleDismissAlert = async (alertId: number) => {
    await dismissAlertApi(alertId);
    if (currentPortfolio) {
      const alertsRes = await fetchPortfolioAlerts(currentPortfolio.id, true);
      setAlerts(alertsRes.alerts);
    }
  };

  const handleMigrateData = async () => {
    if (!currentPortfolio) return;
    try {
      const result = await migrateOldPositions(currentPortfolio.id);
      await loadPortfolioData(currentPortfolio.id);
      showSnackbar(t('portfolio.migrate_success', { count: result.migrated_count }), 'success');
    } catch (err: any) {
      showSnackbar(err.message || t('common.error'), 'error');
    }
  };

  const handleRunStressTest = async (params: { scenario_type?: string; scenario?: Record<string, number> }): Promise<StressTestResult> => {
    if (!currentPortfolio) throw new Error('No portfolio selected');
    return await runStressTest(currentPortfolio.id, params);
  };

  const handleLoadSignalDetail = async (assetCode: string): Promise<PortfolioSignalDetail> => {
    if (!currentPortfolio) throw new Error('No portfolio selected');
    return await fetchSignalDetail(currentPortfolio.id, assetCode);
  };

  const showSnackbar = (message: string, severity: 'success' | 'error') => {
    setSnackbar({ open: true, message, severity });
  };

  const handleRefresh = () => {
    if (currentPortfolio) {
      loadPortfolioData(currentPortfolio.id);
      loadInstitutionalData(currentPortfolio.id);
      setDiagnosis(null);
    }
  };

  if (loading && !currentPortfolio) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Page Header with Portfolio Switcher */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <PortfolioSwitcher
          portfolios={portfolios}
          currentPortfolio={currentPortfolio}
          onSwitch={handleSwitchPortfolio}
          onCreate={handleCreatePortfolio}
          onDelete={handleDeletePortfolio}
          onSetDefault={handleSetDefault}
        />
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={() => setSearchDialogOpen(true)}
            sx={{
              bgcolor: '#6366f1',
              borderRadius: '10px',
              textTransform: 'none',
              fontWeight: 600,
              '&:hover': { bgcolor: '#4f46e5' },
            }}
          >
            {t('portfolio.add_transaction')}
          </Button>
          <Tooltip title={t('portfolio.migrate_desc')}>
            <IconButton onClick={handleMigrateData}>
              <DataMigrationIcon />
            </IconButton>
          </Tooltip>
          <Tooltip title={t('common.refresh')}>
            <IconButton onClick={handleRefresh}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      {/* Alerts Banner */}
      {alerts.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <AlertBanner
            alerts={alerts}
            onDismiss={handleDismissAlert}
            onMarkRead={handleMarkAlertRead}
          />
        </Box>
      )}

      {/* NEW: Enhanced Portfolio Header with Risk Metrics */}
      <PortfolioHeader
        totalValue={summary.totalValue}
        totalPnl={summary.totalPnl}
        totalPnlPct={summary.totalPnlPct}
        sparklineData={sparklineData ? {
          values: sparklineData.values,
          dates: sparklineData.dates,
          trend: sparklineData.trend,
        } : undefined}
        loading={riskLoading}
      />

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{
          mb: 3,
          '& .MuiTab-root': { textTransform: 'none', fontWeight: 600 },
        }}
      >
        <Tab value="returns" label={t('portfolio.returnsAnalysis', '收益分析')} icon={<ShowChartIcon sx={{ fontSize: 16 }} />} iconPosition="start" />
        <Tab value="positions" label={t('portfolio.smartPositionsTab', '智能持仓')} icon={<AccountBalanceWalletIcon sx={{ fontSize: 16 }} />} iconPosition="start" />
        <Tab value="overview" label={t('portfolio.commandCenter', '投资指挥舱')} />
        <Tab value="transactions" label={t('portfolio.transaction_history')} icon={<ReceiptIcon sx={{ fontSize: 16 }} />} iconPosition="start" />
      </Tabs>

      {/* Tab Content */}
      {tab === 'overview' && (
        <>
          {/* T-Layout: Left Panel (2/3) + Right Panel (1/3) */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            {/* Left Panel: Stress Test Sandbox - Deferred rendering */}
            <Grid size={{ xs: 12, lg: 8 }}>
              {stressTestLoading || (stressTestScenarios.length === 0 && stressTestSliders.length === 0) ? (
                <Paper
                  elevation={0}
                  sx={{
                    p: 4,
                    minHeight: 400,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    background: alpha(theme.palette.background.paper, 0.8),
                    backdropFilter: 'blur(10px)',
                    border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                    borderRadius: 3,
                  }}
                >
                  <Box sx={{ textAlign: 'center' }}>
                    <CircularProgress size={32} sx={{ mb: 2 }} />
                    <Typography color="text.secondary">
                      {t('portfolio.loadingStressTest', '加载压力测试...')}
                    </Typography>
                  </Box>
                </Paper>
              ) : (
                <StressTestSandbox
                  portfolioId={currentPortfolio?.id || 0}
                  scenarios={stressTestScenarios}
                  onRunStressTest={handleRunStressTest}
                />
              )}
            </Grid>

            {/* Right Panel: Correlation Heatmap with AI Explanation */}
            <Grid size={{ xs: 12, lg: 4 }}>
              <Paper
                elevation={0}
                sx={{
                  p: 2,
                  height: '100%',
                  minHeight: 500,
                  background: alpha(theme.palette.background.paper, 0.8),
                  backdropFilter: 'blur(10px)',
                  border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
                  borderRadius: 3,
                  display: 'flex',
                  flexDirection: 'column',
                }}
              >
                {/* Title */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <GridViewIcon sx={{ fontSize: 20, color: 'primary.main' }} />
                  <Typography variant="subtitle1" fontWeight={600}>
                    {t('portfolio.correlationAnalysis', '持仓相关性分析')}
                  </Typography>
                </Box>

                {/* Correlation Heatmap */}
                <CorrelationHeatmap
                  data={correlationData?.matrix || []}
                  labels={correlationData?.labels || []}
                  codes={correlationData?.codes || []}
                  size={correlationData?.size || 0}
                  diversificationScore={correlationData?.diversification_score || 0}
                  diversificationStatus={correlationData?.diversification_status || 'unknown'}
                  loading={correlationLoading}
                  height={300}
                />

                {/* AI Explanation Section */}
                <Box sx={{ mt: 2, flex: 1 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <AutoAwesomeIcon sx={{ fontSize: 16, color: 'warning.main' }} />
                      <Typography variant="caption" fontWeight={600} color="text.secondary">
                        {t('portfolio.aiExplanation', 'AI 解读')}
                      </Typography>
                    </Box>
                    {!correlationExplanation && !correlationExplanationLoading && correlationData && (
                      <Button
                        size="small"
                        onClick={() => loadCorrelationExplanation()}
                        sx={{ textTransform: 'none', fontSize: '0.75rem' }}
                      >
                        {t('portfolio.generateExplanation', '生成解读')}
                      </Button>
                    )}
                  </Box>
                  <Paper
                    variant="outlined"
                    sx={{
                      p: 1.5,
                      bgcolor: alpha(theme.palette.warning.main, 0.03),
                      borderColor: alpha(theme.palette.warning.main, 0.2),
                      borderRadius: 2,
                      minHeight: 80,
                    }}
                  >
                    {correlationExplanationLoading ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <CircularProgress size={16} />
                        <Typography variant="caption" color="text.secondary">
                          {t('portfolio.generatingExplanation', 'AI 正在分析...')}
                        </Typography>
                      </Box>
                    ) : correlationExplanation ? (
                      <Typography variant="body2" sx={{ fontSize: '0.8rem', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                        {correlationExplanation}
                      </Typography>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        {correlationData
                          ? t('portfolio.clickToGenerate', '点击"生成解读"让 AI 分析您的持仓相关性')
                          : t('portfolio.loadingCorrelation', '加载相关性数据...')}
                      </Typography>
                    )}
                  </Paper>
                </Box>
              </Paper>
            </Grid>
          </Grid>
        </>
      )}

      {tab === 'positions' && (
        <>
          {/* Smart Position Table with AI Signals */}
          <Box sx={{ mb: 3 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
              <Typography variant="h6" fontWeight={600} sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <AutoAwesomeIcon sx={{ color: 'primary.main' }} />
                {t('portfolio.smartPositions', '智能持仓')}
              </Typography>
              <Button
                size="small"
                variant="outlined"
                startIcon={<AutoAwesomeIcon />}
                onClick={() => setDiagnosisDialogOpen(true)}
                sx={{ 
                  textTransform: 'none', 
                  borderRadius: 2,
                  color: '#6366f1',
                  borderColor: alpha('#6366f1', 0.5),
                  '&:hover': {
                    borderColor: '#6366f1',
                    bgcolor: alpha('#6366f1', 0.05),
                  }
                }}
              >
                {t('portfolio.ai_diagnosis', 'AI Diagnosis')}
              </Button>
            </Box>
            <SmartPositionTable
              positions={positions}
              signals={signals}
              diagnosis={diagnosis}
              loadingDiagnosis={diagnosisLoading}
              onRunDiagnosis={loadDiagnosis}
              onDelete={handleDeletePosition}
              onEdit={handleEditPosition}
              onRecalculate={handleRecalculatePosition}
              onLoadSignalDetail={handleLoadSignalDetail}
              loading={loading || signalsLoading}
            />
          </Box>

          {/* AI组合诊断 & Rebalancing Suggestions */}
          <Grid container spacing={3}>
            <Grid size={{ xs: 12, lg: 6 }}>
              <PortfolioDiagnosisCard
                diagnosis={diagnosis}
                loading={diagnosisLoading}
                onRefresh={loadDiagnosis}
                sx={{ height: '100%' }}
              />
            </Grid>
            <Grid size={{ xs: 12, lg: 6 }}>
              <RebalanceSuggestions
                suggestions={rebalanceSuggestions}
                currentAllocation={currentAllocation}
                loading={diagnosisLoading}
                onRefresh={loadDiagnosis}
                sx={{ height: '100%' }}
              />
            </Grid>
          </Grid>
        </>
      )}

      {tab === 'transactions' && (
        <TransactionHistory
          transactions={transactions}
          onDelete={handleDeleteTransaction}
          loading={loading}
        />
      )}

      {tab === 'returns' && (
        <>
          {/* Returns Overview - KPI Cards */}
          <ReturnsOverview
            data={returnsSummary}
            loading={returnsLoading}
          />

          {/* Returns Calendar and Daily Detail */}
          <Grid container spacing={3} sx={{ mb: 3 }}>
            {/* Returns Calendar - Heatmap */}
            <Grid size={{ xs: 12, lg: 5 }}>
              <ReturnsCalendar
                data={returnsCalendar}
                loading={returnsLoading}
                onViewChange={loadReturnsCalendar}
              />
            </Grid>

            {/* Daily Returns Detail Table */}
            <Grid size={{ xs: 12, lg: 7 }}>
              <DailyReturnsDetailComponent
                data={dailyReturnsDetail}
                loading={returnsLoading}
                explanationData={returnsExplanation}
                explanationLoading={returnsExplanationLoading}
                onGenerateExplanation={loadReturnsExplanation}
                onRefreshExplanation={loadReturnsExplanation}
              />
            </Grid>
          </Grid>
        </>
      )}

      {/* Diagnosis Dialog */}
      <Dialog
        open={diagnosisDialogOpen}
        onClose={() => setDiagnosisDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { borderRadius: 3, p: 0, overflow: 'hidden' }
        }}
      >
        <Box sx={{ position: 'relative' }}>
          <IconButton
            onClick={() => setDiagnosisDialogOpen(false)}
            sx={{ position: 'absolute', right: 8, top: 8, zIndex: 1 }}
          >
            <CloseIcon />
          </IconButton>
          <PortfolioDiagnosisCard
            diagnosis={diagnosis || null}
            loading={diagnosisLoading}
            onRefresh={loadDiagnosis}
          />
        </Box>
      </Dialog>

      {/* Dialogs */}
      <AssetSearchDialog
        open={searchDialogOpen}
        onClose={() => setSearchDialogOpen(false)}
        onSelect={handleAssetSelect}
      />

      <TransactionForm
        open={transactionFormOpen}
        onClose={() => {
          setTransactionFormOpen(false);
          setSelectedAsset(null);
        }}
        onSubmit={handleCreateTransaction}
        assetCode={selectedAsset?.code}
        assetName={selectedAsset?.name}
        assetType={selectedAsset?.type}
      />

      {/* Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
      >
        <Alert
          severity={snackbar.severity}
          onClose={() => setSnackbar((s) => ({ ...s, open: false }))}
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
}
