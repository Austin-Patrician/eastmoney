import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Alert,
  Box,
  Chip,
  Divider,
  Grid,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  alpha,
  useTheme,
} from '@mui/material';

import { getStocksLiveWsUrl, type StockLiveEvent } from '../../api';

interface LiveMonitorTabProps {
  code: string;
  market?: string;
}

interface DepthLevel {
  price: number;
  volume: number;
  orders?: number;
}

interface TapeItem {
  ts: number;
  timeLabel: string;
  price: number;
  volume: number;
  side: string;
}

interface TrendPoint {
  ts: number;
  price: number;
}

type WsStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

const DEFAULT_TYPES = ['quote', 'depth', 'tick', 'kline@1'];
const MAX_TICKS = 100;
const MAX_TREND_POINTS = 320;

const toNumber = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') {
    return null;
  }
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

const formatClock = (ts: number): string => {
  if (!Number.isFinite(ts) || ts <= 0) {
    return '--:--:--';
  }
  return new Date(ts).toLocaleTimeString();
};

const formatVolume = (value: number): string => {
  if (!Number.isFinite(value)) {
    return '--';
  }
  if (Math.abs(value) >= 100000000) {
    return `${(value / 100000000).toFixed(2)}B`;
  }
  if (Math.abs(value) >= 10000) {
    return `${(value / 10000).toFixed(2)}W`;
  }
  return value.toLocaleString();
};

const normalizeDepth = (levels: unknown, side: 'ask' | 'bid'): DepthLevel[] => {
  if (!Array.isArray(levels)) {
    return [];
  }

  const mapped = levels
    .map((item): DepthLevel | null => {
      if (Array.isArray(item)) {
        const price = toNumber(item[0]);
        const volume = toNumber(item[1]);
        if (price === null || volume === null) {
          return null;
        }
        return { price, volume };
      }
      if (typeof item === 'object' && item !== null) {
        const obj = item as Record<string, unknown>;
        const price = toNumber(obj.p);
        const volume = toNumber(obj.v);
        const orders = toNumber(obj.o);
        if (price === null || volume === null) {
          return null;
        }
        return { price, volume, orders: orders === null ? undefined : orders };
      }
      return null;
    })
    .filter((item): item is DepthLevel => Boolean(item));

  if (side === 'ask') {
    return mapped.sort((a, b) => a.price - b.price).slice(0, 5).reverse();
  }
  return mapped.sort((a, b) => b.price - a.price).slice(0, 5);
};

const normalizeSide = (raw: unknown): string => {
  if (typeof raw === 'number') {
    if (raw > 0) return 'B';
    if (raw < 0) return 'S';
  }
  const str = String(raw || '').toUpperCase();
  if (str.includes('B') || str === '1' || str === 'BUY') return 'B';
  if (str.includes('S') || str === '-1' || str === 'SELL') return 'S';
  return '-';
};

