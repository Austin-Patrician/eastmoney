/**
 * Forex Rates Widget
 *
 * Displays major currency exchange rates.
 */

import { Box, Typography } from '@mui/material';
import CurrencyExchangeIcon from '@mui/icons-material/CurrencyExchange';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, ForexRatesData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetForexRates } from '../../api';

export default function ForexRatesWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<ForexRatesData>(
        fetchWidgetForexRates,
        config.refreshInterval ? config.refreshInterval * 1000 : 3600000
    );

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error || data?.error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-col gap-2">
                {data?.rates?.map((rate) => (
                    <Box
                        key={rate.code}
                        className="flex justify-between items-center p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
                    >
                        <Box className="flex items-center gap-3">
                            <CurrencyExchangeIcon className="text-blue-500" fontSize="small" />
                            <Box>
                                <Typography variant="body2" className="font-medium text-slate-700">
                                    {isZh ? rate.name : rate.name_en}
                                </Typography>
                                <Typography variant="caption" className="text-slate-400">
                                    {rate.date}
                                </Typography>
                            </Box>
                        </Box>
                        <Box className="text-right">
                            <Typography variant="h6" className="font-mono font-bold text-slate-800">
                                {rate.rate?.toFixed(4)}
                            </Typography>
                            <Box className="flex items-center justify-end gap-1">
                                {rate.change_pct >= 0 ? (
                                    <TrendingUpIcon className="text-red-500" fontSize="small" />
                                ) : (
                                    <TrendingDownIcon className="text-green-500" fontSize="small" />
                                )}
                                <Typography
                                    variant="caption"
                                    className={`font-bold ${rate.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}
                                >
                                    {rate.change_pct >= 0 ? '+' : ''}{rate.change_pct?.toFixed(2)}%
                                </Typography>
                            </Box>
                        </Box>
                    </Box>
                ))}

                {(!data?.rates || data.rates.length === 0) && !loading && (
                    <Box className="h-full flex items-center justify-center text-slate-400">
                        {isZh ? '暂无汇率数据' : 'No forex data available'}
                    </Box>
                )}
            </Box>
        </WidgetContainer>
    );
}
