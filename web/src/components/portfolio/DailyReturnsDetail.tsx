import React, { useState } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  Chip,
  useTheme,
  alpha,
  ToggleButton,
  ToggleButtonGroup,
  Button,
  IconButton,
  Tooltip,
  Collapse,
} from '@mui/material';
import {
  AccountBalance,
  ShowChart,
  ViewList,
  ViewModule,
  AutoAwesome,
  ContentCopy,
  Refresh,
  ExpandMore,
  ExpandLess,
} from '@mui/icons-material';
import {
  Treemap,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
} from 'recharts';
import { useTranslation } from 'react-i18next';
import type { DailyReturnsDetail as DailyReturnsDetailType, DailyPositionReturn, ReturnsExplanation } from '../../api';

interface DailyReturnsDetailProps {
  data: DailyReturnsDetailType | null;
  loading?: boolean;
  // AI Explanation props
  explanationData?: ReturnsExplanation | null;
  explanationLoading?: boolean;
  onGenerateExplanation?: () => void;
  onRefreshExplanation?: () => void;
}

type SortField = 'asset_name' | 'position_pnl' | 'nav_change_pct' | 'contribution_pct' | 'weight_pct';
type SortOrder = 'asc' | 'desc';

// Custom content component for Treemap with softer colors
const TreemapContent = (props: any) => {
  const { x, y, width, height, name, payload } = props;
  if (!width || !height || width <= 0 || height <= 0) return null;

  const pnl = props.pnl || (payload && payload.pnl);
  const returnPct = props.returnPct || (payload && payload.returnPct);

  const pnlValue = pnl ?? 0;
  const isPositive = pnlValue >= 0;
  
  // Softer colors: Red (Rise) #ef5350, Green (Fall) #66bb6a
  // Opacity based on return magnitude (capped at 5% for max opacity)
  const opacity = 0.5 + Math.min(Math.abs(returnPct || 0) / 5, 0.5);
  
  const fill = isPositive 
    ? `rgba(239, 83, 80, ${opacity})`   // Red
    : `rgba(102, 187, 106, ${opacity})`; // Green

  const showName = width > 40 && height > 30;
  const showPnl = width > 40 && height > 50;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={fill}
        stroke="#fff"
        strokeWidth={1}
        rx={4}
        ry={4}
      />
      {showName && (
        <text
          x={x + width / 2}
          y={y + height / 2 - (showPnl ? 7 : 0)}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#fff"
          fontSize={12}
          fontWeight={500}
          style={{ pointerEvents: 'none' }}
        >
          {name && name.length > 4 ? name.substring(0, 4) : name}
        </text>
      )}
      {showPnl && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 9}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="rgba(255,255,255,0.9)"
          fontSize={11}
          style={{ pointerEvents: 'none' }}
        >
          {pnlValue >= 0 ? '+' : ''}{pnlValue.toFixed(0)}
        </text>
      )}
    </g>
  );
};