export default function LiveMonitorTab({ code, market }: LiveMonitorTabProps) {
  const { t } = useTranslation();
  const theme = useTheme();

  const [status, setStatus] = useState<WsStatus>('connecting');
  const [quote, setQuote] = useState<Record<string, unknown> | null>(null);
  const [asks, setAsks] = useState<DepthLevel[]>([]);
  const [bids, setBids] = useState<DepthLevel[]>([]);
  const [ticks, setTicks] = useState<TapeItem[]>([]);
  const [trend, setTrend] = useState<TrendPoint[]>([]);
  const [lastUpdateTs, setLastUpdateTs] = useState<number>(0);
  const rafRef = useRef<number | null>(null);

  const quoteRef = useRef<Record<string, unknown> | null>(null);
  const asksRef = useRef<DepthLevel[]>([]);
  const bidsRef = useRef<DepthLevel[]>([]);
  const ticksRef = useRef<TapeItem[]>([]);
  const trendRef = useRef<TrendPoint[]>([]);
  const lastTsRef = useRef<number>(0);

  const scheduleFlush = () => {
    if (rafRef.current !== null) {
      return;
    }
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null;
      setQuote(quoteRef.current);
      setAsks([...asksRef.current]);
      setBids([...bidsRef.current]);
      setTicks([...ticksRef.current]);
      setTrend([...trendRef.current]);
      setLastUpdateTs(lastTsRef.current);
    });
  };

  const appendTrendPoint = (ts: number, price: number) => {
    if (!Number.isFinite(price)) {
      return;
    }
    const pointTs = Number.isFinite(ts) && ts > 0 ? ts : Date.now();
    const data = trendRef.current;
    const last = data[data.length - 1];
    if (last && Math.abs(last.ts - pointTs) < 1000) {
      last.price = price;
      last.ts = pointTs;
    } else {
      data.push({ ts: pointTs, price });
    }
    if (data.length > MAX_TREND_POINTS) {
      trendRef.current = data.slice(data.length - MAX_TREND_POINTS);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (!token) {
      setStatus('error');
      return;
    }

    let active = true;
    let ws: WebSocket | null = null;
    let reconnectTimer: number | null = null;
    let heartbeatTimer: number | null = null;
    let attempts = 0;

    const clearTimers = () => {
      if (reconnectTimer !== null) {
        window.clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (heartbeatTimer !== null) {
        window.clearInterval(heartbeatTimer);
        heartbeatTimer = null;
      }
    };

    const connect = () => {
      if (!active) {
        return;
      }
      setStatus('connecting');
      try {
        ws = new WebSocket(getStocksLiveWsUrl(token));
      } catch (_error) {
        setStatus('error');
        return;
      }

      ws.onopen = () => {
        attempts = 0;
        setStatus('connected');
        ws?.send(JSON.stringify({
          ac: 'subscribe',
          symbol: code,
          market,
          types: DEFAULT_TYPES,
        }));
        heartbeatTimer = window.setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ ac: 'ping' }));
          }
        }, 25000);
      };

      ws.onmessage = (event) => {
        let payload: StockLiveEvent | null = null;
        try {
          payload = JSON.parse(event.data) as StockLiveEvent;
        } catch (_error) {
          return;
        }
        if (!payload) {
          return;
        }

        if (payload.type === 'system') {
          if (payload.event === 'connected') {
            setStatus('connected');
          }
          if (payload.event === 'error') {
            setStatus('error');
          }
          return;
        }

        const data = payload.data || {};
        const eventType = String(payload.type || '');
        const eventTs = toNumber(payload.ts) || toNumber((data as Record<string, unknown>).t) || Date.now();
        lastTsRef.current = eventTs;

        if (eventType === 'quote') {
          quoteRef.current = data;
          const price = toNumber((data as Record<string, unknown>).ld);
          if (price !== null) {
            appendTrendPoint(eventTs, price);
          }
        } else if (eventType === 'depth') {
          asksRef.current = normalizeDepth((data as Record<string, unknown>).a, 'ask');
          bidsRef.current = normalizeDepth((data as Record<string, unknown>).b, 'bid');
        } else if (eventType === 'tick') {
          const price = toNumber((data as Record<string, unknown>).p);
          const volume = toNumber((data as Record<string, unknown>).v);
          if (price !== null && volume !== null) {
            const tickItem: TapeItem = {
              ts: eventTs,
              timeLabel: formatClock(eventTs),
              price,
              volume,
              side: normalizeSide((data as Record<string, unknown>).o),
            };
            ticksRef.current = [tickItem, ...ticksRef.current].slice(0, MAX_TICKS);
          }
        } else if (eventType.startsWith('kline@')) {
          const price = toNumber(
            (data as Record<string, unknown>).c ??
            (data as Record<string, unknown>).ld ??
            (data as Record<string, unknown>).p
          );
          if (price !== null) {
            appendTrendPoint(eventTs, price);
          }
        }
        scheduleFlush();
      };

      ws.onerror = () => {
        setStatus('error');
      };

      ws.onclose = () => {
        clearTimers();
        if (!active) {
          return;
        }
        setStatus('disconnected');
        attempts += 1;
        const delay = Math.min(1000 * (2 ** Math.min(attempts, 4)), 10000);
        reconnectTimer = window.setTimeout(() => connect(), delay);
      };
    };

    connect();

    return () => {
      active = false;
      clearTimers();
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          ac: 'unsubscribe',
          symbol: code,
          market,
          types: DEFAULT_TYPES,
        }));
      }
      ws?.close();
    };
  }, [code, market]);

  const latestPrice = toNumber(quote?.ld) ?? toNumber(quote?.p);
  const changePct = toNumber(quote?.chp);
  const highPrice = toNumber(quote?.h);
  const lowPrice = toNumber(quote?.l);
  const openPrice = toNumber(quote?.o);
  const prevClose = toNumber(quote?.p);
  const turnover = toNumber(quote?.tu);
  const trendColor = (changePct ?? 0) >= 0 ? '#ef4444' : '#22c55e';

  const trendSvgPoints = useMemo(() => {
    if (trend.length < 2) {
      return '';
    }
    const width = 760;
    const height = 240;
    const padding = 24;
    const prices = trend.map((p) => p.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    return trend
      .map((point, idx) => {
        const x = (idx / (trend.length - 1)) * (width - 2 * padding) + padding;
        const y = (height - padding) - ((point.price - min) / range) * (height - 2 * padding);
        return `${x},${y}`;
      })
      .join(' ');
  }, [trend]);

  const statusColor = status === 'connected' ? 'success' : status === 'connecting' ? 'warning' : 'error';
  const statusLabel = t(`stocks.live.status.${status}`);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
      {!localStorage.getItem('token') && (
        <Alert severity="warning">{t('stocks.live.no_token')}</Alert>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 800 }}>
          {t('stocks.live.title')}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Chip size="small" color={statusColor} label={statusLabel} />
          <Typography variant="caption" sx={{ color: 'text.secondary', fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
            {t('stocks.live.last_update')}: {formatClock(lastUpdateTs)}
          </Typography>
        </Box>
      </Box>

      <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 4 }}>
          <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2.5 }}>
            <Typography variant="overline" sx={{ fontWeight: 800, color: 'text.secondary' }}>
              {t('stocks.live.price_board')}
            </Typography>
            <Typography
              variant="h4"
              sx={{
                mt: 1,
                fontWeight: 900,
                fontFamily: 'JetBrains Mono',
                color: (changePct ?? 0) > 0 ? '#ef4444' : (changePct ?? 0) < 0 ? '#22c55e' : 'text.primary',
              }}
            >
              {latestPrice !== null ? latestPrice.toFixed(2) : '--'}
            </Typography>
            <Typography
              sx={{
                fontFamily: 'JetBrains Mono',
                fontWeight: 700,
                color: (changePct ?? 0) > 0 ? '#ef4444' : (changePct ?? 0) < 0 ? '#22c55e' : 'text.secondary',
              }}
            >
              {changePct !== null ? `${changePct > 0 ? '+' : ''}${changePct.toFixed(2)}%` : '--'}
            </Typography>
            <Divider sx={{ my: 1.5 }} />
            <Grid container spacing={1}>
              <Grid size={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('stocks.details.open')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{openPrice !== null ? openPrice.toFixed(2) : '--'}</Typography>
              </Grid>
              <Grid size={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('stocks.details.high')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{highPrice !== null ? highPrice.toFixed(2) : '--'}</Typography>
              </Grid>
              <Grid size={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('stocks.details.low')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{lowPrice !== null ? lowPrice.toFixed(2) : '--'}</Typography>
              </Grid>
              <Grid size={6}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('stocks.live.prev_close')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{prevClose !== null ? prevClose.toFixed(2) : '--'}</Typography>
              </Grid>
              <Grid size={12}>
                <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('stocks.live.turnover')}</Typography>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>{turnover !== null ? formatVolume(turnover) : '--'}</Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, lg: 8 }}>
          <Paper
            elevation={0}
            sx={{
              p: 2,
              border: '1px solid',
              borderColor: 'divider',
              borderRadius: 2.5,
              minHeight: 270,
            }}
          >
            <Typography variant="overline" sx={{ fontWeight: 800, color: 'text.secondary' }}>
              {t('stocks.live.intraday')}
            </Typography>
            {trendSvgPoints ? (
              <Box sx={{ mt: 1, bgcolor: alpha(trendColor, 0.03), borderRadius: 2, border: '1px solid', borderColor: alpha(trendColor, 0.18), p: 1 }}>
                <svg viewBox="0 0 760 240" style={{ width: '100%', height: 220 }}>
                  <polyline
                    points={trendSvgPoints}
                    fill="none"
                    stroke={trendColor}
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Box>
            ) : (
              <Box sx={{ py: 8, textAlign: 'center', color: 'text.secondary' }}>
                <Typography variant="body2">{t('stocks.live.no_realtime')}</Typography>
              </Box>
            )}
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2.5 }}>
            <Typography variant="overline" sx={{ fontWeight: 800, color: 'text.secondary' }}>
              {t('stocks.live.order_book')}
            </Typography>
            <TableContainer sx={{ mt: 1 }}>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 800, fontSize: '0.75rem' }}>{t('stocks.live.side')}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800, fontSize: '0.75rem' }}>{t('stocks.live.price')}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800, fontSize: '0.75rem' }}>{t('stocks.live.volume')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {asks.map((level, idx) => (
                    <TableRow key={`ask-${idx}`}>
                      <TableCell sx={{ color: '#ef4444', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {`${t('stocks.live.ask')}${Math.max(1, asks.length - idx)}`}
                      </TableCell>
                      <TableCell align="right" sx={{ color: '#ef4444', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {level.price.toFixed(2)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', color: 'text.secondary' }}>
                        {formatVolume(level.volume)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {bids.map((level, idx) => (
                    <TableRow key={`bid-${idx}`}>
                      <TableCell sx={{ color: '#22c55e', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {`${t('stocks.live.bid')}${idx + 1}`}
                      </TableCell>
                      <TableCell align="right" sx={{ color: '#22c55e', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {level.price.toFixed(2)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', color: 'text.secondary' }}>
                        {formatVolume(level.volume)}
                      </TableCell>
                    </TableRow>
                  ))}
                  {asks.length === 0 && bids.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={3} sx={{ color: 'text.secondary', textAlign: 'center', py: 3 }}>
                        {t('stocks.live.no_realtime')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>

        <Grid size={{ xs: 12, lg: 6 }}>
          <Paper elevation={0} sx={{ p: 2, border: '1px solid', borderColor: 'divider', borderRadius: 2.5 }}>
            <Typography variant="overline" sx={{ fontWeight: 800, color: 'text.secondary' }}>
              {t('stocks.live.tape')}
            </Typography>
            <TableContainer sx={{ mt: 1, maxHeight: 320 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ fontWeight: 800, fontSize: '0.75rem', bgcolor: theme.palette.background.paper }}>{t('stocks.live.time')}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800, fontSize: '0.75rem', bgcolor: theme.palette.background.paper }}>{t('stocks.live.price')}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800, fontSize: '0.75rem', bgcolor: theme.palette.background.paper }}>{t('stocks.live.volume')}</TableCell>
                    <TableCell align="right" sx={{ fontWeight: 800, fontSize: '0.75rem', bgcolor: theme.palette.background.paper }}>{t('stocks.live.side')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {ticks.map((item, idx) => (
                    <TableRow key={`${item.ts}-${idx}`}>
                      <TableCell sx={{ fontFamily: 'JetBrains Mono' }}>{item.timeLabel}</TableCell>
                      <TableCell
                        align="right"
                        sx={{
                          fontFamily: 'JetBrains Mono',
                          color: item.side === 'B' ? '#ef4444' : item.side === 'S' ? '#22c55e' : 'text.primary',
                          fontWeight: 700,
                        }}
                      >
                        {item.price.toFixed(2)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', color: 'text.secondary' }}>
                        {formatVolume(item.volume)}
                      </TableCell>
                      <TableCell align="right" sx={{ fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                        {item.side}
                      </TableCell>
                    </TableRow>
                  ))}
                  {ticks.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={4} sx={{ color: 'text.secondary', textAlign: 'center', py: 3 }}>
                        {t('stocks.live.no_realtime')}
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

