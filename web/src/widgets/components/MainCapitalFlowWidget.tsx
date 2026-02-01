/**
 * Main Capital Flow Widget
 *
 * Displays top stocks by main capital net inflow.
 */

import { Box, Typography, Chip } from '@mui/material';
import TimelineIcon from '@mui/icons-material/Timeline';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, MainCapitalFlowData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetMainCapitalFlow } from '../../api';

const NumberMono = ({ children, className = "" }: { children: React.ReactNode; className?: string }) => (
    <span className={`font-mono tracking-tight ${className}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
        {children}
    </span>
);

const ColorVal = ({ val, suffix = "", bold = true }: { val: number; suffix?: string; bold?: boolean }) => {
    const colorClass = val > 0 ? "text-red-600" : val < 0 ? "text-green-600" : "text-slate-500";
    return (
        <NumberMono className={`${bold ? 'font-bold' : ''} ${colorClass}`}>
            {val > 0 ? '+' : ''}{val}{suffix}
        </NumberMono>
    );
};

export default function MainCapitalFlowWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    const limit = (config.settings?.limit as number) || 10;

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<MainCapitalFlowData>(
        () => fetchWidgetMainCapitalFlow(limit),
        config.refreshInterval ? config.refreshInterval * 1000 : 300000
    );

    const topFlows = data?.top_flows || [];
    const mainFlow = data?.market_overview?.main_flow || 0;

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-col">
                {/* Header with total flow */}
                <Box className="flex justify-between items-center mb-3">
                    <Box className="flex items-center gap-2">
                        <TimelineIcon className="text-indigo-600" fontSize="small" />
                        <Typography variant="caption" className="text-slate-400 font-medium">
                            {isZh ? '净流入领跑者' : 'Top Net Inflow'}
                        </Typography>
                    </Box>
                    <Chip
                        label={`${isZh ? '主力净流入' : 'Main Flow'}: ${mainFlow}${isZh ? '亿' : 'B'}`}
                        size="small"
                        className="bg-indigo-50 text-indigo-700 font-bold border border-indigo-100"
                    />
                </Box>

                {/* Table */}
                <Box className="flex-1 overflow-auto">
                    <table className="w-full text-sm">
                        <thead className="text-slate-400 text-[11px] uppercase tracking-wider border-b border-slate-50">
                            <tr>
                                <th className="text-left py-2 font-bold">{isZh ? '代码' : 'Code'}</th>
                                <th className="text-left py-2 font-bold">{isZh ? '名称' : 'Name'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '净流入' : 'Net Inflow'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '涨跌幅' : 'Change'}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {topFlows.map((row) => (
                                <tr key={row.code} className="hover:bg-indigo-50/30 transition-colors">
                                    <td className="py-2 font-mono text-slate-400">{row.code}</td>
                                    <td className="py-2 font-bold text-slate-700">{row.name}</td>
                                    <td className="py-2 text-right">
                                        <NumberMono className="text-indigo-700 font-bold bg-indigo-50 px-2 py-0.5 rounded">
                                            +{row.net_buy}
                                        </NumberMono>
                                    </td>
                                    <td className="py-2 text-right">
                                        <ColorVal val={row.change_pct} suffix="%" />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {topFlows.length === 0 && !loading && (
                        <Box className="py-8 text-center text-slate-400">
                            {isZh ? '暂无数据' : 'No data available'}
                        </Box>
                    )}
                </Box>
            </Box>
        </WidgetContainer>
    );
}
