/**
 * Industry Flow Widget
 *
 * Displays industry-level capital flow data from THS.
 */

import { Box, Typography } from '@mui/material';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, IndustryFlowData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetIndustryFlow } from '../../api';

export default function IndustryFlowWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    const limit = (config.settings?.limit as number) || 5;

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<IndustryFlowData>(
        () => fetchWidgetIndustryFlow(limit),
        config.refreshInterval ? config.refreshInterval * 1000 : 600000
    );

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error || data?.error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-col gap-4">
                {/* Net Inflow Leaders */}
                <Box className="flex-1">
                    <Box className="flex items-center gap-2 mb-2">
                        <ArrowDropUpIcon className="text-red-500" />
                        <Typography variant="caption" className="text-slate-500 font-bold uppercase">
                            {isZh ? '净流入领先' : 'Net Inflow Leaders'}
                        </Typography>
                    </Box>
                    <Box className="space-y-1">
                        {data?.gainers?.slice(0, limit).map((item, idx) => (
                            <Box
                                key={item.name}
                                className="flex justify-between items-center p-2 rounded bg-red-50/50 hover:bg-red-50 transition-colors"
                            >
                                <Box className="flex items-center gap-2">
                                    <span className="text-[10px] font-mono text-white bg-red-400 w-5 h-5 flex items-center justify-center rounded font-bold">
                                        {idx + 1}
                                    </span>
                                    <Typography variant="body2" className="font-medium text-slate-700">
                                        {item.name}
                                    </Typography>
                                </Box>
                                <Box className="flex items-center gap-3">
                                    <span className={`text-sm font-bold ${item.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.change_pct >= 0 ? '+' : ''}{item.change_pct}%
                                    </span>
                                    <span className="text-sm font-mono text-red-600 bg-red-100 px-2 py-0.5 rounded">
                                        +{item.net_inflow}{isZh ? '亿' : 'B'}
                                    </span>
                                </Box>
                            </Box>
                        ))}
                    </Box>
                </Box>

                {/* Net Outflow Leaders */}
                <Box className="flex-1">
                    <Box className="flex items-center gap-2 mb-2">
                        <ArrowDropDownIcon className="text-green-500" />
                        <Typography variant="caption" className="text-slate-500 font-bold uppercase">
                            {isZh ? '净流出领先' : 'Net Outflow Leaders'}
                        </Typography>
                    </Box>
                    <Box className="space-y-1">
                        {data?.losers?.slice(0, limit).map((item, idx) => (
                            <Box
                                key={item.name}
                                className="flex justify-between items-center p-2 rounded bg-green-50/50 hover:bg-green-50 transition-colors"
                            >
                                <Box className="flex items-center gap-2">
                                    <span className="text-[10px] font-mono text-white bg-green-400 w-5 h-5 flex items-center justify-center rounded font-bold">
                                        {idx + 1}
                                    </span>
                                    <Typography variant="body2" className="font-medium text-slate-700">
                                        {item.name}
                                    </Typography>
                                </Box>
                                <Box className="flex items-center gap-3">
                                    <span className={`text-sm font-bold ${item.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.change_pct >= 0 ? '+' : ''}{item.change_pct}%
                                    </span>
                                    <span className="text-sm font-mono text-green-600 bg-green-100 px-2 py-0.5 rounded">
                                        {item.net_inflow}{isZh ? '亿' : 'B'}
                                    </span>
                                </Box>
                            </Box>
                        ))}
                    </Box>
                </Box>
            </Box>
        </WidgetContainer>
    );
}
