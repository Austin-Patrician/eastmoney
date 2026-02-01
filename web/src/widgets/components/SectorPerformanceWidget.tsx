/**
 * Sector Performance Widget
 *
 * Displays sector/concept performance ranking.
 */

import { Box, Typography, Chip } from '@mui/material';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, SectorPerformanceData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetSectorPerformance } from '../../api';

export default function SectorPerformanceWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    // Increase default limit to 20 to fill vertical space
    const limit = (config.settings?.limit as number) || 20;

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<SectorPerformanceData>(
        () => fetchWidgetSectorPerformance(limit),
        config.refreshInterval ? config.refreshInterval * 1000 : 600000
    );

    const renderTable = (items: any[], type: 'gainer' | 'loser') => {
        const isGainer = type === 'gainer';
        const colorClass = isGainer ? 'text-red-600' : 'text-green-600';
        const bgClass = isGainer ? 'bg-red-50/50' : 'bg-green-50/50';
        const icon = isGainer ? <ArrowDropUpIcon className="text-red-500" /> : <ArrowDropDownIcon className="text-green-500" />;
        const title = isGainer ? (isZh ? `领涨板块` : 'Gainers') : (isZh ? `领跌板块` : 'Losers');

        return (
            <Box className="flex-1 flex flex-col min-w-0 h-full border rounded-lg border-slate-100 overflow-hidden">
                <Box className={`flex items-center justify-between px-3 py-2 ${bgClass} border-b border-slate-100`}>
                    <Box className="flex items-center gap-1">
                        {icon}
                        <Typography variant="subtitle2" className={`font-bold uppercase ${isGainer ? 'text-red-700' : 'text-green-700'}`}>
                            {title}
                        </Typography>
                    </Box>
                    <Typography variant="caption" className="text-slate-400 font-medium">
                        TOP {limit}
                    </Typography>
                </Box>
                
                <Box className="flex-1 overflow-auto custom-scrollbar">
                    <table className="w-full text-xs relative">
                        <thead className="text-slate-500 font-semibold bg-white sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th className="text-left py-2 pl-3 w-8">#</th>
                                <th className="text-left py-2">{isZh ? '名称' : 'Name'}</th>
                                <th className="text-right py-2">{isZh ? '涨跌' : 'Chg%'}</th>
                                <th className="text-right py-2 pr-3">{isZh ? '净流' : 'Net'}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {items?.map((item, idx) => (
                                <tr key={item.name} className="hover:bg-slate-50 transition-colors group">
                                    <td className="py-1 pl-3">
                                        <span className={`flex items-center justify-center w-4 h-4 rounded text-[9px] font-bold text-white ${idx < 3 ? (isGainer ? 'bg-red-400' : 'bg-green-400') : 'bg-slate-200 text-slate-500'}`}>
                                            {idx + 1}
                                        </span>
                                    </td>
                                    <td className="py-1 font-medium text-slate-700 truncate max-w-[80px] group-hover:text-blue-600 transition-colors cursor-pointer" title={item.name}>
                                        {item.name}
                                    </td>
                                    <td className={`py-1 text-right font-bold ${item.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.change_pct >= 0 ? '+' : ''}{item.change_pct}%
                                    </td>
                                    <td className={`py-1 text-right font-mono pr-3 ${item.net_inflow >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.net_inflow > 0 ? '+' : ''}{item.net_inflow}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </Box>
            </Box>
        );
    };

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error || data?.error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-row gap-3 overflow-hidden p-1">
                {renderTable(data?.gainers || [], 'gainer')}
                {renderTable(data?.losers || [], 'loser')}
            </Box>
        </WidgetContainer>
    );
}
