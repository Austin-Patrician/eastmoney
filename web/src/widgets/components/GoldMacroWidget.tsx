/**
 * Gold & Macro Widget
 *
 * Displays gold price and DXY index.
 */

import { Box, Typography } from '@mui/material';
import PublicIcon from '@mui/icons-material/Public';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchDashboardOverview } from '../../api';

interface GoldMacroData {
    gold_macro?: {
        price: number;
        change_pct: number;
        dxy: number;
    };
}

export default function GoldMacroWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<GoldMacroData>(
        fetchDashboardOverview,
        config.refreshInterval ? config.refreshInterval * 1000 : 300000
    );

    const gold = data?.gold_macro;

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full flex flex-col justify-center relative overflow-hidden">
                <PublicIcon className="absolute -right-6 -bottom-8 text-amber-500 opacity-10 text-[100px]" />
                <Box className="relative z-10">
                    <Box className="flex justify-between items-center mb-1">
                        <Typography variant="caption" className="text-slate-400 font-bold uppercase tracking-wider">
                            {isZh ? '黄金' : 'Gold'}
                        </Typography>
                        <Typography variant="caption" className="text-amber-600 font-bold bg-amber-50 px-1 rounded">
                            XAU
                        </Typography>
                    </Box>
                    <Typography variant="h4" className="font-mono font-bold text-slate-800 tracking-tight">
                        ${gold?.price || 0}
                    </Typography>
                    <Box className="flex items-center gap-2 mt-1">
                        <span className={`text-xs font-bold ${(gold?.change_pct || 0) >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                            {(gold?.change_pct || 0) >= 0 ? '+' : ''}{gold?.change_pct || 0}%
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono font-bold bg-slate-50 px-1 rounded border border-slate-100">
                            DXY {gold?.dxy || 0}
                        </span>
                    </Box>
                </Box>
            </Box>
        </WidgetContainer>
    );
}
