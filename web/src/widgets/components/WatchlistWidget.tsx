/**
 * Watchlist Widget
 *
 * Displays user's watchlist stocks with real-time quotes.
 */

import { Box, Typography } from '@mui/material';
import StarIcon from '@mui/icons-material/Star';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, WatchlistData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetWatchlist } from '../../api';

const NumberMono = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <span className={`font-mono tracking-tight ${className}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
        {children}
    </span>
);

export default function WatchlistWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<WatchlistData>(
        fetchWidgetWatchlist,
        config.refreshInterval ? config.refreshInterval * 1000 : 60000
    );

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error || data?.error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-col">
                {data?.trade_date && (
                    <Box className="flex items-center gap-2 mb-3">
                        <StarIcon className="text-amber-500" fontSize="small" />
                        <Typography variant="caption" className="text-slate-500">
                            {data.trade_date}
                        </Typography>
                    </Box>
                )}

                <Box className="flex-1 overflow-auto">
                    <table className="w-full text-sm">
                        <thead className="text-slate-400 text-[11px] uppercase tracking-wider border-b border-slate-100">
                            <tr>
                                <th className="text-left py-2 font-bold">{isZh ? '代码' : 'Code'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '价格' : 'Price'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '涨跌幅' : 'Change'}</th>
                                <th className="text-right py-2 font-bold">PE</th>
                                <th className="text-right py-2 font-bold">{isZh ? '市值' : 'MktCap'}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {data?.stocks?.map((stock) => (
                                <tr key={stock.code} className="hover:bg-amber-50/30 transition-colors">
                                    <td className="py-2 font-mono text-slate-600 font-medium">{stock.code}</td>
                                    <td className="py-2 text-right">
                                        <NumberMono className="font-bold text-slate-800">
                                            {stock.close?.toFixed(2)}
                                        </NumberMono>
                                    </td>
                                    <td className={`py-2 text-right font-bold ${stock.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {stock.change_pct >= 0 ? '+' : ''}{stock.change_pct?.toFixed(2)}%
                                    </td>
                                    <td className="py-2 text-right text-slate-500">
                                        {stock.pe?.toFixed(1) || '-'}
                                    </td>
                                    <td className="py-2 text-right text-slate-500">
                                        {stock.total_mv ? `${stock.total_mv}${isZh ? '亿' : 'B'}` : '-'}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {(!data?.stocks || data.stocks.length === 0) && !loading && (
                        <Box className="py-8 text-center text-slate-400">
                            <StarIcon className="text-slate-300 mb-2" />
                            <Typography variant="body2">
                                {isZh ? '暂无自选股' : 'No stocks in watchlist'}
                            </Typography>
                        </Box>
                    )}
                </Box>
            </Box>
        </WidgetContainer>
    );
}
