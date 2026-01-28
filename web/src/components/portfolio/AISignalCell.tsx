import React from 'react';
import { Box, Tooltip, useTheme, alpha, Typography, Chip } from '@mui/material';
import { TrendingUp, TrendingDown, RadioButtonUnchecked, AutoAwesome } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

interface AISignalCellProps {
  signalType: 'opportunity' | 'risk' | 'neutral';
  strength?: number;
  summary?: string;
  onClick?: () => void;
}

const AISignalCell: React.FC<AISignalCellProps> = ({
  signalType,
  strength = 0.5,
  summary,
  onClick,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const getSignalConfig = () => {
    const strengthPercent = Math.round(strength * 100);

    switch (signalType) {
      case 'opportunity':
        return {
          color: '#10b981', // emerald-500
          bgColor: alpha('#10b981', 0.12),
          borderColor: alpha('#10b981', 0.3),
          glowColor: 'rgba(16, 185, 129, 0.4)',
          label: t('portfolio.buy', '买入'),
          icon: TrendingUp,
          strengthLabel: strengthPercent >= 70 ? '强' : strengthPercent >= 40 ? '中' : '弱',
        };
      case 'risk':
        return {
          color: '#ef4444', // red-500
          bgColor: alpha('#ef4444', 0.12),
          borderColor: alpha('#ef4444', 0.3),
          glowColor: 'rgba(239, 68, 68, 0.4)',
          label: t('portfolio.sell', '卖出'),
          icon: TrendingDown,
          strengthLabel: strengthPercent >= 70 ? '强' : strengthPercent >= 40 ? '中' : '弱',
        };
      case 'neutral':
      default:
        return {
          color: '#6b7280', // gray-500
          bgColor: alpha('#9ca3af', 0.1),
          borderColor: alpha('#9ca3af', 0.25),
          glowColor: 'transparent',
          label: t('portfolio.hold', '持有'),
          icon: RadioButtonUnchecked,
          strengthLabel: '',
        };
    }
  };

  const config = getSignalConfig();
  const IconComponent = config.icon;

  return (
    <Tooltip
      title={
        <Box sx={{ p: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <AutoAwesome sx={{ fontSize: 14, color: '#fbbf24' }} />
            <Typography variant="caption" fontWeight={600} sx={{ color: 'common.white' }}>
              AI 智能分析
            </Typography>
          </Box>
          <Typography variant="body2" sx={{ mb: 1, color: 'common.white' }}>
            {summary || t('portfolio.noSignalDescription', '暂无详细分析')}
          </Typography>
          {signalType !== 'neutral' && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                信号强度:
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                {[1, 2, 3, 4, 5].map((level) => (
                  <Box
                    key={level}
                    sx={{
                      width: 8,
                      height: 12,
                      borderRadius: 0.5,
                      bgcolor: level <= Math.ceil(strength * 5) ? config.color : 'rgba(255,255,255,0.2)',
                      transition: 'background-color 0.2s',
                    }}
                  />
                ))}
              </Box>
              <Typography variant="caption" sx={{ color: config.color, fontWeight: 600 }}>
                {(strength * 100).toFixed(0)}%
              </Typography>
            </Box>
          )}
          <Typography
            variant="caption"
            sx={{ display: 'block', mt: 1, color: theme.palette.primary.light, opacity: 0.9 }}
          >
            {t('portfolio.clickForDetails', '点击查看详情')} →
          </Typography>
        </Box>
      }
      arrow
      placement="top"
    >
      <Chip
        icon={<IconComponent sx={{ fontSize: 14, color: `${config.color} !important` }} />}
        label={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Typography
              variant="caption"
              sx={{ fontWeight: 600, fontSize: '0.75rem', letterSpacing: 0.5 }}
            >
              {config.label}
            </Typography>
            {signalType !== 'neutral' && config.strengthLabel && (
              <Typography
                variant="caption"
                sx={{
                  fontSize: '0.65rem',
                  opacity: 0.85,
                  fontWeight: 500,
                }}
              >
                ({config.strengthLabel})
              </Typography>
            )}
          </Box>
        }
        onClick={onClick}
        size="small"
        sx={{
          height: 24,
          bgcolor: config.bgColor,
          border: `1px solid ${config.borderColor}`,
          color: config.color,
          cursor: 'pointer',
          transition: 'all 0.2s ease-in-out',
          boxShadow: signalType !== 'neutral' ? `0 0 6px ${alpha(config.color, 0.2)}` : 'none',
          '&:hover': {
            bgcolor: alpha(config.color, 0.18),
            borderColor: config.color,
            boxShadow: signalType !== 'neutral' ? `0 0 10px ${alpha(config.color, 0.3)}` : 'none',
            transform: 'translateY(-1px)',
          },
          '& .MuiChip-icon': {
            marginLeft: '6px',
            marginRight: '-2px',
          },
          '& .MuiChip-label': {
            paddingLeft: '6px',
            paddingRight: '10px',
          },
        }}
      />
    </Tooltip>
  );
};

export default AISignalCell;