const DailyReturnsDetail: React.FC<DailyReturnsDetailProps> = ({
  data,
  loading = false,
  explanationData,
  explanationLoading = false,
  onGenerateExplanation,
  onRefreshExplanation,
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [sortField, setSortField] = useState<SortField>('position_pnl');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [viewMode, setViewMode] = useState<'table' | 'chart'>('table');
  const [showExplanation, setShowExplanation] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (explanationData?.explanation) {
      navigator.clipboard.writeText(explanationData.explanation);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  };

  const sortedPositions = React.useMemo(() => {
    if (!data?.positions) return [];
    return [...data.positions].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortOrder === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortOrder === 'asc'
        ? (aVal as number) - (bVal as number)
        : (bVal as number) - (aVal as number);
    });
  }, [data?.positions, sortField, sortOrder]);

  if (loading) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 200,
          background: alpha(theme.palette.background.paper, 0.8),
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          borderRadius: 3,
        }}
      >
        <Box sx={{ textAlign: 'center' }}>
          <CircularProgress size={32} sx={{ mb: 1 }} />
          <Typography color="text.secondary">
            {t('portfolio.loadingDailyDetail', '加载当日明细...')}
          </Typography>
        </Box>
      </Paper>
    );
  }

  if (!data || data.positions.length === 0) {
    return (
      <Paper
        elevation={0}
        sx={{
          p: 3,
          textAlign: 'center',
          background: alpha(theme.palette.background.paper, 0.8),
          border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
          borderRadius: 3,
        }}
      >
        <Typography color="text.secondary">
          {t('portfolio.noDailyData', '暂无当日收益数据')}
        </Typography>
      </Paper>
    );
  }

  const renderContributionBar = (position: DailyPositionReturn) => {
    const maxContrib = Math.max(...data.positions.map(p => Math.abs(p.contribution_pct)));
    const width = maxContrib > 0 ? (Math.abs(position.contribution_pct) / maxContrib) * 100 : 0;
    const pnl = position.position_pnl ?? 0;
    const color = pnl >= 0 ? theme.palette.success.main : theme.palette.error.main;

    return (
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, minWidth: 120 }}>
        <Box
          sx={{
            height: 6,
            width: `${width}%`,
            bgcolor: alpha(color, 0.6),
            borderRadius: 1,
            minWidth: 2,
          }}
        />
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'JetBrains Mono, monospace',
            color: pnl >= 0 ? 'success.main' : 'error.main',
          }}
        >
          {position.contribution_pct.toFixed(1)}%
        </Typography>
      </Box>
    );
  };

  return (
    <Paper
      elevation={0}
      sx={{
        background: alpha(theme.palette.background.paper, 0.8),
        border: `1px solid ${alpha(theme.palette.divider, 0.1)}`,
        borderRadius: 3,
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box sx={{ p: 2, borderBottom: `1px solid ${theme.palette.divider}`, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 3 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ShowChart sx={{ fontSize: 20, color: 'primary.main' }} />
            <Typography variant="subtitle1" fontWeight={600}>
              {t('portfolio.dailyReturnsDetail', '当日收益明细')}
            </Typography>
            <Chip size="small" label={data.date} sx={{ fontSize: '0.7rem' }} />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Typography
              variant="h6"
              fontWeight={700}
              sx={{
                color: data.total_pnl >= 0 ? 'success.main' : 'error.main',
                fontFamily: 'JetBrains Mono, monospace',
              }}
            >
              {data.total_pnl >= 0 ? '+' : ''}¥{data.total_pnl.toFixed(2)}
            </Typography>
            <Chip
              size="small"
              label={`${data.total_pnl_pct >= 0 ? '+' : ''}${data.total_pnl_pct.toFixed(2)}%`}
              sx={{
                bgcolor: alpha(data.total_pnl >= 0 ? theme.palette.success.main : theme.palette.error.main, 0.1),
                color: data.total_pnl >= 0 ? 'success.main' : 'error.main',
                fontWeight: 600,
              }}
            />
          </Box>
        </Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          {/* AI Explanation Button */}
          {onGenerateExplanation && (
            <Button
              size="small"
              variant={showExplanation || explanationData ? 'contained' : 'outlined'}
              color="warning"
              startIcon={explanationLoading ? <CircularProgress size={14} color="inherit" /> : <AutoAwesome sx={{ fontSize: 16 }} />}
              endIcon={showExplanation ? <ExpandLess /> : <ExpandMore />}
              onClick={() => {
                if (!explanationData && !explanationLoading) {
                  onGenerateExplanation();
                }
                setShowExplanation(!showExplanation);
              }}
              disabled={explanationLoading}
              sx={{ textTransform: 'none', mr: 1 }}
            >
              {t('portfolio.aiExplanation', 'AI 解读')}
            </Button>
          )}
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={(_, newView) => {
              if (newView) setViewMode(newView);
            }}
            size="small"
          >
            <ToggleButton value="table" aria-label="table view">
              <ViewList fontSize="small" />
            </ToggleButton>
            <ToggleButton value="chart" aria-label="chart view">
              <ViewModule fontSize="small" />
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
      </Box>

      {/* AI Explanation Panel */}
      <Collapse in={showExplanation}>
        <Box
          sx={{
            p: 2,
            bgcolor: alpha(theme.palette.warning.main, 0.03),
            borderBottom: `1px solid ${alpha(theme.palette.warning.main, 0.2)}`,
          }}
        >
          {explanationLoading ? (
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', py: 3 }}>
              <Box sx={{ textAlign: 'center' }}>
                <CircularProgress size={24} sx={{ mb: 1, color: 'warning.main' }} />
                <Typography variant="body2" color="text.secondary">
                  {t('portfolio.generatingExplanation', 'AI 正在分析您的收益情况...')}
                </Typography>
              </Box>
            </Box>
          ) : explanationData ? (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <AutoAwesome sx={{ fontSize: 16, color: 'warning.main' }} />
                  <Typography variant="body2" fontWeight={600} color="warning.main">
                    {t('portfolio.aiAnalysis', 'AI 分析')}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <Tooltip title={copied ? t('common.copied', '已复制') : t('common.copy', '复制')}>
                    <IconButton size="small" onClick={handleCopy}>
                      <ContentCopy sx={{ fontSize: 14 }} />
                    </IconButton>
                  </Tooltip>
                  {onRefreshExplanation && (
                    <Tooltip title={t('portfolio.regenerate', '重新生成')}>
                      <IconButton size="small" onClick={onRefreshExplanation}>
                        <Refresh sx={{ fontSize: 14 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              </Box>
              <Typography
                variant="body2"
                sx={{
                  lineHeight: 1.8,
                  whiteSpace: 'pre-wrap',
                  color: 'text.primary',
                }}
              >
                {explanationData.explanation}
              </Typography>
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{ display: 'block', mt: 1, textAlign: 'right' }}
              >
                {t('portfolio.generatedAt', '生成于')} {new Date(explanationData.generated_at).toLocaleString()}
              </Typography>
            </Box>
          ) : (
            <Box sx={{ textAlign: 'center', py: 2 }}>
              <Typography variant="body2" color="text.secondary">
                {t('portfolio.clickToGenerate', '点击"AI 解读"按钮让 AI 分析您的今日收益表现')}
              </Typography>
            </Box>
          )}
        </Box>
      </Collapse>

      {viewMode === 'chart' ? (
        <Box sx={{ width: '100%', height: 400, p: 2 }}>
          <Box sx={{ width: '100%', height: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <Treemap
                data={data.positions
                  .filter(p => !p.is_pending && p.position_pnl != null)
                  .map(p => ({
                    name: p.asset_name,
                    code: p.asset_code,
                    size: Math.abs(p.position_pnl!) || 0.01,
                    returnPct: p.nav_change_pct ?? 0,
                    pnl: p.position_pnl,
                  }))}
                dataKey="size"
                stroke="#fff"
              content={<TreemapContent />}
            >
                <RechartsTooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const item = payload[0].payload;
                      if (!item.code) return null;
                      return (
                        <Box sx={{ bgcolor: 'background.paper', p: 1.5, border: '1px solid', borderColor: 'divider', borderRadius: 1, boxShadow: 3 }}>
                          <Typography variant="subtitle2" fontWeight={600}>{item.name}</Typography>
                          <Typography variant="caption" display="block" color="text.secondary" gutterBottom>{item.code}</Typography>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 0.5 }}>
                            <Typography variant="body2" color="text.secondary">{t('portfolio.navChange')}</Typography>
                            <Typography variant="body2" fontWeight={600} color={item.returnPct >= 0 ? 'error.main' : 'success.main'}>
                              {item.returnPct >= 0 ? '+' : ''}{item.returnPct.toFixed(2)}%
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 0.5 }}>
                            <Typography variant="body2" color="text.secondary">{t('portfolio.positionPnl')}</Typography>
                            <Typography variant="body2" fontWeight={600} color={item.pnl >= 0 ? 'error.main' : 'success.main'}>
                              {item.pnl >= 0 ? '+' : ''}¥{item.pnl.toFixed(2)}
                            </Typography>
                          </Box>
                          <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2 }}>
                            <Typography variant="body2" color="text.secondary">{t('portfolio.weight')}</Typography>
                            <Typography variant="body2" fontWeight={600}>
                              {item.size.toFixed(2)}%
                            </Typography>
                          </Box>
                        </Box>
                      );
                    }
                    return null;
                  }}
                />
              </Treemap>
            </ResponsiveContainer>
          </Box>
        </Box>
      ) : (
      <TableContainer sx={{ maxHeight: 400 }}>
        <Table stickyHeader size="small">
          <TableHead>
            <TableRow>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                <TableSortLabel
                  active={sortField === 'asset_name'}
                  direction={sortField === 'asset_name' ? sortOrder : 'asc'}
                  onClick={() => handleSort('asset_name')}
                >
                  {t('portfolio.asset', '资产')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                {t('portfolio.yesterdayNav', '昨日净值')}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                {t('portfolio.todayNav', '今日净值')}
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                <TableSortLabel
                  active={sortField === 'nav_change_pct'}
                  direction={sortField === 'nav_change_pct' ? sortOrder : 'asc'}
                  onClick={() => handleSort('nav_change_pct')}
                >
                  {t('portfolio.navChange', '涨跌幅')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                <TableSortLabel
                  active={sortField === 'position_pnl'}
                  direction={sortField === 'position_pnl' ? sortOrder : 'asc'}
                  onClick={() => handleSort('position_pnl')}
                >
                  {t('portfolio.positionPnl', '持仓盈亏')}
                </TableSortLabel>
              </TableCell>
              <TableCell sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                <TableSortLabel
                  active={sortField === 'contribution_pct'}
                  direction={sortField === 'contribution_pct' ? sortOrder : 'asc'}
                  onClick={() => handleSort('contribution_pct')}
                >
                  {t('portfolio.contribution', '贡献度')}
                </TableSortLabel>
              </TableCell>
              <TableCell align="right" sx={{ fontWeight: 600, bgcolor: 'background.paper' }}>
                <TableSortLabel
                  active={sortField === 'weight_pct'}
                  direction={sortField === 'weight_pct' ? sortOrder : 'asc'}
                  onClick={() => handleSort('weight_pct')}
                >
                  {t('portfolio.weight', '权重')}
                </TableSortLabel>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {sortedPositions.map((position) => (
              <TableRow
                key={position.position_id}
                hover
                sx={{
                  '&:last-child td, &:last-child th': { border: 0 },
                  ...(position.is_pending && {
                    bgcolor: alpha(theme.palette.warning.main, 0.03),
                  }),
                }}
              >
                <TableCell>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {position.asset_type === 'fund' ? (
                      <AccountBalance sx={{ fontSize: 16, color: 'primary.main' }} />
                    ) : (
                      <ShowChart sx={{ fontSize: 16, color: 'secondary.main' }} />
                    )}
                    <Box>
                      <Typography variant="body2" fontWeight={500}>
                        {position.asset_name}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {position.asset_code}
                      </Typography>
                    </Box>
                  </Box>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" sx={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {position.yesterday_nav != null ? `¥${position.yesterday_nav.toFixed(4)}` : '--'}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  {position.is_pending ? (
                    <Chip
                      size="small"
                      label={t('portfolio.pendingUpdate', '待更新')}
                      sx={{
                        height: 20,
                        fontSize: '0.7rem',
                        bgcolor: alpha(theme.palette.warning.main, 0.1),
                        color: 'warning.main',
                        fontWeight: 500,
                      }}
                    />
                  ) : (
                    <Typography variant="body2" sx={{ fontFamily: 'JetBrains Mono, monospace' }}>
                      {position.today_nav != null ? `¥${position.today_nav.toFixed(4)}` : '--'}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  {position.is_pending || position.nav_change_pct == null ? (
                    <Typography variant="body2" color="text.disabled">--</Typography>
                  ) : (
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontWeight: 600,
                        color: position.nav_change_pct >= 0 ? 'success.main' : 'error.main',
                      }}
                    >
                      {position.nav_change_pct >= 0 ? '+' : ''}{position.nav_change_pct.toFixed(2)}%
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right">
                  {position.is_pending || position.position_pnl == null ? (
                    <Typography variant="body2" color="text.disabled">--</Typography>
                  ) : (
                    <Typography
                      variant="body2"
                      sx={{
                        fontFamily: 'JetBrains Mono, monospace',
                        fontWeight: 600,
                        color: position.position_pnl >= 0 ? 'success.main' : 'error.main',
                      }}
                    >
                      {position.position_pnl >= 0 ? '+' : ''}¥{position.position_pnl.toFixed(2)}
                    </Typography>
                  )}
                </TableCell>
                <TableCell>
                  {position.is_pending ? (
                    <Typography variant="body2" color="text.disabled">--</Typography>
                  ) : (
                    renderContributionBar(position)
                  )}
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" sx={{ fontFamily: 'JetBrains Mono, monospace' }}>
                    {position.weight_pct.toFixed(1)}%
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      )}
    </Paper>
  );
};

export default DailyReturnsDetail;
