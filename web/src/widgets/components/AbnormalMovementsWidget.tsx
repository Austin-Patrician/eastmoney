/**
 * Abnormal Movements Widget
 *
 * Displays real-time stock movement signals.
 */

import { Box, Typography, Paper } from '@mui/material';
import BoltIcon from '@mui/icons-material/Bolt';
import ArrowDropUpIcon from '@mui/icons-material/ArrowDropUp';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchDashboardOverview } from '../../api';

interface AbnormalMovement {
    time: string;
    name: string;
    type: string;
    info: string;
}

interface AbnormalData {
    abnormal_movements?: AbnormalMovement[];
}

export default function AbnormalMovementsWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<AbnormalData>(
        fetchDashboardOverview,
        config.refreshInterval ? config.refreshInterval * 1000 : 30000
    );

    const movements = data?.abnormal_movements || [];

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full overflow-x-auto whitespace-nowrap scrollbar-hide flex gap-3 items-stretch">
                {movements.map((m, i) => (
                    <Paper
                        key={i}
                        elevation={0}
                        className="inline-block min-w-[180px] p-3 rounded-xl border border-slate-200 bg-white hover:border-amber-300 hover:shadow-md transition-all flex-shrink-0"
                    >
                        <Box className="flex justify-between items-start mb-2">
                            <span className="bg-slate-100 text-slate-400 px-2 py-0.5 rounded text-[10px] font-mono font-bold">
                                {m.time}
                            </span>
                            {m.type.includes('拉升') || m.type.includes('涨') ? (
                                <ArrowDropUpIcon fontSize="small" className="text-red-500 bg-red-50 rounded-full p-0.5" />
                            ) : (
                                <ArrowDropDownIcon fontSize="small" className="text-green-500 bg-green-50 rounded-full p-0.5" />
                            )}
                        </Box>

                        <Typography variant="subtitle2" className="font-bold text-slate-800 truncate mb-1">
                            {m.name}
                        </Typography>
                        <Typography variant="caption" className="text-slate-400 font-mono text-[10px] block mb-2">
                            {m.info.replace('Code: ', '')}
                        </Typography>

                        <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wide border ${
                            m.type.includes('拉升') || m.type.includes('涨')
                                ? 'bg-red-50 text-red-600 border-red-100'
                                : m.type.includes('跳水') || m.type.includes('跌')
                                ? 'bg-green-50 text-green-600 border-green-100'
                                : 'bg-slate-100 text-slate-500 border-slate-200'
                        }`}>
                            {m.type.replace('Sector', '').trim()}
                        </span>
                    </Paper>
                ))}

                {movements.length === 0 && !loading && (
                    <Box className="w-full text-center text-slate-400 text-sm italic flex items-center justify-center">
                        <BoltIcon className="text-amber-400 mr-2" />
                        {isZh ? '等待市场信号...' : 'Waiting for market signals...'}
                    </Box>
                )}
            </Box>
        </WidgetContainer>
    );
}
