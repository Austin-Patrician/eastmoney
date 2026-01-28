import { useTranslation } from 'react-i18next';
import { Paper, Typography, Box, Button, Chip, Skeleton } from '@mui/material';
import type { SxProps, Theme } from '@mui/material';
import TipsAndUpdatesIcon from '@mui/icons-material/TipsAndUpdates';
import type { RebalanceSuggestion } from '../../api';

interface RebalanceSuggestionsProps {
  suggestions: RebalanceSuggestion[];
  currentAllocation: Record<string, number>;
  loading: boolean;
  onRefresh: () => void;
  sx?: SxProps<Theme>;
}

const PRIORITY_COLORS: Record<string, 'error' | 'warning' | 'info' | 'default'> = {
  high: 'error',
  medium: 'warning',
  low: 'info',
};

const ACTION_LABELS: Record<string, string> = {
  reduce: '减仓',
  review: '审视',
  consider_reduce: '考虑减仓',
  adjust: '调整',
};

export default function RebalanceSuggestions({
  suggestions,
  currentAllocation,
  loading,
  onRefresh,
  sx,
}: RebalanceSuggestionsProps) {
  const { t } = useTranslation();

  // Safe defaults for potentially undefined data
  const allocation = currentAllocation || {};
  const suggestionsList = suggestions || [];

  if (loading) {
    return (
      <Paper sx={{ p: 2, borderRadius: '12px', ...sx }}>
        <Skeleton width="60%" height={28} />
        <Skeleton width="100%" height={60} sx={{ mt: 1 }} />
        <Skeleton width="100%" height={60} />
      </Paper>
    );
  }

  return (
    <Paper sx={{ p: 2, borderRadius: '12px', ...sx }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <TipsAndUpdatesIcon sx={{ color: '#f59e0b' }} />
          <Typography variant="h6" sx={{ fontWeight: 600 }}>
            {t('portfolio.rebalance_suggestions')}
          </Typography>
        </Box>
        <Button
          size="small"
          onClick={onRefresh}
          sx={{ textTransform: 'none', color: '#6366f1' }}
        >
          {t('common.refresh')}
        </Button>
      </Box>

      {/* Current Allocation */}
      {Object.keys(allocation).length > 0 && (
        <Box sx={{ display: 'flex', gap: 1, mb: 2 }}>
          {Object.entries(allocation).map(([type, pct]) => (
            <Chip
              key={type}
              label={`${type === 'stock' ? t('portfolio.stock_type') : t('portfolio.fund_type')}: ${pct}%`}
              variant="outlined"
              size="small"
            />
          ))}
        </Box>
      )}

      {suggestionsList.length === 0 ? (
        <Box sx={{ textAlign: 'center', py: 3 }}>
          <Typography color="text.secondary">{t('portfolio.no_suggestions')}</Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {suggestionsList.map((suggestion, idx) => (
            <Box
              key={idx}
              sx={{
                p: 1.5,
                borderRadius: '8px',
                border: '1px solid',
                borderColor: 'divider',
                bgcolor: 'action.hover',
              }}
            >
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 0.5 }}>
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {suggestion.asset_name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <Chip
                    label={ACTION_LABELS[suggestion.action] || suggestion.action}
                    size="small"
                    color={PRIORITY_COLORS[suggestion.priority] || 'default'}
                    sx={{ height: 20, fontSize: '0.65rem' }}
                  />
                </Box>
              </Box>
              <Typography variant="body2" color="text.secondary">
                {suggestion.reason}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Paper>
  );
}
