import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    Button,
    TextField,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Chip,
    Switch,
    FormControlLabel,
    Alert,
    Snackbar,
    CircularProgress,
    InputAdornment,
    Autocomplete,
    Dialog,
    DialogTitle,
    DialogContent,
    DialogActions,
    IconButton,
    Divider,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CheckIcon from '@mui/icons-material/Check';
import { getUserPreferences, saveUserPreferences, getPreferencePresets, type UserPreferences } from '../api';

const SECTORS_ZH = ['科技', '医药', '消费', '金融', '工业', '能源', '材料', '房地产', '公用事业', '通信', '军工', '新能源', '芯片', '互联网'];
const SECTORS_EN = ['Technology', 'Healthcare', 'Consumer', 'Finance', 'Industrial', 'Energy', 'Materials', 'Real Estate', 'Utilities', 'Telecom', 'Defense', 'New Energy', 'Semiconductor', 'Internet'];
const FUND_TYPES_ZH = ['股票型', '混合型', '指数型', '债券型', 'ETF', 'QDII'];
const FUND_TYPES_EN = ['Equity', 'Hybrid', 'Index', 'Bond', 'ETF', 'QDII'];

interface PreferencesModalProps {
    open: boolean;
    onClose: () => void;
    onSaved?: () => void;
}

const SectionTitle = ({ title, subtitle }: { title: string; subtitle?: string }) => (
    <Box sx={{ mb: 1.5 }}>
        <Typography sx={{ color: '#334155', fontWeight: 600, fontSize: '0.85rem' }}>
            {title}
        </Typography>
        {subtitle && (
            <Typography sx={{ color: '#94a3b8', fontSize: '0.7rem' }}>
                {subtitle}
            </Typography>
        )}
    </Box>
);

