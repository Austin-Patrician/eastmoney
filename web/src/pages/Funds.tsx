import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Typography,
  Button,
  Grid,
  IconButton,
  TextField,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Autocomplete,
  CircularProgress,
  Chip,
  Box,
  Divider,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableRow,
  TableHead,
  Tabs,
  Tab,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Snackbar,
  Alert,
  Checkbox,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SearchIcon from '@mui/icons-material/Search';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import HistoryIcon from '@mui/icons-material/History';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import AssessmentIcon from '@mui/icons-material/Assessment';
import EditIcon from '@mui/icons-material/Edit';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CloseIcon from '@mui/icons-material/Close';
import DashboardIcon from '@mui/icons-material/Dashboard';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import FolderIcon from '@mui/icons-material/Folder';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

import {
  fetchFunds,
  saveFund,
  deleteFund,
  searchMarketFunds,
  generateReport,
  compareFundsAdvanced,
  fetchBatchEstimation,
} from '../api';

import type { MarketFund, FundItem, FundComparisonResponse, BatchFundEstimation } from '../api';
import { useAppContext } from '../contexts/AppContext';
import { FundMarketOverview, FundRankingTable, FundDetailDialog } from '../components/fund';

const CHART_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];


export default function FundsPage() {
  const { t } = useTranslation();
  const { setCurrentPage, setCurrentFund } = useAppContext();
  const [funds, setFunds] = useState<FundItem[]>([]);
  const [loading, setLoading] = useState(false);
  
  // Page Tab State
  const [pageTab, setPageTab] = useState(0);
  const [selectedRankingType] = useState('股票型');
  
  // Unified Dialog State (Add/Edit)
  const [openDialog, setOpenDialog] = useState(false);
  const [editingFund, setEditingFund] = useState<FundItem | null>(null);
  const [formCode, setFormCode] = useState('');
  const [formName, setFormName] = useState('');
  const [formStyle, setFormStyle] = useState('');
  const [formFocus, setFormFocus] = useState('');
  const [formPreTime, setFormPreTime] = useState('');
  const [formPostTime, setFormPostTime] = useState('');

  // Search State
  const [searchResults, setSearchResults] = useState<MarketFund[]>([]);
  const [searching, setSearching] = useState(false);
  const [inputValue, setInputValue] = useState(''); // Track input for manual search trigger

  // Detail View State
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedFund, setSelectedFund] = useState<FundItem | null>(null);

  // Action Menu State
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuFund, setMenuFund] = useState<FundItem | null>(null);

  // Notification State
  const [notify, setNotify] = useState<{ open: boolean, message: string, severity: 'success' | 'info' | 'warning' | 'error' }>({
    open: false,
    message: '',
    severity: 'info'
  });

  const showNotify = (message: string, severity: 'success' | 'info' | 'warning' | 'error' = 'info') => {
    setNotify({ open: true, message, severity });
  };

  // Comparison Mode State
  const [compareMode, setCompareMode] = useState(false);
  const [selectedForCompare, setSelectedForCompare] = useState<Set<string>>(new Set());
  const [comparisonData, setComparisonData] = useState<FundComparisonResponse | null>(null);
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareTab, setCompareTab] = useState(0);

  // Real-time Estimation State
  const [estimations, setEstimations] = useState<Record<string, BatchFundEstimation>>({});
  const [estimationLoading, setEstimationLoading] = useState(false);
  const [isTrading, setIsTrading] = useState(false);
  const [lastEstimationUpdate, setLastEstimationUpdate] = useState<string | null>(null);

  // Toggle fund selection for comparison
  const handleToggleCompare = (code: string) => {
    const newSet = new Set(selectedForCompare);
    if (newSet.has(code)) {
      newSet.delete(code);
    } else if (newSet.size < 10) {
      newSet.add(code);
    } else {
      showNotify(t('funds.compare.max_funds'), 'warning');
      return;
    }
    setSelectedForCompare(newSet);
  };

  // Run comparison
  const handleRunComparison = async () => {
    if (selectedForCompare.size < 2) {
      showNotify(t('funds.compare.min_funds'), 'warning');
      return;
    }
    setCompareLoading(true);
    try {
      const codes = Array.from(selectedForCompare);
      const result = await compareFundsAdvanced(codes);
      setComparisonData(result);
    } catch (err: any) {
      showNotify(err.message || t('funds.compare.error'), 'error');
    } finally {
      setCompareLoading(false);
    }
  };

  // Get NAV chart data for comparison
  const getNavChartData = () => {
    if (!comparisonData?.nav_comparison?.curves) return [];
    const curves = comparisonData.nav_comparison.curves;
    const fundCodes = Object.keys(curves);
    if (fundCodes.length === 0) return [];

    const dateSet = new Set<string>();
    fundCodes.forEach((code) => {
      curves[code].data.forEach((d: any) => dateSet.add(d.date));
    });

    const sortedDates = Array.from(dateSet).sort();
    return sortedDates.map((date) => {
      const point: any = { date };
      fundCodes.forEach((code) => {
        const entry = curves[code].data.find((d: any) => d.date === date);
        point[code] = entry?.value || null;
      });
      return point;
    });
  };

  // Clear comparison
  const handleClearComparison = () => {
    setCompareMode(false);
    setSelectedForCompare(new Set());
    setComparisonData(null);
  };

  const handleOpenMenu = (event: React.MouseEvent<HTMLElement>, fund: FundItem) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setMenuFund(fund);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
    setMenuFund(null);
  };

  const handleRunAnalysis = async (mode: 'pre' | 'post') => {
    if (!menuFund) return;
    try {
        showNotify(`Initializing ${mode.toUpperCase()} market intelligence for ${menuFund.code}...`, 'info');
        await generateReport(mode, menuFund.code);
        showNotify(t('funds.messages.trigger_success'), 'success');
    } catch (error) {
        showNotify(`Failed to trigger intelligence node: ${error}`, 'error');
    }
  };

  const handleOpenDialog = (fund?: FundItem) => {
    setAnchorEl(null);
    setSearchResults([]);
    setInputValue('');
    if (fund) {
        setEditingFund(fund);
        setFormCode(fund.code);
        setFormName(fund.name);
        setFormStyle(fund.style || '');
        setFormFocus(fund.focus?.join(', ') || '');
        setFormPreTime(fund.pre_market_time || '');
        setFormPostTime(fund.post_market_time || '');
    } else {
        setEditingFund(null);
        setFormCode('');
        setFormName('');
        setFormStyle('');
        setFormFocus('');
        setFormPreTime('09:15');
        setFormPostTime('15:30');
    }
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formCode || !formName) {
        showNotify('Code and Name are required', 'error');
        return;
    }

    const focusArray = formFocus.split(/[,，]/).map(s => s.trim()).filter(Boolean);
    const updatedFund: FundItem = {
        code: formCode,
        name: formName,
        style: formStyle,
        focus: focusArray,
        pre_market_time: formPreTime || undefined,
        post_market_time: formPostTime || undefined,
        is_active: true
    };

    try {
        await saveFund(updatedFund);
        showNotify(t('funds.messages.save_success'), 'success');
        setOpenDialog(false);
        loadFunds();
    } catch (error) {
        console.error(error);
        showNotify(t('funds.messages.save_error'), 'error');
    }
  };

  const handleSearch = async (query: string) => {
    if (query.length < 2) return;
    setSearching(true);
    try {
      const results = await searchMarketFunds(query);
      setSearchResults(results);
    } catch (error) {
      console.error(error);
    } finally {
      setSearching(false);
    }
  };

  const handleMarketFundSelect = (_event: any, value: MarketFund | null) => {
    if (value) {
        setFormCode(value.code);
        setFormName(value.name);
        setFormStyle(value.type || '');
    }
  };

  useEffect(() => {
    setCurrentPage('funds');
    loadFunds();
    return () => {
      // Clear fund context when leaving page
      setCurrentFund(null);
    };
  }, []);

  const loadFunds = async () => {
    setLoading(true);
    try {
      const data = await fetchFunds();
      setFunds(data);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  // Load estimation data
  const loadEstimations = async () => {
    if (funds.length === 0) return;
    
    setEstimationLoading(true);
    try {
      const codes = funds.map(f => f.code);
      const result = await fetchBatchEstimation(codes);
      
      // Build map by code for easy lookup
      const estimationMap: Record<string, BatchFundEstimation> = {};
      result.estimations.forEach(est => {
        estimationMap[est.code] = est;
      });
      
      setEstimations(estimationMap);
      setIsTrading(result.is_trading);
      setLastEstimationUpdate(result.timestamp);
    } catch (error) {
      console.error('Failed to load estimations:', error);
    } finally {
      setEstimationLoading(false);
    }
  };

  // Load estimations when funds change or when on "My Holdings" tab
  useEffect(() => {
    if (pageTab === 2 && funds.length > 0) {
      loadEstimations();
    }
  }, [funds, pageTab]);

  // Auto-refresh estimations during trading hours (every 60 seconds)
  useEffect(() => {
    if (pageTab !== 2 || funds.length === 0) return;
    
    // Set up interval for auto-refresh
    const intervalId = setInterval(() => {
      loadEstimations();
    }, 60000); // 60 seconds
    
    return () => clearInterval(intervalId);
  }, [pageTab, funds]);

  const handleDelete = async (code: string) => {
    if (window.confirm(t('funds.messages.delete_confirm'))) {
      try {
        await deleteFund(code);
        showNotify(t('funds.messages.delete_success'), 'success');
        loadFunds();
      } catch (error) {
        showNotify(`Error removing fund: ${error}`, 'error');
      }
    }
  };
  const handleViewDetails = async (fund: FundItem) => {
    setSelectedFund(fund);
    setDetailOpen(true);

    // Update context for AI assistant
    setCurrentFund({ code: fund.code, name: fund.name });
  };

  return (
    <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3 }}>
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <Typography variant="h4" className="font-bold text-slate-900" sx={{ fontFamily: 'JetBrains Mono' }}>
            {t('funds.title')}
          </Typography>
          <Typography variant="subtitle1" className="text-slate-500 mt-1">
            {t('funds.subtitle')}
          </Typography>
        </div>
        <Box sx={{ display: 'flex', gap: 1.5 }}>
          {pageTab === 2 && compareMode ? (
            <>
              <Button
                variant="outlined"
                onClick={handleClearComparison}
                startIcon={<CloseIcon />}
                sx={{
                  borderRadius: '10px',
                  textTransform: 'none',
                  fontWeight: 600,
                  borderColor: '#e2e8f0',
                  color: '#64748b',
                }}
              >
                {t('funds.compare.cancel')}
              </Button>
              <Button
                variant="contained"
                onClick={handleRunComparison}
                disabled={selectedForCompare.size < 2 || compareLoading}
                startIcon={compareLoading ? <CircularProgress size={16} color="inherit" /> : <CompareArrowsIcon />}
                sx={{
                  backgroundColor: '#22c55e',
                  borderRadius: '10px',
                  px: 3,
                  textTransform: 'none',
                  fontWeight: 600,
                  '&:hover': { backgroundColor: '#16a34a' },
                  '&:disabled': { backgroundColor: '#94a3b8' },
                }}
              >
                {t('funds.compare.compare_btn')} ({selectedForCompare.size}/10)
              </Button>
            </>
          ) : pageTab === 2 && (
            <>
              <Button
                variant="outlined"
                startIcon={<CompareArrowsIcon />}
                onClick={() => setCompareMode(true)}
                sx={{
                  borderRadius: '10px',
                  textTransform: 'none',
                  fontWeight: 600,
                  borderColor: '#e2e8f0',
                  color: '#64748b',
                  '&:hover': { borderColor: '#6366f1', color: '#6366f1', bgcolor: 'rgba(99, 102, 241, 0.05)' },
                }}
              >
                {t('funds.compare.title')}
              </Button>
              <Button
                variant="contained"
                startIcon={<AddIcon />}
                onClick={() => handleOpenDialog()}
                sx={{
                  backgroundColor: '#6366f1',
                  borderRadius: '10px',
                  px: 3,
                  textTransform: 'none',
                  fontWeight: 600,
                  '&:hover': { backgroundColor: '#4f46e5' }
                }}
              >
                {t('funds.add_target')}
              </Button>
            </>
          )}
        </Box>
      </div>

      {/* Page Tabs */}
      <Paper 
        elevation={0} 
        sx={{ 
          borderRadius: '12px', 
          border: '1px solid #f1f5f9',
          bgcolor: '#fafafa',
        }}
      >
        <Tabs
          value={pageTab}
          onChange={(_, v) => setPageTab(v)}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            '& .MuiTab-root': {
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.9rem',
              minHeight: 56,
              color: '#64748b',
              '&.Mui-selected': {
                color: '#6366f1',
              },
            },
            '& .MuiTabs-indicator': {
              backgroundColor: '#6366f1',
              height: 3,
              borderRadius: '3px 3px 0 0',
            },
          }}
        >
          <Tab 
            icon={<DashboardIcon sx={{ fontSize: 20 }} />} 
            iconPosition="start" 
            label="市场概览" 
          />
          <Tab 
            icon={<EmojiEventsIcon sx={{ fontSize: 20 }} />} 
            iconPosition="start" 
            label="基金排行" 
          />
          <Tab 
            icon={<FolderIcon sx={{ fontSize: 20 }} />} 
            iconPosition="start" 
            label="我的持仓" 
          />
        </Tabs>
      </Paper>

      {/* Tab Content */}
      {pageTab === 0 && (
        <FundMarketOverview />
      )}

      {pageTab === 1 && (
        <FundRankingTable 
          initialFundType={selectedRankingType}
          onFundClick={(code, name) => {
            // Open fund details dialog
            const fundItem: FundItem = { code, name, is_active: true };
            handleViewDetails(fundItem);
          }}
        />
      )}

      {pageTab === 2 && (
        <>
          {loading ? (
            <div className="flex justify-center py-20">
              <CircularProgress size={32} sx={{ color: '#6366f1' }} />
            </div>
          ) : (
        <>
          {/* Estimation Status Bar */}
          <Box sx={{ 
            display: 'flex', 
            justifyContent: 'space-between', 
            alignItems: 'center',
            px: 2,
            py: 1.5,
            bgcolor: isTrading ? 'rgba(34, 197, 94, 0.05)' : '#f8fafc',
            border: '1px solid',
            borderColor: isTrading ? 'rgba(34, 197, 94, 0.2)' : '#e2e8f0',
            borderRadius: '12px',
            mb: 2,
          }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <TrendingUpIcon sx={{ color: isTrading ? '#22c55e' : '#94a3b8', fontSize: 20 }} />
              <Typography sx={{ fontSize: '0.85rem', fontWeight: 700, color: isTrading ? '#16a34a' : '#64748b' }}>
                {isTrading ? '盘中估值 · 实时更新' : '收盘估值 · 15:00数据'}
              </Typography>
              {isTrading && (
                <Chip 
                  label="LIVE" 
                  size="small" 
                  sx={{ 
                    bgcolor: '#22c55e', 
                    color: '#fff', 
                    fontSize: '0.6rem', 
                    fontWeight: 900,
                    height: '18px',
                    animation: 'pulse 2s infinite',
                    '@keyframes pulse': {
                      '0%, 100%': { opacity: 1 },
                      '50%': { opacity: 0.7 },
                    },
                  }} 
                />
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              {lastEstimationUpdate && (
                <Typography sx={{ fontSize: '0.75rem', color: '#94a3b8', fontFamily: 'JetBrains Mono' }}>
                  更新于 {new Date(lastEstimationUpdate).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </Typography>
              )}
              <IconButton 
                size="small" 
                onClick={loadEstimations}
                disabled={estimationLoading}
                sx={{ 
                  color: '#64748b',
                  '&:hover': { color: '#6366f1', bgcolor: 'rgba(99, 102, 241, 0.05)' },
                }}
              >
                <RefreshIcon 
                  fontSize="small" 
                  sx={{ 
                    animation: estimationLoading ? 'spin 1s linear infinite' : 'none',
                    '@keyframes spin': { from: { transform: 'rotate(0deg)' }, to: { transform: 'rotate(360deg)' } },
                  }} 
                />
              </IconButton>
            </Box>
          </Box>

        <TableContainer component={Paper} elevation={0} sx={{ borderRadius: '16px', border: '1px solid #f1f5f9', overflow: 'hidden' }}>
          <Table sx={{ minWidth: 650 }}>
            <TableHead sx={{ bgcolor: '#f8fafc' }}>
              <TableRow>
                {compareMode && (
                  <TableCell padding="checkbox" sx={{ py: 2 }}>
                    <Checkbox
                      indeterminate={selectedForCompare.size > 0 && selectedForCompare.size < funds.length}
                      checked={funds.length > 0 && selectedForCompare.size === funds.length}
                      onChange={(e) => {
                        if (e.target.checked) {
                          const allCodes = new Set(funds.slice(0, 10).map(f => f.code));
                          setSelectedForCompare(allCodes);
                        } else {
                          setSelectedForCompare(new Set());
                        }
                      }}
                      sx={{ color: '#94a3b8' }}
                    />
                  </TableCell>
                )}
                <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.fund_entity')}</TableCell>
                <TableCell align="right" sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>估算净值</TableCell>
                <TableCell align="right" sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>估算涨幅</TableCell>
                <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.strategy')}</TableCell>
                <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.auto_schedule')}</TableCell>
                <TableCell align="right" sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.actions')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {funds.map((fund, idx) => (
                <TableRow
                  key={fund.code}
                  hover
                  onClick={() => compareMode ? handleToggleCompare(fund.code) : handleViewDetails(fund)}
                  sx={{
                    cursor: 'pointer',
                    '&:last-child td, &:last-child th': { border: 0 },
                    bgcolor: selectedForCompare.has(fund.code) ? 'rgba(99, 102, 241, 0.05)' : 'inherit',
                  }}
                >
                  {compareMode && (
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedForCompare.has(fund.code)}
                        onChange={() => handleToggleCompare(fund.code)}
                        onClick={(e) => e.stopPropagation()}
                        sx={{
                          color: '#94a3b8',
                          '&.Mui-checked': { color: CHART_COLORS[idx % CHART_COLORS.length] },
                        }}
                      />
                    </TableCell>
                  )}
                  <TableCell sx={{ py: 2.5 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                      <Box sx={{ p: 1, bgcolor: '#f1f5f9', borderRadius: '10px', color: '#6366f1' }}>    
                        <AccountBalanceWalletIcon fontSize="small" />
                      </Box>
                      <Box>
                        <Typography sx={{ fontWeight: 800, color: '#1e293b', fontSize: '0.9rem' }}>{fund.name}</Typography>
                        <Typography sx={{ color: '#94a3b8', fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>{fund.code}</Typography>
                      </Box>
                    </Box>
                  </TableCell>
                  {/* Estimated NAV */}
                  <TableCell align="right">
                    {estimations[fund.code]?.not_available ? (
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>--</Typography>
                    ) : estimations[fund.code]?.estimated_nav ? (
                      <Box>
                        <Typography sx={{ 
                          fontFamily: 'JetBrains Mono', 
                          fontWeight: 800, 
                          fontSize: '0.95rem',
                          color: '#1e293b',
                        }}>
                          {estimations[fund.code].estimated_nav?.toFixed(4)}
                        </Typography>
                        <Typography sx={{ 
                          fontSize: '0.65rem', 
                          color: '#94a3b8',
                          fontFamily: 'JetBrains Mono',
                        }}>
                          前值 {estimations[fund.code].prev_nav?.toFixed(4)}
                        </Typography>
                      </Box>
                    ) : (
                      <Typography sx={{ color: '#cbd5e1', fontSize: '0.75rem' }}>加载中...</Typography>
                    )}
                  </TableCell>
                  {/* Estimated Change % */}
                  <TableCell align="right">
                    {estimations[fund.code]?.not_available ? (
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem' }}>--</Typography>
                    ) : estimations[fund.code]?.estimated_change_pct !== null && estimations[fund.code]?.estimated_change_pct !== undefined ? (
                      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                        <Typography sx={{ 
                          fontFamily: 'JetBrains Mono', 
                          fontWeight: 900, 
                          fontSize: '1rem',
                          color: (estimations[fund.code].estimated_change_pct ?? 0) > 0 
                            ? '#ef4444' 
                            : (estimations[fund.code].estimated_change_pct ?? 0) < 0 
                              ? '#22c55e' 
                              : '#64748b',
                        }}>
                          {(estimations[fund.code].estimated_change_pct ?? 0) > 0 ? '+' : ''}
                          {estimations[fund.code].estimated_change_pct?.toFixed(2)}%
                        </Typography>
                      </Box>
                    ) : (
                      <Typography sx={{ color: '#cbd5e1', fontSize: '0.75rem' }}>--</Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip 
                      label={fund.style || 'Other'} 
                      size="small" 
                      variant="outlined" 
                      sx={{ 
                        fontSize: '0.65rem', 
                        fontWeight: 800, 
                        color: '#64748b', 
                        bgcolor: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '6px'
                      }} 
                    />
                  </TableCell>
                  <TableCell>
                    {(!fund.pre_market_time && !fund.post_market_time) ? (
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.05em' }}>{t('funds.table.manual_only')}</Typography>
                    ) : (
                        <Box sx={{ display: 'flex', gap: 1 }}>
                            {fund.pre_market_time && <Chip label={`${t('funds.table.pre')} ${fund.pre_market_time}`} size="small" sx={{ fontSize: '0.6rem', height: '18px', bgcolor: 'rgba(99, 102, 241, 0.05)', color: '#6366f1', fontWeight: 800 }} />}
                            {fund.post_market_time && <Chip label={`${t('funds.table.post')} ${fund.post_market_time}`} size="small" sx={{ fontSize: '0.6rem', height: '18px', bgcolor: 'rgba(245, 158, 11, 0.05)', color: '#d97706', fontWeight: 800 }} />}
                        </Box>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <IconButton 
                      size="small" 
                      onClick={(e) => handleOpenMenu(e, fund)}
                      sx={{ color: '#94a3b8', '&:hover': { color: '#6366f1', bgcolor: 'rgba(99, 102, 241, 0.05)' } }}
                    >
                      <MoreVertIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
        </>
          )}
        </>
      )}

      {/* Comparison Results Dialog */}
      <Dialog
        open={comparisonData !== null}
        onClose={() => setComparisonData(null)}
        maxWidth="lg"
        fullWidth
        scroll="paper"
        PaperProps={{
          sx: {
            borderRadius: '20px',
            bgcolor: '#ffffff',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            maxHeight: '90vh',
          }
        }}
      >
        {comparisonData && (
          <>
            <DialogTitle sx={{ p: 0 }}>
              <Box sx={{ p: 2.5, bgcolor: '#f8fafc', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <Typography variant="h6" sx={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 1 }}>
                  <CompareArrowsIcon sx={{ color: '#6366f1' }} />
                  {t('funds.compare.results_title')} ({Object.keys(comparisonData.nav_comparison?.curves || {}).length} {t('funds.compare.funds')})
                </Typography>
                <IconButton size="small" onClick={() => setComparisonData(null)} sx={{ color: '#94a3b8' }}>
                  <CloseIcon />
                </IconButton>
              </Box>
            </DialogTitle>

            <DialogContent sx={{ p: 0 }}>
              <Tabs
                value={compareTab}
                onChange={(_, v) => setCompareTab(v)}
                sx={{
                  borderBottom: '1px solid #f1f5f9',
                  px: 2,
                  '& .MuiTab-root': { textTransform: 'none', fontWeight: 700 },
                  '& .Mui-selected': { color: '#6366f1 !important' },
                  '& .MuiTabs-indicator': { bgcolor: '#6366f1' },
                }}
              >
                <Tab label={t('funds.compare.nav_chart')} />
                <Tab label={t('funds.compare.return_compare')} />
                <Tab label={t('funds.compare.risk_compare')} />
                <Tab label={t('funds.compare.holdings_overlap')} />
              </Tabs>

              <Box sx={{ p: 3 }}>
                {/* NAV Chart */}
                {compareTab === 0 && (
                  <Box sx={{ height: 400 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={getNavChartData()}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                        <XAxis dataKey="date" tick={{ fontSize: 11 }} tickFormatter={(v) => v.slice(5)} />
                        <YAxis tick={{ fontSize: 11 }} domain={['auto', 'auto']} />
                        <RechartsTooltip formatter={(value: any) => [value?.toFixed(4), '']} />
                        <Legend />
                        {Object.keys(comparisonData.nav_comparison?.curves || {}).map((code, idx) => (
                          <Line
                            key={code}
                            type="monotone"
                            dataKey={code}
                            name={comparisonData.nav_comparison.curves[code].name}
                            stroke={CHART_COLORS[idx % CHART_COLORS.length]}
                            dot={false}
                            strokeWidth={2}
                          />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </Box>
                )}

                {/* Return Comparison */}
                {compareTab === 1 && comparisonData.return_comparison && (
                  <TableContainer>
                    <Table>
                      <TableHead sx={{ bgcolor: '#f8fafc' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 800 }}>{t('funds.compare.fund_name')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>1M</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>3M</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>6M</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>1Y</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>3Y</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.values(comparisonData.return_comparison.returns).map((fund: any, idx) => (
                          <TableRow key={fund.code} hover>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: CHART_COLORS[idx % CHART_COLORS.length] }} />
                                <Typography sx={{ fontWeight: 600 }}>{fund.name}</Typography>
                              </Box>
                            </TableCell>
                            {['1m', '3m', '6m', '1y', '3y'].map((period) => (
                              <TableCell
                                key={period}
                                align="right"
                                sx={{
                                  fontFamily: 'JetBrains Mono',
                                  fontWeight: 700,
                                  color: fund[period] > 0 ? 'success.main' : fund[period] < 0 ? 'error.main' : 'text.primary',
                                }}
                              >
                                {fund[period] !== null ? `${fund[period] > 0 ? '+' : ''}${fund[period]}%` : '-'}
                              </TableCell>
                            ))}
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}

                {/* Risk Comparison */}
                {compareTab === 2 && comparisonData.risk_comparison && (
                  <TableContainer>
                    <Table>
                      <TableHead sx={{ bgcolor: '#f8fafc' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 800 }}>{t('funds.compare.fund_name')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>{t('funds.risk.sharpe_ratio')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>{t('funds.risk.max_drawdown')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>{t('funds.risk.volatility')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>{t('funds.risk.calmar_ratio')}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 800 }}>{t('funds.risk.annual_return')}</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {Object.values(comparisonData.risk_comparison.metrics).map((fund: any, idx) => (
                          <TableRow key={fund.code} hover>
                            <TableCell>
                              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: CHART_COLORS[idx % CHART_COLORS.length] }} />
                                <Typography sx={{ fontWeight: 600 }}>{fund.name}</Typography>
                              </Box>
                            </TableCell>
                            <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 700 }}>{fund.sharpe_ratio}</TableCell>
                            <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 700, color: 'error.main' }}>-{fund.max_drawdown}%</TableCell>
                            <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 700 }}>{fund.annual_volatility}%</TableCell>
                            <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 700 }}>{fund.calmar_ratio}</TableCell>
                            <TableCell
                              align="right"
                              sx={{
                                fontFamily: 'JetBrains Mono',
                                fontWeight: 700,
                                color: fund.annual_return > 0 ? 'success.main' : 'error.main',
                              }}
                            >
                              {fund.annual_return > 0 ? '+' : ''}{fund.annual_return}%
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </TableContainer>
                )}

                {/* Holdings Overlap */}
                {compareTab === 3 && comparisonData.holdings_overlap && (
                  <Box>
                    {comparisonData.holdings_overlap.common_stocks?.length > 0 ? (
                      <>
                        <Typography variant="subtitle2" sx={{ mb: 2, fontWeight: 700 }}>
                          {t('funds.compare.common_holdings')} ({comparisonData.holdings_overlap.common_stocks.length})
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                          {comparisonData.holdings_overlap.common_stocks.map((stock: any) => (
                            <Chip
                              key={stock.code}
                              label={`${stock.name} (${stock.count} ${t('funds.compare.funds')})`}
                              variant="outlined"
                              size="small"
                              sx={{ borderRadius: '8px' }}
                            />
                          ))}
                        </Box>
                      </>
                    ) : (
                      <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                        {comparisonData.holdings_overlap.message || t('funds.compare.no_common_holdings')}
                      </Typography>
                    )}
                  </Box>
                )}
              </Box>

              {/* Ranking Section */}
              {comparisonData.ranking && (
                <Box sx={{ p: 3, borderTop: '1px solid #f1f5f9', bgcolor: '#fcfcfc' }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 700 }}>
                    {t('funds.compare.ranking')}
                  </Typography>
                  <Grid container spacing={2}>
                    {comparisonData.ranking.ranking.map((fund: any) => (
                      <Grid size={{ xs: 12, sm: 6, md: 4 }} key={fund.code}>
                        <Paper
                          variant="outlined"
                          sx={{
                            p: 2,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 2,
                            borderRadius: '12px',
                            borderLeft: fund.rank === 1 ? 4 : 0,
                            borderColor: fund.rank === 1 ? 'warning.main' : '#e2e8f0',
                            bgcolor: fund.rank === 1 ? 'rgba(245, 158, 11, 0.05)' : '#fff',
                          }}
                        >
                          <Typography
                            variant="h4"
                            sx={{
                              fontWeight: 900,
                              fontFamily: 'JetBrains Mono',
                              color: fund.rank === 1 ? 'warning.main' : fund.rank === 2 ? '#94a3b8' : fund.rank === 3 ? '#cd7f32' : 'text.secondary',
                            }}
                          >
                            #{fund.rank}
                          </Typography>
                          <Box>
                            <Typography variant="body1" sx={{ fontWeight: 700 }}>{fund.name}</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'JetBrains Mono' }}>
                              {t('funds.compare.score')}: {fund.score}
                            </Typography>
                          </Box>
                        </Paper>
                      </Grid>
                    ))}
                  </Grid>
                </Box>
              )}
            </DialogContent>

            <DialogActions sx={{ p: 2, borderTop: '1px solid #f1f5f9', bgcolor: '#fcfcfc' }}>
              <Button
                onClick={() => setComparisonData(null)}
                variant="contained"
                sx={{
                  bgcolor: '#0f172a',
                  color: '#ffffff',
                  px: 4,
                  borderRadius: '10px',
                  textTransform: 'none',
                  fontWeight: 700,
                  '&:hover': { bgcolor: '#1e293b' }
                }}
              >
                {t('funds.details.close')}
              </Button>
            </DialogActions>
          </>
        )}
      </Dialog>

      {/* Notifications */}
      <Snackbar 
        open={notify.open} 
        autoHideDuration={4000} 
        onClose={() => setNotify(prev => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
      >
        <Alert severity={notify.severity} sx={{ width: '100%', borderRadius: '10px', fontWeight: 700, boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }}>
          {notify.message}
        </Alert>
      </Snackbar>

      {/* Fund Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
            elevation: 2,
            sx: { 
                minWidth: 200, 
                bgcolor: '#ffffff', 
                border: '1px solid #e2e8f0',
                borderRadius: '12px',
                mt: 1,
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
            }
        }}
      >
        <MenuItem onClick={() => { handleCloseMenu(); if (menuFund) handleViewDetails(menuFund); }} sx={{ py: 1.5 }}>
            <ListItemIcon><AnalyticsIcon fontSize="small" sx={{ color: '#6366f1' }} /></ListItemIcon>    
            <ListItemText primary={t('funds.menu.view_intelligence')} primaryTypographyProps={{ fontSize: '0.85rem', fontWeight: 700 }} />
        </MenuItem>
        
        <Divider sx={{ my: 0.5, borderColor: '#f1f5f9' }} />

        <MenuItem onClick={() => { handleCloseMenu(); handleRunAnalysis('pre'); }} sx={{ py: 1 }}>       
            <ListItemIcon><AssessmentIcon fontSize="small" color="primary" /></ListItemIcon>
            <ListItemText primary={t('funds.menu.run_pre')} primaryTypographyProps={{ fontSize: '0.85rem', color: '#334155' }} />
        </MenuItem>
        <MenuItem onClick={() => { handleCloseMenu(); handleRunAnalysis('post'); }} sx={{ py: 1 }}>      
            <ListItemIcon><AssessmentIcon fontSize="small" sx={{ color: '#f59e0b' }} /></ListItemIcon>   
            <ListItemText primary={t('funds.menu.run_post')} primaryTypographyProps={{ fontSize: '0.85rem', color: '#334155' }} />
        </MenuItem>
        
        <Divider sx={{ my: 0.5, borderColor: '#f1f5f9' }} />

        <MenuItem onClick={() => { handleCloseMenu(); if (menuFund) handleOpenDialog(menuFund); }} sx={{ py: 1 }}>
            <ListItemIcon><EditIcon fontSize="small" sx={{ color: '#64748b' }} /></ListItemIcon>
            <ListItemText primary={t('funds.menu.edit_config')} primaryTypographyProps={{ fontSize: '0.85rem', color: '#334155' }} />
        </MenuItem>
        <MenuItem onClick={() => { handleCloseMenu(); if (menuFund) handleDelete(menuFund.code); }} sx={{ py: 1 }}>
            <ListItemIcon><DeleteIcon fontSize="small" color="error" /></ListItemIcon>
            <ListItemText primary={t('funds.menu.delete')} primaryTypographyProps={{ fontSize: '0.85rem', color: '#f43f5e', fontWeight: 700 }} />
        </MenuItem>
      </Menu>

      {/* Add/Edit Fund Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800, borderBottom: '1px solid #f1f5f9' }}>
            {editingFund ? t('funds.dialog.edit_title') : t('funds.dialog.add_title')}
        </DialogTitle>
        <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 3 }}>
                
                {/* 1. Market Search (Only for new targets) */}
                {!editingFund && (
                    <Box>
                        <Typography variant="overline" sx={{ color: '#64748b', fontWeight: 800, mb: 1, display: 'block' }}>{t('funds.dialog.market_search')}</Typography>
                        <Autocomplete
                            fullWidth
                            inputValue={inputValue}
                            onInputChange={(_, newInputValue) => setInputValue(newInputValue)}
                            onChange={handleMarketFundSelect}
                            options={searchResults}
                            getOptionLabel={(option) => `[${option.code}] ${option.name}`}
                            loading={searching}
                            renderInput={(params) => (
                            <TextField
                                {...params}
                                label={t('funds.dialog.search_placeholder')}
                                variant="outlined"
                                size="small"
                                onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                        e.preventDefault();
                                        handleSearch(inputValue);
                                    }
                                }}
                                InputProps={{
                                ...params.InputProps,
                                startAdornment: (
                                    <>
                                    <SearchIcon className="text-slate-400 mr-2" />
                                    {params.InputProps.startAdornment}
                                    </>
                                ),
                                endAdornment: (
                                    <>
                                    {searching ? <CircularProgress color="inherit" size={20} /> : null}
                                    {params.InputProps.endAdornment}
                                    </>
                                ),
                                }}
                            />
                            )}
                        />
                    </Box>
                )}

                {/* 2. Asset Identity */}
                <Box>
                    <Typography variant="overline" sx={{ color: '#64748b', fontWeight: 800, mb: 1, display: 'block' }}>{t('funds.dialog.asset_identity')}</Typography>
                    <Grid container spacing={2}>
                        <Grid size={4}>
                            <TextField
                                label={t('funds.dialog.fund_code')}
                                fullWidth
                                size="small"
                                value={formCode}
                                onChange={(e) => setFormCode(e.target.value)}
                                disabled={!!editingFund}
                                placeholder="000000"
                            />
                        </Grid>
                        <Grid size={8}>
                            <TextField
                                label={t('funds.dialog.fund_name')}
                                fullWidth
                                size="small"
                                value={formName}
                                onChange={(e) => setFormName(e.target.value)}
                                placeholder="Target Name"
                            />
                        </Grid>
                    </Grid>
                </Box>

                {/* 3. Strategy Configuration */}
                <Box>
                    <Typography variant="overline" sx={{ color: '#64748b', fontWeight: 800, mb: 1, display: 'block' }}>{t('funds.dialog.strategy_config')}</Typography>
                    <Grid container spacing={2}>
                        <Grid size={6}>
                            <TextField
                                label={t('funds.dialog.style')}
                                fullWidth
                                size="small"
                                value={formStyle}
                                onChange={(e) => setFormStyle(e.target.value)}
                                placeholder="Growth, Sector, etc."
                            />
                        </Grid>
                        <Grid size={6}>
                            <TextField
                                label={t('funds.dialog.focus_sectors')}
                                fullWidth
                                size="small"
                                value={formFocus}
                                onChange={(e) => setFormFocus(e.target.value)}
                                placeholder="AI, Bio, Chips..."
                                helperText="Comma separated"
                            />
                        </Grid>
                    </Grid>
                </Box>

                {/* 4. Automation Windows */}
                <Box sx={{ p: 2, bgcolor: '#f8fafc', borderRadius: '12px', border: '1px dashed #e2e8f0' }}>
                    <Typography variant="overline" sx={{ color: '#64748b', fontWeight: 800, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                        <HistoryIcon sx={{ fontSize: 16 }} /> {t('funds.dialog.schedule')}
                    </Typography>
                    <Grid container spacing={2}>
                        <Grid size={6}>
                            <TextField
                                label={t('funds.dialog.pre_market')}
                                type="time"
                                fullWidth
                                size="small"
                                value={formPreTime}
                                onChange={(e) => setFormPreTime(e.target.value)}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>
                        <Grid size={6}>
                            <TextField
                                label={t('funds.dialog.post_market')}
                                type="time"
                                fullWidth
                                size="small"
                                value={formPostTime}
                                onChange={(e) => setFormPostTime(e.target.value)}
                                InputLabelProps={{ shrink: true }}
                            />
                        </Grid>
                    </Grid>
                </Box>
            </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3, borderTop: '1px solid #f1f5f9' }}>
          <Button onClick={() => setOpenDialog(false)} sx={{ color: '#64748b', fontWeight: 700 }}>{t('funds.dialog.cancel')}</Button>
          <Button 
            onClick={handleSave} 
            variant="contained" 
            sx={{ bgcolor: '#6366f1', fontWeight: 800, borderRadius: '8px', px: 4, '&:hover': { bgcolor: '#4f46e5' } }}
          >
            {t('funds.dialog.confirm')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Enhanced Fund Details Dialog */}
      <FundDetailDialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        fundCode={selectedFund?.code || ''}
        fundName={selectedFund?.name || ''}
      />
    </Box>
  );
}
