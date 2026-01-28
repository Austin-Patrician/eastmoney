import React, { useState, useMemo } from 'react';
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Typography,
  Chip,
  IconButton,
  Tooltip,
  Button,
  useTheme,
  alpha,
} from '@mui/material';
import {
  Delete,
  Refresh,
  Edit,
  TrendingUp,
  TrendingDown,
  AutoAwesome,
} from '@mui/icons-material';
import { useTranslation } from 'react-i18next';
import AISignalCell from './AISignalCell';
import AISignalDrawer from './AISignalDrawer';
import EditPositionDialog from './EditPositionDialog';
import type { PortfolioDiagnosis } from '../../api';

interface Position {
  id: number;
  asset_code: string;
  asset_name?: string;
  asset_type: 'stock' | 'fund';
  total_shares: number;
  average_cost: number;
  total_cost?: number;
  current_price?: number | null;
  current_value?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
  sector?: string;
}

interface Signal {
  code: string;
  name: string;
  signal_type: 'opportunity' | 'risk' | 'neutral';
  strength: number;
  summary: string;
  reasons: string[];
}

interface SignalDetail {
  code: string;
  name: string;
  signal_type: 'opportunity' | 'risk' | 'neutral';
  strength: number;
  reasons: string[];
  summary: string;
  explanation: string;
  action_suggestion: string;
  confidence: 'high' | 'medium' | 'low';
  factors: Array<{
    name: string;
    signal: string;
    weight: number;
    details: string;
  }>;
  generated_at: string;
}

interface SmartPositionTableProps {
  positions: Position[];
  signals: Signal[];
  diagnosis?: PortfolioDiagnosis | null;
  loadingDiagnosis?: boolean;
  onRunDiagnosis?: () => void;
  onDelete?: (positionId: number) => void;
  onRecalculate?: (positionId: number) => void;
  onEdit?: (positionId: number, updates: { total_shares?: number; average_cost?: number; notes?: string }) => Promise<void>;
  onLoadSignalDetail?: (assetCode: string) => Promise<SignalDetail>;
  loading?: boolean;
  showActions?: boolean;
}

type SortField = 'name' | 'value' | 'pnl' | 'pnl_pct' | 'signal';
type SortOrder = 'asc' | 'desc';

// Limit initial render to prevent memory issues with large portfolios
const INITIAL_DISPLAY_LIMIT = 20;

