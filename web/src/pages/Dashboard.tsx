import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
    Box,
    Typography,
    Chip,
    IconButton,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import GridLayout from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

import type { WidgetConfig } from '../widgets/types';
import { getWidgetComponent } from '../widgets/registry';

// Fixed layout with widgets (compact view)
const DEFAULT_WIDGETS: WidgetConfig[] = [
    // Row 0: Header - Market Overview (compact)
    { id: 'indices', type: 'market_indices', position: { x: 0, y: 0, w: 6, h: 1 } },
    { id: 'sentiment', type: 'market_sentiment', position: { x: 6, y: 0, w: 4, h: 1 } },
    { id: 'stats', type: 'system_stats', position: { x: 10, y: 0, w: 2, h: 1 } },

    // Row 1-3: Main Data - Capital Flow (reduced height, scrollable)
    { id: 'mainflow', type: 'main_capital_flow', position: { x: 0, y: 1, w: 4, h: 3 } },
    { id: 'sectors', type: 'sector_performance', position: { x: 4, y: 1, w: 4, h: 3 } },
    { id: 'northbound', type: 'northbound_flow', position: { x: 8, y: 1, w: 4, h: 3 } },

    // Row 4: Alert Banner (compact)
    { id: 'abnormal', type: 'abnormal_movements', position: { x: 0, y: 4, w: 12, h: 1 } },

    // Row 5-9: Top List (full width)
    { id: 'toplist', type: 'top_list', position: { x: 0, y: 5, w: 12, h: 5 } },
];

export default function DashboardPage() {
    const { t } = useTranslation();
    const [containerWidth, setContainerWidth] = useState(1200);
    const [refreshKey, setRefreshKey] = useState(0);

    // Handle container resize
    useEffect(() => {
        const updateWidth = () => {
            const container = document.getElementById('dashboard-container');
            if (container) {
                setContainerWidth(container.offsetWidth);
            }
        };

        updateWidth();
        window.addEventListener('resize', updateWidth);
        return () => window.removeEventListener('resize', updateWidth);
    }, []);

    // Convert widgets to react-grid-layout format (static layout)
    const layoutItems = DEFAULT_WIDGETS.map((w) => ({
        i: w.id,
        x: w.position.x,
        y: w.position.y,
        w: w.position.w,
        h: w.position.h,
        static: true, // Make all widgets static (non-draggable, non-resizable)
    }));

    // Refresh all data
    const handleRefresh = () => {
        setRefreshKey(prev => prev + 1);
    };

    return (
        <Box id="dashboard-container" className="flex flex-col gap-6 w-full h-full pb-10">
            {/* Header */}
            <Box className="flex justify-between items-center">
                <Box className="flex items-center gap-3">
                    <Typography variant="h5" className="font-extrabold text-slate-800 tracking-tight">
                        {t('dashboard.title')}
                    </Typography>
                    <Chip
                        label={t('common.live')}
                        size="small"
                        color="success"
                        className="h-5 text-[10px] font-bold"
                    />
                </Box>
                <Box className="flex items-center gap-2">
                    <IconButton
                        size="small"
                        onClick={handleRefresh}
                        className="bg-white border border-slate-200 shadow-sm hover:bg-slate-50"
                    >
                        <RefreshIcon fontSize="small" />
                    </IconButton>
                </Box>
            </Box>

            {/* Widget Grid */}
            <Box className="relative">
                <GridLayout
                    className="layout"
                    layout={layoutItems}
                    width={containerWidth}
                    gridConfig={{
                        cols: 12,
                        rowHeight: 70,
                        margin: [12, 12],
                    }}
                    dragConfig={{
                        enabled: false,
                    }}
                    resizeConfig={{
                        enabled: false,
                    }}
                >
                    {DEFAULT_WIDGETS.map((widget) => {
                        const WidgetComponent = getWidgetComponent(widget.type);
                        if (!WidgetComponent) return null;

                        return (
                            <div key={widget.id} className="relative">
                                <WidgetComponent
                                    key={refreshKey}
                                    id={widget.id}
                                    config={widget}
                                    isEditing={false}
                                />
                            </div>
                        );
                    })}
                </GridLayout>
            </Box>
        </Box>
    );
}
