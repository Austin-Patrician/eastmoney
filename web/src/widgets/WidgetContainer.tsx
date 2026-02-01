/**
 * Widget Container Component
 *
 * Wraps individual widgets with common functionality:
 * - Loading state
 * - Error handling
 * - Refresh button
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import type { ReactNode } from 'react';
import { Box, Paper, Typography, IconButton, CircularProgress, Tooltip, Fade } from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTranslation } from 'react-i18next';
import type { WidgetConfig } from './types';
import { getWidgetDefinition } from './registry';

interface WidgetContainerProps {
    config: WidgetConfig;
    children: ReactNode;
    loading?: boolean;
    error?: string | null;
    onRefresh?: () => void;
    lastUpdated?: string;
}

export default function WidgetContainer({
    config,
    children,
    loading = false,
    error = null,
    onRefresh,
    lastUpdated,
}: WidgetContainerProps) {
    const { t, i18n } = useTranslation();
    const definition = getWidgetDefinition(config.type);
    const isZh = i18n.language === 'zh';

    const title = config.title || (isZh ? definition?.name : definition?.nameEn) || config.type;

    return (
        <Paper
            elevation={0}
            className="group h-full flex flex-col bg-white overflow-hidden transition-all duration-200 border border-slate-200 hover:shadow-md hover:border-slate-300"
            sx={{ borderRadius: 3 }}
        >
            {/* Header */}
            <Box className="flex justify-between items-center px-3 py-2 border-b border-slate-50 min-h-[36px]">
                <Box className="flex items-center gap-2 overflow-hidden">
                    <Typography
                        variant="caption"
                        className="font-bold text-slate-400 uppercase tracking-wider text-[10px] truncate select-none"
                    >
                        {title}
                    </Typography>
                    {definition?.pointsRequired && definition.pointsRequired > 0 && (
                        <span className="text-[9px] px-1 py-0.5 bg-amber-50 text-amber-600 rounded font-mono border border-amber-100">
                            PRO
                        </span>
                    )}
                </Box>

                <Box className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                    {loading && <CircularProgress size={10} className="text-slate-400 mr-1 opacity-100" />}

                    {!loading && lastUpdated && (
                        <Tooltip title={`Updated: ${new Date(lastUpdated).toLocaleTimeString()}`}>
                            <Box className="w-1.5 h-1.5 rounded-full bg-green-400 mr-1" />
                        </Tooltip>
                    )}

                    {onRefresh && !loading && (
                        <IconButton
                            size="small"
                            onClick={(e) => { e.stopPropagation(); onRefresh(); }}
                            className="w-6 h-6 text-slate-300 hover:text-slate-600 hover:bg-slate-50"
                        >
                            <RefreshIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                    )}
                </Box>
            </Box>

            {/* Content */}
            <Box className="flex-1 overflow-auto p-3 relative">
                {error ? (
                    <Fade in>
                        <Box className="h-full flex flex-col items-center justify-center text-center p-2">
                            <Typography variant="caption" className="text-red-500 font-medium mb-1">
                                {isZh ? '数据加载失败' : 'Failed to load'}
                            </Typography>
                            <Typography variant="caption" className="text-slate-400 text-[10px] line-clamp-2">
                                {error}
                            </Typography>
                            {onRefresh && (
                                <IconButton size="small" onClick={onRefresh} className="mt-2 text-slate-400">
                                    <RefreshIcon fontSize="small" />
                                </IconButton>
                            )}
                        </Box>
                    </Fade>
                ) : loading && !children ? (
                    <Box className="h-full flex items-center justify-center">
                        <CircularProgress size={20} className="text-indigo-500 opacity-50" thickness={4} />
                    </Box>
                ) : (
                    children
                )}
            </Box>
        </Paper>
    );
}

// Hook for widget data fetching with auto-refresh
export function useWidgetData<T>(
    fetchFn: () => Promise<T>,
    refreshInterval: number = 60000,
    enabled: boolean = true
) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<string | null>(null);

    // Use ref to store fetchFn to avoid re-creating fetchData on every render
    const fetchFnRef = useRef(fetchFn);
    // Track initialization to avoid loading spinners on auto-refresh
    const initialized = useRef(false);

    // Update ref when fetchFn changes
    useEffect(() => {
        fetchFnRef.current = fetchFn;
    }, [fetchFn]);

    const fetchData = useCallback(async (isAutoRefresh = false) => {
        if (!enabled) return;

        try {
            // Only set loading true if it's the first load or explicit refresh (not auto-refresh)
            if (!initialized.current && !isAutoRefresh) {
                setLoading(true);
            }
            
            setError(null);
            const result = await fetchFnRef.current();
            setData(result);
            setLastUpdated(new Date().toISOString());
            initialized.current = true;
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to fetch data');
        } finally {
            setLoading(false);
        }
    }, [enabled]);

    useEffect(() => {
        fetchData(false); // Initial load

        if (refreshInterval > 0 && enabled) {
            const interval = setInterval(() => fetchData(true), refreshInterval);
            return () => clearInterval(interval);
        }
    }, [fetchData, refreshInterval, enabled]);

    return { data, loading, error, lastUpdated, refresh: () => fetchData(false) };
}
