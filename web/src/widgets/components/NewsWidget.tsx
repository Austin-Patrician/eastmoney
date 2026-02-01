/**
 * News Widget
 *
 * Displays financial news feed.
 */

import { Box, Typography, Chip, Tooltip } from '@mui/material';
import ArticleIcon from '@mui/icons-material/Article';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import { useTranslation } from 'react-i18next';
import type{ WidgetProps, NewsData } from '../types';
import WidgetContainer, { useWidgetData } from '../WidgetContainer';
import { fetchWidgetNews } from '../../api';

export default function NewsWidget({ id, config, isEditing }: WidgetProps) {
    const { t, i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    const limit = (config.settings?.limit as number) || 10;

    const { data, loading, error, lastUpdated, refresh } = useWidgetData<NewsData>(
        () => fetchWidgetNews(limit),
        config.refreshInterval ? config.refreshInterval * 1000 : 600000
    );

    const formatRelativeTime = (datetime: string) => {
        if (!datetime) return '';
        try {
            const date = new Date(datetime);
            const now = new Date();
            const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

            if (diffInSeconds < 60) {
                return isZh ? '刚刚' : 'Just now';
            }
            const diffInMinutes = Math.floor(diffInSeconds / 60);
            if (diffInMinutes < 60) {
                return isZh ? `${diffInMinutes}分钟前` : `${diffInMinutes}m ago`;
            }
            const diffInHours = Math.floor(diffInMinutes / 60);
            if (diffInHours < 24) {
                return isZh ? `${diffInHours}小时前` : `${diffInHours}h ago`;
            }
            const diffInDays = Math.floor(diffInHours / 24);
            if (diffInDays < 7) {
                 return isZh ? `${diffInDays}天前` : `${diffInDays}d ago`;
            }
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        } catch {
            return '';
        }
    };

    const getSourceColor = (source: string) => {
        const s = source.toLowerCase();
        if (s.includes('sina') || s.includes('新浪')) return 'error';
        if (s.includes('east') || s.includes('东财')) return 'warning';
        if (s.includes('cls') || s.includes('财联社')) return 'info';
        return 'default';
    };

    return (
        <WidgetContainer
            config={config}
            loading={loading}
            error={error || data?.error}
            onRefresh={refresh}
            lastUpdated={lastUpdated || undefined}
        >
            <Box className="h-full overflow-auto pr-1">
                <Box className="flex flex-col gap-3 p-1">
                    {data?.news?.map((item, idx) => (
                        <Box
                            key={`${item.datetime}-${idx}`}
                            className="group p-3 rounded-lg border border-slate-100 bg-white hover:bg-slate-50 hover:shadow-sm transition-all duration-200 cursor-default"
                        >
                            <Box className="flex flex-col gap-1.5">
                                <Box className="flex items-start justify-between gap-2">
                                    <Typography
                                        variant="subtitle2"
                                        className="font-bold text-slate-800 leading-snug line-clamp-2 group-hover:text-blue-700 transition-colors"
                                    >
                                        {item.title}
                                    </Typography>
                                </Box>
                                
                                {item.content && (
                                    <Typography
                                        variant="body2"
                                        className="text-slate-600 text-xs leading-relaxed line-clamp-3"
                                    >
                                        {item.content}
                                    </Typography>
                                )}

                                <Box className="flex items-center justify-between mt-1">
                                    <Box className="flex items-center gap-2">
                                        {item.source && (
                                            <Chip 
                                                label={item.source} 
                                                size="small" 
                                                variant="outlined"
                                                color={getSourceColor(item.source)}
                                                className="h-5 text-[10px] font-medium border-slate-200"
                                            />
                                        )}
                                        <Box className="flex items-center gap-1 text-slate-400">
                                            <AccessTimeIcon style={{ fontSize: 12 }} />
                                            <Tooltip title={item.datetime} placement="top" arrow>
                                                <Typography variant="caption" className="text-[10px] font-medium">
                                                    {formatRelativeTime(item.datetime)}
                                                </Typography>
                                            </Tooltip>
                                        </Box>
                                    </Box>
                                </Box>
                            </Box>
                        </Box>
                    ))}
                </Box>

                {(!data?.news || data.news.length === 0) && !loading && (
                    <Box className="h-full flex flex-col items-center justify-center text-slate-400 gap-2">
                        <ArticleIcon fontSize="large" className="opacity-20" />
                        <Typography variant="body2">
                            {isZh ? '暂无新闻' : 'No news available'}
                        </Typography>
                    </Box>
                )}
            </Box>
        </WidgetContainer>
    );
}