export default function PreferencesModal({ open, onClose, onSaved }: PreferencesModalProps) {
    const { t, i18n } = useTranslation();
    const isEn = i18n.language === 'en';
    const SECTORS = isEn ? SECTORS_EN : SECTORS_ZH;
    const FUND_TYPES = isEn ? FUND_TYPES_EN : FUND_TYPES_ZH;

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [preferences, setPreferences] = useState<Partial<UserPreferences>>({});
    const [presets, setPresets] = useState<Record<string, UserPreferences>>({});
    const [hasExistingPrefs, setHasExistingPrefs] = useState(false);
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' | 'info' }>({
        open: false,
        message: '',
        severity: 'success'
    });

    const RISK_LEVELS = [
        { value: 'conservative', label: t('recommendations.preferences.conservative'), desc: t('recommendations.preferences.low_risk') },
        { value: 'moderate', label: t('recommendations.preferences.moderate'), desc: t('recommendations.preferences.medium_risk') },
        { value: 'aggressive', label: t('recommendations.preferences.aggressive'), desc: t('recommendations.preferences.medium_high_risk') },
        { value: 'speculative', label: t('recommendations.preferences.speculative'), desc: t('recommendations.preferences.high_risk') },
    ];

    const INVESTMENT_HORIZONS = [
        { value: 'short_term', label: t('recommendations.preferences.horizon_short') },
        { value: 'medium_term', label: t('recommendations.preferences.horizon_medium') },
        { value: 'long_term', label: t('recommendations.preferences.horizon_long') },
    ];

    const INVESTMENT_GOALS = [
        { value: 'capital_preservation', label: t('recommendations.preferences.goal_preservation') },
        { value: 'steady_income', label: t('recommendations.preferences.goal_income') },
        { value: 'capital_appreciation', label: t('recommendations.preferences.goal_appreciation') },
        { value: 'speculation', label: t('recommendations.preferences.goal_speculation') },
    ];

    const INVESTMENT_STYLES = [
        { value: 'value', label: t('recommendations.preferences.style_value') },
        { value: 'growth', label: t('recommendations.preferences.style_growth') },
        { value: 'blend', label: t('recommendations.preferences.style_blend') },
        { value: 'momentum', label: t('recommendations.preferences.style_momentum') },
        { value: 'dividend', label: t('recommendations.preferences.style_dividend') },
    ];

    useEffect(() => {
        if (open) {
            loadPreferences();
            loadPresets();
        }
    }, [open]);

    const loadPreferences = async () => {
        try {
            setLoading(true);
            const data = await getUserPreferences();
            setPreferences(data.preferences);
            setHasExistingPrefs(data.exists);
        } catch (error) {
            console.error('Failed to load preferences:', error);
        } finally {
            setLoading(false);
        }
    };

    const loadPresets = async () => {
        try {
            const data = await getPreferencePresets();
            setPresets(data.presets);
        } catch (error) {
            console.error('Failed to load presets:', error);
        }
    };

    const handleSave = async () => {
        try {
            setSaving(true);
            await saveUserPreferences(preferences);
            setHasExistingPrefs(true);
            setSnackbar({ open: true, message: t('recommendations.preferences.save_success'), severity: 'success' });
            onSaved?.();
            setTimeout(() => onClose(), 800);
        } catch (error) {
            console.error('Failed to save preferences:', error);
            setSnackbar({ open: true, message: t('recommendations.preferences.save_error'), severity: 'error' });
        } finally {
            setSaving(false);
        }
    };

    const handleReset = () => {
        loadPreferences();
        setSnackbar({ open: true, message: t('recommendations.preferences.reset_done'), severity: 'info' });
    };

    const updatePreference = <K extends keyof UserPreferences>(key: K, value: UserPreferences[K]) => {
        setPreferences(prev => ({ ...prev, [key]: value }));
    };

    const inputSx = {
        '& .MuiOutlinedInput-root': { borderRadius: '8px', fontSize: '0.85rem' },
        '& .MuiInputLabel-root': { fontSize: '0.85rem' }
    };

    return (
        <>
            <Dialog
                open={open}
                onClose={onClose}
                maxWidth="sm"
                fullWidth
                PaperProps={{ sx: { borderRadius: '12px', maxHeight: '85vh' } }}
            >
                <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', py: 2, px: 2.5 }}>
                    <Box>
                        <Typography sx={{ fontWeight: 600, color: '#1e293b', fontSize: '1rem' }}>
                            {t('recommendations.preferences.title')}
                        </Typography>
                        <Typography sx={{ color: '#64748b', fontSize: '0.75rem' }}>
                            {hasExistingPrefs ? t('recommendations.preferences.configured') : t('recommendations.preferences.hint')}
                        </Typography>
                    </Box>
                    <IconButton onClick={onClose} size="small" sx={{ color: '#94a3b8' }}>
                        <CloseIcon fontSize="small" />
                    </IconButton>
                </DialogTitle>

                <DialogContent sx={{ p: 2.5 }}>
                    {loading ? (
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 8 }}>
                            <CircularProgress size={32} sx={{ color: '#6366f1' }} />
                        </Box>
                    ) : (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                            {/* Risk Level */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.risk_level')} subtitle={t('recommendations.preferences.risk_hint')} />
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 1 }}>
                                    {RISK_LEVELS.map((level) => {
                                        const isSelected = preferences.risk_level === level.value;
                                        return (
                                            <Box
                                                key={level.value}
                                                onClick={() => {
                                                    if (presets[level.value]) {
                                                        setPreferences(presets[level.value]);
                                                        setSnackbar({
                                                            open: true,
                                                            message: t('recommendations.preferences.template_applied', { name: level.label }),
                                                            severity: 'success'
                                                        });
                                                    }
                                                }}
                                                sx={{
                                                    p: 1.25,
                                                    borderRadius: '8px',
                                                    border: isSelected ? '2px solid #6366f1' : '1px solid #e2e8f0',
                                                    bgcolor: isSelected ? '#eef2ff' : '#fafafa',
                                                    cursor: 'pointer',
                                                    transition: 'all 0.15s ease',
                                                    '&:hover': { borderColor: '#a5b4fc', bgcolor: '#f5f3ff' },
                                                }}
                                            >
                                                <Typography sx={{ fontWeight: 600, fontSize: '0.8rem', color: isSelected ? '#4f46e5' : '#475569' }}>
                                                    {level.label}
                                                </Typography>
                                                <Typography sx={{ fontSize: '0.65rem', color: '#94a3b8' }}>
                                                    {level.desc}
                                                </Typography>
                                            </Box>
                                        );
                                    })}
                                </Box>
                            </Box>

                            <Divider />

                            {/* Basic Settings */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.basic_info')} subtitle={t('recommendations.preferences.basic_hint')} />
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                    <FormControl size="small" sx={inputSx}>
                                        <InputLabel>{t('recommendations.preferences.horizon')}</InputLabel>
                                        <Select
                                            value={preferences.investment_horizon || 'medium_term'}
                                            onChange={(e) => updatePreference('investment_horizon', e.target.value as any)}
                                            label={t('recommendations.preferences.horizon')}
                                        >
                                            {INVESTMENT_HORIZONS.map((option) => (
                                                <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>

                                    <FormControl size="small" sx={inputSx}>
                                        <InputLabel>{t('recommendations.preferences.goal')}</InputLabel>
                                        <Select
                                            value={preferences.investment_goal || 'capital_appreciation'}
                                            onChange={(e) => updatePreference('investment_goal', e.target.value as any)}
                                            label={t('recommendations.preferences.goal')}
                                        >
                                            {INVESTMENT_GOALS.map((option) => (
                                                <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>

                                    <FormControl size="small" sx={inputSx}>
                                        <InputLabel>{t('recommendations.preferences.style')}</InputLabel>
                                        <Select
                                            value={preferences.investment_style || 'blend'}
                                            onChange={(e) => updatePreference('investment_style', e.target.value as any)}
                                            label={t('recommendations.preferences.style')}
                                        >
                                            {INVESTMENT_STYLES.map((option) => (
                                                <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>

                                    <TextField
                                        label={t('recommendations.preferences.capital')}
                                        type="number"
                                        size="small"
                                        value={preferences.total_capital || ''}
                                        onChange={(e) => updatePreference('total_capital', parseFloat(e.target.value) || undefined)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">{t('recommendations.preferences.capital_unit')}</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                </Box>
                            </Box>

                            <Divider />

                            {/* Risk Control */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.risk_control')} subtitle={t('recommendations.preferences.risk_control_hint')} />
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                    <TextField
                                        label={t('recommendations.preferences.max_drawdown')}
                                        type="number"
                                        size="small"
                                        value={((preferences.max_drawdown_tolerance || 0.2) * 100).toFixed(0)}
                                        onChange={(e) => updatePreference('max_drawdown_tolerance', parseFloat(e.target.value) / 100)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.stop_loss_pct')}
                                        type="number"
                                        size="small"
                                        value={((preferences.stop_loss_percentage || 0.08) * 100).toFixed(0)}
                                        onChange={(e) => updatePreference('stop_loss_percentage', parseFloat(e.target.value) / 100)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.take_profit_pct')}
                                        type="number"
                                        size="small"
                                        value={preferences.take_profit_percentage ? (preferences.take_profit_percentage * 100).toFixed(0) : ''}
                                        onChange={(e) => updatePreference('take_profit_percentage', e.target.value ? parseFloat(e.target.value) / 100 : undefined)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.max_position')}
                                        type="number"
                                        size="small"
                                        value={((preferences.max_single_position || 0.15) * 100).toFixed(0)}
                                        onChange={(e) => updatePreference('max_single_position', parseFloat(e.target.value) / 100)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">%</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                </Box>
                            </Box>

                            <Divider />

                            {/* Stock Filters */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.stock_filter')} subtitle={t('recommendations.preferences.stock_filter_hint')} />
                                <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                    <TextField
                                        label={t('recommendations.preferences.min_market_cap')}
                                        type="number"
                                        size="small"
                                        value={preferences.min_market_cap ? preferences.min_market_cap / 1e8 : ''}
                                        onChange={(e) => updatePreference('min_market_cap', e.target.value ? parseFloat(e.target.value) * 1e8 : undefined)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">{t('recommendations.preferences.billion')}</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.max_market_cap')}
                                        type="number"
                                        size="small"
                                        value={preferences.max_market_cap ? preferences.max_market_cap / 1e8 : ''}
                                        onChange={(e) => updatePreference('max_market_cap', e.target.value ? parseFloat(e.target.value) * 1e8 : undefined)}
                                        InputProps={{ endAdornment: <InputAdornment position="end">{t('recommendations.preferences.billion')}</InputAdornment> }}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.min_pe')}
                                        type="number"
                                        size="small"
                                        value={preferences.min_pe || ''}
                                        onChange={(e) => updatePreference('min_pe', e.target.value ? parseFloat(e.target.value) : undefined)}
                                        sx={inputSx}
                                    />
                                    <TextField
                                        label={t('recommendations.preferences.max_pe')}
                                        type="number"
                                        size="small"
                                        value={preferences.max_pe || ''}
                                        onChange={(e) => updatePreference('max_pe', e.target.value ? parseFloat(e.target.value) : undefined)}
                                        sx={inputSx}
                                    />
                                </Box>

                                <Box sx={{ display: 'flex', gap: 2, mt: 2, p: 1.5, bgcolor: '#f8fafc', borderRadius: '8px' }}>
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                size="small"
                                                checked={preferences.avoid_st_stocks ?? true}
                                                onChange={(e) => updatePreference('avoid_st_stocks', e.target.checked)}
                                                sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#6366f1' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#6366f1' } }}
                                            />
                                        }
                                        label={<Typography sx={{ color: '#475569', fontSize: '0.8rem' }}>{t('recommendations.preferences.exclude_st')}</Typography>}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                size="small"
                                                checked={preferences.avoid_new_stocks ?? true}
                                                onChange={(e) => updatePreference('avoid_new_stocks', e.target.checked)}
                                                sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#6366f1' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#6366f1' } }}
                                            />
                                        }
                                        label={<Typography sx={{ color: '#475569', fontSize: '0.8rem' }}>{t('recommendations.preferences.exclude_new')}</Typography>}
                                    />
                                    <FormControlLabel
                                        control={
                                            <Switch
                                                size="small"
                                                checked={preferences.require_profitable ?? true}
                                                onChange={(e) => updatePreference('require_profitable', e.target.checked)}
                                                sx={{ '& .MuiSwitch-switchBase.Mui-checked': { color: '#6366f1' }, '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': { bgcolor: '#6366f1' } }}
                                            />
                                        }
                                        label={<Typography sx={{ color: '#475569', fontSize: '0.8rem' }}>{t('recommendations.preferences.require_profit')}</Typography>}
                                    />
                                </Box>
                            </Box>

                            <Divider />

                            {/* Sector Preferences */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.sector_pref')} subtitle={t('recommendations.preferences.sector_pref_hint')} />
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    <Autocomplete
                                        multiple
                                        size="small"
                                        options={SECTORS}
                                        value={preferences.preferred_sectors || []}
                                        onChange={(_, newValue) => updatePreference('preferred_sectors', newValue)}
                                        renderInput={(params) => (
                                            <TextField {...params} label={t('recommendations.preferences.preferred_sectors')} placeholder={t('recommendations.preferences.select')} sx={inputSx} />
                                        )}
                                        renderTags={(value, getTagProps) =>
                                            value.map((option, index) => (
                                                <Chip label={option} size="small" {...getTagProps({ index })} sx={{ bgcolor: '#dcfce7', color: '#166534', fontSize: '0.75rem', height: 24 }} />
                                            ))
                                        }
                                    />
                                    <Autocomplete
                                        multiple
                                        size="small"
                                        options={SECTORS}
                                        value={preferences.excluded_sectors || []}
                                        onChange={(_, newValue) => updatePreference('excluded_sectors', newValue)}
                                        renderInput={(params) => (
                                            <TextField {...params} label={t('recommendations.preferences.excluded_sectors')} placeholder={t('recommendations.preferences.select')} sx={inputSx} />
                                        )}
                                        renderTags={(value, getTagProps) =>
                                            value.map((option, index) => (
                                                <Chip label={option} size="small" {...getTagProps({ index })} sx={{ bgcolor: '#fee2e2', color: '#991b1b', fontSize: '0.75rem', height: 24 }} />
                                            ))
                                        }
                                    />
                                </Box>
                            </Box>

                            <Divider />

                            {/* Fund Preferences */}
                            <Box>
                                <SectionTitle title={t('recommendations.preferences.fund_pref')} subtitle={t('recommendations.preferences.fund_pref_hint')} />
                                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                    <Autocomplete
                                        multiple
                                        size="small"
                                        options={FUND_TYPES}
                                        value={preferences.preferred_fund_types || []}
                                        onChange={(_, newValue) => updatePreference('preferred_fund_types', newValue)}
                                        renderInput={(params) => (
                                            <TextField {...params} label={t('recommendations.preferences.preferred_fund_types')} placeholder={t('recommendations.preferences.select')} sx={inputSx} />
                                        )}
                                        renderTags={(value, getTagProps) =>
                                            value.map((option, index) => (
                                                <Chip label={option} size="small" {...getTagProps({ index })} sx={{ bgcolor: '#e0e7ff', color: '#3730a3', fontSize: '0.75rem', height: 24 }} />
                                            ))
                                        }
                                    />
                                    <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 2 }}>
                                        <TextField
                                            label={t('recommendations.preferences.min_fund_scale')}
                                            type="number"
                                            size="small"
                                            value={preferences.min_fund_scale ? preferences.min_fund_scale / 1e8 : 1}
                                            onChange={(e) => updatePreference('min_fund_scale', parseFloat(e.target.value) * 1e8)}
                                            InputProps={{ endAdornment: <InputAdornment position="end">{t('recommendations.preferences.billion')}</InputAdornment> }}
                                            sx={inputSx}
                                        />
                                        <TextField
                                            label={t('recommendations.preferences.recommendation_count')}
                                            type="number"
                                            size="small"
                                            value={preferences.fund_recommendation_count || 5}
                                            onChange={(e) => updatePreference('fund_recommendation_count', parseInt(e.target.value))}
                                            InputProps={{ endAdornment: <InputAdornment position="end">{t('recommendations.preferences.count_unit')}</InputAdornment> }}
                                            sx={inputSx}
                                        />
                                    </Box>
                                </Box>
                            </Box>
                        </Box>
                    )}
                </DialogContent>

                <DialogActions sx={{ borderTop: '1px solid #e2e8f0', px: 2.5, py: 1.5, gap: 1 }}>
                    <Button variant="text" onClick={handleReset} disabled={saving || loading} size="small" sx={{ color: '#64748b', fontSize: '0.8rem' }}>
                        {t('recommendations.preferences.reset')}
                    </Button>
                    <Box sx={{ flex: 1 }} />
                    <Button
                        variant="text"
                        onClick={onClose}
                        disabled={saving}
                        size="small"
                        sx={{ color: '#64748b', fontSize: '0.8rem' }}
                    >
                        {t('recommendations.preferences.cancel')}
                    </Button>
                    <Button
                        variant="contained"
                        startIcon={saving ? <CircularProgress size={14} color="inherit" /> : <CheckIcon sx={{ fontSize: 16 }} />}
                        onClick={handleSave}
                        disabled={saving || loading}
                        size="small"
                        sx={{ borderRadius: '8px', bgcolor: '#4f46e5', fontSize: '0.8rem', px: 2, '&:hover': { bgcolor: '#4338ca' } }}
                    >
                        {saving ? t('recommendations.preferences.saving') : t('recommendations.preferences.save')}
                    </Button>
                </DialogActions>
            </Dialog>

            <Snackbar
                open={snackbar.open}
                autoHideDuration={2000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })} sx={{ borderRadius: '8px', fontSize: '0.8rem' }}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </>
    );
}
