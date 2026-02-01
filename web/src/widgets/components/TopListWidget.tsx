/**
 * Top List Widget (Dragon Tiger List)
 *
 * Displays stocks on the Dragon Tiger list.
 */

import { Box, Typography, Chip } from '@mui/material';
import EmojiEventsIcon from '@mui/icons-material/EmojiEvents';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, TopListData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetTopList } from '../../api';

export default function TopListWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    const limit = (config.settings?.limit as number) || 20;

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<TopListData>(
        () => fetchWidgetTopList(limit),
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
            <Box className="h-full flex flex-col">
                {data?.trade_date && (
                    <Box className="flex items-center gap-2 mb-3">
                        <EmojiEventsIcon className="text-amber-500" fontSize="small" />
                        <Typography variant="caption" className="text-slate-500">
                            {isZh ? '交易日' : 'Trade Date'}: {data.trade_date}
                        </Typography>
                    </Box>
                )}

                <Box className="flex-1 overflow-auto">
                    <table className="w-full text-sm">
                        <thead className="text-slate-400 text-[11px] uppercase tracking-wider border-b border-slate-100">
                            <tr>
                                <th className="text-left py-2 font-bold">{isZh ? '代码' : 'Code'}</th>
                                <th className="text-left py-2 font-bold">{isZh ? '名称' : 'Name'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '涨跌' : 'Chg%'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '净买' : 'Net'}</th>
                                <th className="text-right py-2 font-bold">{isZh ? '换手' : 'T/O'}</th>
                                <th className="text-left py-2 font-bold pl-2">{isZh ? '原因' : 'Reason'}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-50">
                            {data?.data?.map((item) => (
                                <tr key={item.code} className="hover:bg-amber-50/30 transition-colors">
                                    <td className="py-2 font-mono text-slate-500 text-xs">{item.code}</td>
                                    <td className="py-2 font-medium text-slate-700 truncate max-w-[80px]" title={item.name}>{item.name}</td>
                                    <td className={`py-2 text-right font-bold ${item.change_pct >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.change_pct >= 0 ? '+' : ''}{item.change_pct?.toFixed(2)}%
                                    </td>
                                    <td className={`py-2 text-right font-mono ${item.net_amount >= 0 ? 'text-red-600' : 'text-green-600'}`}>
                                        {item.net_amount > 0 ? '+' : ''}{item.net_amount}
                                    </td>
                                    <td className="py-2 text-right font-mono text-slate-600">
                                        {item.turnover_rate?.toFixed(1)}%
                                    </td>
                                    <td className="py-2 pl-2">
                                        <Chip
                                            label={item.reason?.slice(0, 8) || '-'}
                                            size="small"
                                            title={item.reason}
                                            className="h-5 text-[10px] bg-amber-50 text-amber-700 max-w-[100px]"
                                        />
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {(!data?.data || data.data.length === 0) && !loading && (
                        <Box className="py-8 text-center text-slate-400">
                            {isZh ? '暂无龙虎榜数据' : 'No dragon tiger list data'}
                        </Box>
                    )}
                </Box>
            </Box>
        </WidgetContainer>
    );
}
