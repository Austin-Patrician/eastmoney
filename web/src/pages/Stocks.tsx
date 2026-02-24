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
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Snackbar,
  Alert,
  Tabs,
  Tab,
  alpha,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SearchIcon from '@mui/icons-material/Search';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import AnalyticsIcon from '@mui/icons-material/Analytics';
import EditIcon from '@mui/icons-material/Edit';
import BusinessIcon from '@mui/icons-material/Business';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import WbSunnyIcon from '@mui/icons-material/WbSunny';
import NightsStayIcon from '@mui/icons-material/NightsStay';
import AccountBalanceIcon from '@mui/icons-material/AccountBalance';
import GroupsIcon from '@mui/icons-material/Groups';
import CandlestickChartIcon from '@mui/icons-material/CandlestickChart';
import EventIcon from '@mui/icons-material/Event';
import SpeedIcon from '@mui/icons-material/Speed';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import FilterListIcon from '@mui/icons-material/FilterList';
import TimelineIcon from '@mui/icons-material/Timeline';

import {
  fetchStocks,
  saveStock,
  deleteStock,
  searchMarketStocks,
  fetchStockDetails,
  fetchStockHistory,
  analyzeStock,
  fetchMarketAIBrief
} from '../api';

import type { MarketStock, StockItem, StockDetails, NavPoint, MarketAIBrief } from '../api';
import { useAppContext } from '../contexts/AppContext';
import { 
  FinancialTab, 
  ShareholderTab, 
  MarginTab, 
  EventsTab, 
  QuantTab, 
  AIDiagnosisCard,
  MarketPulseCard,
  HotStocksList,
  LimitPoolTabs,
  LiveMonitorTab,
} from '../components/stock';

