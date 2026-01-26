import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  Alert,
} from '@mui/material';

interface PositionFormProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (data: PositionFormData) => Promise<void>;
  fundCode: string;
  fundName: string;
  initialData?: PositionFormData;
  mode: 'create' | 'edit';
}

export interface PositionFormData {
  fund_code: string;
  fund_name: string;
  shares: number;
  cost_basis: number;
  purchase_date: string;
  notes?: string;
}

export default function PositionForm({
  open,
  onClose,
  onSubmit,
  fundCode,
  fundName,
  initialData,
  mode,
}: PositionFormProps) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState<PositionFormData>({
    fund_code: fundCode,
    fund_name: fundName,
    shares: 0,
    cost_basis: 0,
    purchase_date: new Date().toISOString().split('T')[0],
    notes: '',
  });

  useEffect(() => {
    if (initialData) {
      setFormData(initialData);
    } else {
      setFormData({
        fund_code: fundCode,
        fund_name: fundName,
        shares: 0,
        cost_basis: 0,
        purchase_date: new Date().toISOString().split('T')[0],
        notes: '',
      });
    }
  }, [fundCode, fundName, initialData, open]);

  const handleChange = (field: keyof PositionFormData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = e.target.value;
    setFormData((prev) => ({
      ...prev,
      [field]: field === 'shares' || field === 'cost_basis' ? parseFloat(value) || 0 : value,
    }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);

    // Validation
    if (!formData.shares || formData.shares <= 0) {
      setError(t('funds.position.error_shares'));
      setLoading(false);
      return;
    }
    if (!formData.cost_basis || formData.cost_basis <= 0) {
      setError(t('funds.position.error_cost'));
      setLoading(false);
      return;
    }
    if (!formData.purchase_date) {
      setError(t('funds.position.error_date'));
      setLoading(false);
      return;
    }

    try {
      await onSubmit(formData);
      onClose();
    } catch (err: any) {
      setError(err.message || t('funds.position.error_save'));
    } finally {
      setLoading(false);
    }
  };

  // Calculate estimated position value
  const estimatedValue = formData.shares * formData.cost_basis;

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {mode === 'create' ? t('funds.position.add_title') : t('funds.position.edit_title')}
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ mt: 1 }}>
          {/* Fund Info (read-only) */}
          <Box sx={{ mb: 3, p: 2, bgcolor: 'grey.50', borderRadius: 1 }}>
            <Typography variant="caption" color="text.secondary">
              {t('funds.position.fund')}
            </Typography>
            <Typography variant="body1" sx={{ fontWeight: 600 }}>
              {fundName} ({fundCode})
            </Typography>
          </Box>

          {/* Shares */}
          <TextField
            fullWidth
            label={t('funds.position.shares')}
            type="number"
            value={formData.shares || ''}
            onChange={handleChange('shares')}
            sx={{ mb: 2 }}
            InputProps={{
              endAdornment: <InputAdornment position="end">{t('funds.position.shares_unit')}</InputAdornment>,
            }}
            inputProps={{ min: 0, step: 0.01 }}
          />

          {/* Cost Basis */}
          <TextField
            fullWidth
            label={t('funds.position.cost_basis')}
            type="number"
            value={formData.cost_basis || ''}
            onChange={handleChange('cost_basis')}
            sx={{ mb: 2 }}
            InputProps={{
              startAdornment: <InputAdornment position="start">¥</InputAdornment>,
            }}
            inputProps={{ min: 0, step: 0.0001 }}
            helperText={t('funds.position.cost_basis_help')}
          />

          {/* Purchase Date */}
          <TextField
            fullWidth
            label={t('funds.position.purchase_date')}
            type="date"
            value={formData.purchase_date}
            onChange={handleChange('purchase_date')}
            sx={{ mb: 2 }}
            slotProps={{
              inputLabel: { shrink: true }
            }}
          />

          {/* Notes */}
          <TextField
            fullWidth
            label={t('funds.position.notes')}
            value={formData.notes || ''}
            onChange={handleChange('notes')}
            multiline
            rows={2}
            sx={{ mb: 2 }}
          />

          {/* Estimated Value */}
          {estimatedValue > 0 && (
            <Box sx={{ p: 2, bgcolor: 'primary.50', borderRadius: 1, borderLeft: 4, borderColor: 'primary.main' }}>
              <Typography variant="caption" color="text.secondary">
                {t('funds.position.estimated_cost')}
              </Typography>
              <Typography variant="h6" sx={{ fontWeight: 700, color: 'primary.main', fontFamily: 'JetBrains Mono' }}>
                ¥{estimatedValue.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </Typography>
            </Box>
          )}
        </Box>
      </DialogContent>
      <DialogActions sx={{ px: 3, pb: 2 }}>
        <Button onClick={onClose} disabled={loading}>
          {t('common.cancel')}
        </Button>
        <Button variant="contained" onClick={handleSubmit} disabled={loading}>
          {loading ? t('common.saving') : mode === 'create' ? t('funds.position.add') : t('common.save')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
