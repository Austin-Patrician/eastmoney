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
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import HistoryIcon from '@mui/icons-material/History';
import PieChartIcon from '@mui/icons-material/PieChart';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import AssessmentIcon from '@mui/icons-material/Assessment';
import EditIcon from '@mui/icons-material/Edit';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import CloseIcon from '@mui/icons-material/Close';
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
  fetchFundMarketDetails,
  fetchFundNavHistory,
  generateReport,
  compareFundsAdvanced,
} from '../api';

import type { MarketFund, FundItem, NavPoint, FundComparisonResponse } from '../api';
import { useAppContext } from '../contexts/AppContext';

const CHART_COLORS = [
  '#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];


export default function FundsPage() {
  const { t } = useTranslation();
  const { setCurrentPage, setCurrentFund } = useAppContext();
  const [funds, setFunds] = useState<FundItem[]>([]);
  const [loading, setLoading] = useState(false);
  
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
  const [fundDetails, setFundDetails] = useState<any>(null);
  const [navHistory, setNavHistory] = useState<NavPoint[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailTab, setDetailTab] = useState(0);

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
    setLoadingDetails(true);
    setFundDetails(null);
    setNavHistory([]);

    // Update context for AI assistant
    setCurrentFund({ code: fund.code, name: fund.name });

    try {
      const [details, nav] = await Promise.all([
        fetchFundMarketDetails(fund.code),
        fetchFundNavHistory(fund.code)
      ]);
      setFundDetails(details);
      setNavHistory(nav);
    } catch (error) {
      console.error("Failed to load fund details", error);
    } finally {
      setLoadingDetails(false);
    }
  };

  // Improved SVG Line Chart Renderer
  const renderMiniChart = (data: NavPoint[]) => {
    if (!data || data.length < 2) return null;
    const values = data.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min;
    const padding = 20;
    const width = 800;
    const height = 240;
    
    const points = data.map((d, i) => {
      const x = (i / (data.length - 1)) * (width - 2 * padding) + padding;
      const y = (height - padding) - ((d.value - min) / range) * (height - 2 * padding);
      return `${x},${y}`;
    }).join(' ');

    return (
      <Box sx={{ bgcolor: '#fcfcfc', p: 2, borderRadius: '12px', border: '1px solid #f1f5f9' }}>
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48 overflow-visible">
          {/* Horizontal Grid Lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((v) => {
              const y = (height - padding) - v * (height - 2 * padding);
              const val = (min + v * range).toFixed(4);
              return (
                  <g key={v}>
                      <line x1={padding} y1={y} x2={width-padding} y2={y} stroke="#e2e8f0" strokeDasharray="4 4" />
                      <text x={0} y={y + 4} fontSize="10" fill="#94a3b8" fontFamily="JetBrains Mono">{val}</text>
                  </g>
              )
          })}
          <polyline
            fill="none"
            stroke="#6366f1"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={points}
          />
          {/* Shadow area */}
          <path
            d={`M${padding},${height-padding} L${points} L${width-padding},${height-padding} Z`}
            fill="rgba(99, 102, 241, 0.08)"
          />
        </svg>
      </Box>
    );
  };

  return (
    <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 4 }}>
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
          {compareMode ? (
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
          ) : (
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

      {loading ? (
        <div className="flex justify-center py-20">
          <CircularProgress size={32} sx={{ color: '#6366f1' }} />
        </div>
      ) : (
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
                <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.strategy')}</TableCell>
                <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.75rem', py: 2 }}>{t('funds.table.sectors')}</TableCell>
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
                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                        {fund.focus?.map((tag, i) => (
                            <Chip key={i} label={tag} size="small" sx={{ fontSize: '0.6rem', height: '18px', bgcolor: '#f1f5f9', color: '#64748b' }} />
                        ))}
                    </Box>
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

      {/* Fund Details Dialog - Professional Financial Factsheet */}

      {/* Fund Details Dialog - Professional Financial Factsheet */}
      <Dialog 
        open={detailOpen} 
        onClose={() => setDetailOpen(false)} 
        maxWidth="sm" 
        fullWidth
        scroll="paper"
        PaperProps={{ 
          sx: { 
            borderRadius: '20px', 
            bgcolor: '#ffffff', 
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            height: '90vh',
          } 
        }}
      >
        {/* Header Section - Modern Ticker Style */}
        <DialogTitle sx={{ p: 0 }}>
          <Box sx={{ 
            bgcolor: '#fcfcfc', 
            p: 3.5, 
            borderBottom: '1px solid #f1f5f9',
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <Box sx={{ flex: 1 }}>
                <Typography variant="h5" sx={{ fontWeight: 900, color: '#0f172a', letterSpacing: '-0.02em', mb: 1, lineHeight: 1.2 }}>
                    {selectedFund?.name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                    <Box sx={{ px: 1, py: 0.25, bgcolor: '#6366f1', borderRadius: '4px' }}>
                        <Typography sx={{ color: '#fff', fontWeight: 800, fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>
                            {selectedFund?.code}
                        </Typography>
                    </Box>
                    <Typography variant="caption" sx={{ color: '#64748b', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {typeof fundDetails?.info?.type === 'string' ? fundDetails.info.type : 'Sector Strategy'}
                    </Typography>
                </Box>
              </Box>
              <Box sx={{ textAlign: 'right', minWidth: '120px' }}>
                <Typography sx={{ color: '#6366f1', fontSize: '0.7rem', fontWeight: 900, mb: 0.5, letterSpacing: '0.1em' }}>{t('funds.details.latest_nav')}</Typography>
                <Typography variant="h4" sx={{ color: '#0f172a', fontWeight: 900, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                    {fundDetails?.info?.nav && typeof fundDetails.info.nav !== 'object' && fundDetails.info.nav !== "---" 
                      ? fundDetails.info.nav 
                      : (navHistory.length > 0 ? navHistory[navHistory.length - 1].value.toFixed(4) : '---')}
                </Typography>
              </Box>
            </Box>
            
            {/* Quick Metadata Grid */}
            <Grid container spacing={2} sx={{ mt: 1 }}>
                 {[
                   { label: t('funds.details.manager'), value: fundDetails?.info?.manager },
                   { label: t('funds.details.fund_size'), value: fundDetails?.info?.size },
                   { label: t('funds.details.morningstar'), value: fundDetails?.info?.rating },
                 ].map((item, i) => (
                   <Grid size={4} key={i}>
                      <Typography sx={{ color: '#94a3b8', fontSize: '0.65rem', fontWeight: 800, mb: 0.5 }}>{item.label}</Typography>
                      <Typography sx={{ color: '#334155', fontSize: '0.75rem', fontWeight: 700 }}>
                        {item.value && typeof item.value !== 'object' ? item.value : '---'}
                      </Typography>
                   </Grid>
                 ))}
            </Grid>
          </Box>
        </DialogTitle>

        <DialogContent sx={{ p: 0, bgcolor: '#ffffff' }}>
          {loadingDetails ? (
            <Box sx={{ py: 12, textAlign: 'center' }}>
              <CircularProgress size={32} thickness={5} sx={{ color: '#6366f1', mb: 2 }} />
              <Typography variant="body2" sx={{ color: '#64748b', fontWeight: 600 }}>Fetching Market Intelligence...</Typography>
            </Box>
          ) : fundDetails ? (
            <Box sx={{ p: 3.5, display: 'flex', flexDirection: 'column', gap: 5 }}>
              
              {/* 1. Core Chart Section */}
              <Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                    <Typography variant="overline" sx={{ color: '#0f172a', fontWeight: 900, fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 1 }}>
                        <TrendingUpIcon sx={{ fontSize: 18, color: '#6366f1' }} /> {t('funds.details.performance_analytics')}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#94a3b8', fontWeight: 700 }}>{t('funds.details.last_100_days')}</Typography>
                </Box>
                <Box sx={{ p: 2.5, borderRadius: '16px', border: '1px solid #f1f5f9', bgcolor: '#fcfcfc', boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.02)' }}>
                    {renderMiniChart(navHistory)}
                </Box>
              </Box>

              {/* 2. Statistical Data Tabs */}
              <Box>
                <Typography variant="overline" sx={{ color: '#0f172a', fontWeight: 900, fontSize: '0.75rem', mb: 2, display: 'block' }}>
                    {t('funds.details.historical_reference')}
                </Typography>
                <Tabs 
                    value={detailTab} 
                    onChange={(_, v) => setDetailTab(v)}
                    sx={{
                        minHeight: '40px',
                        mb: 2.5,
                        borderBottom: '1px solid #f1f5f9',
                        '& .MuiTab-root': { py: 1, minHeight: '40px', textTransform: 'none', fontWeight: 800, fontSize: '0.85rem', color: '#94a3b8' },
                        '& .Mui-selected': { color: '#6366f1 !important' },
                        '& .MuiTabs-indicator': { bgcolor: '#6366f1', height: 3, borderRadius: '3px 3px 0 0' }
                    }}
                >
                    <Tab label={t('funds.details.stats_tab')} />
                    <Tab label={t('funds.details.nav_tab')} />
                </Tabs>

                {detailTab === 0 ? (
                    <TableContainer sx={{ borderRadius: '12px', border: '1px solid #f1f5f9' }}>
                        <Table size="small">
                            <TableHead sx={{ bgcolor: '#f8fafc' }}>
                                <TableRow>
                                    <TableCell sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.7rem' }}>{t('funds.details.timeframe')}</TableCell>
                                    <TableCell align="right" sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.7rem' }}>{t('funds.details.return')}</TableCell>
                                    <TableCell align="right" sx={{ color: '#64748b', fontWeight: 800, fontSize: '0.7rem' }}>{t('funds.details.rank')}</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {fundDetails.performance.map((p: any, idx: number) => (
                                    <TableRow key={idx} hover sx={{ '&:last-child td': { border: 0 } }}>
                                        <TableCell sx={{ color: '#334155', fontWeight: 700, fontSize: '0.8rem' }}>{p['时间范围']}</TableCell>
                                        <TableCell align="right" sx={{ 
                                            fontWeight: 900, 
                                            fontFamily: 'JetBrains Mono',
                                            fontSize: '0.85rem',
                                            color: (p['收益率'] === null || p['收益率'] === undefined) ? '#cbd5e1' : (parseFloat(p['收益率']) >= 0 ? '#ef4444' : '#22c55e')
                                        }}>
                                            {p['收益率'] !== null && p['收益率'] !== undefined ? `${p['收益率']}%` : '---'}
                                        </TableCell>
                                        <TableCell align="right" sx={{ color: '#94a3b8', fontSize: '0.7rem', fontWeight: 800 }}>{p['同类排名']}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                ) : (
                    <TableContainer sx={{ borderRadius: '12px', border: '1px solid #f1f5f9', maxHeight: '320px' }}>
                        <Table size="small" stickyHeader>
                            <TableHead>
                                <TableRow>
                                    <TableCell sx={{ bgcolor: '#f8fafc', color: '#64748b', fontWeight: 800, fontSize: '0.7rem' }}>{t('funds.details.date')}</TableCell>
                                    <TableCell align="right" sx={{ bgcolor: '#f8fafc', color: '#64748b', fontWeight: 800, fontSize: '0.7rem' }}>{t('funds.details.adj_nav')}</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {[...navHistory].reverse().map((point, idx) => (
                                    <TableRow key={idx} hover sx={{ '&:last-child td': { border: 0 } }}>
                                        <TableCell sx={{ color: '#64748b', fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>{point.date}</TableCell>
                                        <TableCell align="right" sx={{ fontWeight: 800, color: '#0f172a', fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                                            {point.value !== null && point.value !== undefined ? point.value.toFixed(4) : '---'}
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                )}
              </Box>

              {/* 3. Strategic Holdings Section */}
              <Box sx={{ mb: 2 }}>
                <Typography variant="overline" sx={{ color: '#0f172a', fontWeight: 900, fontSize: '0.75rem', mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                    <PieChartIcon sx={{ fontSize: 18, color: '#6366f1' }} /> {t('funds.details.core_holdings')}
                </Typography>
                {fundDetails.portfolio && fundDetails.portfolio.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                        {fundDetails.portfolio.map((stock: any, idx: number) => (
                            <Box key={idx} sx={{ 
                                p: 1.5, 
                                borderRadius: '12px', 
                                border: '1px solid #f1f5f9',
                                '&:hover': { bgcolor: '#f8fafc' },
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}>
                                <Box sx={{ flex: 1 }}>
                                    <Typography sx={{ color: '#0f172a', fontWeight: 800, fontSize: '0.85rem' }}>{stock['股票名称']}</Typography>
                                    <Typography sx={{ color: '#94a3b8', fontSize: '0.7rem', fontFamily: 'JetBrains Mono' }}>{stock['股票代码']}</Typography>
                                </Box>
                                <Box sx={{ textAlign: 'right', width: '40%' }}>
                                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1.5 }}>
                                        <Typography sx={{ color: '#6366f1', fontWeight: 900, fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                                            {stock['占净值比例']}%
                                        </Typography>
                                        <Box sx={{ width: '60px', height: '6px', bgcolor: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                                            <Box sx={{ width: `${stock['占净值比例']}%`, height: '100%', bgcolor: '#6366f1', borderRadius: '3px' }} />
                                        </Box>
                                    </Box>
                                </Box>
                            </Box>
                        ))}
                    </Box>
                ) : (
                    <Box sx={{ py: 6, textAlign: 'center', bgcolor: '#f8fafc', borderRadius: '16px', border: '1px dashed #e2e8f0' }}>
                        <PieChartIcon sx={{ fontSize: 32, color: '#e2e8f0', mb: 1 }} />
                        <Typography sx={{ color: '#94a3b8', fontSize: '0.8rem', fontWeight: 700 }}>{t('funds.details.no_portfolio')}</Typography>
                    </Box>
                )}
              </Box>

            </Box>
          ) : (
             <Box sx={{ py: 15, textAlign: 'center' }}>
                 <Typography sx={{ color: '#94a3b8', fontWeight: 800 }}>VIBE_ALPHA: NODE_NOT_FOUND</Typography>
             </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 3, bgcolor: '#fcfcfc', borderTop: '1px solid #f1f5f9' }}>
          <Button 
            fullWidth
            onClick={() => setDetailOpen(false)} 
            variant="contained" 
            sx={{ 
                bgcolor: '#0f172a', 
                color: '#ffffff',
                py: 1.5,
                borderRadius: '12px',
                textTransform: 'none',
                fontWeight: 800,
                fontSize: '0.9rem',
                boxShadow: 'none',
                '&:hover': { bgcolor: '#1e293b', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)' }
            }}
          >
            {t('funds.details.close')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
