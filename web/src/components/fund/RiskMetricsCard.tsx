import { useState, useEffect } from 'react';
import type { ReactElement } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Box,
  Typography,
  CircularProgress,
  Paper,
  Grid,
  Tooltip,
  IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import SpeedIcon from '@mui/icons-material/Speed';
import EqualizerIcon from '@mui/icons-material/Equalizer';
import { fetchFundRiskMetrics } from '../../api';
import type { FundRiskMetricsResponse } from '../../api';

interface RiskMetricsCardProps {
  code: string;
  fundName: string;
}

interface MetricCardProps {
  label: string;
  value: number | string | null;
  unit?: string;
  rating?: string;
  description?: string;
  icon: ReactElement;
  inverted?: boolean; // For metrics where lower is better
}

function MetricCard({ label, value, unit, rating, description, icon, inverted }: MetricCardProps) {
  const getRatingColor = (r: string | undefined, inv: boolean) => {
    if (!r) return '#64748b';
    const ratings: Record<string, string> = {
      excellent: '#22c55e',
      good: '#3b82f6',
      average: '#f59e0b',
      below_average: '#f97316',
      poor: '#ef4444',
    };
    return ratings[r] || '#64748b';
  };

  const color = getRatingColor(rating, inverted || false);

  return (
    <Tooltip title={description || ''} arrow placement="top">
      <Paper
        sx={{
          p: 2,
          height: '100%',
          display: 'flex',
          flexDirection: 'column',
          borderTop: 3,
          borderColor: color,
          transition: 'transform 0.2s, box-shadow 0.2s',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: 2,
          },
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Box sx={{ color }}>{icon}</Box>
          <Typography variant="caption" color="text.secondary" sx={{ fontWeight: 500 }}>
            {label}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 0.5 }}>
          <Typography
            variant="h5"
            sx={{ fontWeight: 700, fontFamily: 'JetBrains Mono', color }}
          >
            {value !== null ? value : '-'}
          </Typography>
          {unit && (
            <Typography variant="caption" color="text.secondary">
              {unit}
            </Typography>
          )}
        </Box>
        {rating && (
          <Typography
            variant="caption"
            sx={{
              mt: 0.5,
              color,
              textTransform: 'capitalize',
              fontWeight: 500,
            }}
          >
            {rating.replace('_', ' ')}
          </Typography>
        )}
      </Paper>
    </Tooltip>
  );
}

export default function RiskMetricsCard({ code, fundName }: RiskMetricsCardProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<FundRiskMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFundRiskMetrics(code);
      setData(result);
    } catch (err) {
      setError(t('funds.risk.error'));
      console.error('Failed to load risk metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, [code]);

  if (loading) {
    return (
      <Paper sx={{ p: 3, height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <CircularProgress />
      </Paper>
    );
  }

  if (error || !data) {
    return (
      <Paper sx={{ p: 3, height: 200 }}>
        <Typography color="error">{error || t('funds.risk.no_data')}</Typography>
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          {t('funds.risk.title')}
        </Typography>
        <Tooltip title={t('common.refresh')}>
          <IconButton onClick={loadMetrics} size="small">
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={2}>
        <Grid size={{ xs: 6, sm: 3 }}>
          <MetricCard
            label={t('funds.risk.sharpe_ratio')}
            value={data.sharpe_ratio?.value}
            rating={data.sharpe_ratio?.rating}
            description={data.sharpe_ratio?.description}
            icon={<SpeedIcon fontSize="small" />}
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <MetricCard
            label={t('funds.risk.max_drawdown')}
            value={data.max_drawdown?.value}
            unit="%"
            rating={data.max_drawdown?.rating}
            description={data.max_drawdown?.description}
            icon={<TrendingDownIcon fontSize="small" />}
            inverted
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <MetricCard
            label={t('funds.risk.volatility')}
            value={data.annual_volatility?.value}
            unit="%"
            rating={data.annual_volatility?.rating}
            description={data.annual_volatility?.description}
            icon={<ShowChartIcon fontSize="small" />}
            inverted
          />
        </Grid>
        <Grid size={{ xs: 6, sm: 3 }}>
          <MetricCard
            label={t('funds.risk.calmar_ratio')}
            value={data.calmar_ratio}
            rating={data.calmar_ratio && data.calmar_ratio > 1 ? 'good' : data.calmar_ratio && data.calmar_ratio > 0.5 ? 'average' : 'below_average'}
            description={t('funds.risk.calmar_description')}
            icon={<EqualizerIcon fontSize="small" />}
          />
        </Grid>
      </Grid>

      {/* Additional metrics row */}
      <Grid container spacing={2} sx={{ mt: 1 }}>
        <Grid size={{ xs: 6, sm: 4 }}>
          <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {t('funds.risk.annual_return')}
            </Typography>
            <Typography
              variant="body1"
              sx={{
                fontWeight: 600,
                fontFamily: 'JetBrains Mono',
                color: (data.annual_return?.value || 0) >= 0 ? '#22c55e' : '#ef4444',
              }}
            >
              {data.annual_return?.value !== undefined ? `${data.annual_return.value}%` : '-'}
            </Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 6, sm: 4 }}>
          <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {t('funds.risk.total_return')}
            </Typography>
            <Typography
              variant="body1"
              sx={{
                fontWeight: 600,
                fontFamily: 'JetBrains Mono',
                color: (data.total_return?.value || 0) >= 0 ? '#22c55e' : '#ef4444',
              }}
            >
              {data.total_return?.value !== undefined ? `${data.total_return.value}%` : '-'}
            </Typography>
          </Box>
        </Grid>
        <Grid size={{ xs: 6, sm: 4 }}>
          <Box sx={{ p: 1.5, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {t('funds.risk.win_rate')}
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 600, fontFamily: 'JetBrains Mono' }}>
              {data.win_rate?.value !== undefined ? `${data.win_rate.value}%` : '-'}
            </Typography>
          </Box>
        </Grid>
      </Grid>

      {/* Period info */}
      {data.period && (
        <Box sx={{ mt: 2, pt: 2, borderTop: 1, borderColor: 'divider' }}>
          <Typography variant="caption" color="text.secondary">
            {t('funds.risk.analysis_period')}: {data.period.start_date} ~ {data.period.end_date}
            ({data.period.trading_days} {t('funds.risk.trading_days')})
          </Typography>
        </Box>
      )}
    </Paper>
  );
}
