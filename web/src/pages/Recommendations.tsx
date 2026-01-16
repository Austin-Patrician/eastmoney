import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    CircularProgress,
    Chip,
    IconButton,
    Paper,
    Button,
    ToggleButton,
    ToggleButtonGroup,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    Tab,
    Alert,
    Tooltip,
    Collapse,
    Snackbar,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import AutoAwesomeIcon from '@mui/icons-material/AutoAwesome';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import PieChartIcon from '@mui/icons-material/PieChart';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import InsightsIcon from '@mui/icons-material/Insights';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import {
    generateRecommendations,
    fetchLatestRecommendations,
    
} from '../api';

import type {RecommendationResult,
    RecommendationStock,
    RecommendationFund,} from '../api';

// --- Utility Components ---

const NumberMono = ({ children, className = "", style = {} }: { children: React.ReactNode, className?: string, style?: React.CSSProperties }) => (
    <span className={`font-mono tracking-tight ${className}`} style={{ ...style, fontVariantNumeric: 'tabular-nums' }}>
        {children}
    </span>
);

const ColorVal = ({ val, suffix = "", bold = true }: { val: number | null | undefined, suffix?: string, bold?: boolean }) => {
    if (val === null || val === undefined) return <span className="text-slate-400">-</span>;
    const colorClass = val > 0 ? "text-red-600" : val < 0 ? "text-green-600" : "text-slate-500";
    return (
        <NumberMono className={`${bold ? 'font-semibold' : ''} ${colorClass}`}>
            {val > 0 ? '+' : ''}{typeof val === 'number' ? val.toFixed(2) : val}{suffix}
        </NumberMono>
    );
};

const ScoreBar = ({ score, maxScore = 100 }: { score: number, maxScore?: number }) => {
    const percentage = Math.min((score / maxScore) * 100, 100);
    const getColor = () => {
        if (percentage >= 70) return 'bg-green-500';
        if (percentage >= 50) return 'bg-blue-500';
        if (percentage >= 30) return 'bg-yellow-500';
        return 'bg-red-500';
    };
    return (
        <Box className="flex items-center gap-2 w-full">
            <Box className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
                <Box className={`h-full ${getColor()} rounded-full transition-all`} style={{ width: `${percentage}%` }} />
            </Box>
            <NumberMono className="text-xs font-semibold text-slate-600 w-8 text-right">{score.toFixed(0)}</NumberMono>
        </Box>
    );
};

const ConfidenceChip = ({ confidence }: { confidence?: string }) => {
    const { t } = useTranslation();
    if (!confidence) return null;
    const level = confidence.toLowerCase();
    const config: Record<string, { bg: string, text: string, label: string }> = {
        '高': { bg: 'bg-green-50', text: 'text-green-700', label: t('recommendations.confidence_levels.high') },
        'high': { bg: 'bg-green-50', text: 'text-green-700', label: t('recommendations.confidence_levels.high') },
        '中': { bg: 'bg-blue-50', text: 'text-blue-700', label: t('recommendations.confidence_levels.medium') },
        'medium': { bg: 'bg-blue-50', text: 'text-blue-700', label: t('recommendations.confidence_levels.medium') },
        '低': { bg: 'bg-orange-50', text: 'text-orange-700', label: t('recommendations.confidence_levels.low') },
        'low': { bg: 'bg-orange-50', text: 'text-orange-700', label: t('recommendations.confidence_levels.low') },
    };
    const c = config[level] || config['medium'];
    return <Chip label={c.label} size="small" className={`h-5 text-[10px] font-bold ${c.bg} ${c.text}`} />;
};

const formatMarketCap = (cap: number | null | undefined): string => {
    if (!cap) return '-';
    if (cap >= 1e12) return `${(cap / 1e12).toFixed(1)}万亿`;
    if (cap >= 1e8) return `${(cap / 1e8).toFixed(0)}亿`;
    return `${(cap / 1e4).toFixed(0)}万`;
};

