import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Button,
  Chip,
  CircularProgress,
  Alert,
  Grid,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  Autocomplete,
} from '@mui/material';
import AccountBalanceWalletIcon from '@mui/icons-material/AccountBalanceWallet';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import SearchIcon from '@mui/icons-material/Search';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip as RechartsTooltip } from 'recharts';
import {
  fetchPortfolioPositions,
  fetchPortfolioSummary,
  fetchPortfolioOverlap,
  createPosition,
  updatePosition,
  deletePosition,
  searchMarketFunds,
} from '../api';
import type { PortfolioPosition, PortfolioSummaryResponse, PortfolioOverlapResponse, MarketFund } from '../api';
import PositionForm from '../components/fund/PositionForm';
import type { PositionFormData } from '../components/fund/PositionForm';

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export default function Portfolio() {
  const { t } = useTranslation();
  const [positions, setPositions] = useState<PortfolioPosition[]>([]);
  const [summary, setSummary] = useState<PortfolioSummaryResponse | null>(null);
  const [overlap, setOverlap] = useState<PortfolioOverlapResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Position form state
  const [formOpen, setFormOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<PortfolioPosition | null>(null);
  const [selectedFund, setSelectedFund] = useState<{ code: string; name: string } | null>(null);

  // Fund search dialog state
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const [searchResults, setSearchResults] = useState<MarketFund[]>([]);
  const [searching, setSearching] = useState(false);
  const [searchInput, setSearchInput] = useState('');

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [positionsRes, summaryRes] = await Promise.all([
        fetchPortfolioPositions(),
        fetchPortfolioSummary(),
      ]);
      setPositions(positionsRes.positions || []);
      setSummary(summaryRes);

      // Load overlap analysis if we have positions
      if (positionsRes.positions?.length >= 2) {
        try {
          const overlapRes = await fetchPortfolioOverlap();
          setOverlap(overlapRes);
        } catch (err) {
          console.log('Overlap analysis not available');
        }
      }
    } catch (err: any) {
      setError(err.message || t('portfolio.error_load'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleAddPosition = (fund: { code: string; name: string }) => {
    setSelectedFund(fund);
    setEditingPosition(null);
    setSearchDialogOpen(false);
    setFormOpen(true);
  };

  // Search for funds
  const handleSearch = async (query: string) => {
    if (query.length < 2) return;
    setSearching(true);
    try {
      const results = await searchMarketFunds(query);
      setSearchResults(results);
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setSearching(false);
    }
  };

  // Open search dialog
  const handleOpenSearchDialog = () => {
    setSearchResults([]);
    setSearchInput('');
    setSearchDialogOpen(true);
  };

  const handleEditPosition = (position: PortfolioPosition) => {
    setSelectedFund({ code: position.fund_code, name: position.fund_name || '' });
    setEditingPosition(position);
    setFormOpen(true);
  };

  const handleDeletePosition = async (positionId: number) => {
    if (!window.confirm(t('portfolio.confirm_delete'))) return;
    try {
      await deletePosition(positionId);
      loadData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleFormSubmit = async (data: PositionFormData) => {
    if (editingPosition) {
      await updatePosition(editingPosition.id, data);
    } else {
      await createPosition(data);
    }
    loadData();
  };

  // Prepare allocation pie data
  const allocationData = summary?.allocation?.map((item, idx) => ({
    name: item.fund_name || item.fund_code,
    value: item.weight,
    color: COLORS[idx % COLORS.length],
  })) || [];

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" sx={{ fontWeight: 700 }}>
          <AccountBalanceWalletIcon sx={{ mr: 1, verticalAlign: 'middle' }} />
          {t('portfolio.title')}
        </Typography>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleOpenSearchDialog}
            sx={{
              bgcolor: '#6366f1',
              borderRadius: '10px',
              textTransform: 'none',
              fontWeight: 600,
              '&:hover': { bgcolor: '#4f46e5' },
            }}
          >
            {t('portfolio.add_position')}
          </Button>
          <Tooltip title={t('common.refresh')}>
            <IconButton onClick={loadData}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      {/* Summary Cards */}
      {summary && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {t('portfolio.total_value')}
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
                ¥{summary.total_value.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {t('portfolio.total_cost')}
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
                ¥{summary.total_cost.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
              </Typography>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {t('portfolio.total_pnl')}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                {summary.total_pnl >= 0 ? (
                  <TrendingUpIcon color="success" />
                ) : (
                  <TrendingDownIcon color="error" />
                )}
                <Typography
                  variant="h5"
                  sx={{
                    fontWeight: 700,
                    fontFamily: 'JetBrains Mono',
                    color: summary.total_pnl >= 0 ? 'success.main' : 'error.main',
                  }}
                >
                  {summary.total_pnl >= 0 ? '+' : ''}
                  ¥{summary.total_pnl.toLocaleString('zh-CN', { minimumFractionDigits: 2 })}
                </Typography>
              </Box>
            </Paper>
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="caption" color="text.secondary">
                {t('portfolio.pnl_pct')}
              </Typography>
              <Typography
                variant="h5"
                sx={{
                  fontWeight: 700,
                  fontFamily: 'JetBrains Mono',
                  color: summary.total_pnl_pct >= 0 ? 'success.main' : 'error.main',
                }}
              >
                {summary.total_pnl_pct >= 0 ? '+' : ''}
                {summary.total_pnl_pct.toFixed(2)}%
              </Typography>
            </Paper>
          </Grid>
        </Grid>
      )}

      <Grid container spacing={3}>
        {/* Positions Table */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Paper sx={{ p: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600 }}>
                {t('portfolio.positions')} ({positions.length})
              </Typography>
            </Box>

            {positions.length === 0 ? (
              <Box sx={{ textAlign: 'center', py: 4 }}>
                <Typography color="text.secondary" sx={{ mb: 2 }}>
                  {t('portfolio.no_positions')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {t('portfolio.add_from_funds')}
                </Typography>
              </Box>
            ) : (
              <TableContainer sx={{ maxHeight: 500 }}>
                <Table size="small" stickyHeader>
                  <TableHead>
                    <TableRow>
                      <TableCell>{t('portfolio.fund')}</TableCell>
                      <TableCell align="right">{t('portfolio.shares')}</TableCell>
                      <TableCell align="right">{t('portfolio.cost')}</TableCell>
                      <TableCell align="right">{t('portfolio.current_nav')}</TableCell>
                      <TableCell align="right">{t('portfolio.value')}</TableCell>
                      <TableCell align="right">{t('portfolio.pnl')}</TableCell>
                      <TableCell align="center">{t('common.actions')}</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {positions.map((pos) => (
                      <TableRow key={pos.id} hover>
                        <TableCell>
                          <Box>
                            <Typography variant="body2" sx={{ fontWeight: 600 }}>
                              {pos.fund_name || pos.fund_code}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {pos.fund_code}
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono' }}>
                          {pos.shares.toFixed(2)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono' }}>
                          ¥{pos.cost_basis.toFixed(4)}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono' }}>
                          {pos.current_nav ? `¥${pos.current_nav.toFixed(4)}` : '-'}
                        </TableCell>
                        <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono' }}>
                          ¥{pos.position_value.toFixed(2)}
                        </TableCell>
                        <TableCell
                          align="right"
                          sx={{
                            fontFamily: 'JetBrains Mono',
                            color: pos.pnl >= 0 ? 'success.main' : 'error.main',
                          }}
                        >
                          {pos.pnl >= 0 ? '+' : ''}
                          ¥{pos.pnl.toFixed(2)}
                          <Typography variant="caption" sx={{ display: 'block' }}>
                            ({pos.pnl_pct >= 0 ? '+' : ''}
                            {pos.pnl_pct.toFixed(2)}%)
                          </Typography>
                        </TableCell>
                        <TableCell align="center">
                          <IconButton size="small" onClick={() => handleEditPosition(pos)}>
                            <EditIcon fontSize="small" />
                          </IconButton>
                          <IconButton size="small" color="error" onClick={() => handleDeletePosition(pos.id)}>
                            <DeleteIcon fontSize="small" />
                          </IconButton>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </Paper>
        </Grid>

        {/* Allocation Pie Chart */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Paper sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
              {t('portfolio.allocation')}
            </Typography>
            {allocationData.length > 0 ? (
              <Box sx={{ height: 300 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={allocationData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={80}
                      label={({ name, value }) => `${(name || '').slice(0, 6)}... ${value.toFixed(1)}%`}
                      labelLine={{ stroke: '#64748b' }}
                    >
                      {allocationData.map((entry, idx) => (
                        <Cell key={idx} fill={entry.color} />
                      ))}
                    </Pie>
                    <RechartsTooltip formatter={(value: any) => `${value.toFixed(2)}%`} />
                  </PieChart>
                </ResponsiveContainer>
              </Box>
            ) : (
              <Typography color="text.secondary" sx={{ textAlign: 'center', py: 4 }}>
                {t('portfolio.no_allocation')}
              </Typography>
            )}
          </Paper>
        </Grid>

        {/* Holdings Overlap */}
        {overlap && overlap.concentration_warnings?.length > 0 && (
          <Grid size={{ xs: 12 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2, display: 'flex', alignItems: 'center', gap: 1 }}>
                <WarningAmberIcon color="warning" />
                {t('portfolio.concentration_warnings')}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {overlap.concentration_warnings.map((warning: any) => (
                  <Chip
                    key={warning.stock_code}
                    label={warning.message}
                    color="warning"
                    variant="outlined"
                  />
                ))}
              </Box>
            </Paper>
          </Grid>
        )}

        {/* Top Holdings */}
        {overlap && overlap.aggregated_holdings?.length > 0 && (
          <Grid size={{ xs: 12 }}>
            <Paper sx={{ p: 2 }}>
              <Typography variant="h6" sx={{ fontWeight: 600, mb: 2 }}>
                {t('portfolio.top_holdings')}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {overlap.aggregated_holdings.slice(0, 20).map((holding: any) => (
                  <Chip
                    key={holding.stock_code}
                    label={`${holding.stock_name} (${holding.total_weight.toFixed(1)}%)`}
                    variant="outlined"
                    size="small"
                  />
                ))}
              </Box>
            </Paper>
          </Grid>
        )}
      </Grid>

      {/* Position Form Dialog */}
      {selectedFund && (
        <PositionForm
          open={formOpen}
          onClose={() => {
            setFormOpen(false);
            setSelectedFund(null);
            setEditingPosition(null);
          }}
          onSubmit={handleFormSubmit}
          fundCode={selectedFund.code}
          fundName={selectedFund.name}
          initialData={
            editingPosition
              ? {
                  fund_code: editingPosition.fund_code,
                  fund_name: editingPosition.fund_name || '',
                  shares: editingPosition.shares,
                  cost_basis: editingPosition.cost_basis,
                  purchase_date: editingPosition.purchase_date,
                  notes: editingPosition.notes,
                }
              : undefined
          }
          mode={editingPosition ? 'edit' : 'create'}
        />
      )}

      {/* Fund Search Dialog */}
      <Dialog
        open={searchDialogOpen}
        onClose={() => setSearchDialogOpen(false)}
        maxWidth="sm"
        fullWidth
        PaperProps={{ sx: { borderRadius: '16px' } }}
      >
        <DialogTitle sx={{ fontWeight: 700, borderBottom: '1px solid #f1f5f9' }}>
          {t('portfolio.search_fund')}
        </DialogTitle>
        <DialogContent sx={{ pt: 3 }}>
          <Autocomplete
            fullWidth
            options={searchResults}
            getOptionLabel={(option) => `${option.code} - ${option.name}`}
            loading={searching}
            inputValue={searchInput}
            onInputChange={(_, value) => {
              setSearchInput(value);
              if (value.length >= 2) {
                handleSearch(value);
              }
            }}
            onChange={(_, value) => {
              if (value) {
                handleAddPosition({ code: value.code, name: value.name });
              }
            }}
            renderInput={(params) => (
              <TextField
                {...params}
                label={t('portfolio.search_placeholder')}
                placeholder={t('portfolio.search_hint')}
                slotProps={{
                  input: {
                    ...params.InputProps,
                    startAdornment: (
                      <>
                        <SearchIcon sx={{ color: '#94a3b8', mr: 1 }} />
                        {params.InputProps.startAdornment}
                      </>
                    ),
                    endAdornment: (
                      <>
                        {searching && <CircularProgress size={20} />}
                        {params.InputProps.endAdornment}
                      </>
                    ),
                  },
                }}
              />
            )}
            renderOption={(props, option) => (
              <li {...props} key={option.code}>
                <Box sx={{ py: 0.5 }}>
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {option.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'JetBrains Mono' }}>
                    {option.code} {option.type && `· ${option.type}`}
                  </Typography>
                </Box>
              </li>
            )}
            noOptionsText={searchInput.length < 2 ? t('portfolio.search_hint') : t('portfolio.no_results')}
          />
          <Typography variant="body2" color="text.secondary" sx={{ mt: 2, textAlign: 'center' }}>
            {t('portfolio.search_tip')}
          </Typography>
        </DialogContent>
      </Dialog>
    </Box>
  );
}
