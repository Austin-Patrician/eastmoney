import { useState, useEffect } from 'react';
import { Box, Typography, Skeleton } from '@mui/material';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import TrendingDownIcon from '@mui/icons-material/TrendingDown';
import { useTranslation } from 'react-i18next';
import { fetchDashboardOverview } from '../../api';

interface MarketOverviewData {
    market_overview?: {
        breadth?: {
            up: number;
            down: number;
            flat: number;
            limit_up: number;
            limit_down: number;
        };
        turnover?: {
            total: number;
        };
    };
}

interface MarketPulseCardProps {
    onRefresh?: () => void;
}

export default function MarketPulseCard({ onRefresh }: MarketPulseCardProps) {
    const { i18n } = useTranslation();
    const isZh = i18n.language === 'zh';
    
    // Data State
    const [data, setData] = useState<MarketOverviewData | null>(null);
    const [loading, setLoading] = useState(true);

    const loadData = async (silent: boolean = false) => {
            if (!silent) {
                setLoading(true);
            }
            try {
                const res = await fetchDashboardOverview();
                setData(res);
                onRefresh?.();
            } catch (error) {
                console.error("Failed to load market pulse", error);
            } finally {
                if (!silent) {
                    setLoading(false);
                }
            }
        };

    useEffect(() => {
        loadData();

        const timer = window.setInterval(() => {
            if (document.visibilityState === 'visible') {
                loadData(true);
            }
        }, 15000);

        return () => window.clearInterval(timer);
    }, []);

    if (loading) {
        return <Skeleton width={300} height={40} />;
    }

    const breadth = data?.market_overview?.breadth || { up: 0, down: 0, flat: 0, limit_up: 0, limit_down: 0 };
    const total = (breadth.up + breadth.down + breadth.flat) || 1;
    
    // Calculate percentages for the bar
    const upPct = (breadth.up / total) * 100;
    const downPct = (breadth.down / total) * 100;
    const flatPct = 100 - upPct - downPct;

    return (
        <Box 
            sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: 2,
                bgcolor: 'background.paper',
                px: 2,
                py: 1,
                borderRadius: '12px',
                border: '1px solid',
                borderColor: 'divider',
                boxShadow: '0 2px 4px rgba(0,0,0,0.02)'
            }}
        >
            {/* Bulls (Up) */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <TrendingUpIcon sx={{ fontSize: 18, color: '#ef4444' }} />
                <Typography variant="h6" sx={{ fontWeight: 900, color: '#dc2626', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                    {breadth.up}
                </Typography>
                <Box sx={{ px: 0.5, py: 0, bgcolor: '#fef2f2', color: '#b91c1c', borderRadius: 0.5, border: '1px solid #fecaca' }}>
                    <Typography variant="caption" sx={{ fontWeight: 800, fontSize: '0.6rem' }}>
                        {isZh ? '涨停' : 'L.UP'} {breadth.limit_up}
                    </Typography>
                </Box>
            </Box>

            {/* Sentiment Spectrum Bar (Compact) */}
            <Box sx={{ width: 80, height: 4, display: 'flex', borderRadius: 2, overflow: 'hidden', bgcolor: 'action.hover' }}>
                <Box sx={{ width: `${upPct}%`, bgcolor: '#ef4444' }} />
                <Box sx={{ width: `${flatPct}%`, bgcolor: 'action.disabledBackground' }} />
                <Box sx={{ width: `${downPct}%`, bgcolor: '#22c55e' }} />
            </Box>

            {/* Bears (Down) */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Box sx={{ px: 0.5, py: 0, bgcolor: '#f0fdf4', color: '#15803d', borderRadius: 0.5, border: '1px solid #bbf7d0' }}>
                    <Typography variant="caption" sx={{ fontWeight: 800, fontSize: '0.6rem' }}>
                        {isZh ? '跌停' : 'L.DOWN'} {breadth.limit_down}
                    </Typography>
                </Box>
                <Typography variant="h6" sx={{ fontWeight: 900, color: '#16a34a', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                    {breadth.down}
                </Typography>
                <TrendingDownIcon sx={{ fontSize: 18, color: '#22c55e' }} />
            </Box>
        </Box>
    );
}