const formatAmount = (amount: number | null | undefined): string => {
    if (!amount) return '-';
    if (Math.abs(amount) >= 1e8) return `${(amount / 1e8).toFixed(2)}亿`;
    if (Math.abs(amount) >= 1e4) return `${(amount / 1e4).toFixed(0)}万`;
    return amount.toFixed(0);
};

// --- Stock Table Component ---

interface StockTableProps {
    stocks: RecommendationStock[];
    isShortTerm: boolean;
}

const StockTable = ({ stocks, isShortTerm }: StockTableProps) => {
    const { t } = useTranslation();

    if (!stocks || stocks.length === 0) {
        return <Typography className="text-slate-400 text-center py-8">{t('recommendations.no_data')}</Typography>;
    }

    return (
        <TableContainer>
            <Table size="small">
                <TableHead>
                    <TableRow className="bg-slate-50">
                        <TableCell className="font-bold text-slate-600 text-xs w-8">{t('recommendations.table.rank')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.code')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.name')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.price')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.change')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs w-28">{t('recommendations.table.score')}</TableCell>
                        {isShortTerm ? (
                            <>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.net_inflow')}</TableCell>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.volume_ratio')}</TableCell>
                            </>
                        ) : (
                            <>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.pe')}</TableCell>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.market_cap')}</TableCell>
                            </>
                        )}
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.confidence')}</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {stocks.map((stock, index) => (
                        <TableRow key={stock.code} className="hover:bg-slate-50 transition-colors">
                            <TableCell>
                                <Box className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                    index < 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'
                                }`}>
                                    {index + 1}
                                </Box>
                            </TableCell>
                            <TableCell>
                                <NumberMono className="text-sm font-semibold text-slate-700">{stock.code}</NumberMono>
                            </TableCell>
                            <TableCell>
                                <Tooltip title={stock.investment_logic || ''} arrow>
                                    <Typography className="text-sm font-medium text-slate-800 cursor-help truncate max-w-[120px]">
                                        {stock.name}
                                    </Typography>
                                </Tooltip>
                            </TableCell>
                            <TableCell className="text-right">
                                <NumberMono className="text-sm font-semibold text-slate-800">
                                    {(stock.current_price || stock.price)?.toFixed(2) || '-'}
                                </NumberMono>
                            </TableCell>
                            <TableCell className="text-right">
                                <ColorVal val={stock.change_pct} suffix="%" />
                            </TableCell>
                            <TableCell>
                                <ScoreBar score={stock.recommendation_score || stock.score || 0} />
                            </TableCell>
                            {isShortTerm ? (
                                <>
                                    <TableCell className="text-right">
                                        <NumberMono className={`text-sm ${(stock.main_net_inflow || 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                                            {formatAmount(stock.main_net_inflow)}
                                        </NumberMono>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <NumberMono className="text-sm text-slate-600">
                                            {stock.volume_ratio?.toFixed(2) || '-'}
                                        </NumberMono>
                                    </TableCell>
                                </>
                            ) : (
                                <>
                                    <TableCell className="text-right">
                                        <NumberMono className="text-sm text-slate-600">
                                            {stock.pe?.toFixed(1) || '-'}
                                        </NumberMono>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <NumberMono className="text-sm text-slate-600">
                                            {formatMarketCap(stock.market_cap)}
                                        </NumberMono>
                                    </TableCell>
                                </>
                            )}
                            <TableCell>
                                <ConfidenceChip confidence={stock.confidence} />
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

// --- Fund Table Component ---

interface FundTableProps {
    funds: RecommendationFund[];
    isShortTerm: boolean;
}