const SmartPositionTable: React.FC<SmartPositionTableProps> = ({
  positions,
  signals,
  diagnosis,
  loadingDiagnosis = false,
  onRunDiagnosis,
  onDelete,
  onRecalculate,
  onEdit,
  onLoadSignalDetail,
  loading = false,
  showActions = true,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const [sortField, setSortField] = useState<SortField>('value');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [showAllPositions, setShowAllPositions] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [editingPosition, setEditingPosition] = useState<Position | null>(null);
  const [selectedSignalDetail, setSelectedSignalDetail] = useState<SignalDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // Memoize signalMap to prevent recreating on every render
  const signalMap = useMemo(() =>
    signals.reduce((acc, signal) => {
      acc[signal.code] = signal;
      return acc;
    }, {} as Record<string, Signal>),
    [signals]
  );

  // Memoize sorted positions to avoid re-sorting on every render
  const sortedPositions = useMemo(() => {
    return [...positions].sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;

      switch (sortField) {
        case 'name':
          aVal = a.asset_name || a.asset_code;
          bVal = b.asset_name || b.asset_code;
          break;
        case 'value':
          aVal = a.current_value || 0;
          bVal = b.current_value || 0;
          break;
        case 'pnl':
          aVal = a.unrealized_pnl || 0;
          bVal = b.unrealized_pnl || 0;
          break;
        case 'pnl_pct':
          aVal = a.unrealized_pnl_pct || 0;
          bVal = b.unrealized_pnl_pct || 0;
          break;
        case 'signal':
          const aSignal = signalMap[a.asset_code];
          const bSignal = signalMap[b.asset_code];
          // Sort by signal type priority: risk > opportunity > neutral
          const getPriority = (s?: Signal) => {
            if (!s) return 0;
            if (s.signal_type === 'risk') return 3;
            if (s.signal_type === 'opportunity') return 2;
            return 1;
          };
          aVal = getPriority(aSignal) * 100 + (aSignal?.strength || 0) * 100;
          bVal = getPriority(bSignal) * 100 + (bSignal?.strength || 0) * 100;
          break;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }

      return sortOrder === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });
  }, [positions, sortField, sortOrder, signalMap]);

  // Limit displayed positions to prevent memory issues
  const displayedPositions = useMemo(() => {
    if (showAllPositions || sortedPositions.length <= INITIAL_DISPLAY_LIMIT) {
      return sortedPositions;
    }
    return sortedPositions.slice(0, INITIAL_DISPLAY_LIMIT);
  }, [sortedPositions, showAllPositions]);

  const hasMorePositions = sortedPositions.length > INITIAL_DISPLAY_LIMIT && !showAllPositions;

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const handleEditClick = (position: Position) => {
    setEditingPosition(position);
    setEditDialogOpen(true);
  };

  const handleEditSave = async (positionId: number, updates: { total_shares?: number; average_cost?: number; notes?: string }) => {
    if (onEdit) {
      await onEdit(positionId, updates);
    }
  };

  const handleSignalClick = async (assetCode: string) => {
    if (!onLoadSignalDetail) return;

    setDrawerOpen(true);
    setLoadingDetail(true);
    setSelectedSignalDetail(null);

    try {
      const detail = await onLoadSignalDetail(assetCode);
      setSelectedSignalDetail(detail);
    } catch (error) {
      console.error('Failed to load signal detail:', error);
    } finally {
      setLoadingDetail(false);
    }
  };

  const formatNumber = (num: number | null | undefined, decimals = 2) => {
    if (num === null || num === undefined) return '--';
    return num.toLocaleString('zh-CN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const formatPercent = (num: number | null | undefined) => {
    if (num === null || num === undefined) return '--';
    const sign = num >= 0 ? '+' : '';
    return `${sign}${num.toFixed(2)}%`;
  };

  return (
    <>
      <Paper
        elevation={0}
        sx={{
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          borderRadius: 2,
          overflow: 'hidden',
        }}
      >
        <TableContainer>
          <Table size="small">
          <TableHead>
            <TableRow sx={{ bgcolor: alpha(theme.palette.background.default, 0.5) }}>
              <TableCell>
                <TableSortLabel
                  active={sortField === 'name'}
                  direction={sortField === 'name' ? sortOrder : 'asc'}
                  onClick={() => handleSort('name')}
                >
                  {t('portfolio.asset', '资产')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">{t('portfolio.shares', '持仓')}</TableCell>
              <TableCell align="right">{t('portfolio.cost', '成本')}</TableCell>
              <TableCell align="right">{t('portfolio.currentPrice', '现价')}</TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'value'}
                  direction={sortField === 'value' ? sortOrder : 'asc'}
                  onClick={() => handleSort('value')}
                >
                  {t('portfolio.value', '市值')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="right">
                <TableSortLabel
                  active={sortField === 'pnl_pct'}
                  direction={sortField === 'pnl_pct' ? sortOrder : 'asc'}
                  onClick={() => handleSort('pnl_pct')}
                >
                  {t('portfolio.pnl', '盈亏')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="center">
                <TableSortLabel
                  active={sortField === 'signal'}
                  direction={sortField === 'signal' ? sortOrder : 'asc'}
                  onClick={() => handleSort('signal')}
                >
                  {t('portfolio.aiSignal', 'AI信号')}
                </TableSortLabel>
              </TableCell>
              {showActions && (
                <TableCell align="center">{t('portfolio.actions', '操作')}</TableCell>
              )}
            </TableRow>
          </TableHead>
          <TableBody>
            {displayedPositions.map((position) => {
              const signal = signalMap[position.asset_code];
              const pnl = position.unrealized_pnl;
              const pnlPct = position.unrealized_pnl_pct;
              const isProfitable = (pnl ?? 0) >= 0;

              return (
                <TableRow
                  key={position.id}
                  hover
                  sx={{
                    '&:last-child td': { border: 0 },
                    ...(signal?.signal_type === 'risk' && {
                      bgcolor: alpha(theme.palette.error.main, 0.02),
                    }),
                    ...(signal?.signal_type === 'opportunity' && {
                      bgcolor: alpha(theme.palette.success.main, 0.02),
                    }),
                  }}
                >
                  {/* Asset Name */}
                  <TableCell>
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        {position.asset_name || position.asset_code}
                      </Typography>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Typography variant="caption" color="text.secondary">
                          {position.asset_code}
                        </Typography>
                        <Chip
                          size="small"
                          label={position.asset_type === 'stock' ? t('portfolio.stock', '股票') : t('portfolio.fund', '基金')}
                          sx={{
                            height: 16,
                            fontSize: '0.65rem',
                            bgcolor: position.asset_type === 'stock'
                              ? alpha(theme.palette.info.main, 0.1)
                              : alpha(theme.palette.success.main, 0.1),
                            color: position.asset_type === 'stock'
                              ? theme.palette.info.main
                              : theme.palette.success.main,
                          }}
                        />
                      </Box>
                    </Box>
                  </TableCell>

                  {/* Shares */}
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
                      {formatNumber(position.total_shares, 0)}
                    </Typography>
                  </TableCell>

                  {/* Cost */}
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: '"Roboto Mono", monospace' }}>
                      {formatNumber(position.average_cost, 4)}
                    </Typography>
                  </TableCell>

                  {/* Current Price */}
                  <TableCell align="right">
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: '"Roboto Mono", monospace',
                        color: position.current_price ? 'inherit' : 'text.secondary',
                      }}
                    >
                      {position.current_price ? formatNumber(position.current_price, 4) : '--'}
                    </Typography>
                  </TableCell>

                  {/* Value */}
                  <TableCell align="right">
                    <Typography variant="body2" fontWeight={500} sx={{ fontFamily: '"Roboto Mono", monospace' }}>
                      ¥{formatNumber(position.current_value)}
                    </Typography>
                  </TableCell>

                  {/* P&L */}
                  <TableCell align="right">
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 0.5 }}>
                      {pnl !== null && pnl !== undefined && (
                        isProfitable ?
                          <TrendingUp sx={{ fontSize: 16, color: 'success.main' }} /> :
                          <TrendingDown sx={{ fontSize: 16, color: 'error.main' }} />
                      )}
                      <Box>
                        <Typography
                          variant="body2"
                          fontWeight={500}
                          sx={{
                            color: isProfitable ? 'success.main' : 'error.main',
                            fontFamily: '"Roboto Mono", monospace',
                          }}
                        >
                          {pnl !== null && pnl !== undefined ? (isProfitable ? '+' : '') + formatNumber(pnl) : '--'}
                        </Typography>
                        <Typography
                          variant="caption"
                          sx={{
                            color: isProfitable ? 'success.main' : 'error.main',
                            display: 'block',
                            textAlign: 'right',
                          }}
                        >
                          {formatPercent(pnlPct)}
                        </Typography>
                      </Box>
                    </Box>
                  </TableCell>

                  {/* AI Signal */}
                  <TableCell align="center">
                    <AISignalCell
                      signalType={signal?.signal_type || 'neutral'}
                      strength={signal?.strength || 0.5}
                      summary={signal?.summary}
                      onClick={() => handleSignalClick(position.asset_code)}
                    />
                  </TableCell>

                  {/* Actions */}
                  {showActions && (
                    <TableCell align="center">
                      <Box sx={{ display: 'flex', justifyContent: 'center', gap: 0.5 }}>
                        {onEdit && (
                          <Tooltip title={t('portfolio.edit', '编辑')}>
                            <IconButton
                              size="small"
                              onClick={() => handleEditClick(position)}
                              sx={{
                                color: 'primary.main',
                                '&:hover': { bgcolor: alpha(theme.palette.primary.main, 0.1) },
                              }}
                            >
                              <Edit fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {onRecalculate && (
                          <Tooltip title={t('portfolio.recalculate', '重新计算')}>
                            <IconButton
                              size="small"
                              onClick={() => onRecalculate(position.id)}
                            >
                              <Refresh fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                        {onDelete && (
                          <Tooltip title={t('portfolio.delete', '删除')}>
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => onDelete(position.id)}
                            >
                              <Delete fontSize="small" />
                            </IconButton>
                          </Tooltip>
                        )}
                      </Box>
                    </TableCell>
                  )}
                </TableRow>
              );
            })}

            {sortedPositions.length === 0 && (
              <TableRow>
                <TableCell colSpan={showActions ? 8 : 7} align="center" sx={{ py: 4 }}>
                  <Typography color="text.secondary">
                    {loading ? t('portfolio.loading', '加载中...') : t('portfolio.noPositions', '暂无持仓')}
                  </Typography>
                </TableCell>
              </TableRow>
            )}

            {/* Show More button */}
            {hasMorePositions && (
              <TableRow>
                <TableCell colSpan={showActions ? 8 : 7} align="center" sx={{ py: 2 }}>
                  <Button
                    size="small"
                    onClick={() => setShowAllPositions(true)}
                    sx={{ textTransform: 'none' }}
                  >
                    {t('portfolio.showMore', '显示全部 {{count}} 个持仓', { count: sortedPositions.length })}
                  </Button>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      </Paper>

      {/* Signal Detail Drawer */}
      <AISignalDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        signalDetail={selectedSignalDetail}
        loading={loadingDetail}
      />

      {/* Edit Position Dialog */}
      <EditPositionDialog
        open={editDialogOpen}
        position={editingPosition}
        onClose={() => {
          setEditDialogOpen(false);
          setEditingPosition(null);
        }}
        onSave={handleEditSave}
      />
    </>
  );
};

export default SmartPositionTable;
