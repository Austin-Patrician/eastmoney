import React, { useEffect, useRef, useMemo } from 'react';
import { Box, Paper, Typography, useTheme, alpha, Tooltip } from '@mui/material';
import * as echarts from 'echarts';
import { useTranslation } from 'react-i18next';

// Limit max items to prevent memory exhaustion with large portfolios
const MAX_HEATMAP_ITEMS = 10;

interface CorrelationDataPoint {
  x: number;
  y: number;
  value: number;
  row_code: string;
  col_code: string;
  row_name: string;
  col_name: string;
}

interface CorrelationHeatmapProps {
  data: CorrelationDataPoint[];
  labels: string[];
  codes: string[];
  size: number;
  diversificationScore?: number;
  diversificationStatus?: string;
  onCellClick?: (rowCode: string, colCode: string, correlation: number) => void;
  loading?: boolean;
  height?: number;
}

const CorrelationHeatmap: React.FC<CorrelationHeatmapProps> = ({
  data,
  labels,
  codes,
  size,
  diversificationScore = 0,
  diversificationStatus = 'unknown',
  onCellClick,
  loading = false,
  height = 400,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const chartRef = useRef<HTMLDivElement>(null);
  const chartInstance = useRef<echarts.ECharts | null>(null);

  // Truncate data to prevent memory exhaustion with large portfolios
  const { truncatedData, truncatedLabels, truncatedCodes, isTruncated } = useMemo(() => {
    const actualSize = Math.min(size, MAX_HEATMAP_ITEMS);
    const isTruncated = size > MAX_HEATMAP_ITEMS;

    if (!isTruncated) {
      return {
        truncatedData: data,
        truncatedLabels: labels,
        truncatedCodes: codes,
        isTruncated: false,
      };
    }

    // Filter data to only include points within the truncated range
    const filteredData = data.filter(d => d.x < actualSize && d.y < actualSize);

    return {
      truncatedData: filteredData,
      truncatedLabels: labels.slice(0, actualSize),
      truncatedCodes: codes.slice(0, actualSize),
      isTruncated: true,
    };
  }, [data, labels, codes, size]);

  useEffect(() => {
    if (!chartRef.current || loading || truncatedData.length === 0) return;

    // Initialize or get existing chart instance
    if (!chartInstance.current) {
      chartInstance.current = echarts.init(chartRef.current, theme.palette.mode);
    }

    const chart = chartInstance.current;

    // Transform data for ECharts
    const chartData = truncatedData.map((d) => [d.x, d.y, d.value]);
    const effectiveSize = truncatedLabels.length;

    const option: echarts.EChartsOption = {
      tooltip: {
        position: 'top',
        formatter: (params: any) => {
          const dataIndex = params.dataIndex;
          const point = truncatedData[dataIndex];
          if (!point) return '';

          const value = point.value;
          let colorClass = '';
          let interpretation = '';

          if (value >= 0.8) {
            colorClass = 'color: #ff4d4f';
            interpretation = t('portfolio.highCorrelation', '高度正相关 - 同质化风险');
          } else if (value >= 0.5) {
            colorClass = 'color: #faad14';
            interpretation = t('portfolio.moderateCorrelation', '中度正相关');
          } else if (value >= -0.2) {
            colorClass = 'color: #8c8c8c';
            interpretation = t('portfolio.lowCorrelation', '低相关 - 有效分散');
          } else if (value >= -0.5) {
            colorClass = 'color: #52c41a';
            interpretation = t('portfolio.negativeCorrelation', '负相关 - 对冲效果');
          } else {
            colorClass = 'color: #1890ff';
            interpretation = t('portfolio.strongNegative', '强负相关 - 对冲保护');
          }

          return `
            <div style="padding: 8px;">
              <div style="font-weight: 600; margin-bottom: 4px;">
                ${point.row_name} vs ${point.col_name}
              </div>
              <div style="${colorClass}; font-size: 1.2em; font-weight: 700;">
                ${value.toFixed(3)}
              </div>
              <div style="color: #8c8c8c; font-size: 0.85em; margin-top: 4px;">
                ${interpretation}
              </div>
            </div>
          `;
        },
      },
      grid: {
        left: '15%',
        right: '10%',
        top: '10%',
        bottom: '15%',
      },
      xAxis: {
        type: 'category',
        data: truncatedLabels,
        splitArea: { show: true },
        axisLabel: {
          color: theme.palette.text.secondary,
          fontSize: 10,
          rotate: 45,
          interval: 0,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'category',
        data: truncatedLabels,
        splitArea: { show: true },
        axisLabel: {
          color: theme.palette.text.secondary,
          fontSize: 10,
          interval: 0,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'vertical',
        right: '2%',
        top: 'center',
        itemHeight: 150,
        inRange: {
          color: [
            '#1890ff',  // Strong negative: blue
            '#52c41a',  // Negative: green
            '#d9d9d9',  // Neutral: gray
            '#faad14',  // Moderate positive: yellow
            '#ff4d4f',  // Strong positive: red
          ],
        },
        textStyle: {
          color: theme.palette.text.secondary,
        },
      },
      series: [
        {
          name: 'Correlation',
          type: 'heatmap',
          data: chartData,
          label: {
            show: effectiveSize <= 8,
            formatter: (params: any) => {
              const val = params.value[2];
              return val.toFixed(2);
            },
            fontSize: 9,
            color: theme.palette.text.primary,
          },
          emphasis: {
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
            },
          },
        },
      ],
    };

    chart.setOption(option);

    // Handle click events
    chart.off('click');
    if (onCellClick) {
      chart.on('click', (params: any) => {
        const dataIndex = params.dataIndex;
        const point = truncatedData[dataIndex];
        if (point) {
          onCellClick(point.row_code, point.col_code, point.value);
        }
      });
    }

    // Handle resize
    const handleResize = () => {
      chart.resize();
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [truncatedData, truncatedLabels, theme, onCellClick, loading, t]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (chartInstance.current) {
        chartInstance.current.dispose();
        chartInstance.current = null;
      }
    };
  }, []);

  const getStatusColor = () => {
    switch (diversificationStatus) {
      case 'excellent': return theme.palette.success.main;
      case 'good': return theme.palette.success.light;
      case 'fair': return theme.palette.warning.main;
      case 'poor': return theme.palette.error.light;
      case 'critical': return theme.palette.error.main;
      default: return theme.palette.grey[500];
    }
  };

  const getStatusLabel = () => {
    switch (diversificationStatus) {
      case 'excellent': return t('portfolio.excellentDiversification', '优秀分散');
      case 'good': return t('portfolio.goodDiversification', '良好分散');
      case 'fair': return t('portfolio.fairDiversification', '一般分散');
      case 'poor': return t('portfolio.poorDiversification', '分散不足');
      case 'critical': return t('portfolio.criticalDiversification', '高度集中');
      default: return '--';
    }
  };

  if (loading) {
    return (
      <Box
        sx={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography color="text.secondary">
          {t('portfolio.loadingCorrelation', '加载相关性数据...')}
        </Typography>
      </Box>
    );
  }

  if (data.length === 0) {
    return (
      <Box
        sx={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography color="text.secondary">
          {t('portfolio.noCorrelationData', '需要至少2个持仓才能计算相关性')}
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {/* Diversification Score Header */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          mb: 2,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Typography variant="subtitle2" color="text.secondary">
            {t('portfolio.correlationMatrix', '相关性矩阵')}
          </Typography>
          {isTruncated && (
            <Typography variant="caption" color="warning.main">
              ({t('portfolio.showingTop', '仅显示前{{count}}个', { count: MAX_HEATMAP_ITEMS })})
            </Typography>
          )}
        </Box>
        <Tooltip title={t('portfolio.diversificationTooltip', '分散化评分基于持仓间的平均相关性，越低表示分散效果越好')}>
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              px: 1.5,
              py: 0.5,
              bgcolor: alpha(getStatusColor(), 0.1),
              borderRadius: 2,
            }}
          >
            <Typography variant="caption" color="text.secondary">
              {t('portfolio.diversification', '分散度')}:
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{ color: getStatusColor() }}
            >
              {diversificationScore.toFixed(0)}
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: getStatusColor() }}
            >
              ({getStatusLabel()})
            </Typography>
          </Box>
        </Tooltip>
      </Box>

      {/* Heatmap Chart */}
      <Box
        ref={chartRef}
        sx={{
          width: '100%',
          height,
        }}
      />

      {/* Legend explanation */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          gap: 3,
          mt: 2,
          flexWrap: 'wrap',
        }}
      >
        {[
          { color: '#ff4d4f', label: t('portfolio.highPositive', '高正相关 (风险)'), range: '0.8~1.0' },
          { color: '#d9d9d9', label: t('portfolio.uncorrelated', '不相关 (分散)'), range: '-0.2~0.2' },
          { color: '#52c41a', label: t('portfolio.negative', '负相关 (对冲)'), range: '-0.8~-1.0' },
        ].map((item) => (
          <Box key={item.label} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <Box
              sx={{
                width: 12,
                height: 12,
                bgcolor: item.color,
                borderRadius: 0.5,
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {item.label}
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};

export default CorrelationHeatmap;
