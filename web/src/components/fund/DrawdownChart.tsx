import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { fetchFundDrawdownHistory } from '../../api';
import type { FundDrawdownResponse } from '../../api';

interface DrawdownChartProps {
  code: string;
  fundName: string;
}

export default function DrawdownChart({ code, fundName }: DrawdownChartProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<FundDrawdownResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDrawdown = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFundDrawdownHistory(code);
      setData(result);
    } catch (err) {
      setError(t('funds.drawdown.error'));
      console.error('Failed to load drawdown history:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDrawdown();
  }, [code]);

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error || !data) {
    return (
      <Paper sx={{ p: 3, height: 400 }}>
        <Typography color="error">{error || t('funds.drawdown.no_data')}</Typography>
      </Paper>
    );
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <Paper sx={{ p: 1.5, boxShadow: 2 }}>
          <Typography variant="caption" color="text.secondary">
            {label}
          </Typography>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 600,
              fontFamily: 'JetBrains Mono',
              color: payload[0].value < 0 ? '#ef4444' : '#22c55e',
            }}
          >
            {payload[0].value.toFixed(2)}%
          </Typography>
        </Paper>
      );
    }
    return null;
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {t('funds.drawdown.title')}
          </Typography>
          {data.is_in_drawdown ? (
            <Chip
              icon={<WarningAmberIcon />}
              label={`${t('funds.drawdown.in_drawdown')}: -${data.current_drawdown}%`}
              color="warning"
              size="small"
            />
          ) : (
            <Chip
              icon={<CheckCircleIcon />}
              label={t('funds.drawdown.at_high')}
              color="success"
              size="small"
            />
          )}
        </Box>
        <Tooltip title={t('common.refresh')}>
          <IconButton onClick={loadDrawdown} size="small">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Drawdown Chart */}
      <Box sx={{ height: 250 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data.drawdown_series}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickFormatter={(value) => value.slice(5)} // Show MM-DD
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickFormatter={(value) => `${value}%`}
              domain={['dataMin', 0]}
            />
            <RechartsTooltip content={<CustomTooltip />} />
            <ReferenceLine y={0} stroke="#64748b" strokeDasharray="3 3" />
            <ReferenceLine y={-5} stroke="#f59e0b" strokeDasharray="3 3" label="-5%" />
            <ReferenceLine y={-10} stroke="#f97316" strokeDasharray="3 3" label="-10%" />
            <ReferenceLine y={-20} stroke="#ef4444" strokeDasharray="3 3" label="-20%" />
            <Area
              type="monotone"
              dataKey="drawdown"
              stroke="#ef4444"
              fill="#fecaca"
              fillOpacity={0.6}
            />
          </AreaChart>
        </ResponsiveContainer>
      </Box>

      {/* Statistics */}
      <Box sx={{ display: 'flex', gap: 3, mt: 2, flexWrap: 'wrap' }}>
        <Box sx={{ p: 1.5, bgcolor: 'error.50', borderRadius: 1, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            {t('funds.drawdown.max_drawdown')}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, color: 'error.main', fontFamily: 'JetBrains Mono' }}>
            -{data.max_drawdown.value}%
          </Typography>
        </Box>
        <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            {t('funds.drawdown.total_periods')}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
            {data.statistics.total_periods}
          </Typography>
        </Box>
        <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            {t('funds.drawdown.avg_drawdown')}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
            -{data.statistics.avg_drawdown}%
          </Typography>
        </Box>
        <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1, minWidth: 120 }}>
          <Typography variant="caption" color="text.secondary">
            {t('funds.drawdown.avg_recovery')}
          </Typography>
          <Typography variant="h6" sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
            {data.statistics.avg_recovery_days || '-'} {t('common.days')}
          </Typography>
        </Box>
      </Box>

      {/* Drawdown Periods Table */}
      {data.periods.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" sx={{ mb: 1, fontWeight: 600 }}>
            {t('funds.drawdown.periods_history')}
          </Typography>
          <TableContainer sx={{ maxHeight: 200 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>{t('funds.drawdown.start_date')}</TableCell>
                  <TableCell>{t('funds.drawdown.trough_date')}</TableCell>
                  <TableCell>{t('funds.drawdown.recovery_date')}</TableCell>
                  <TableCell align="right">{t('funds.drawdown.drawdown')}</TableCell>
                  <TableCell align="right">{t('funds.drawdown.duration')}</TableCell>
                  <TableCell align="right">{t('funds.drawdown.recovery_days')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.periods.slice(0, 10).map((period, idx) => (
                  <TableRow key={idx} hover>
                    <TableCell sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
                      {period.start_date}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
                      {period.trough_date}
                    </TableCell>
                    <TableCell sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
                      {period.recovery_date || (
                        <Chip label={t('funds.drawdown.ongoing')} size="small" color="warning" />
                      )}
                    </TableCell>
                    <TableCell
                      align="right"
                      sx={{
                        fontFamily: 'JetBrains Mono',
                        fontSize: '0.8rem',
                        color: 'error.main',
                        fontWeight: 600,
                      }}
                    >
                      -{period.drawdown}%
                    </TableCell>
                    <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
                      {period.duration} {t('common.days')}
                    </TableCell>
                    <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontSize: '0.8rem' }}>
                      {period.recovery_days ? `${period.recovery_days} ${t('common.days')}` : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}
    </Paper>
  );
}
