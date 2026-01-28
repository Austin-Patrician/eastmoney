import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Box,
  Typography,
  InputAdornment,
  IconButton,
  alpha,
  useTheme,
  Chip,
} from '@mui/material';
import { Close, Edit, TrendingUp, TrendingDown } from '@mui/icons-material';
import { useTranslation } from 'react-i18next';

interface Position {
  id: number;
  asset_code: string;
  asset_name?: string;
  asset_type: 'stock' | 'fund';
  total_shares: number;
  average_cost: number;
  current_price?: number | null;
  current_value?: number | null;
  unrealized_pnl?: number | null;
  unrealized_pnl_pct?: number | null;
}

interface EditPositionDialogProps {
  open: boolean;
  position: Position | null;
  onClose: () => void;
  onSave: (positionId: number, updates: { total_shares?: number; average_cost?: number; notes?: string }) => Promise<void>;
  loading?: boolean;
}

const EditPositionDialog: React.FC<EditPositionDialogProps> = ({
  open,
  position,
  onClose,
  onSave,
  loading = false,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();

  const [shares, setShares] = useState<string>('');
  const [cost, setCost] = useState<string>('');
  const [notes, setNotes] = useState<string>('');
  const [saving, setSaving] = useState(false);

  // Reset form when position changes
  useEffect(() => {
    if (position) {
      setShares(position.total_shares?.toString() || '0');
      setCost(position.average_cost?.toString() || '0');
      setNotes('');
    }
  }, [position]);

  const handleSave = async () => {
    if (!position) return;

    const updates: { total_shares?: number; average_cost?: number; notes?: string } = {};

    const newShares = parseFloat(shares);
    const newCost = parseFloat(cost);

    if (!isNaN(newShares) && newShares !== position.total_shares) {
      updates.total_shares = newShares;
    }
    if (!isNaN(newCost) && newCost !== position.average_cost) {
      updates.average_cost = newCost;
    }
    if (notes.trim()) {
      updates.notes = notes.trim();
    }

    if (Object.keys(updates).length === 0) {
      onClose();
      return;
    }

    setSaving(true);
    try {
      await onSave(position.id, updates);
      onClose();
    } catch (error) {
      console.error('Failed to save position:', error);
    } finally {
      setSaving(false);
    }
  };

  // Calculate preview values
  const newShares = parseFloat(shares) || 0;
  const newCost = parseFloat(cost) || 0;
  const newTotalCost = newShares * newCost;
  const currentPrice = position?.current_price || 0;
  const newValue = newShares * currentPrice;
  const newPnl = currentPrice > 0 ? newValue - newTotalCost : 0;
  const newPnlPct = newTotalCost > 0 && currentPrice > 0 ? ((currentPrice / newCost) - 1) * 100 : 0;

  if (!position) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          overflow: 'hidden',
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: alpha(theme.palette.primary.main, 0.05),
          borderBottom: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Edit sx={{ color: 'primary.main' }} />
          <Box>
            <Typography variant="h6" fontWeight={600}>
              {t('portfolio.editPosition', '编辑持仓')}
            </Typography>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
              <Typography variant="body2" color="text.secondary">
                {position.asset_name || position.asset_code}
              </Typography>
              <Chip
                size="small"
                label={position.asset_code}
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
            </Box>
          </Box>
        </Box>
        <IconButton onClick={onClose} size="small">
          <Close />
        </IconButton>
      </DialogTitle>

      <DialogContent sx={{ pt: 3 }}>
        {/* Current Info */}
        <Box
          sx={{
            p: 2,
            mb: 3,
            borderRadius: 2,
            bgcolor: alpha(theme.palette.info.main, 0.05),
            border: `1px solid ${alpha(theme.palette.info.main, 0.15)}`,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
            当前信息
          </Typography>
          <Box sx={{ display: 'flex', gap: 3 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">持仓份额</Typography>
              <Typography variant="body2" fontWeight={500}>
                {position.total_shares?.toLocaleString()}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">成本价</Typography>
              <Typography variant="body2" fontWeight={500}>
                ¥{position.average_cost?.toFixed(4)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">现价</Typography>
              <Typography variant="body2" fontWeight={500}>
                {position.current_price ? `¥${position.current_price.toFixed(4)}` : '--'}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Edit Fields */}
        <Box sx={{ display: 'flex', gap: 2, mb: 3 }}>
          <TextField
            label={t('portfolio.shares', '持仓份额')}
            type="number"
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            fullWidth
            size="small"
            InputProps={{
              inputProps: { min: 0, step: 'any' },
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
              },
            }}
          />
          <TextField
            label={t('portfolio.costPrice', '成本价')}
            type="number"
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            fullWidth
            size="small"
            InputProps={{
              startAdornment: <InputAdornment position="start">¥</InputAdornment>,
              inputProps: { min: 0, step: 'any' },
            }}
            sx={{
              '& .MuiOutlinedInput-root': {
                borderRadius: 2,
              },
            }}
          />
        </Box>

        {/* Preview */}
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            bgcolor: alpha(theme.palette.background.default, 0.5),
            border: `1px dashed ${alpha(theme.palette.divider, 0.3)}`,
          }}
        >
          <Typography variant="caption" color="text.secondary" sx={{ mb: 1.5, display: 'block' }}>
            变更预览
          </Typography>
          <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
            <Box>
              <Typography variant="caption" color="text.secondary">总成本</Typography>
              <Typography variant="body2" fontWeight={600}>
                ¥{newTotalCost.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">市值</Typography>
              <Typography variant="body2" fontWeight={600}>
                {currentPrice > 0 ? `¥${newValue.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '--'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">预计盈亏</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                {currentPrice > 0 && (
                  newPnl >= 0 ? (
                    <TrendingUp sx={{ fontSize: 14, color: 'success.main' }} />
                  ) : (
                    <TrendingDown sx={{ fontSize: 14, color: 'error.main' }} />
                  )
                )}
                <Typography
                  variant="body2"
                  fontWeight={600}
                  sx={{ color: currentPrice > 0 ? (newPnl >= 0 ? 'success.main' : 'error.main') : 'text.secondary' }}
                >
                  {currentPrice > 0
                    ? `${newPnl >= 0 ? '+' : ''}¥${newPnl.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} (${newPnlPct >= 0 ? '+' : ''}${newPnlPct.toFixed(2)}%)`
                    : '--'}
                </Typography>
              </Box>
            </Box>
          </Box>
        </Box>

        {/* Notes */}
        <TextField
          label={t('portfolio.notes', '备注')}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          fullWidth
          size="small"
          multiline
          rows={2}
          placeholder="可选：记录调整原因..."
          sx={{
            mt: 2,
            '& .MuiOutlinedInput-root': {
              borderRadius: 2,
            },
          }}
        />
      </DialogContent>

      <DialogActions sx={{ px: 3, py: 2, borderTop: `1px solid ${alpha(theme.palette.divider, 0.1)}` }}>
        <Button onClick={onClose} sx={{ textTransform: 'none' }}>
          {t('common.cancel', '取消')}
        </Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={saving || loading}
          sx={{
            textTransform: 'none',
            borderRadius: 2,
            px: 3,
            bgcolor: '#6366f1',
            '&:hover': { bgcolor: '#4f46e5' },
          }}
        >
          {saving ? t('common.saving', '保存中...') : t('common.save', '保存')}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default EditPositionDialog;