const FundTable = ({ funds, isShortTerm }: FundTableProps) => {
    const { t } = useTranslation();

    if (!funds || funds.length === 0) {
        return <Typography className="text-slate-400 text-center py-8">{t('recommendations.no_data')}</Typography>;
    }

    return (
        <TableContainer>
            <Table size="small">
                <TableHead>
                    <TableRow className="bg-slate-50">
                        <TableCell className="font-bold text-slate-600 text-xs w-8">{t('recommendations.table.rank')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.code')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.name')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.fund_type')}</TableCell>
                        {isShortTerm ? (
                            <>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.return_1w')}</TableCell>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.return_1m')}</TableCell>
                            </>
                        ) : (
                            <>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.return_1y')}</TableCell>
                                <TableCell className="font-bold text-slate-600 text-xs text-right">{t('recommendations.table.return_3y')}</TableCell>
                            </>
                        )}
                        <TableCell className="font-bold text-slate-600 text-xs w-28">{t('recommendations.table.score')}</TableCell>
                        <TableCell className="font-bold text-slate-600 text-xs">{t('recommendations.table.confidence')}</TableCell>
                    </TableRow>
                </TableHead>
                <TableBody>
                    {funds.map((fund, index) => (
                        <TableRow key={fund.code} className="hover:bg-slate-50 transition-colors">
                            <TableCell>
                                <Box className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                                    index < 3 ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600'
                                }`}>
                                    {index + 1}
                                </Box>
                            </TableCell>
                            <TableCell>
                                <NumberMono className="text-sm font-semibold text-slate-700">{fund.code}</NumberMono>
                            </TableCell>
                            <TableCell>
                                <Tooltip title={fund.investment_logic || ''} arrow>
                                    <Typography className="text-sm font-medium text-slate-800 cursor-help truncate max-w-[160px]">
                                        {fund.name}
                                    </Typography>
                                </Tooltip>
                            </TableCell>
                            <TableCell>
                                <Chip
                                    label={fund.fund_type || '-'}
                                    size="small"
                                    className="h-5 text-[10px] bg-indigo-50 text-indigo-700 font-medium"
                                />
                            </TableCell>
                            {isShortTerm ? (
                                <>
                                    <TableCell className="text-right">
                                        <ColorVal val={fund.return_1w} suffix="%" />
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <ColorVal val={fund.return_1m} suffix="%" />
                                    </TableCell>
                                </>
                            ) : (
                                <>
                                    <TableCell className="text-right">
                                        <ColorVal val={fund.return_1y} suffix="%" />
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <ColorVal val={fund.return_3y} suffix="%" />
                                    </TableCell>
                                </>
                            )}
                            <TableCell>
                                <ScoreBar score={fund.recommendation_score || fund.score || 0} />
                            </TableCell>
                            <TableCell>
                                <ConfidenceChip confidence={fund.confidence} />
                            </TableCell>
                        </TableRow>
                    ))}
                </TableBody>
            </Table>
        </TableContainer>
    );
};

// --- Recommendation Section Component ---

interface RecommendationSectionProps {
    title: string;
    subtitle: string;
    icon: React.ReactNode;
    stocks: RecommendationStock[];
    funds: RecommendationFund[];
    marketView?: string;
    sectorPreference?: string[];
    riskWarning?: string;
    isShortTerm: boolean;
    defaultExpanded?: boolean;
}

const RecommendationSection = ({
    title,
    subtitle,
    icon,
    stocks,
    funds,
    marketView,
    sectorPreference,
    riskWarning,
    isShortTerm,
    defaultExpanded = true,
}: RecommendationSectionProps) => {
    const { t } = useTranslation();
    const [tabValue, setTabValue] = useState(0);
    const [expanded, setExpanded] = useState(defaultExpanded);

    return (
        <Paper elevation={0} className="border border-slate-200 rounded-xl bg-white overflow-hidden shadow-sm">
            {/* Section Header */}
            <Box
                className="px-5 py-4 flex items-center justify-between cursor-pointer hover:bg-slate-50 transition-colors"
                onClick={() => setExpanded(!expanded)}
            >
                <Box className="flex items-center gap-3">
                    <Box className={`w-10 h-10 rounded-lg flex items-center justify-center ${isShortTerm ? 'bg-blue-100' : 'bg-purple-100'}`}>
                        {icon}
                    </Box>
                    <Box>
                        <Typography variant="h6" className="font-bold text-slate-800">{title}</Typography>
                        <Typography variant="caption" className="text-slate-500">{subtitle}</Typography>
                    </Box>
                </Box>
                <Box className="flex items-center gap-2">
                    <Chip
                        label={`${stocks?.length || 0} ${t('recommendations.tabs.stocks')}`}
                        size="small"
                        className="h-6 text-xs bg-slate-100 text-slate-600"
                    />
                    <Chip
                        label={`${funds?.length || 0} ${t('recommendations.tabs.funds')}`}
                        size="small"
                        className="h-6 text-xs bg-slate-100 text-slate-600"
                    />
                    <IconButton size="small">
                        {expanded ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                    </IconButton>
                </Box>
            </Box>

            <Collapse in={expanded}>
                {/* Market View & Sector Cards */}
                {(marketView || (sectorPreference && sectorPreference.length > 0)) && (
                    <Box className="px-5 pb-3 flex flex-wrap gap-3">
                        {marketView && (
                            <Box className="flex-1 min-w-[200px] p-3 bg-slate-50 rounded-lg border border-slate-100">
                                <Box className="flex items-center gap-2 mb-2">
                                    <InsightsIcon className="text-slate-400 text-sm" />
                                    <Typography variant="caption" className="text-slate-500 font-bold uppercase">
                                        {t('recommendations.market_view.title')}
                                    </Typography>
                                </Box>
                                <Typography variant="body2" className="text-slate-700">
                                    {marketView}
                                </Typography>
                            </Box>
                        )}
                        {sectorPreference && sectorPreference.length > 0 && (
                            <Box className="flex-1 min-w-[200px] p-3 bg-slate-50 rounded-lg border border-slate-100">
                                <Box className="flex items-center gap-2 mb-2">
                                    <TrendingUpIcon className="text-slate-400 text-sm" />
                                    <Typography variant="caption" className="text-slate-500 font-bold uppercase">
                                        {t('recommendations.sector.hot_sectors')}
                                    </Typography>
                                </Box>
                                <Box className="flex flex-wrap gap-1">
                                    {sectorPreference.map((sector, i) => (
                                        <Chip key={i} label={sector} size="small" className="h-6 text-xs bg-green-50 text-green-700" />
                                    ))}
                                </Box>
                            </Box>
                        )}
                    </Box>
                )}

                {/* Tabs for Stocks/Funds */}
                <Box className="border-t border-slate-100">
                    <Tabs
                        value={tabValue}
                        onChange={(_, v) => setTabValue(v)}
                        className="px-5"
                        TabIndicatorProps={{ className: 'bg-blue-600' }}
                    >
                        <Tab
                            icon={<ShowChartIcon className="text-sm" />}
                            iconPosition="start"
                            label={t('recommendations.tabs.stocks')}
                            className="min-h-[48px] text-sm"
                        />
                        <Tab
                            icon={<PieChartIcon className="text-sm" />}
                            iconPosition="start"
                            label={t('recommendations.tabs.funds')}
                            className="min-h-[48px] text-sm"
                        />
                    </Tabs>
                </Box>

                {/* Table Content */}
                <Box className="px-5 pb-5">
                    {tabValue === 0 ? (
                        <StockTable stocks={stocks} isShortTerm={isShortTerm} />
                    ) : (
                        <FundTable funds={funds} isShortTerm={isShortTerm} />
                    )}
                </Box>

                {/* Risk Warning */}
                {riskWarning && (
                    <Box className="px-5 pb-4">
                        <Alert
                            severity="warning"
                            icon={<WarningAmberIcon className="text-amber-600" />}
                            className="bg-amber-50 border border-amber-200"
                        >
                            <Typography variant="body2" className="text-amber-800">
                                {riskWarning}
                            </Typography>
                        </Alert>
                    </Box>
                )}
            </Collapse>
        </Paper>
    );
};

// --- Main Page Component ---

export default function RecommendationsPage() {
    const { t } = useTranslation();
    const [data, setData] = useState<RecommendationResult | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [mode, setMode] = useState<'all' | 'short' | 'long'>('all');
    const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'error' }>({
        open: false,
        message: '',
        severity: 'success'
    });

    const loadData = async () => {
        try {
            setLoading(true);
            const result = await fetchLatestRecommendations();
            if (result.available && result.data) {
                setData(result.data);
            }
        } catch (error) {
            console.error('Failed to load recommendations', error);
        } finally {
            setLoading(false);
        }
    };

    const handleGenerate = async (forceRefresh: boolean = false) => {
        try {
            setGenerating(true);
            setSnackbar({ open: true, message: t('recommendations.messages.generate_started'), severity: 'success' });

            const result = await generateRecommendations({ mode, force_refresh: forceRefresh });
            setData(result);

            setSnackbar({ open: true, message: t('recommendations.messages.generate_success'), severity: 'success' });
        } catch (error) {
            console.error('Failed to generate recommendations', error);
            setSnackbar({ open: true, message: t('recommendations.messages.generate_error'), severity: 'error' });
        } finally {
            setGenerating(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // Extract data based on mode
    const shortTermData = data?.short_term;
    const longTermData = data?.long_term;

    const shortStocks = shortTermData?.short_term_stocks || shortTermData?.stocks || [];
    const shortFunds = shortTermData?.short_term_funds || shortTermData?.funds || [];
    const longStocks = longTermData?.long_term_stocks || longTermData?.stocks || [];
    const longFunds = longTermData?.long_term_funds || longTermData?.funds || [];

    return (
        <Box className="flex flex-col gap-6 w-full h-full pb-10">
            {/* Header */}
            <Box className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <Box className="flex items-center gap-3">
                    <Box className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg">
                        <AutoAwesomeIcon className="text-white" />
                    </Box>
                    <Box>
                        <Typography variant="h5" className="font-extrabold text-slate-800 tracking-tight">
                            {t('recommendations.title')}
                        </Typography>
                        <Typography variant="body2" className="text-slate-500">
                            {t('recommendations.subtitle')}
                        </Typography>
                    </Box>
                </Box>

                <Box className="flex items-center gap-3">
                    {/* Mode Selector */}
                    <ToggleButtonGroup
                        value={mode}
                        exclusive
                        onChange={(_, v) => v && setMode(v)}
                        size="small"
                        className="bg-slate-100 rounded-lg"
                    >
                        <ToggleButton value="all" className="px-4 text-xs font-semibold">
                            {t('recommendations.mode.all')}
                        </ToggleButton>
                        <ToggleButton value="short" className="px-4 text-xs font-semibold">
                            {t('recommendations.mode.short')}
                        </ToggleButton>
                        <ToggleButton value="long" className="px-4 text-xs font-semibold">
                            {t('recommendations.mode.long')}
                        </ToggleButton>
                    </ToggleButtonGroup>

                    {/* Generate Button */}
                    <Button
                        variant="contained"
                        startIcon={generating ? <CircularProgress size={16} color="inherit" /> : <AutoAwesomeIcon />}
                        onClick={() => handleGenerate(false)}
                        disabled={generating}
                        className="bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md hover:shadow-lg"
                    >
                        {generating ? t('recommendations.generating') : t('recommendations.generate')}
                    </Button>

                    {/* Force Refresh */}
                    <Tooltip title={t('recommendations.force_refresh')}>
                        <IconButton
                            size="small"
                            onClick={() => handleGenerate(true)}
                            disabled={generating}
                            className="bg-white border border-slate-200 shadow-sm hover:bg-slate-50"
                        >
                            <RefreshIcon fontSize="small" />
                        </IconButton>
                    </Tooltip>
                </Box>
            </Box>

            {/* Last Updated Info */}
            {data?.generated_at && (
                <Box className="flex items-center gap-2 text-slate-500">
                    <AccessTimeIcon className="text-sm" />
                    <Typography variant="caption">
                        {t('recommendations.last_updated')}: {new Date(data.generated_at).toLocaleString()}
                    </Typography>
                    {data.metadata && (
                        <Box className="flex gap-3 ml-4">
                            <Chip
                                label={`${t('recommendations.metadata.screening_time')}: ${data.metadata.screening_time?.toFixed(1)}s`}
                                size="small"
                                className="h-5 text-[10px] bg-slate-100"
                            />
                            <Chip
                                label={`${t('recommendations.metadata.llm_time')}: ${data.metadata.llm_time?.toFixed(1)}s`}
                                size="small"
                                className="h-5 text-[10px] bg-slate-100"
                            />
                            <Chip
                                label={`${t('recommendations.metadata.total_time')}: ${data.metadata.total_time?.toFixed(1)}s`}
                                size="small"
                                className="h-5 text-[10px] bg-blue-100 text-blue-700"
                            />
                        </Box>
                    )}
                </Box>
            )}

            {/* Loading State */}
            {loading && (
                <Box className="flex items-center justify-center py-20">
                    <CircularProgress size={32} className="text-slate-400" />
                </Box>
            )}

            {/* No Data State */}
            {!loading && !data && (
                <Paper elevation={0} className="border border-slate-200 rounded-xl bg-white p-12 text-center">
                    <AutoAwesomeIcon className="text-6xl text-slate-300 mb-4" />
                    <Typography variant="h6" className="text-slate-600 mb-2">
                        {t('recommendations.no_data')}
                    </Typography>
                    <Typography variant="body2" className="text-slate-400 mb-6">
                        {t('recommendations.no_data_hint')}
                    </Typography>
                    <Button
                        variant="contained"
                        startIcon={<AutoAwesomeIcon />}
                        onClick={() => handleGenerate(false)}
                        disabled={generating}
                        className="bg-gradient-to-r from-blue-600 to-purple-600"
                    >
                        {t('recommendations.generate')}
                    </Button>
                </Paper>
            )}

            {/* Recommendations Content */}
            {!loading && data && (
                <Box className="flex flex-col gap-6">
                    {/* Short-Term Section */}
                    {(mode === 'all' || mode === 'short') && shortTermData && (
                        <RecommendationSection
                            title={t('recommendations.short_term.title')}
                            subtitle={t('recommendations.short_term.subtitle')}
                            icon={<TrendingUpIcon className="text-blue-600" />}
                            stocks={shortStocks}
                            funds={shortFunds}
                            marketView={shortTermData.market_view}
                            sectorPreference={shortTermData.sector_preference}
                            riskWarning={shortTermData.risk_warning}
                            isShortTerm={true}
                            defaultExpanded={true}
                        />
                    )}

                    {/* Long-Term Section */}
                    {(mode === 'all' || mode === 'long') && longTermData && (
                        <RecommendationSection
                            title={t('recommendations.long_term.title')}
                            subtitle={t('recommendations.long_term.subtitle')}
                            icon={<CalendarMonthIcon className="text-purple-600" />}
                            stocks={longStocks}
                            funds={longFunds}
                            marketView={longTermData.macro_view}
                            sectorPreference={longTermData.sector_preference}
                            riskWarning={longTermData.risk_warning}
                            isShortTerm={false}
                            defaultExpanded={mode !== 'all'}
                        />
                    )}
                </Box>
            )}

            {/* Snackbar */}
            <Snackbar
                open={snackbar.open}
                autoHideDuration={4000}
                onClose={() => setSnackbar({ ...snackbar, open: false })}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                <Alert severity={snackbar.severity} onClose={() => setSnackbar({ ...snackbar, open: false })}>
                    {snackbar.message}
                </Alert>
            </Snackbar>
        </Box>
    );
}