function AIBriefBanner() {
  const { t } = useTranslation();
  const theme = useTheme();
  const [brief, setBrief] = useState<MarketAIBrief | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const res = await fetchMarketAIBrief();
        setBrief(res);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) return null;
  if (!brief) return null;

  return (
    <Paper
      elevation={0}
      sx={{
        p: 2,
        borderRadius: 3,
        bgcolor: alpha(theme.palette.primary.main, 0.03),
        border: '1px dashed',
        borderColor: alpha(theme.palette.primary.main, 0.2),
        display: 'flex',
        alignItems: 'flex-start',
        gap: 2,
        mb: 1 
      }}
    >
      <AutoAwesomeIcon sx={{ color: 'primary.main', fontSize: 20, mt: 0.3 }} />
      <Box>
        <Typography variant="subtitle2" sx={{ fontWeight: 800, color: 'primary.main', mb: 0.5 }}>
          {t('stocks.market.ai_brief_title')}
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.primary', lineHeight: 1.6 }}>
          {brief.brief}
        </Typography>
        {brief.top_industries && brief.top_industries.length > 0 && (
          <Box sx={{ mt: 1.5, display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {brief.top_industries.map((ind, idx) => (
              <Chip
                key={idx}
                label={`${ind.name}`}
                size="small"
                sx={{
                  height: 20,
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  bgcolor: alpha('#ef4444', 0.08),
                  color: '#ef4444',
                  border: '1px solid',
                  borderColor: alpha('#ef4444', 0.2),
                }}
              />
            ))}
          </Box>
        )}
      </Box>
    </Paper>
  );
}

export default function StocksPage() {
  const { t } = useTranslation();
  const theme = useTheme();
  const { setCurrentPage, setCurrentStock } = useAppContext();
  const [stocks, setStocks] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [lastRealtimeUpdate, setLastRealtimeUpdate] = useState<string>('');
  
  // Unified Dialog State (Add/Edit)
  const [openDialog, setOpenDialog] = useState(false);
  const [editingStock, setEditingStock] = useState<StockItem | null>(null);
  const [formCode, setFormCode] = useState('');
  const [formName, setFormName] = useState('');
  const [formMarket, setFormMarket] = useState('');

  // Search State
  const [searchResults, setSearchResults] = useState<MarketStock[]>([]);
  const [searching, setSearching] = useState(false);
  const [inputValue, setInputValue] = useState('');

  // Detail View State
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedStock, setSelectedStock] = useState<StockItem | null>(null);
  const [stockDetails, setStockDetails] = useState<StockDetails | null>(null);
  const [history, setHistory] = useState<NavPoint[]>([]);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [detailTab, setDetailTab] = useState(0);

  // AI Diagnosis state
  const [showAIDiagnosis, setShowAIDiagnosis] = useState(false);

  // Action Menu State
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [menuStock, setMenuStock] = useState<StockItem | null>(null);

  // Notification State
  const [notify, setNotify] = useState<{ open: boolean, message: string, severity: 'success' | 'info' | 'warning' | 'error' }>({
    open: false,
    message: '',
    severity: 'info'
  });

  const showNotify = (message: string, severity: 'success' | 'info' | 'warning' | 'error' = 'info') => { 
    setNotify({ open: true, message, severity });
  };

  const handleOpenMenu = (event: React.MouseEvent<HTMLElement>, stock: StockItem) => {
    event.stopPropagation();
    setAnchorEl(event.currentTarget);
    setMenuStock(stock);
  };

  const handleCloseMenu = () => {
    setAnchorEl(null);
    setMenuStock(null);
  };

  const handleOpenDialog = (stock?: StockItem) => {
    setAnchorEl(null);
    setSearchResults([]);
    setInputValue('');
    if (stock) {
        setEditingStock(stock);
        setFormCode(stock.code);
        setFormName(stock.name);
        setFormMarket(stock.market || '');
    } else {
        setEditingStock(null);
        setFormCode('');
        setFormName('');
        setFormMarket('');
    }
    setOpenDialog(true);
  };

  const handleSave = async () => {
    if (!formCode || !formName) {
        showNotify(t('stocks.messages.required_fields'), 'error');
        return;
    }

    const updatedStock: StockItem = {
        code: formCode,
        name: formName,
        market: formMarket,
        is_active: true,
        sector: editingStock?.sector || '' // Preserve existing sector if editing, else empty for auto-fetch
    };

    try {
        await saveStock(updatedStock);
        showNotify(t('stocks.messages.save_success'), 'success');
        setOpenDialog(false);
        loadStocks();
    } catch (error) {
        console.error(error);
        showNotify(t('stocks.messages.save_error'), 'error');
    }
  };

  const handleSearch = async (query: string) => {
    if (query.length < 2) return;
    setSearching(true);
    try {
      const results = await searchMarketStocks(query);
      setSearchResults(results);
    } catch (error) {
      console.error(error);
    } finally {
      setSearching(false);
    }
  };

  const handleMarketStockSelect = (_event: any, value: MarketStock | null) => {
    if (value) {
        setFormCode(value.code);
        setFormName(value.name);
    }
  };

  const loadStocks = async (silent: boolean = false) => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const data = await fetchStocks();
      setStocks(data);
      setLastRealtimeUpdate(new Date().toLocaleTimeString());
    } catch (error) {
      console.error(error);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    setCurrentPage('stocks');
    loadStocks();
    return () => {
      // Clear stock context when leaving page
      setCurrentStock(null);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadStocks(true);
      }
    }, 10000);

    return () => window.clearInterval(timer);
  }, []);

  const handleDelete = async (code: string) => {
    if (window.confirm(t('stocks.messages.delete_confirm'))) {
      try {
        await deleteStock(code);
        showNotify(t('stocks.messages.delete_success'), 'success');
        loadStocks();
      } catch (error) {
        showNotify(`${t('stocks.messages.delete_error')}: ${error}`, 'error');
      }
    }
  };

  const handleViewDetails = async (stock: StockItem) => {
    setSelectedStock(stock);
    setDetailOpen(true);
    setLoadingDetails(true);
    setStockDetails(null);
    setHistory([]);
    setDetailTab(0); // Reset to overview tab
    setShowAIDiagnosis(false); // Reset AI diagnosis

    // Update context for AI assistant
    setCurrentStock({ code: stock.code, name: stock.name });

    try {
      const [details, hist] = await Promise.all([
          fetchStockDetails(stock.code),
          fetchStockHistory(stock.code)
      ]);
      setStockDetails(details);
      setHistory(hist);
    } catch (error) {
      console.error("Failed to load stock details", error);
    } finally {
      setLoadingDetails(false);
    }
  };

  useEffect(() => {
    if (!detailOpen || !selectedStock) {
      return;
    }

    const timer = window.setInterval(async () => {
      if (document.visibilityState !== 'visible') {
        return;
      }
      try {
        const details = await fetchStockDetails(selectedStock.code);
        setStockDetails((prev) => ({
          ...(prev || {}),
          ...details,
          info: details?.info || prev?.info || {}
        }));
      } catch (error) {
        console.error('Failed to refresh stock quote', error);
      }
    }, 3000);

    return () => window.clearInterval(timer);
  }, [detailOpen, selectedStock?.code]);

  const handleAnalyzeStock = async (stock: StockItem, mode: 'pre' | 'post') => {
    handleCloseMenu();
    showNotify(t('stocks.messages.analysis_started', { name: stock.name, mode: mode === 'pre' ? t('stocks.analysis.pre_market') : t('stocks.analysis.post_market') }), 'info');
    try {
      await analyzeStock(stock.code, mode);
      showNotify(t('stocks.messages.analysis_success', { name: stock.name }), 'success');
    } catch (error) {
      console.error('Analysis failed:', error);
      showNotify(t('stocks.messages.analysis_error'), 'error');
    }
  };

  const renderMiniChart = (data: NavPoint[]) => {
    if (!data || data.length < 2) return null;
    const values = data.map(d => d.value);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const padding = 20;
    const width = 800;
    const height = 240;
    
    const points = data.map((d, i) => {
      const x = (i / (data.length - 1)) * (width - 2 * padding) + padding;
      const y = (height - padding) - ((d.value - min) / range) * (height - 2 * padding);
      return `${x},${y}`;
    }).join(' ');

    const trendColor = values[values.length - 1] >= values[0] ? '#ef4444' : '#22c55e'; // Red Up, Green Down

    return (
      <Box sx={{ bgcolor: alpha(trendColor, 0.02), p: 2, borderRadius: '12px', border: `1px solid ${alpha(trendColor, 0.1)}` }}>
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-48 overflow-visible">
          {[0, 0.25, 0.5, 0.75, 1].map((v) => {
              const y = (height - padding) - v * (height - 2 * padding);
              const val = (min + v * range).toFixed(2);
              return (
                  <g key={v}>
                      <line x1={padding} y1={y} x2={width-padding} y2={y} stroke={alpha(theme.palette.divider, 0.5)} strokeDasharray="4 4" />
                      <text x={0} y={y + 4} fontSize="10" fill={theme.palette.text.secondary} fontFamily="JetBrains Mono">{val}</text>
                  </g>
              )
          })}
          <polyline
            fill="none"
            stroke={trendColor}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            points={points}
          />
          <path
            d={`M${padding},${height-padding} L${points} L${width-padding},${height-padding} Z`}
            fill={alpha(trendColor, 0.08)}
          />
        </svg>
      </Box>
    );
  };

  return (
    <Box sx={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 3, pb: 4 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <Box>
            <Typography variant="h4" sx={{ fontWeight: 800, color: 'text.primary', fontFamily: 'JetBrains Mono', letterSpacing: '-0.02em' }}>
              {t('stocks.title')}
            </Typography>
            <Typography variant="subtitle1" sx={{ color: 'text.secondary', mt: 0.5, fontWeight: 500 }}>
              {t('stocks.subtitle')}
            </Typography>
          </Box>
          {/* Market Pulse Micro-Widget */}
          <MarketPulseCard />
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
          sx={{
            backgroundColor: '#0f172a',
            color: '#fff',
            borderRadius: '8px',
            px: 3,
            py: 1,
            textTransform: 'none',
            fontWeight: 700,
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
            '&:hover': { backgroundColor: '#1e293b' }
          }}
        >
          {t('stocks.add_stock')}
        </Button>
      </Box>

      {/* AI Brief Banner (New) */}
      <AIBriefBanner />

      {/* Market Discovery Section */}
      <Grid container spacing={3}>
        {/* ... existing Grid content ... */}

        <Grid size={{ xs: 12, md: 4 }}>
          <HotStocksList 
            onStockClick={(code, name) => handleViewDetails({ code, name, is_active: true })} 
            limit={15}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 8 }}>
          <LimitPoolTabs 
            onStockClick={(code, name) => handleViewDetails({ code, name, is_active: true })}
            limit={20}
          />
        </Grid>
      </Grid>

      {/* Watchlist Section */}
      <Paper 
        elevation={0}
        sx={{ 
          borderRadius: 3, 
          border: '1px solid',
          borderColor: 'divider',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column'
        }}
      >
        <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: alpha(theme.palette.background.paper, 0.5) }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ p: 0.5, bgcolor: alpha(theme.palette.primary.main, 0.1), borderRadius: 1, color: 'primary.main' }}>
              <FilterListIcon fontSize="small" />
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
              {t('stocks.watchlist_title')}
            </Typography>
            <Chip 
              label={stocks.length} 
              size="small" 
              sx={{ ml: 1, height: 20, fontSize: '0.75rem', fontWeight: 600, bgcolor: alpha(theme.palette.divider, 0.1) }} 
            />
          </Box>
          <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
            {lastRealtimeUpdate ? `Last update ${lastRealtimeUpdate}` : ''}
          </Typography>
        </Box>

        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
            <CircularProgress size={32} sx={{ color: 'primary.main' }} />
          </Box>
        ) : (
          <TableContainer>
            <Table sx={{ minWidth: 650 }}>
              <TableHead sx={{ bgcolor: 'background.default' }}>
                <TableRow>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5, pl: 3 }}>{t('stocks.table.symbol')}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5 }}>{t('stocks.table.latest_price')}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5 }}>{t('common.change')}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5 }}>{t('stocks.table.volume')}</TableCell>
                  <TableCell sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5 }}>{t('stocks.table.sector')}</TableCell>
                  <TableCell align="right" sx={{ color: 'text.secondary', fontWeight: 700, fontSize: '0.75rem', py: 1.5, pr: 3 }}>{t('common.actions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {stocks.map((stock) => {
                  const isPositive = (stock.change_pct || 0) > 0;
                  const isNegative = (stock.change_pct || 0) < 0;
                  const color = isPositive ? '#ef4444' : isNegative ? '#22c55e' : 'text.primary';
                  
                  return (
                    <TableRow 
                      key={stock.code} 
                      hover 
                      onClick={() => handleViewDetails(stock)}
                      sx={{ 
                        cursor: 'pointer', 
                        '&:last-child td, &:last-child th': { border: 0 },
                        transition: 'background-color 0.2s',
                        '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.04) }
                      }}
                    >
                      <TableCell sx={{ py: 2, pl: 3 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                          <Box sx={{ 
                            p: 1, 
                            bgcolor: alpha(theme.palette.background.paper, 0.8), 
                            border: '1px solid',
                            borderColor: 'divider',
                            borderRadius: '10px', 
                            color: 'primary.main',
                            display: 'flex',
                            boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
                          }}>    
                            <ShowChartIcon fontSize="small" />
                          </Box>
                          <Box>
                            <Typography sx={{ fontWeight: 700, color: 'text.primary', fontSize: '0.9rem' }}>{stock.name}</Typography>
                            <Typography sx={{ color: 'text.secondary', fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>{stock.code}</Typography>
                          </Box>
                        </Box>
                      </TableCell>
                      <TableCell align="right">
                        <Typography sx={{ fontWeight: 700, color: 'text.primary', fontFamily: 'JetBrains Mono', fontSize: '0.95rem' }}>
                            {stock.price ? stock.price.toFixed(2) : '---'}
                        </Typography>
                      </TableCell>
                      <TableCell align="right">
                        <Chip 
                          label={stock.change_pct ? `${stock.change_pct > 0 ? '+' : ''}${stock.change_pct.toFixed(2)}%` : '---'}
                          size="small"
                          sx={{ 
                            bgcolor: isPositive ? alpha('#ef4444', 0.1) : isNegative ? alpha('#22c55e', 0.1) : alpha(theme.palette.divider, 0.1),
                            color: color,
                            fontWeight: 700,
                            fontFamily: 'JetBrains Mono',
                            borderRadius: '6px',
                            height: 24
                          }}
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography sx={{ color: 'text.secondary', fontSize: '0.8rem', fontWeight: 600, fontFamily: 'JetBrains Mono' }}>
                            {stock.volume ? (stock.volume / 100).toLocaleString() : '---'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        {stock.sector && (
                            <Chip 
                            label={stock.sector} 
                            size="small" 
                            variant="outlined" 
                            sx={{ 
                                fontSize: '0.65rem', 
                                fontWeight: 700, 
                                color: 'text.secondary', 
                                borderColor: alpha(theme.palette.divider, 0.8),
                                borderRadius: '6px',
                                height: 22
                            }} 
                            />
                        )}
                      </TableCell>
                      <TableCell align="right" sx={{ pr: 3 }}>
                        <IconButton 
                          size="small" 
                          onClick={(e) => handleOpenMenu(e, stock)}
                          sx={{ color: 'text.secondary', '&:hover': { color: 'primary.main', bgcolor: alpha(theme.palette.primary.main, 0.1) } }}
                        >
                          <MoreVertIcon fontSize="small" />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Paper>

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

      {/* Stock Action Menu */}
      <Menu
        anchorEl={anchorEl}
        open={Boolean(anchorEl)}
        onClose={handleCloseMenu}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
        PaperProps={{
            elevation: 0,
            sx: {
                minWidth: 200,
                border: '1px solid',
                borderColor: 'divider',
                borderRadius: '12px',
                mt: 1,
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)'
            }
        }}
      >
        <MenuItem onClick={() => { handleCloseMenu(); if (menuStock) handleViewDetails(menuStock); }} sx={{ py: 1.5 }}>
            <ListItemIcon><AnalyticsIcon fontSize="small" sx={{ color: 'primary.main' }} /></ListItemIcon>
            <ListItemText primary={t('stocks.menu.view_details')} primaryTypographyProps={{ fontSize: '0.85rem', fontWeight: 700 }} />
        </MenuItem>

        <Divider sx={{ my: 0.5 }} />

        <MenuItem onClick={() => { if (menuStock) handleAnalyzeStock(menuStock, 'pre'); }} sx={{ py: 1 }}>
            <ListItemIcon><WbSunnyIcon fontSize="small" sx={{ color: '#f59e0b' }} /></ListItemIcon>
            <ListItemText primary={t('stocks.menu.pre_market_analysis')} primaryTypographyProps={{ fontSize: '0.85rem' }} />
        </MenuItem>
        <MenuItem onClick={() => { if (menuStock) handleAnalyzeStock(menuStock, 'post'); }} sx={{ py: 1 }}>
            <ListItemIcon><NightsStayIcon fontSize="small" sx={{ color: '#8b5cf6' }} /></ListItemIcon>
            <ListItemText primary={t('stocks.menu.post_market_analysis')} primaryTypographyProps={{ fontSize: '0.85rem' }} />
        </MenuItem>

        <Divider sx={{ my: 0.5 }} />

        <MenuItem onClick={() => { handleCloseMenu(); if (menuStock) handleOpenDialog(menuStock); }} sx={{ py: 1 }}>
            <ListItemIcon><EditIcon fontSize="small" sx={{ color: 'text.secondary' }} /></ListItemIcon>
            <ListItemText primary={t('stocks.menu.edit_config')} primaryTypographyProps={{ fontSize: '0.85rem' }} />
        </MenuItem>
        <MenuItem onClick={() => { handleCloseMenu(); if (menuStock) handleDelete(menuStock.code); }} sx={{ py: 1 }}>
            <ListItemIcon><DeleteIcon fontSize="small" color="error" /></ListItemIcon>
            <ListItemText primary={t('common.delete')} primaryTypographyProps={{ fontSize: '0.85rem', color: 'error.main', fontWeight: 700 }} />
        </MenuItem>
      </Menu>

      {/* Add/Edit Stock Dialog */}
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth PaperProps={{ sx: { borderRadius: 3 } }}>
        <DialogTitle sx={{ fontWeight: 800, borderBottom: '1px solid', borderColor: 'divider' }}>
            {editingStock ? t('stocks.dialog.edit_title') : t('stocks.dialog.add_title')}
        </DialogTitle>
        <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3, pt: 3 }}>
                
                {/* 1. Market Search */}
                {!editingStock && (
                    <Box>
                        <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 800, mb: 1, display: 'block' }}>{t('stocks.dialog.market_search')}</Typography>
                        <Autocomplete
                            fullWidth
                            inputValue={inputValue}
                            onInputChange={(_, newInputValue) => setInputValue(newInputValue)}
                            onChange={handleMarketStockSelect}
                            options={searchResults}
                            getOptionLabel={(option) => `[${option.code}] ${option.name}`}
                            loading={searching}
                            renderInput={(params) => (
                            <TextField
                                {...params}
                                label={t('stocks.dialog.search_placeholder')}
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
                    <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 800, mb: 1, display: 'block' }}>{t('stocks.dialog.stock_info')}</Typography>
                    <Grid container spacing={2}>
                        <Grid size={4}>
                            <TextField
                                label={t('common.code')}
                                fullWidth
                                size="small"
                                value={formCode}
                                onChange={(e) => setFormCode(e.target.value)}
                                disabled={!!editingStock}
                                placeholder="000000"
                            />
                        </Grid>
                        <Grid size={8}>
                            <TextField
                                label={t('common.name')}
                                fullWidth
                                size="small"
                                value={formName}
                                onChange={(e) => setFormName(e.target.value)}
                                placeholder={t('stocks.dialog.name_placeholder')}
                            />
                        </Grid>
                    </Grid>
                </Box>

                {/* 3. Config */}
                <Box>
                    <Typography variant="overline" sx={{ color: 'text.secondary', fontWeight: 800, mb: 1, display: 'block' }}>{t('stocks.dialog.config')}</Typography>
                    <Grid container spacing={2}>
                        <Grid size={6}>
                            <Box sx={{ p: 1.5, bgcolor: 'action.hover', borderRadius: '8px', border: '1px dashed', borderColor: 'divider' }}>
                                <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', mb: 0.5, fontWeight: 700 }}>{t('stocks.dialog.sector')}</Typography>
                                <Typography variant="body2" sx={{ color: 'text.primary', fontWeight: 500 }}>
                                    {editingStock?.sector || (formCode ? "Auto-detected upon save" : "---")}
                                </Typography>
                            </Box>
                        </Grid>
                        <Grid size={6}>
                            <TextField
                                label={t('stocks.dialog.market')}
                                fullWidth
                                size="small"
                                value={formMarket}
                                onChange={(e) => setFormMarket(e.target.value)}
                                placeholder={t('stocks.dialog.market_placeholder')}
                            />
                        </Grid>
                    </Grid>
                </Box>
            </Box>
        </DialogContent>
        <DialogActions sx={{ p: 3, borderTop: '1px solid', borderColor: 'divider' }}>
          <Button onClick={() => setOpenDialog(false)} sx={{ color: 'text.secondary', fontWeight: 700 }}>{t('common.cancel')}</Button>
          <Button 
            onClick={handleSave} 
            variant="contained" 
            sx={{ bgcolor: '#0f172a', fontWeight: 800, borderRadius: '8px', px: 4, '&:hover': { bgcolor: '#1e293b' } }}
          >
            {t('common.save')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Stock Details Dialog */}
      <Dialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        maxWidth="md"
        fullWidth
        scroll="paper"
        PaperProps={{
          sx: {
            borderRadius: '20px',
            bgcolor: 'background.paper',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
            maxHeight: '90vh'
          }
        }}
      >
        <DialogTitle sx={{ p: 0 }}>
          <Box sx={{
            bgcolor: 'background.default',
            p: 3,
            borderBottom: '1px solid',
            borderColor: 'divider',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start'
          }}>
             <Box>
                <Typography variant="h5" sx={{ fontWeight: 900, color: 'text.primary', letterSpacing: '-0.02em', mb: 1 }}>
                    {selectedStock?.name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
                    <Box sx={{ px: 1, py: 0.25, bgcolor: '#0f172a', borderRadius: '4px' }}>
                        <Typography sx={{ color: '#fff', fontWeight: 800, fontFamily: 'JetBrains Mono', fontSize: '0.75rem' }}>
                            {selectedStock?.code}
                        </Typography>
                    </Box>
                    <Button
                      size="small"
                      variant={showAIDiagnosis ? "contained" : "outlined"}
                      startIcon={<AutoAwesomeIcon />}
                      onClick={() => setShowAIDiagnosis(!showAIDiagnosis)}
                      sx={{
                        textTransform: 'none',
                        fontWeight: 700,
                        fontSize: '0.75rem',
                        borderRadius: '6px',
                        bgcolor: showAIDiagnosis ? '#8b5cf6' : 'transparent',
                        borderColor: '#8b5cf6',
                        color: showAIDiagnosis ? '#fff' : '#8b5cf6',
                        '&:hover': {
                          bgcolor: showAIDiagnosis ? '#7c3aed' : alpha('#8b5cf6', 0.1),
                          borderColor: '#7c3aed'
                        }
                      }}
                    >
                      {t('stocks.ai.diagnosis_btn')}
                    </Button>
                </Box>
             </Box>
             <Box sx={{ textAlign: 'right' }}>
                 <Typography variant="h4" sx={{
                     fontWeight: 900, fontFamily: 'JetBrains Mono',
                     color: (stockDetails?.quote?.涨跌幅 > 0) ? '#ef4444' : (stockDetails?.quote?.涨跌幅 < 0) ? '#22c55e' : 'text.primary'
                 }}>
                    {stockDetails?.quote?.最新价 || '---'}
                 </Typography>
                 <Typography sx={{
                     fontWeight: 800, fontFamily: 'JetBrains Mono', fontSize: '0.9rem',
                     color: (stockDetails?.quote?.涨跌幅 > 0) ? '#ef4444' : (stockDetails?.quote?.涨跌幅 < 0) ? '#22c55e' : 'text.secondary'
                 }}>
                     {stockDetails?.quote?.涨跌幅 ? `${stockDetails.quote.涨跌幅}%` : '---'}
                 </Typography>
             </Box>
          </Box>

          {/* Tab Navigation */}
          <Tabs
            value={detailTab}
            onChange={(_, val) => setDetailTab(val)}
            variant="scrollable"
            scrollButtons="auto"
            sx={{
              borderBottom: '1px solid',
              borderColor: 'divider',
              px: 2,
              bgcolor: 'background.default',
              '& .MuiTabs-indicator': { bgcolor: 'primary.main' },
              '& .MuiTab-root': { textTransform: 'none', fontWeight: 700, minHeight: 48, fontSize: '0.85rem' }
            }}
          >
            <Tab icon={<ShowChartIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.overview')} />
            <Tab icon={<TimelineIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.live')} />
            <Tab icon={<AccountBalanceIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.financial')} />
            <Tab icon={<GroupsIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.shareholder')} />
            <Tab icon={<CandlestickChartIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.margin')} />
            <Tab icon={<EventIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.events')} />
            <Tab icon={<SpeedIcon sx={{ fontSize: 18 }} />} iconPosition="start" label={t('stocks.tabs.quant')} />
          </Tabs>
        </DialogTitle>

        <DialogContent sx={{ p: 0, bgcolor: 'background.paper' }}>
          {/* AI Diagnosis Card - Overlay */}
          {showAIDiagnosis && selectedStock && (
            <Box sx={{ p: 3, bgcolor: 'action.hover', borderBottom: '1px solid', borderColor: 'divider' }}>
              <AIDiagnosisCard
                code={selectedStock.code}
                stockName={selectedStock.name}
                onClose={() => setShowAIDiagnosis(false)}
              />
            </Box>
          )}

          {/* Tab 0: Overview */}
          {detailTab === 0 && (
            loadingDetails ? (
              <Box sx={{ py: 12, textAlign: 'center' }}>
                <CircularProgress size={32} thickness={5} sx={{ color: 'primary.main', mb: 2 }} />
              </Box>
            ) : stockDetails ? (
              <Box sx={{ p: 3, display: 'flex', flexDirection: 'column', gap: 3 }}>
                  {/* Chart Section */}
                  <Box>
                      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                          <Typography variant="overline" sx={{ color: 'text.primary', fontWeight: 900, fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: 1 }}>
                              <TrendingUpIcon sx={{ fontSize: 18, color: 'primary.main' }} /> {t('funds.details.performance_analytics')}
                          </Typography>
                          <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 700 }}>{t('funds.details.last_100_days')}</Typography>
                      </Box>
                      {renderMiniChart(history)}
                  </Box>

                  {/* Market Data */}
                  <Box>
                      <Typography variant="overline" sx={{ color: 'text.primary', fontWeight: 900, fontSize: '0.75rem', mb: 2, display: 'block' }}>
                          {t('stocks.details.market_data')}
                      </Typography>
                      <Grid container spacing={2}>
                          <Grid size={4}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.open')}</Typography>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{stockDetails.quote?.今开 || '---'}</Typography>
                          </Grid>
                          <Grid size={4}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.high')}</Typography>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{stockDetails.quote?.最高 || '---'}</Typography>
                          </Grid>
                          <Grid size={4}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.low')}</Typography>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{stockDetails.quote?.最低 || '---'}</Typography>
                          </Grid>
                           <Grid size={4}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.volume')}</Typography>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{stockDetails.quote?.成交量 || '---'}</Typography>
                          </Grid>
                          <Grid size={4}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.amount')}</Typography>
                              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>{stockDetails.quote?.成交额 || '---'}</Typography>
                          </Grid>
                      </Grid>
                  </Box>

                  {/* Company Info */}
                  <Box>
                      <Typography variant="overline" sx={{ color: 'text.primary', fontWeight: 900, fontSize: '0.75rem', mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                          <BusinessIcon sx={{ fontSize: 18, color: 'primary.main' }} /> {t('stocks.details.company_profile')}
                      </Typography>
                      <Grid container spacing={2}>
                          <Grid size={6}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.industry')}</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 700 }}>{stockDetails.info?.industry || '---'}</Typography>
                          </Grid>
                          <Grid size={6}>
                              <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.market_cap')}</Typography>
                              <Typography variant="body2" sx={{ fontWeight: 700 }}>{stockDetails.info?.market_cap || '---'}</Typography>
                          </Grid>
                          <Grid size={3}>
                               <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.pe')}</Typography>
                               <Typography variant="body2" sx={{ fontWeight: 700 }}>{stockDetails.info?.pe || '---'}</Typography>
                          </Grid>
                          <Grid size={3}>
                               <Typography variant="caption" sx={{ color: 'text.secondary', fontWeight: 800 }}>{t('stocks.details.pb')}</Typography>
                               <Typography variant="body2" sx={{ fontWeight: 700 }}>{stockDetails.info?.pb || '---'}</Typography>
                          </Grid>
                      </Grid>
                  </Box>
              </Box>
            ) : (
               <Box sx={{ py: 10, textAlign: 'center' }}>
                   <Typography sx={{ color: 'text.secondary' }}>{t('stocks.details.no_details')}</Typography>
               </Box>
            )
          )}

          {/* Tab 1: Live Monitor */}
          {detailTab === 1 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <LiveMonitorTab code={selectedStock.code} market={selectedStock.market} />
            </Box>
          )}

          {/* Tab 2: Financial Analysis */}
          {detailTab === 2 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <FinancialTab code={selectedStock.code} />
            </Box>
          )}

          {/* Tab 3: Shareholder Analysis */}
          {detailTab === 3 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <ShareholderTab code={selectedStock.code} />
            </Box>
          )}

          {/* Tab 4: Margin/Leverage */}
          {detailTab === 4 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <MarginTab code={selectedStock.code} />
            </Box>
          )}

          {/* Tab 5: Events Calendar */}
          {detailTab === 5 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <EventsTab code={selectedStock.code} />
            </Box>
          )}

          {/* Tab 6: Quantitative Signals */}
          {detailTab === 6 && selectedStock && (
            <Box sx={{ p: 3 }}>
              <QuantTab code={selectedStock.code} />
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2, bgcolor: 'background.default', borderTop: '1px solid', borderColor: 'divider' }}>
          <Button
            fullWidth
            onClick={() => setDetailOpen(false)}
            variant="contained"
            sx={{
                bgcolor: '#0f172a',
                color: '#ffffff',
                py: 1.5,
                borderRadius: '12px',
                fontWeight: 800,
                boxShadow: 'none',
                '&:hover': { bgcolor: '#1e293b' }
            }}
          >
            {t('stocks.details.close')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
