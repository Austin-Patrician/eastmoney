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
  Chip,
  Tabs,
  Tab,
  alpha,
  useTheme,
} from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import RefreshIcon from '@mui/icons-material/Refresh';
import { fetchLimitUpStocks, fetchLimitDownStocks } from '../../api';
import type { LimitStock } from '../../api';

interface LimitPoolTabsProps {
  onStockClick?: (code: string, name: string) => void;
  limit?: number;
}

export default function LimitPoolTabs({ onStockClick, limit = 20 }: LimitPoolTabsProps) {
  const { t, i18n } = useTranslation();
  const theme = useTheme();
  const [activeTab, setActiveTab] = useState<'up' | 'down'>('up');
  const [upData, setUpData] = useState<LimitStock[]>([]);
  const [downData, setDownData] = useState<LimitStock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updateTime, setUpdateTime] = useState<string>('');

  const loadData = async (silent: boolean = false) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const [upResult, downResult] = await Promise.all([
        fetchLimitUpStocks(limit),
        fetchLimitDownStocks(limit),
      ]);
      setUpData(upResult.items);
      setDownData(downResult.items);
      setUpdateTime(upResult.update_time);
    } catch (err) {
      setError(t('stocks.market.load_error'));
      console.error('Failed to load limit pool:', err);
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

  const formatTime = (time: string): string => {
    if (!time || time.length !== 6) return time;
    return `${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`;
  };

  const currentData = activeTab === 'up' ? upData : downData;
  const isUp = activeTab === 'up';

  // Chinese Market Colors: Red = Up, Green = Down
  const upColor = '#ef4444';
  const downColor = '#22c55e';
  const activeColor = isUp ? upColor : downColor;

  if (loading) {
    return (
      <Paper sx={{ p: 2, height: '100%', borderRadius: 3, boxShadow: '0 4px 20px rgba(0,0,0,0.05)' }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
          <Skeleton width={200} height={40} />
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
      <Box sx={{ 
        p: 1, 
        borderBottom: '1px solid', 
        borderColor: 'divider', 
        display: 'flex', 
        justifyContent: 'space-between', 
        alignItems: 'center',
        bgcolor: alpha(theme.palette.background.paper, 0.5)
      }}>
        <Tabs
          value={activeTab}
          onChange={(_, v) => setActiveTab(v)}
          sx={{
            minHeight: 36,
            '& .MuiTabs-indicator': {
              bgcolor: activeColor,
              height: 3,
              borderRadius: '3px 3px 0 0',
            },
            '& .MuiTab-root': {
              minHeight: 36,
              py: 0.5,
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.9rem',
              color: 'text.secondary',
              '&.Mui-selected': {
                color: activeColor,
              }
            }
          }}
        >
          <Tab
            value="up"
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TrendingUpIcon sx={{ fontSize: 18 }} />
                <span>{t('stocks.market.limit_up_pool')}</span>
                <Chip 
                  label={upData.length} 
                  size="small" 
                  sx={{ 
                    ml: 0.5, 
                    height: 18, 
                    fontSize: '0.7rem',
                    bgcolor: alpha(upColor, 0.1),
                    color: upColor,
                    fontWeight: 700,
                  }} 
                />
              </Box>
            }
          />
          <Tab
            value="down"
            label={
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TrendingDownIcon sx={{ fontSize: 18 }} />
                <span>{t('stocks.market.limit_down_pool')}</span>
                <Chip 
                  label={downData.length} 
                  size="small" 
                  sx={{ 
                    ml: 0.5, 
                    height: 18, 
                    fontSize: '0.7rem',
                    bgcolor: alpha(downColor, 0.1),
                    color: downColor,
                    fontWeight: 700,
                  }} 
                />
              </Box>
            }
          />
        </Tabs>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, pr: 1 }}>
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
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.table.code')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.table.price')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.market.consecutive')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.market.turnover')}</TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem' }}>{t('stocks.market.seal_time')}</TableCell>
              <TableCell sx={{ fontWeight: 600, color: 'text.secondary', fontSize: '0.75rem', pr: 3 }}>{t('stocks.market.industry')}</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {currentData.map((stock) => {
              const priceColor = isUp ? upColor : downColor;
              const isHighConsecutive = stock.consecutive > 1;
              
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
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'Monospace' }}>
                      {stock.rank}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" sx={{ fontWeight: 600, fontSize: '0.85rem' }}>
                      {stock.name}
                    </Typography>
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary" sx={{ fontFamily: 'Monospace' }}>
                      {stock.code}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" sx={{ fontWeight: 700, color: priceColor, fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                      {stock.price.toFixed(2)}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    {isHighConsecutive ? (
                      <Chip
                        label={`${stock.consecutive}${i18n.language === 'zh' ? '板' : 'x'}`}
                        size="small"
                        sx={{
                          height: 20,
                          bgcolor: alpha(priceColor, 0.1),
                          color: priceColor,
                          fontWeight: 800,
                          fontSize: '0.7rem',
                          borderRadius: '4px',
                        }}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary" sx={{ fontSize: '0.85rem' }}>
                        {stock.consecutive}
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                      {stock.turnover.toFixed(1)}%
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2" color="text.secondary" sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.85rem' }}>
                      {formatTime(stock.last_seal_time)}
                    </Typography>
                  </TableCell>
                  <TableCell sx={{ pr: 3 }}>
                    <Tooltip title={stock.industry}>
                      <Typography 
                        variant="caption" 
                        sx={{ 
                          maxWidth: 100, 
                          display: 'block',
                          overflow: 'hidden', 
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          bgcolor: alpha(theme.palette.action.active, 0.05),
                          px: 1, py: 0.2, borderRadius: 1,
                          color: 'text.secondary',
                          textAlign: 'center'
                        }}
                      >
                        {stock.industry}
                      </Typography>
                    </Tooltip>
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
