import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Paper,
  Typography,
  Skeleton,
  Tooltip,
  IconButton,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  alpha,
  useTheme,
} from '@mui/material';
import WhatshotIcon from '@mui/icons-material/Whatshot';
import RefreshIcon from '@mui/icons-material/Refresh';
import { fetchHotStocks } from '../../api';
import type { HotStock } from '../../api';

interface HotStocksListProps {
  onStockClick?: (code: string, name: string) => void;
  limit?: number;
}

export default function HotStocksList({ onStockClick, limit = 15 }: HotStocksListProps) {
  const { t } = useTranslation();
  const theme = useTheme();
  const [data, setData] = useState<HotStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updateTime, setUpdateTime] = useState<string>('');

  const loadData = async (silent: boolean = false) => {
    if (!silent) {
      setLoading(true);
    }
    if (!silent) {
      setError(null);
    }
    try {
      const result = await fetchHotStocks(limit);
      setData(result.items);
      setUpdateTime(result.update_time);
    } catch (err) {
      setError(t('stocks.market.load_error'));
      console.error('Failed to load hot stocks:', err);
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  };

  useEffect(() => {
    loadData();

    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        loadData(true);
      }
    }, 15000);

    return () => window.clearInterval(timer);
  }, [limit]);

  const formatChange = (value: number): string => {
    const sign = value > 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  const getRankColor = (rank: number) => {
    if (rank === 1) return '#ef4444'; // Red for #1
    if (rank === 2) return '#f97316'; // Orange for #2
    if (rank === 3) return '#f59e0b'; // Amber for #3
    return '#94a3b8'; // Slate for others
  };

  if (loading) {
    return (
      <Paper sx={{ p: 2, height: '100%', borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Skeleton width={120} height={28} />
          <Skeleton width={24} height={24} variant="circular" />
        </Box>
        {[1, 2, 3, 4, 5].map((i) => (
          <Skeleton key={i} height={32} sx={{ mb: 1 }} />
        ))}
      </Paper>
    );
  }

  if (error) {
    return (
      <Paper sx={{ p: 2, textAlign: 'center', height: '100%', borderRadius: 3 }}>
        <Typography color="error">{error}</Typography>
        <IconButton onClick={() => loadData()} size="small" sx={{ mt: 1 }}>
          <RefreshIcon />
        </IconButton>
      </Paper>
    );
  }

  return (
    <Paper 
      elevation={0}
      sx={{ 
        p: 0, 
        height: '100%', 
        display: 'flex', 
        flexDirection: 'column', 
        borderRadius: 3, 
        border: '1px solid',
        borderColor: 'divider',
        overflow: 'hidden'
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center', bgcolor: alpha(theme.palette.background.paper, 0.5) }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <WhatshotIcon sx={{ color: '#ef4444', fontSize: 20 }} />
          <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
            {t('stocks.market.hot_stocks')}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'Monospace' }}>
            {updateTime}
          </Typography>
          <Tooltip title={t('common.refresh')}>
            <IconButton size="small" onClick={() => loadData()}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      <TableContainer sx={{ flex: 1, overflow: 'auto' }}>
        <Table size="small" stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell width={40} sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem', pl: 3 }}>#</TableCell>
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.table.name')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.table.price')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem', pr: 3 }}>{t('stocks.table.change')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.map((stock) => {
              const rankColor = getRankColor(stock.rank);
              const isPositive = stock.change_pct > 0;
              const isNegative = stock.change_pct < 0;
              const color = isPositive ? '#ef4444' : isNegative ? '#22c55e' : 'text.primary';
              
              return (
                <TableRow
                  key={stock.code}
                  hover
                  sx={{ 
                    cursor: onStockClick ? 'pointer' : 'default',
                    '&:hover': { bgcolor: 'action.hover' },
                    transition: 'background-color 0.2s'
                  }}
                  onClick={() => onStockClick?.(stock.code, stock.name)}
                >
                  <TableCell sx={{ pl: 3 }}>
                    <Typography 
                      variant="caption" 
                      sx={{ 
                        fontWeight: 800, 
                        color: rankColor, 
                        fontFamily: 'Monospace',
                        fontSize: '0.85rem'
                      }}
                    >
                      {stock.rank}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Box>
                      <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                        {stock.name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'Monospace', fontSize: '0.7rem' }}>
                        {stock.code}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 600, fontSize: '0.85rem' }}>
                      {stock.price.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right" sx={{ pr: 3 }}>
                    <Typography 
                      variant="body2" 
                      sx={{ 
                        color: color,
                        fontWeight: 700,
                        fontFamily: 'JetBrains Mono',
                        fontSize: '0.85rem'
                      }}
                    >
                      {formatChange(stock.change_pct)}
                    </Typography>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Paper>
  );
}
