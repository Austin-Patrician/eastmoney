import axios from 'axios';

// In production (build), use relative path '/api' to let Nginx proxy handle it.
// In development (dev), use env var or fallback to localhost:8000.
const API_BASE = import.meta.env.PROD ? '/api' : (import.meta.env.VITE_API_URL || 'http://localhost:8000/api');

// Create axios instance
const api = axios.create({
    baseURL: API_BASE,
});

// Request interceptor: Inject Token
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => Promise.reject(error));

// Response interceptor: Handle 401
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response && error.response.status === 401) {
            // Token expired or invalid
            localStorage.removeItem('token');
            if (window.location.pathname !== '/login') {
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// --- Auth API ---
export const login = async (username: string, password: string): Promise<{ access_token: string }> => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const response = await api.post('/auth/token', formData);
    return response.data;
};

export const register = async (username: string, password: string, email?: string): Promise<{ access_token: string }> => {
    const response = await api.post('/auth/register', { username, password, email });
    return response.data;
};

// --- Existing APIs (Updated to use 'api' instance) ---

export interface ReportSummary {
  filename: string;
  date: string;
  mode: 'pre' | 'post' | 'commodities';
  fund_code?: string;
  fund_name?: string;
  is_summary: boolean;
}

export const fetchReports = async (): Promise<ReportSummary[]> => {
  const response = await api.get('/reports');
  return response.data;
};

export const deleteReport = async (filename: string): Promise<void> => {
  await api.delete(`/reports/${filename}`);
};

export const fetchCommodityReports = async (): Promise<ReportSummary[]> => {
  const response = await api.get('/commodities/reports');
  return response.data;
};

export const deleteCommodityReport = async (filename: string): Promise<void> => {
  await api.delete(`/commodities/reports/${filename}`);
};

export const generateCommodityReport = async (asset: 'gold' | 'silver'): Promise<void> => {
  await api.post('/commodities/analyze', { asset });
};

export const fetchReportContent = async (filename: string): Promise<string> => {
  const response = await api.get(`/reports/${filename}`);
  return response.data.content;
};

export const fetchDashboardOverview = async (): Promise<any> => {
  const response = await api.get('/dashboard/overview');
  return response.data;
};

export const fetchDashboardStats = async (): Promise<any> => {
  const response = await api.get('/dashboard/stats');
  return response.data;
};

export const fetchMarketFunds = async (query: string): Promise<any[]> => {
  const response = await api.get('/market-funds', { params: { query } });
  return response.data;
};

export const generateReport = async (mode: 'pre' | 'post', fundCode?: string): Promise<void> => {
  await api.post(`/generate/${mode}`, { fund_code: fundCode });
};

export interface FundItem {
  code: string;
  name: string;
  style?: string;
  focus?: string[];
  pre_market_time?: string; // HH:MM
  post_market_time?: string; // HH:MM
  is_active?: boolean;
}

export interface SettingsData {
  llm_provider: string;
  gemini_api_key_masked: string;
  openai_api_key_masked: string;
  openai_base_url?: string;
  openai_model?: string;
  tavily_api_key_masked: string;
}

export interface SettingsUpdate {
  llm_provider: string;
  gemini_api_key?: string;
  openai_api_key?: string;
  openai_base_url?: string;
  openai_model?: string;
  tavily_api_key?: string;
}

// Notification Settings
export interface NotificationSettingsData {
  email_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  smtp_password_masked: string;
  smtp_from_email: string;
  smtp_use_tls: boolean;
  recipient_email: string;
  notify_on_report: boolean;
  notify_on_alert: boolean;
  notify_daily_summary: boolean;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string;
  quiet_hours_end: string;
  daily_summary_time: string;
}

export interface NotificationSettingsUpdate {
  email_enabled?: boolean;
  smtp_host?: string;
  smtp_port?: number;
  smtp_user?: string;
  smtp_password?: string;
  smtp_from_email?: string;
  smtp_use_tls?: boolean;
  recipient_email?: string;
  notify_on_report?: boolean;
  notify_on_alert?: boolean;
  notify_daily_summary?: boolean;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  daily_summary_time?: string;
}

export const fetchFunds = async (): Promise<FundItem[]> => {
  const response = await api.get('/funds');
  return response.data;
};

export const saveFund = async (fund: FundItem): Promise<void> => {
  await api.put(`/funds/${fund.code}`, fund);
};

export const deleteFund = async (code: string): Promise<void> => {
  await api.delete(`/funds/${code}`);
};

export interface MarketFund {
    code: string;
    name: string;
    type: string;
    pinyin: string;
}

export const searchMarketFunds = async (query: string): Promise<MarketFund[]> => {
    const response = await api.get('/market/funds', { params: { q: query } });
    return response.data;
};

export interface FundMarketDetails {
    info: Record<string, string>;
    performance: any[];
}

export const fetchFundMarketDetails = async (code: string): Promise<FundMarketDetails> => {
    const response = await api.get(`/market/funds/${code}/details`);
    return response.data;
};

export interface NavPoint {
    date: string;
    value: number;
}

export interface IndexData {
  name: string;
  code: string;
  price: number;
  change_pct: number;
  change_val: number;
}

export const fetchMarketIndices = async (): Promise<IndexData[]> => {
    const response = await api.get('/market/indices');
    return response.data;
};

export const fetchFundNavHistory = async (code: string): Promise<NavPoint[]> => {
    const response = await api.get(`/market/funds/${code}/nav`);
    return response.data;
};

// ==================== Fund Market Enhanced APIs ====================

export interface FundCategoryStats {
  category: string;
  type_key: string;
  total_count: number;
  avg_return_1m: number;
  avg_return_3m: number;
  avg_return_1y: number;
  top_performers: {
    code: string;
    name: string;
    return_1m: number;
  }[];
}

export interface FundMarketOverview {
  timestamp: string;
  categories: FundCategoryStats[];
}

export const fetchFundMarketOverview = async (): Promise<FundMarketOverview> => {
  const response = await api.get('/funds/market/overview');
  return response.data;
};

export interface FundRankingItem {
  rank: number;
  code: string;
  name: string;
  nav: number;
  acc_nav: number;
  return_1w: number;
  return_1m: number;
  return_3m: number;
  return_6m: number;
  return_1y: number;
  return_3y: number;
  fee: string;
}

export interface FundRankingResponse {
  fund_type: string;
  sort_by: string;
  funds: FundRankingItem[];
  total: number;
}

export const fetchFundRanking = async (
  fundType: string = '股票型',
  sortBy: string = '近1月',
  limit: number = 50
): Promise<FundRankingResponse> => {
  const response = await api.get('/funds/market/ranking', {
    params: { fund_type: fundType, sort_by: sortBy, limit },
  });
  return response.data;
};

export interface ETFRealtimeItem {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  change_val: number;
  volume: number;
  amount: number;
  open: number;
  high: number;
  low: number;
  prev_close: number;
  turnover_rate: number;
}

export interface ETFRealtimeResponse {
  etfs: ETFRealtimeItem[];
  timestamp: string;
}

export const fetchETFRealtime = async (limit: number = 50): Promise<ETFRealtimeResponse> => {
  const response = await api.get('/funds/etf/realtime', { params: { limit } });
  return response.data;
};

export interface FundEstimation {
  code: string;
  name: string;
  estimated_nav: number;
  estimated_change_pct: number;
  prev_nav: number;
  prev_nav_date: string;
  estimation_time: string;
  timestamp: string;
}

export const fetchFundEstimation = async (code: string): Promise<FundEstimation> => {
  const response = await api.get(`/funds/${code}/estimation`);
  return response.data;
};

export interface IndustryAllocation {
  industry: string;
  weight: number;
  market_value: number;
}

export interface FundIndustryAllocationResponse {
  code: string;
  allocations: IndustryAllocation[];
  report_date: string | null;
  message?: string;
}

export const fetchFundIndustryAllocation = async (code: string): Promise<FundIndustryAllocationResponse> => {
  const response = await api.get(`/funds/${code}/industry-allocation`);
  return response.data;
};

export interface FundManager {
  name: string;
  start_date: string;
  end_date: string;
  tenure_days: number;
  tenure_return: number;
  best_return?: number;
  education?: string;
  gender?: string;
  birth_year?: string;
  resume?: string;
}

export interface FundManagerDetailResponse {
  code: string;
  fund_name: string;
  managers: FundManager[];
  company: string;
}

export const fetchFundManagerDetail = async (code: string): Promise<FundManagerDetailResponse> => {
  const response = await api.get(`/funds/${code}/manager-detail`);
  return response.data;
};

// ==================== Market Overview APIs ====================

export interface MarketIndex {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  change_val: number;
  volume: number;
  amount: number;
  high: number;
  low: number;
  open: number;
  prev_close: number;
}

export interface MarketIndicesResponse {
  indices: MarketIndex[];
  timestamp: string;
}

export const fetchMarketIndicesData = async (): Promise<MarketIndicesResponse> => {
  const response = await api.get('/funds/market/indices');
  return response.data;
};

export interface SectorItem {
  name: string;
  change_pct: number;
  turnover_rate: number;
  leading_stock: string;
  leading_change: number;
  total_amount: number;
}

export interface MarketSectorsResponse {
  top_gainers: SectorItem[];
  top_losers: SectorItem[];
  timestamp: string;
}

export const fetchMarketSectors = async (limit: number = 10): Promise<MarketSectorsResponse> => {
  const response = await api.get('/funds/market/sectors', { params: { limit } });
  return response.data;
};

export interface NorthboundFlowItem {
  date: string;
  north_money: number;
  south_money: number;
  hgt: number;
  sgt: number;
}

export interface NorthboundFlowResponse {
  today: {
    north_money: number;
    south_money: number;
    hgt: number;
    sgt: number;
  };
  recent: NorthboundFlowItem[];
  timestamp: string;
  message?: string;
}

export const fetchNorthboundFlow = async (): Promise<NorthboundFlowResponse> => {
  const response = await api.get('/funds/market/northbound');
  return response.data;
};

export interface MarketSentiment {
  up_count: number;
  down_count: number;
  flat_count: number;
  limit_up: number;
  limit_down: number;
  timestamp: string;
}

export const fetchMarketSentiment = async (): Promise<MarketSentiment> => {
  const response = await api.get('/funds/market/sentiment');
  return response.data;
};

// ==================== Enhanced Fund Detail API ====================

export interface FundFullDetail {
  code: string;
  basic_info: {
    name: string;
    company: string;
    fund_type: string;
    inception_date: string;
    size: string;
  };
  nav: {
    current: number;
    accumulated: number;
    history: { date: string; value: number }[];
  };
  performance: {
    return_1w?: number;
    return_1m?: number;
    return_3m?: number;
    return_6m?: number;
    return_1y?: number;
    return_2y?: number;
    return_3y?: number;
    return_ytd?: number;
    return_since_inception?: number;
    fee?: string;
  };
  risk_metrics: {
    max_drawdown?: number;
    sharpe_ratio?: number;
    volatility?: number;
    annualized_return?: number;
    calmar_ratio?: number;
    sortino_ratio?: number;
  };
  holdings: {
    code: string;
    name: string;
    weight: number;
  }[];
  industry_allocation: {
    industry: string;
    weight: number;
  }[];
  managers: {
    name: string;
    start_date: string;
    end_date: string;
    tenure_days: number;
    tenure_return: number;
    education?: string;
    gender?: string;
    birth_year?: string;
    resume?: string;
  }[];
  timestamp: string;
}

export const fetchFundFullDetail = async (code: string): Promise<FundFullDetail> => {
  const response = await api.get(`/funds/${code}/full-detail`);
  return response.data;
};

// ==================== End Fund Market Enhanced APIs ====================

export const fetchSettings = async (): Promise<SettingsData> => {
  const response = await api.get('/settings');
  return response.data;
};

export const saveSettings = async (settings: SettingsUpdate): Promise<void> => {
  await api.post('/settings', settings);
};

// Notification Settings API
export const fetchNotificationSettings = async (): Promise<NotificationSettingsData> => {
  const response = await api.get('/settings/notifications');
  return response.data;
};

export const saveNotificationSettings = async (settings: NotificationSettingsUpdate): Promise<void> => {
  await api.post('/settings/notifications', settings);
};

export const sendTestEmail = async (recipient?: string): Promise<{ status: string; message: string }> => {
  const response = await api.post('/settings/notifications/test', { recipient });
  return response.data;
};

export const fetchLLMModels = async (provider: string, apiKey?: string, baseUrl?: string): Promise<{ models: string[], warning?: string }> => {
    const response = await api.post('/llm/models', { provider, api_key: apiKey, base_url: baseUrl });
    return response.data;
};

export interface SentimentResponse {
  report: string;
  filename: string;
}

export const runSentimentAnalysis = async (): Promise<SentimentResponse> => {
  const response = await api.post('/sentiment/analyze');
  return response.data;
};

export interface SentimentReportItem {
  filename: string;
  date: string;
}

export const fetchSentimentReports = async (): Promise<SentimentReportItem[]> => {
  const response = await api.get('/sentiment/reports');
  return response.data;
};

export const deleteSentimentReport = async (filename: string): Promise<void> => {
  await api.delete(`/sentiment/reports/${filename}`);
};


// --- Stock API ---

export interface StockItem {
  code: string;
  name: string;
  market?: string;
  sector?: string;
  is_active?: boolean;
  price?: number;
  change_pct?: number;
  volume?: number;
}

// --- Market Data API ---

export interface MarketActivity {
  上涨: number;
  涨停: number;
  真实涨停: number;
  下跌: number;
  跌停: number;
  真实跌停: number;
  平盘: number;
  活跃度: string;
  统计日期: string;
}

export interface NorthboundFlow {
  最新净流入: string;
  '5日累计净流入'?: string;
  数据日期: string;
  沪股通?: Record<string, any>;
  深股通?: Record<string, any>;
}

export interface MarketSummary {
  activity: MarketActivity;
  northbound: NorthboundFlow;
  update_time: string;
}

export interface HotStock {
  rank: number;
  code: string;
  name: string;
  price: number;
  change: number;
  change_pct: number;
}

export interface LimitStock {
  rank: number;
  code: string;
  name: string;
  price: number;
  change_pct: number;
  amount: number;
  market_cap: number;
  turnover: number;
  seal_money: number;
  first_seal_time?: string;
  last_seal_time: string;
  open_count: number;
  limit_stats?: string;
  consecutive: number;
  industry: string;
}

export interface MarketDataResponse<T> {
  items: T[];
  update_time: string;
}

export const fetchMarketSummary = async (): Promise<MarketSummary> => {
  const response = await api.get('/stocks/market/summary');
  return response.data;
};

export const fetchHotStocks = async (limit: number = 20): Promise<MarketDataResponse<HotStock>> => {
  const response = await api.get('/stocks/market/hot', { params: { limit } });
  return response.data;
};

export const fetchLimitUpStocks = async (limit: number = 30, date?: string): Promise<MarketDataResponse<LimitStock>> => {
  const response = await api.get('/stocks/market/limit-up', { params: { limit, date } });
  return response.data;
};

export const fetchLimitDownStocks = async (limit: number = 30, date?: string): Promise<MarketDataResponse<LimitStock>> => {
  const response = await api.get('/stocks/market/limit-down', { params: { limit, date } });
  return response.data;
};

export interface MarketAIBrief {
  brief: string;
  update_time: string;
  top_industries: { name: string; count: number }[];
  error?: boolean;
}

export const fetchMarketAIBrief = async (): Promise<MarketAIBrief> => {
  const response = await api.get('/stocks/market/ai-brief');
  return response.data;
};

export const fetchStocks = async (): Promise<StockItem[]> => {
  const response = await api.get('/stocks');
  return response.data;
};

export const saveStock = async (stock: StockItem): Promise<void> => {
  await api.put(`/stocks/${stock.code}`, stock);
};

export const deleteStock = async (code: string): Promise<void> => {
  await api.delete(`/stocks/${code}`);
};

export interface MarketStock {
    code: string;
    name: string;
    industry?: string;
    market?: string;
    area?: string;
    list_date?: string;
}

export const searchMarketStocks = async (query: string): Promise<MarketStock[]> => {
    const response = await api.get('/market/stocks', { params: { query } });
    return response.data;
};

export interface StockDetails {
    quote: Record<string, any>;
    info: Record<string, string>;
}

export const fetchStockDetails = async (code: string): Promise<StockDetails> => {
    const response = await api.get(`/market/stocks/${code}/details`);
    return response.data;
};

export const fetchStockHistory = async (code: string): Promise<NavPoint[]> => {
    const response = await api.get(`/market/stocks/${code}/history`);
    return response.data;
};


// --- Stock Analysis API ---

export const analyzeStock = async (code: string, mode: 'pre' | 'post'): Promise<void> => {
    await api.post(`/stocks/${code}/analyze`, { mode });
};

export interface StockReportSummary {
    filename: string;
    date: string;
    mode: 'pre' | 'post';
    stock_code: string;
    stock_name: string;
}

export const fetchStockReports = async (): Promise<StockReportSummary[]> => {
    const response = await api.get('/stocks/reports');
    return response.data;
};

export const fetchStockReportContent = async (filename: string): Promise<string> => {
    const response = await api.get(`/stocks/reports/${filename}`);
    return response.data.content;
};

export const deleteStockReport = async (filename: string): Promise<void> => {
    await api.delete(`/stocks/reports/${filename}`);
};


// --- Recommendation API ---

export interface RecommendationStock {
    code: string;
    name: string;
    current_price?: number;
    price?: number;
    change_pct?: number;
    target_price?: number;
    target_price_1y?: number;
    stop_loss?: number;
    expected_return?: string;
    expected_return_1y?: string;
    recommendation_score: number;
    investment_logic?: string;
    risk_factors?: string[];
    key_catalysts?: string[];
    confidence?: string;
    holding_period?: string;
    market_cap?: number;
    pe?: number;
    pb?: number;
    main_net_inflow?: number;
    volume_ratio?: number;
    score?: number;
    why_now?: string;
    competitive_advantage?: string;
    valuation_analysis?: string;
    industry_position?: string;
    growth_drivers?: string[];
}

export interface RecommendationFund {
    code: string;
    name: string;
    current_nav?: number;
    nav?: number;
    fund_type?: string;
    return_1w?: number;
    return_1m?: number;
    return_3m?: number;
    return_6m?: number;
    return_1y?: number;
    return_3y?: number;
    target_nav?: number;
    recommendation_score: number;
    investment_logic?: string;
    risk_factors?: string[];
    key_catalysts?: string[];
    confidence?: string;
    holding_period?: string;
    score?: number;
    expected_return?: string;
    expected_return_1y?: string;
    why_now?: string;
    manager_analysis?: string;
    fund_style?: string;
    suitable_for?: string;
}

export interface RecommendationResult {
    mode: string;
    generated_at: string;
    personalized?: boolean;
    short_term?: {
        stocks?: RecommendationStock[];
        funds?: RecommendationFund[];
        short_term_stocks?: RecommendationStock[];
        short_term_funds?: RecommendationFund[];
        market_view?: string;
        sector_preference?: string[];
        risk_warning?: string;
    };
    long_term?: {
        stocks?: RecommendationStock[];
        funds?: RecommendationFund[];
        long_term_stocks?: RecommendationStock[];
        long_term_funds?: RecommendationFund[];
        macro_view?: string;
        sector_preference?: string[];
        risk_warning?: string;
    };
    metadata?: {
        screening_time?: number;
        llm_time?: number;
        total_time?: number;
        personalized?: boolean;
    };
}

export const fetchLatestRecommendations = async (): Promise<{
    available: boolean;
    data?: RecommendationResult;
    generated_at?: string;
    mode?: string;
    message?: string;
}> => {
    const response = await api.get('/recommend/latest');
    return response.data;
};

export interface RecommendationHistoryItem {
    id: number;
    mode: string;
    generated_at: string;
    short_term_count?: number;
    long_term_count?: number;
}

export const fetchRecommendationHistory = async (limit: number = 20): Promise<RecommendationHistoryItem[]> => {
    const response = await api.get('/recommend/history', { params: { limit } });
    return response.data;
};


// --- User Preferences API ---

export interface UserPreferences {
    risk_level: 'conservative' | 'moderate' | 'aggressive' | 'speculative';
    investment_horizon: 'short_term' | 'medium_term' | 'long_term';
    investment_goal: 'capital_preservation' | 'steady_income' | 'capital_appreciation' | 'speculation';
    investment_style: 'value' | 'growth' | 'blend' | 'momentum' | 'dividend';
    total_capital?: number;
    max_single_position: number;
    max_sector_position: number;
    max_drawdown_tolerance: number;
    stop_loss_percentage: number;
    take_profit_percentage?: number;
    min_market_cap?: number;
    max_market_cap?: number;
    min_pe?: number;
    max_pe?: number;
    min_pb?: number;
    max_pb?: number;
    min_roe?: number;
    min_dividend_yield?: number;
    preferred_sectors: string[];
    excluded_sectors: string[];
    preferred_themes: string[];
    preferred_fund_types: string[];
    excluded_fund_types: string[];
    min_fund_scale?: number;
    max_fund_management_fee: number;
    stock_recommendation_count: number;
    fund_recommendation_count: number;
    avoid_st_stocks: boolean;
    avoid_new_stocks: boolean;
    require_profitable: boolean;
    min_liquidity?: number;
    created_at?: string;
    updated_at?: string;
}

export const getUserPreferences = async (): Promise<{
    exists: boolean;
    preferences: UserPreferences;
    updated_at?: string;
}> => {
    const response = await api.get('/preferences');
    return response.data;
};

export const saveUserPreferences = async (preferences: Partial<UserPreferences>): Promise<{
    success: boolean;
    message: string;
}> => {
    const response = await api.post('/preferences', preferences);
    return response.data;
};

export const getPreferencePresets = async (): Promise<{
    presets: Record<string, UserPreferences>;
}> => {
    const response = await api.get('/preferences/presets');
    return response.data;
};


// --- Details API ---

export interface StockDetails {
    code: string;
    name: string;
    price: number;
    change_pct: number;
    volume: number;
    turnover: number;
    pe: number;
    pb: number;
    market_cap: number;
    history: Array<{
        日期: string;
        开盘: number;
        收盘: number;
        最高: number;
        最低: number;
        成交量: number;
        成交额: number;
        振幅: number;
        涨跌幅: number;
        涨跌额: number;
        换手率: number;
    }>;
    financial: Record<string, any>;
}

export interface FundDetails {
    code: string;
    name: string;
    type: string;
    basic_info: Record<string, any>;
    nav_history: Array<{
        净值日期: string;
        单位净值: number;
        累计净值: number;
        日增长率: number;
    }>;
    manager_info: Array<Record<string, any>>;
    top_holdings: Array<Record<string, any>>;
}

export const getStockDetails = async (code: string): Promise<StockDetails> => {
    const response = await api.get(`/details/stock/${code}`);
    return response.data;
};

export const getFundDetails = async (code: string): Promise<FundDetails> => {
    const response = await api.get(`/details/fund/${code}`);
    return response.data;
};


// --- Comparison API ---

export interface StockComparison {
    code: string;
    name: string;
    price: number;
    change_pct: number;
    pe: number;
    pb: number;
    market_cap: number;
    volume_ratio: number;
    turnover_rate: number;
    amplitude: number;
}

export interface FundComparison {
    code: string;
    name: string;
    fund_type: string;
    nav: number;
    return_1w: number;
    return_1m: number;
    return_3m: number;
    return_6m: number;
    return_1y: number;
    return_3y: number;
}

export const compareStocks = async (codes: string[]): Promise<{
    stocks: StockComparison[];
}> => {
    const response = await api.post('/compare/stocks', { codes });
    return response.data;
};

export const compareFunds = async (codes: string[]): Promise<{
    funds: FundComparison[];
}> => {
    const response = await api.post('/compare/funds', { codes });
    return response.data;
};


// --- Widget API ---

import type {
    NorthboundFlowData,
    IndustryFlowData,
    SectorPerformanceData,
    TopListData,
    ForexRatesData,
    WatchlistData,
    NewsData,
    MainCapitalFlowData,
    DashboardLayout,
    LayoutPresetsResponse,
} from './widgets/types';

export const fetchWidgetNorthboundFlow = async (days: number = 5): Promise<NorthboundFlowData> => {
    const response = await api.get('/widgets/northbound-flow', { params: { days } });
    return response.data;
};

export const fetchWidgetIndustryFlow = async (limit: number = 10): Promise<IndustryFlowData> => {
    const response = await api.get('/widgets/industry-flow', { params: { limit } });
    return response.data;
};

export const fetchWidgetSectorPerformance = async (limit: number = 10): Promise<SectorPerformanceData> => {
    const response = await api.get('/widgets/sector-performance', { params: { limit } });
    return response.data;
};

export const fetchWidgetTopList = async (limit: number = 10): Promise<TopListData> => {
    const response = await api.get('/widgets/top-list', { params: { limit } });
    return response.data;
};

export const fetchWidgetForexRates = async (): Promise<ForexRatesData> => {
    const response = await api.get('/widgets/forex-rates');
    return response.data;
};

export const fetchWidgetWatchlist = async (): Promise<WatchlistData> => {
    const response = await api.get('/widgets/watchlist');
    return response.data;
};

export const fetchWidgetNews = async (limit: number = 20, src: string = 'sina'): Promise<NewsData> => {
    const response = await api.get('/widgets/news', { params: { limit, src } });
    return response.data;
};

export const fetchWidgetMainCapitalFlow = async (limit: number = 10): Promise<MainCapitalFlowData> => {
    const response = await api.get('/widgets/main-capital-flow', { params: { limit } });
    return response.data;
};


// --- Dashboard Layout API ---

export const fetchDashboardLayouts = async (): Promise<{ layouts: DashboardLayout[] }> => {
    const response = await api.get('/dashboard/layouts');
    return response.data;
};

export const fetchDashboardLayoutCount = async (): Promise<{ count: number; max: number }> => {
    const response = await api.get('/dashboard/layouts/count');
    return response.data;
};

export const fetchDefaultDashboardLayout = async (): Promise<{ layout: DashboardLayout | null; preset?: string }> => {
    const response = await api.get('/dashboard/layouts/default');
    return response.data;
};

export const fetchDashboardLayout = async (layoutId: number): Promise<DashboardLayout> => {
    const response = await api.get(`/dashboard/layouts/${layoutId}`);
    return response.data;
};

export const createDashboardLayout = async (data: {
    name: string;
    layout: Record<string, unknown>;
    is_default?: boolean;
}): Promise<{ id: number; message: string }> => {
    const response = await api.post('/dashboard/layouts', data);
    return response.data;
};

export const updateDashboardLayout = async (
    layoutId: number,
    data: {
        name?: string;
        layout?: Record<string, unknown>;
        is_default?: boolean;
    }
): Promise<{ message: string }> => {
    const response = await api.put(`/dashboard/layouts/${layoutId}`, data);
    return response.data;
};

export const deleteDashboardLayout = async (layoutId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/dashboard/layouts/${layoutId}`);
    return response.data;
};

export const setDefaultDashboardLayout = async (layoutId: number): Promise<{ message: string }> => {
    const response = await api.post(`/dashboard/layouts/${layoutId}/set-default`);
    return response.data;
};

export const fetchDashboardPresets = async (): Promise<LayoutPresetsResponse> => {
    const response = await api.get('/dashboard/presets');
    return response.data;
};


// --- News Center API ---

export interface NewsItem {
    id: string;
    title: string;
    content?: string;
    summary?: string;
    source: string;
    source_name: string;
    category: 'flash' | 'announcement' | 'research' | 'hot' | 'industry' | 'general';
    sentiment?: 'positive' | 'negative' | 'neutral';
    sentiment_score?: number;
    related_stocks?: Array<{ code: string; name?: string; impact?: string }>;
    related_funds?: Array<{ code: string; name?: string }>;
    published_at: string;
    url?: string;
    is_read?: boolean;
    is_bookmarked?: boolean;
    importance?: 'high' | 'medium' | 'low';
}

export interface NewsFeedResponse {
    news: NewsItem[];
    has_watchlist: boolean;
    watchlist_summary?: {
        stocks_count: number;
        funds_count: number;
    };
    category: string;
    page: number;
    page_size: number;
    total: number;
    has_more: boolean;
    updated_at: string;
}

export interface NewsDetailResponse {
    news_id: string;
    analysis: {
        sentiment?: string;
        sentiment_score?: number;
        summary?: string;
        key_points?: string[];
        related_stocks?: Array<{ code: string; name?: string; impact?: string }>;
        cached?: boolean;
        error?: string;
    };
    is_read: boolean;
}

export interface NewsBookmarkRequest {
    news_title?: string;
    news_source?: string;
    news_url?: string;
    news_category?: string;
    bookmarked?: boolean;
}

export const fetchNewsFeed = async (
    category: string = 'all',
    page: number = 1,
    pageSize: number = 20,
    sinceDays?: number
): Promise<NewsFeedResponse> => {
    const response = await api.get('/news/feed', {
        params: { category, page, page_size: pageSize, since_days: sinceDays }
    });
    return response.data;
};

export const fetchNewsDetail = async (
    newsId: string,
    title: string = '',
    content: string = ''
): Promise<NewsDetailResponse> => {
    const response = await api.get(`/news/${newsId}`, {
        params: { title, content }
    });
    return response.data;
};

export const toggleNewsBookmark = async (
    newsId: string,
    request: NewsBookmarkRequest
): Promise<{ bookmarked: boolean }> => {
    const response = await api.post(`/news/${newsId}/bookmark`, request);
    return response.data;
};

export const markNewsRead = async (
    newsId: string,
    request: Partial<NewsBookmarkRequest>
): Promise<{ success: boolean; is_read: boolean }> => {
    const response = await api.post(`/news/${newsId}/read`, request);
    return response.data;
};

export const fetchNewsBookmarks = async (
    limit: number = 50,
    offset: number = 0
): Promise<{ bookmarks: NewsItem[]; total: number }> => {
    const response = await api.get('/news/bookmarks', {
        params: { limit, offset }
    });
    return response.data;
};

export const fetchNewsWatchlistSummary = async (): Promise<{
    stocks_count: number;
    funds_count: number;
    recent_news_count: number;
    unread_count: number;
    important_news: Array<{ id: string; title: string; sentiment: string }>;
    updated_at: string;
}> => {
    const response = await api.get('/news/watchlist-summary');
    return response.data;
};

export const fetchNewsAnnouncements = async (
    stockCode?: string,
    limit: number = 20
): Promise<{ announcements: NewsItem[]; total: number }> => {
    const response = await api.get('/news/announcements', {
        params: { stock_code: stockCode, limit }
    });
    return response.data;
};

export const searchNewsResearch = async (
    query: string,
    limit: number = 10
): Promise<{ results: NewsItem[]; total: number }> => {
    const response = await api.get('/news/research', {
        params: { query, limit }
    });
    return response.data;
};

export const fetchHotNews = async (
    limit: number = 30
): Promise<{ news: NewsItem[]; total: number }> => {
    const response = await api.get('/news/hot', { params: { limit } });
    return response.data;
};


// --- AI Assistant API ---

export interface AssistantContext {
    page?: string;
    stock?: { code: string; name: string } | null;
    fund?: { code: string; name: string } | null;
}

export interface AssistantMessage {
    role: 'user' | 'assistant';
    content: string;
}

export interface AssistantSource {
    title: string;
    url?: string;
    source?: string;
    type?: string;
}

export interface AssistantChatRequest {
    message: string;
    context?: AssistantContext;
    history?: AssistantMessage[];
}

export interface AssistantChatResponse {
    response: string;
    sources: AssistantSource[];
    context_used: {
        stock_code?: string;
        fund_code?: string;
        intent?: string;
        search_keywords?: string[];
        tools_used?: Array<{
            name: string;
            arguments: Record<string, unknown>;
            success: boolean;
        }>;
    };
    suggested_questions?: string[];
}

export const sendAssistantMessage = async (
    request: AssistantChatRequest
): Promise<AssistantChatResponse> => {
    const response = await api.post('/assistant/chat', request);
    return response.data;
};

export const getAssistantSuggestions = async (
    context: AssistantContext
): Promise<{ suggestions: string[] }> => {
    const response = await api.get('/assistant/suggestions', {
        params: {
            page: context.page,
            stock_code: context.stock?.code,
            stock_name: context.stock?.name,
            fund_code: context.fund?.code,
            fund_name: context.fund?.name,
        }
    });
    return response.data;
};


// --- Stock Professional Features API ---

// Financial Health Diagnosis Types
export interface FinancialIndicator {
    ts_code: string;
    ann_date: string;
    end_date: string;
    roe?: number;
    roe_waa?: number;
    roa?: number;
    npta?: number;
    profit_dedt?: number;
    op_yoy?: number;
    ebt_yoy?: number;
    netprofit_margin?: number;
    grossprofit_margin?: number;
    debt_to_assets?: number;
    current_ratio?: number;
    quick_ratio?: number;
    ocfps?: number;
    bps?: number;
    cfps?: number;
    eps?: number;
}

export interface IncomeStatement {
    ts_code: string;
    ann_date: string;
    end_date: string;
    total_revenue?: number;
    revenue?: number;
    total_cogs?: number;
    oper_cost?: number;
    sell_exp?: number;
    admin_exp?: number;
    fin_exp?: number;
    operate_profit?: number;
    total_profit?: number;
    income_tax?: number;
    n_income?: number;
    n_income_attr_p?: number;
}

export interface FinancialSummary {
    roe?: number;
    netprofit_margin?: number;
    debt_to_assets?: number;
    grossprofit_margin?: number;
    current_ratio?: number;
    quick_ratio?: number;
    eps?: number;
    bps?: number;
}

export interface FinancialData {
    code: string;
    indicators: FinancialIndicator[];
    income: IncomeStatement[];
    balance: Record<string, unknown>[];
    cashflow: Record<string, unknown>[];
    health_score?: number;
    summary: FinancialSummary;
}

// Shareholder Structure Types
export interface HolderInfo {
    ts_code: string;
    ann_date: string;
    end_date: string;
    holder_name: string;
    hold_amount?: number;
    hold_ratio?: number;
    holder_type?: string;
}

export interface HolderPeriod {
    period: string;
    holders: HolderInfo[];
}

export interface HolderNumberTrend {
    ts_code: string;
    ann_date: string;
    end_date: string;
    holder_num?: number;
    holder_num_pct_change?: number;
}

export interface ConcentrationChange {
    value: number;
    trend: 'increasing' | 'decreasing';
    signal: 'positive' | 'negative' | 'neutral';
}

export interface ShareholderData {
    code: string;
    top10_holders: HolderPeriod[];
    holder_number_trend: HolderNumberTrend[];
    concentration_change?: ConcentrationChange;
    latest_period?: string;
}

// Margin/Leverage Fund Types
export interface MarginRecord {
    ts_code: string;
    trade_date: string;
    rzye?: number;      // 融资余额
    rqye?: number;      // 融券余额
    rzmre?: number;     // 融资买入额
    rqmcl?: number;     // 融券卖出量
    rzche?: number;     // 融资偿还额
    rqchl?: number;     // 融券偿还量
}

export interface MarginSummary {
    rzye?: number;
    rqye?: number;
    rzmre?: number;
    rqmcl?: number;
    trade_date: string;
    rzye_5d_change?: number;
}

export interface MarginSentiment {
    financing_ratio: number;
    signal: 'bullish' | 'neutral' | 'bearish';
    description: string;
}

export interface MarginData {
    code: string;
    margin_data: MarginRecord[];
    summary: MarginSummary;
    sentiment?: MarginSentiment;
}

// Event Calendar Types
export interface ForecastRecord {
    ts_code: string;
    ann_date: string;
    end_date: string;
    type?: string;
    p_change_min?: number;
    p_change_max?: number;
    net_profit_min?: number;
    net_profit_max?: number;
    summary?: string;
}

export interface ShareUnlockRecord {
    ts_code: string;
    ann_date: string;
    float_date: string;
    float_share?: number;
    float_ratio?: number;
    holder_name?: string;
    share_type?: string;
}

export interface DividendRecord {
    ts_code: string;
    end_date: string;
    ann_date: string;
    div_proc?: string;
    stk_div?: number;
    stk_bo_rate?: number;
    stk_co_rate?: number;
    cash_div?: number;
    cash_div_tax?: number;
    record_date?: string;
    ex_date?: string;
    pay_date?: string;
}

export interface UpcomingEvent {
    type: 'forecast' | 'unlock' | 'dividend';
    date: string;
    title: string;
    detail: string;
    sentiment: 'positive' | 'negative' | 'warning' | 'neutral';
}

export interface EventData {
    code: string;
    forecasts: ForecastRecord[];
    share_unlock: ShareUnlockRecord[];
    dividends: DividendRecord[];
    upcoming_events: UpcomingEvent[];
}

// Quantitative Signal Types
export interface FactorRecord {
    ts_code: string;
    trade_date: string;
    close?: number;
    macd_dif?: number;
    macd_dea?: number;
    macd?: number;
    kdj_k?: number;
    kdj_d?: number;
    kdj_j?: number;
    rsi_6?: number;
    rsi_12?: number;
    rsi_24?: number;
    boll_upper?: number;
    boll_mid?: number;
    boll_lower?: number;
}

export interface SignalValue {
    signal: 'bullish' | 'bearish' | 'neutral' | 'overbought' | 'oversold';
    value?: number | { upper: number; mid?: number; lower: number; close: number };
}

export interface OverallSignal {
    direction: 'bullish' | 'bearish' | 'neutral';
    strength: 'strong' | 'moderate' | 'weak';
    score: number;
}

export interface ChipSummary {
    winner_rate?: number;
    cost_5pct?: number;
    cost_50pct?: number;
    cost_95pct?: number;
    weight_avg?: number;
}

export interface QuantData {
    code: string;
    factors: FactorRecord[];
    chip_data: Record<string, unknown>[];
    signals: {
        macd: SignalValue;
        kdj: SignalValue;
        rsi: SignalValue;
        boll: SignalValue;
    };
    overall_signal?: OverallSignal;
    chip_summary?: ChipSummary;
}

// API Functions for Stock Professional Features
export const fetchStockFinancials = async (code: string): Promise<FinancialData> => {
    const response = await api.get(`/stocks/${code}/financials`);
    return response.data;
};

export const fetchStockShareholders = async (code: string): Promise<ShareholderData> => {
    const response = await api.get(`/stocks/${code}/shareholders`);
    return response.data;
};

export const fetchStockMargin = async (code: string): Promise<MarginData> => {
    const response = await api.get(`/stocks/${code}/margin`);
    return response.data;
};

export const fetchStockEvents = async (code: string): Promise<EventData> => {
    const response = await api.get(`/stocks/${code}/events`);
    return response.data;
};

export const fetchStockQuant = async (code: string): Promise<QuantData> => {
    const response = await api.get(`/stocks/${code}/quant`);
    return response.data;
};


// --- AI Stock Diagnosis API ---

export interface StockDiagnosis {
    score: number;
    rating: string;
    recommendation: string;
    highlights: string[];
    risks: string[];
    action_advice: string;
    key_focus: string;
}

export interface DiagnosisResponse {
    code: string;
    name: string;
    diagnosis: StockDiagnosis;
    data_timestamp: string;
}

export interface QuantInterpretation {
    pattern: string;
    interpretation: string;
    action: string;
}

export interface QuantInterpretationResponse {
    code: string;
    interpretation: QuantInterpretation;
    timestamp: string;
}

export const fetchStockAIDiagnosis = async (code: string): Promise<DiagnosisResponse> => {
    const response = await api.get(`/stocks/${code}/ai-diagnosis`);
    return response.data;
};

export const fetchQuantAIInterpretation = async (code: string): Promise<QuantInterpretationResponse> => {
    const response = await api.get(`/stocks/${code}/quant/ai-interpret`);
    return response.data;
};


// ====================================================================
// Fund Analysis API - Diagnosis, Risk Metrics, Comparison
// ====================================================================

// --- Fund Diagnosis ---

export interface FundDiagnosisDimension {
    name: string;
    name_en: string;
    score: number;
    max: number;
}

export interface FundAnalysisSummary {
    strengths: string[];
    weaknesses: string[];
    recommendation: string;
}

export interface FundDiagnosisResponse {
    fund_code: string;
    score: number;
    grade: string;
    dimensions: FundDiagnosisDimension[];
    radar_data: number[];
    analysis_summary: FundAnalysisSummary;
    computed_at: string;
    error?: string;
}

export const fetchFundDiagnosis = async (code: string, forceRefresh = false): Promise<FundDiagnosisResponse> => {
    const response = await api.get(`/funds/${code}/diagnosis`, {
        params: { force_refresh: forceRefresh }
    });
    return response.data;
};


// --- Fund Risk Metrics ---

export interface RiskMetricValue {
    value: number | null;
    rating?: string;
    description?: string;
    error?: string;
}

export interface MaxDrawdownValue extends RiskMetricValue {
    peak_date?: string;
    trough_date?: string;
    recovery_date?: string | null;
    recovery_days?: number | null;
}

export interface FundRiskMetricsResponse {
    sharpe_ratio: RiskMetricValue;
    max_drawdown: MaxDrawdownValue;
    annual_volatility: RiskMetricValue;
    calmar_ratio: number | null;
    sortino_ratio: RiskMetricValue;
    annual_return: RiskMetricValue;
    total_return: RiskMetricValue;
    var_95: RiskMetricValue;
    var_99: RiskMetricValue;
    win_rate: RiskMetricValue;
    period?: {
        start_date: string;
        end_date: string;
        trading_days: number;
    };
    computed_at: string;
    error?: string;
}

export const fetchFundRiskMetrics = async (code: string): Promise<FundRiskMetricsResponse> => {
    const response = await api.get(`/funds/${code}/risk-metrics`);
    return response.data;
};


// --- Fund Drawdown History ---

export interface DrawdownPeriod {
    start_date: string;
    trough_date: string;
    recovery_date: string | null;
    drawdown: number;
    duration: number;
    recovery_days: number | null;
    total_days?: number;
    is_ongoing?: boolean;
}

export interface DrawdownSeriesPoint {
    date: string;
    drawdown: number;
    value: number;
}

export interface FundDrawdownResponse {
    current_drawdown: number;
    is_in_drawdown: boolean;
    max_drawdown: {
        value: number;
        period: DrawdownPeriod | null;
    };
    periods: DrawdownPeriod[];
    statistics: {
        total_periods: number;
        avg_drawdown: number;
        avg_duration_days: number;
        avg_recovery_days: number | null;
    };
    drawdown_series: DrawdownSeriesPoint[];
    computed_at: string;
    error?: string;
}

export const fetchFundDrawdownHistory = async (code: string, threshold = 0.05): Promise<FundDrawdownResponse> => {
    const response = await api.get(`/funds/${code}/drawdown-history`, {
        params: { threshold }
    });
    return response.data;
};


// --- Advanced Fund Comparison (up to 10 funds) ---

export interface FundNavCurve {
    name: string;
    data: Array<{ date: string; value: number; original_value?: number }>;
}

export interface FundReturnComparison {
    code: string;
    name: string;
    '1m'?: number;
    '3m'?: number;
    '6m'?: number;
    '1y'?: number;
    '3y'?: number;
}

export interface FundRiskComparison {
    code: string;
    name: string;
    sharpe_ratio: number;
    max_drawdown: number;
    annual_volatility: number;
    calmar_ratio: number;
    annual_return: number;
}

export interface CommonStock {
    code: string;
    name: string;
    held_by: string[];
    count: number;
}

export interface FundComparisonRankingItem {
    code: string;
    name: string;
    rank: number;
    score: number;
    components: {
        return: number;
        sharpe: number;
        max_drawdown: number;
    };
}

export interface FundComparisonResponse {
    funds: Array<{ code: string; name: string }>;
    nav_comparison: {
        curves: Record<string, FundNavCurve>;
        date_range: { start: string; end: string } | null;
    };
    return_comparison: {
        returns: Record<string, FundReturnComparison>;
        periods: string[];
        rankings: Record<string, string[]>;
    };
    risk_comparison: {
        metrics: Record<string, FundRiskComparison>;
        rankings: Record<string, string[]>;
    };
    holdings_overlap: {
        overlap_matrix: Record<string, Record<string, number>>;
        common_stocks: CommonStock[];
        total_unique_stocks?: number;
        message?: string;
    };
    ranking: {
        ranking: FundComparisonRankingItem[];
        methodology: string;
    };
    computed_at: string;
}

export const compareFundsAdvanced = async (codes: string[]): Promise<FundComparisonResponse> => {
    const response = await api.post('/funds/compare', { codes });
    return response.data;
};


// ==================== Fund Batch Estimation API ====================

export interface BatchFundEstimation {
    code: string;
    name: string | null;
    estimated_nav: number | null;
    estimated_change_pct: number | null;
    prev_nav: number | null;
    prev_nav_date: string | null;
    estimation_time: string | null;
    not_available?: boolean;
}

export interface BatchEstimationResponse {
    estimations: BatchFundEstimation[];
    is_trading: boolean;
    cache_ttl: number;
    timestamp: string;
}

/**
 * Fetch batch fund estimations for multiple funds.
 * @param codes Optional array of fund codes. If empty, returns estimations for all user's funds.
 */
export const fetchBatchEstimation = async (codes?: string[]): Promise<BatchEstimationResponse> => {
    const params = codes && codes.length > 0 ? { codes: codes.join(',') } : {};
    const response = await api.get('/funds/batch-estimation', { params });
    return response.data;
};


// ====================================================================
// Portfolio Management API
// ====================================================================

export interface PortfolioPosition {
    id: number;
    fund_code: string;
    fund_name?: string;
    shares: number;
    cost_basis: number;
    purchase_date: string;
    notes?: string;
    current_nav?: number;
    position_cost: number;
    position_value: number;
    pnl: number;
    pnl_pct: number;
    created_at?: string;
    updated_at?: string;
}

export interface PortfolioAllocation {
    fund_code: string;
    fund_name?: string;
    value: number;
    weight: number;
}

export interface PortfolioSummaryResponse {
    total_value: number;
    total_cost: number;
    total_pnl: number;
    total_pnl_pct: number;
    positions: Array<{
        fund_code: string;
        fund_name?: string;
        shares: number;
        cost_basis: number;
        current_nav?: number;
        position_cost: number;
        position_value: number;
        pnl: number;
        pnl_pct: number;
        purchase_date?: string;
    }>;
    allocation: PortfolioAllocation[];
    position_count: number;
    computed_at: string;
}

export interface ConcentrationWarning {
    stock_code: string;
    stock_name: string;
    weight: number;
    threshold: number;
    message: string;
}

export interface AggregatedHolding {
    stock_code: string;
    stock_name: string;
    total_weight: number;
    fund_count: number;
    fund_sources: Array<{
        fund_code: string;
        weight_in_fund: number;
        effective_weight: number;
    }>;
}

export interface PortfolioOverlapResponse {
    aggregated_holdings: AggregatedHolding[];
    total_unique_stocks: number;
    concentration_warnings: ConcentrationWarning[];
    overlap_matrix: Record<string, Record<string, number>>;
    industry_breakdown?: Array<{ industry: string; weight: number }>;
    computed_at: string;
    message?: string;
}

export interface PositionCreateData {
    fund_code: string;
    fund_name?: string;
    shares: number;
    cost_basis: number;
    purchase_date: string;
    notes?: string;
}

export const fetchPortfolioPositions = async (): Promise<{ positions: PortfolioPosition[] }> => {
    const response = await api.get('/portfolio/positions');
    return response.data;
};

export const fetchPortfolioSummary = async (): Promise<PortfolioSummaryResponse> => {
    const response = await api.get('/portfolio/summary');
    return response.data;
};

export const fetchPortfolioOverlap = async (): Promise<PortfolioOverlapResponse> => {
    const response = await api.get('/portfolio/overlap');
    return response.data;
};

export const createPosition = async (data: PositionCreateData): Promise<{ id: number; message: string }> => {
    const response = await api.post('/portfolio/positions', data);
    return response.data;
};

export const updatePosition = async (positionId: number, data: Partial<PositionCreateData>): Promise<{ message: string }> => {
    const response = await api.put(`/portfolio/positions/${positionId}`, data);
    return response.data;
};

export const deletePosition = async (positionId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/portfolio/positions/${positionId}`);
    return response.data;
};


// ====================================================================
// New Multi-Portfolio Management API
// ====================================================================

// --- Types ---

export interface Portfolio {
    id: number;
    user_id: number;
    name: string;
    description?: string;
    benchmark_code: string;
    is_default: boolean;
    created_at: string;
    updated_at: string;
}

export interface UnifiedPosition {
    id: number;
    portfolio_id: number;
    user_id: number;
    asset_type: 'stock' | 'fund';
    asset_code: string;
    asset_name?: string;
    total_shares: number;
    average_cost: number;
    total_cost: number;
    current_price?: number | null;
    current_value?: number | null;
    unrealized_pnl?: number | null;
    unrealized_pnl_pct?: number | null;
    sector?: string;
    notes?: string;
    created_at: string;
    updated_at: string;
}

export interface Transaction {
    id: number;
    position_id?: number;
    portfolio_id: number;
    user_id: number;
    asset_type: string;
    asset_code: string;
    asset_name?: string;
    transaction_type: 'buy' | 'sell' | 'dividend' | 'split' | 'transfer_in' | 'transfer_out';
    shares: number;
    price: number;
    total_amount: number;
    fees: number;
    transaction_date: string;
    notes?: string;
    created_at: string;
}

export interface TransactionCreateData {
    asset_type: string;
    asset_code: string;
    asset_name?: string;
    transaction_type: string;
    shares: number;
    price: number;
    total_amount?: number;
    fees?: number;
    transaction_date: string;
    notes?: string;
}

export interface PortfolioCreateData {
    name: string;
    description?: string;
    benchmark_code?: string;
    is_default?: boolean;
}

export interface UnifiedPositionCreateData {
    asset_type: string;
    asset_code: string;
    asset_name?: string;
    total_shares: number;
    average_cost: number;
    sector?: string;
    notes?: string;
}

export interface DIPPlan {
    id: number;
    portfolio_id: number;
    user_id: number;
    asset_type: 'stock' | 'fund';
    asset_code: string;
    asset_name?: string;
    amount_per_period: number;
    frequency: 'daily' | 'weekly' | 'biweekly' | 'monthly';
    execution_day?: number;
    start_date: string;
    end_date?: string;
    is_active: boolean;
    total_invested: number;
    total_shares: number;
    execution_count: number;
    last_executed_at?: string;
    next_execution_date?: string;
    notes?: string;
    created_at: string;
    updated_at: string;
}

export interface DIPPlanCreateData {
    asset_type: string;
    asset_code: string;
    asset_name?: string;
    amount_per_period: number;
    frequency: string;
    execution_day?: number;
    start_date: string;
    end_date?: string;
    is_active?: boolean;
    notes?: string;
}

export interface PortfolioAlert {
    id: number;
    portfolio_id: number;
    user_id: number;
    alert_type: string;
    severity: 'info' | 'warning' | 'critical';
    title: string;
    message: string;
    details?: Record<string, any>;
    is_read: boolean;
    is_dismissed: boolean;
    triggered_at: string;
    read_at?: string;
    dismissed_at?: string;
}

export interface PortfolioDiagnosisDimension {
    name: string;
    score: number;
    max: number;
}

export interface PortfolioDiagnosis {
    portfolio: Portfolio;
    total_score: number;
    max_score: number;
    grade: string;
    dimensions: PortfolioDiagnosisDimension[];
    recommendations: string[];
    analyzed_at: string;
}

export interface RebalanceSuggestion {
    asset_code: string | null;
    asset_name: string;
    action: string;
    reason: string;
    priority: string;
}

export interface PortfolioSummaryNew {
    portfolio: Portfolio;
    total_value: number;
    total_cost: number;
    total_pnl: number;
    total_pnl_pct: number;
    positions_count: number;
    positions: UnifiedPosition[];
    allocation: {
        by_type: Record<string, number>;
        by_sector: Record<string, number>;
    };
}

export interface PortfolioSnapshot {
    id: number;
    portfolio_id: number;
    snapshot_date: string;
    total_value: number;
    total_cost: number;
    daily_pnl?: number;
    daily_pnl_pct?: number;
    cumulative_pnl?: number;
    cumulative_pnl_pct?: number;
    benchmark_value?: number;
    benchmark_return_pct?: number;
    allocation?: Record<string, any>;
}

// --- Portfolio CRUD ---

export const fetchPortfolios = async (): Promise<{ portfolios: Portfolio[] }> => {
    const response = await api.get('/portfolios');
    return response.data;
};

export const fetchDefaultPortfolio = async (): Promise<Portfolio> => {
    const response = await api.get('/portfolios/default');
    return response.data;
};

export const fetchPortfolioById = async (portfolioId: number): Promise<Portfolio> => {
    const response = await api.get(`/portfolios/${portfolioId}`);
    return response.data;
};

export const createPortfolio = async (data: PortfolioCreateData): Promise<{ id: number; message: string }> => {
    const response = await api.post('/portfolios', data);
    return response.data;
};

export const updatePortfolio = async (portfolioId: number, data: Partial<PortfolioCreateData>): Promise<{ message: string }> => {
    const response = await api.put(`/portfolios/${portfolioId}`, data);
    return response.data;
};

export const deletePortfolio = async (portfolioId: number): Promise<{ message: string }> => {
    const response = await api.delete(`/portfolios/${portfolioId}`);
    return response.data;
};

export const setDefaultPortfolio = async (portfolioId: number): Promise<{ message: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/set-default`);
    return response.data;
};

// --- Unified Positions ---

export const fetchPortfolioPositionsNew = async (
    portfolioId: number,
    assetType?: string
): Promise<{ positions: UnifiedPosition[]; portfolio: Portfolio }> => {
    const params: Record<string, string> = {};
    if (assetType) params.asset_type = assetType;
    const response = await api.get(`/portfolios/${portfolioId}/positions`, { params });
    return response.data;
};

export const createUnifiedPosition = async (
    portfolioId: number,
    data: UnifiedPositionCreateData
): Promise<{ id: number; message: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/positions`, data);
    return response.data;
};

export interface UnifiedPositionUpdateData {
    asset_name?: string;
    total_shares?: number;
    average_cost?: number;
    sector?: string;
    notes?: string;
}

export const updateUnifiedPosition = async (
    portfolioId: number,
    positionId: number,
    data: UnifiedPositionUpdateData
): Promise<{ message: string }> => {
    const response = await api.put(`/portfolios/${portfolioId}/positions/${positionId}`, data);
    return response.data;
};

export const deleteUnifiedPosition = async (
    portfolioId: number,
    positionId: number
): Promise<{ message: string }> => {
    const response = await api.delete(`/portfolios/${portfolioId}/positions/${positionId}`);
    return response.data;
};

// --- Transactions ---

export const fetchTransactions = async (
    portfolioId: number,
    assetType?: string,
    limit: number = 100,
    offset: number = 0
): Promise<{ transactions: Transaction[]; portfolio: Portfolio }> => {
    const params: Record<string, any> = { limit, offset };
    if (assetType) params.asset_type = assetType;
    const response = await api.get(`/portfolios/${portfolioId}/transactions`, { params });
    return response.data;
};

export const createTransaction = async (
    portfolioId: number,
    data: TransactionCreateData
): Promise<{ id: number; message: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/transactions`, data);
    return response.data;
};

export const deleteTransaction = async (
    portfolioId: number,
    transactionId: number
): Promise<{ message: string }> => {
    const response = await api.delete(`/portfolios/${portfolioId}/transactions/${transactionId}`);
    return response.data;
};

export const recalculatePosition = async (
    portfolioId: number,
    positionId: number
): Promise<{ position: UnifiedPosition; message: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/positions/${positionId}/recalculate`);
    return response.data;
};

// --- Portfolio Analysis ---

export const fetchPortfolioSummaryNew = async (portfolioId: number): Promise<PortfolioSummaryNew> => {
    const response = await api.get(`/portfolios/${portfolioId}/summary`);
    return response.data;
};

export const fetchPortfolioPerformance = async (
    portfolioId: number,
    startDate?: string,
    endDate?: string
): Promise<{ portfolio: Portfolio; snapshots: PortfolioSnapshot[] }> => {
    const params: Record<string, string> = {};
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const response = await api.get(`/portfolios/${portfolioId}/performance`, { params });
    return response.data;
};

export const fetchPortfolioRiskMetrics = async (portfolioId: number): Promise<any> => {
    const response = await api.get(`/portfolios/${portfolioId}/risk-metrics`);
    return response.data;
};

export const fetchPortfolioBenchmark = async (
    portfolioId: number,
    days: number = 30
): Promise<any> => {
    const response = await api.get(`/portfolios/${portfolioId}/benchmark`, { params: { days } });
    return response.data;
};

// --- Portfolio AI ---

export const fetchPortfolioDiagnosis = async (portfolioId: number): Promise<PortfolioDiagnosis> => {
    const response = await api.get(`/portfolios/${portfolioId}/ai-diagnosis`);
    return response.data;
};

export const fetchRebalanceSuggestions = async (
    portfolioId: number,
    riskPreference: string = 'moderate'
): Promise<{ portfolio: Portfolio; current_allocation: Record<string, number>; suggestions: RebalanceSuggestion[]; generated_at: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/ai-rebalance`, { risk_preference: riskPreference });
    return response.data;
};

export const portfolioAIChat = async (
    portfolioId: number,
    message: string,
    context?: Record<string, any>
): Promise<any> => {
    const response = await api.post(`/portfolios/${portfolioId}/ai-chat`, { message, context });
    return response.data;
};

// --- Alerts ---

export const fetchPortfolioAlerts = async (
    portfolioId: number,
    unreadOnly: boolean = false,
    limit: number = 50
): Promise<{ alerts: PortfolioAlert[]; unread_count: number }> => {
    const response = await api.get(`/portfolios/${portfolioId}/alerts`, {
        params: { unread_only: unreadOnly, limit }
    });
    return response.data;
};

export const fetchAllAlerts = async (
    unreadOnly: boolean = false,
    limit: number = 50
): Promise<{ alerts: PortfolioAlert[]; unread_count: number }> => {
    const response = await api.get('/alerts', {
        params: { unread_only: unreadOnly, limit }
    });
    return response.data;
};

export const markAlertRead = async (alertId: number): Promise<{ message: string }> => {
    const response = await api.post(`/alerts/${alertId}/read`);
    return response.data;
};

export const dismissAlertApi = async (alertId: number): Promise<{ message: string }> => {
    const response = await api.post(`/alerts/${alertId}/dismiss`);
    return response.data;
};

// --- DIP Plans ---

export const fetchDIPPlans = async (
    portfolioId: number,
    activeOnly: boolean = false
): Promise<{ dip_plans: DIPPlan[]; portfolio: Portfolio }> => {
    const response = await api.get(`/portfolios/${portfolioId}/dip-plans`, {
        params: { active_only: activeOnly }
    });
    return response.data;
};

export const createDIPPlan = async (
    portfolioId: number,
    data: DIPPlanCreateData
): Promise<{ id: number; message: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/dip-plans`, data);
    return response.data;
};

export const fetchDIPPlan = async (
    portfolioId: number,
    planId: number
): Promise<DIPPlan> => {
    const response = await api.get(`/portfolios/${portfolioId}/dip-plans/${planId}`);
    return response.data;
};

export const updateDIPPlan = async (
    portfolioId: number,
    planId: number,
    data: Partial<DIPPlanCreateData>
): Promise<{ message: string }> => {
    const response = await api.put(`/portfolios/${portfolioId}/dip-plans/${planId}`, data);
    return response.data;
};

export const deleteDIPPlan = async (
    portfolioId: number,
    planId: number
): Promise<{ message: string }> => {
    const response = await api.delete(`/portfolios/${portfolioId}/dip-plans/${planId}`);
    return response.data;
};

export const executeDIPPlan = async (
    portfolioId: number,
    planId: number,
    price?: number
): Promise<{ message: string; transaction_id: number; shares: number; price: number }> => {
    const params: Record<string, any> = {};
    if (price) params.price = price;
    const response = await api.post(`/portfolios/${portfolioId}/dip-plans/${planId}/execute`, null, { params });
    return response.data;
};

// --- Data Migration ---

export const migrateOldPositions = async (portfolioId: number): Promise<{ message: string; migrated_count: number }> => {
    const response = await api.post(`/portfolios/${portfolioId}/migrate-positions`);
    return response.data;
};

// --- Portfolio Advanced Analytics (Institutional-Grade) ---

// Stress Test Types
export interface StressTestScenario {
    id: string;
    name: string;
    description: string;
    category: string;
    icon: string;
}

export interface StressTestSlider {
    id: string;
    name: string;
    min: number;
    max: number;
    step: number;
    default: number;
    unit: string;
    description: string;
}

export interface StressTestLoser {
    code: string;
    name: string;
    current_value: number;
    weight: number;
    impact_pct: number;
    projected_change: number;
    projected_value: number;
}

export interface StressTestResult {
    scenario: Record<string, any>;
    scenario_name?: string;
    portfolio_value: number;
    projected_pnl: number;
    projected_pnl_pct: number;
    projected_value: number;
    var_95: number;
    var_95_pct: number;
    cvar_95: number;
    top_losers: StressTestLoser[];
    top_gainers: StressTestLoser[];
    position_impacts: StressTestLoser[];
    risk_level: string;
    computed_at: string;
}

// Correlation Types
export interface CorrelationDataPoint {
    x: number;
    y: number;
    value: number;
    row_code: string;
    col_code: string;
    row_name: string;
    col_name: string;
}

export interface HighCorrelationPair {
    pair: [string, string];
    pair_names: [string, string];
    correlation: number;
    risk_level: string;
    message: string;
}

export interface CorrelationInterpretation {
    type: string;
    title: string;
    content: string;
    severity: string;
}

export interface CorrelationResult {
    matrix: CorrelationDataPoint[];
    labels: string[];
    codes: string[];
    size: number;
    high_correlations: HighCorrelationPair[];
    diversification_score: number;
    diversification_status: string;
    interpretations: CorrelationInterpretation[];
    analysis_days: number;
    computed_at: string;
    message?: string;
}

// Signal Types
export interface SignalFactor {
    name: string;
    signal: string;
    weight: number;
    details: string;
}

export interface PortfolioSignal {
    code: string;
    name: string;
    signal_type: 'opportunity' | 'risk' | 'neutral';
    strength: number;
    reasons: string[];
    details: Record<string, any>;
    summary: string;
    action_suggestion: string;
}

export interface PortfolioSignalDetail extends PortfolioSignal {
    explanation: string;
    confidence: 'high' | 'medium' | 'low';
    factors: SignalFactor[];
    generated_at: string;
}

export interface SignalsResult {
    signals: PortfolioSignal[];
    counts: {
        opportunity: number;
        risk: number;
        neutral: number;
    };
    total: number;
    generated_at: string;
}

// Risk Summary Types
export interface RiskSummary {
    beta: number | null;
    beta_status: string;
    sharpe_ratio: number | null;
    sharpe_status: string;
    var_95: number | null;
    var_95_pct: number | null;
    volatility: number | null;
    max_drawdown: number | null;
    health_score: number;
    health_grade: string;
    total_value: number;
    position_count: number;
    analysis_days: number;
    message?: string;
    computed_at: string;
}

// Sparkline Types
export interface SparklineData {
    portfolio_id: number;
    values: number[];
    dates: string[];
    change: number;
    change_pct: number;
    trend: 'up' | 'down' | 'flat';
    days: number;
}

// Stress Test APIs
export const fetchStressTestScenarios = async (portfolioId: number): Promise<{
    scenarios: StressTestScenario[];
    sliders: StressTestSlider[];
}> => {
    const response = await api.get(`/portfolios/${portfolioId}/stress-test/scenarios`);
    return response.data;
};

export const runStressTest = async (
    portfolioId: number,
    params: {
        scenario_type?: string;
        scenario?: Record<string, number>;
    }
): Promise<StressTestResult> => {
    const response = await api.post(`/portfolios/${portfolioId}/stress-test`, params);
    return response.data;
};

// Correlation API
export const fetchPortfolioCorrelation = async (
    portfolioId: number,
    days: number = 90
): Promise<CorrelationResult> => {
    const response = await api.get(`/portfolios/${portfolioId}/correlation`, {
        params: { days }
    });
    return response.data;
};

// Correlation AI Explanation API
export const fetchCorrelationExplanation = async (
    portfolioId: number,
    correlationData: CorrelationResult
): Promise<{ explanation: string }> => {
    const response = await api.post(`/portfolios/${portfolioId}/correlation/explain`, {
        correlation_data: correlationData
    });
    return response.data;
};

// Signals APIs
export const fetchPortfolioSignals = async (portfolioId: number): Promise<SignalsResult> => {
    const response = await api.get(`/portfolios/${portfolioId}/signals`);
    return response.data;
};

export const fetchSignalDetail = async (
    portfolioId: number,
    assetCode: string
): Promise<PortfolioSignalDetail> => {
    const response = await api.get(`/portfolios/${portfolioId}/signals/${assetCode}`);
    return response.data;
};

// Risk Summary API
export const fetchRiskSummary = async (portfolioId: number): Promise<RiskSummary> => {
    const response = await api.get(`/portfolios/${portfolioId}/risk-summary`);
    return response.data;
};

// Sparkline API
export const fetchPortfolioSparkline = async (
    portfolioId: number,
    days: number = 7
): Promise<SparklineData> => {
    const response = await api.get(`/portfolios/${portfolioId}/sparkline`, {
        params: { days }
    });
    return response.data;
};


// ====================================================================
// Returns Analysis API
// ====================================================================

// Returns Summary Types
export interface ReturnsDayInfo {
    date: string;
    pnl: number;
    pnl_pct: number;
}

export interface ReturnsSummary {
    total_pnl: number;
    total_pnl_pct: number;
    annualized_return: number;
    today_pnl: number;
    today_pnl_pct: number;
    week_pnl: number;
    week_pnl_pct: number;
    month_pnl: number;
    month_pnl_pct: number;
    max_drawdown: number;
    max_drawdown_pct: number;
    win_rate: number;
    profitable_days: number;
    total_trading_days: number;
    best_day: ReturnsDayInfo | null;
    worst_day: ReturnsDayInfo | null;
}

// Returns Calendar Types
export interface ReturnsCalendarEntry {
    date: string;
    pnl: number;
    pnl_pct: number;
    is_trading_day?: boolean;
}

export interface ReturnsCalendarStats {
    total_periods: number;
    profitable_periods: number;
    loss_periods: number;
    best_period: { date: string; pnl_pct: number } | null;
    worst_period: { date: string; pnl_pct: number } | null;
}

export interface ReturnsCalendarData {
    view: 'day' | 'month' | 'year';
    data: ReturnsCalendarEntry[];
    stats: ReturnsCalendarStats;
}

// Daily Returns Detail Types
export interface DailyPositionReturn {
    position_id: number;
    asset_code: string;
    asset_name: string;
    asset_type: 'stock' | 'fund';
    shares: number;
    yesterday_nav: number | null;
    yesterday_date?: string;
    today_nav: number | null;
    today_date?: string;
    nav_change: number | null;
    nav_change_pct: number | null;
    position_pnl: number | null;
    position_pnl_pct: number | null;
    contribution_pct: number;
    market_value: number;
    weight_pct: number;
    is_pending?: boolean;
}

export interface DailyReturnsDetail {
    date: string;
    total_pnl: number;
    total_pnl_pct: number;
    positions: DailyPositionReturn[];
    top_contributors: DailyPositionReturn[];
    top_detractors: DailyPositionReturn[];
    has_pending?: boolean;
}

// Returns Explanation Types
export interface ReturnsExplanation {
    date: string;
    explanation: string;
    generated_at: string;
}

// Returns Summary API
export const fetchReturnsSummary = async (portfolioId: number): Promise<ReturnsSummary> => {
    const response = await api.get(`/portfolios/${portfolioId}/returns/summary`);
    return response.data;
};

// Returns Calendar API
export const fetchReturnsCalendar = async (
    portfolioId: number,
    view: 'day' | 'month' | 'year' = 'day',
    startDate?: string,
    endDate?: string
): Promise<ReturnsCalendarData> => {
    const response = await api.get(`/portfolios/${portfolioId}/returns/calendar`, {
        params: { view, start_date: startDate, end_date: endDate }
    });
    return response.data;
};

// Daily Returns Detail API
export const fetchDailyReturnsDetail = async (
    portfolioId: number,
    date?: string
): Promise<DailyReturnsDetail> => {
    const response = await api.get(`/portfolios/${portfolioId}/returns/daily-detail`, {
        params: { date }
    });
    return response.data;
};

// Returns Explanation API
export const fetchReturnsExplanation = async (
    portfolioId: number,
    date?: string,
    includeMarketContext: boolean = true
): Promise<ReturnsExplanation> => {
    const response = await api.post(`/portfolios/${portfolioId}/returns/explain`, {
        date,
        include_market_context: includeMarketContext
    });
    return response.data;
};


// ====================================================================
// AI-Enhanced Stress Test API (Phase 1 & 2)
// ====================================================================

// AI Scenario Types
export interface AIScenario {
    id: string;
    name: string;
    parameters: {
        interest_rate_change_bp: number;
        fx_change_pct: number;
        index_change_pct: number;
        oil_change_pct: number;
    };
    reasoning: string;
    confidence: 'high' | 'medium' | 'low';
    generated_at: string;
    source: 'ai' | 'fallback';
}

export interface MarketContext {
    indices: Record<string, any>;
    usd_cny: number | null;
    timestamp: string;
}

export interface AIScenarioResponse {
    scenario: AIScenario;
    market_context: MarketContext;
    error?: string;
}

// Stress Test Chat Types
export interface StressTestChatMessage {
    role: 'user' | 'assistant';
    content: string;
}

export interface StressTestChatResponse {
    response: string;
    stress_result: StressTestResult | null;
    scenario_used: Record<string, number> | null;
    suggested_followups: string[];
}

// AI Scenario Generation API
export const generateAIScenario = async (
    portfolioId: number,
    category: string
): Promise<AIScenarioResponse> => {
    const response = await api.post(`/portfolios/${portfolioId}/stress-test/ai-scenarios`, {
        category
    });
    return response.data;
};

// Stress Test Chat API
export const stressTestChat = async (
    portfolioId: number,
    message: string,
    history: StressTestChatMessage[] = []
): Promise<StressTestChatResponse> => {
    const response = await api.post(`/portfolios/${portfolioId}/stress-test/chat`, {
        message,
        history
    });
    return response.data;
};


// ====================================================================
// Recommendation Engine V2 API - Quantitative Factor-Based
// ====================================================================

// V2 Factor Data Types
export interface StockFactors {
    // Technical factors
    consolidation_score?: number;
    volume_precursor?: number;
    ma_convergence?: number;
    rsi?: number;
    macd_signal?: string;
    bollinger_position?: number;
    // Fundamental factors
    roe?: number;
    roe_yoy?: number;
    gross_margin?: number;
    ocf_to_profit?: number;
    peg_ratio?: number;
    pe_percentile?: number;
    pb_percentile?: number;
    revenue_cagr_3y?: number;
    profit_cagr_3y?: number;
    // Sentiment/Money flow factors
    main_inflow_5d?: number;
    main_inflow_trend?: string;
    north_inflow_5d?: number;
    retail_outflow_ratio?: number;
    is_accumulation?: boolean;
    // Scores
    short_term_score?: number;
    long_term_score?: number;
    quality_score?: number;
    growth_score?: number;
    valuation_score?: number;
    price?: number;
}

export interface FundFactors {
    // Risk factors
    sharpe_20d?: number;
    sharpe_1y?: number;
    sortino_1y?: number;
    calmar_1y?: number;
    max_drawdown_1y?: number;
    volatility_60d?: number;
    volatility_1y?: number;
    // Performance factors
    return_1w?: number;
    return_1m?: number;
    return_3m?: number;
    return_6m?: number;
    return_1y?: number;
    return_rank_1m?: number;
    return_rank_1y?: number;
    // Manager factors
    manager_tenure_years?: number;
    manager_alpha_bull?: number;
    manager_alpha_bear?: number;
    style_consistency?: number;
    fund_size?: number;
    // Scores
    short_term_score?: number;
    long_term_score?: number;
    momentum_score?: number;
    alpha_score?: number;
}

export interface RecommendationStockV2 {
    code: string;
    name: string;
    industry?: string;
    score: number;
    factors: StockFactors;
    explanation?: string;
    catalysts?: string[];
    risks?: string[];
    strategy?: string;
}

export interface RecommendationFundV2 {
    code: string;
    name: string;
    type?: string;
    score: number;
    factors: FundFactors;
    explanation?: string;
    catalysts?: string[];
    risks?: string[];
    strategy?: string;
}

export interface RecommendationResultV2 {
    mode: string;
    generated_at: string;
    trade_date: string;
    engine_version: string;
    short_term?: {
        stocks: RecommendationStockV2[];
        funds: RecommendationFundV2[];
        market_view?: string;
    };
    long_term?: {
        stocks: RecommendationStockV2[];
        funds: RecommendationFundV2[];
        macro_view?: string;
    };
    metadata?: {
        factor_computation_time?: number;
        explanation_time?: number;
        total_time?: number;
    };
}

export interface RecommendationRequestV2 {
    mode: 'short' | 'long' | 'all';
    stock_limit?: number;
    fund_limit?: number;
    use_llm?: boolean;
}

export interface FactorStatus {
    stock_factors: {
        count: number;
        latest_date?: string;
    };
    fund_factors: {
        count: number;
        latest_date?: string;
    };
    last_computation?: string;
}

export interface RecommendationPerformance {
    rec_type: string;
    total_count: number;
    hit_target_count: number;
    hit_stop_count: number;
    avg_return: number;
    win_rate: number;
}

// V2 Generate Recommendations
export const generateRecommendationsV2 = async (
    request: RecommendationRequestV2
): Promise<RecommendationResultV2> => {
    const response = await api.post('/recommend/generate', request);
    return response.data;
};

// V2 Get Short-Term Stocks
export const getShortTermStocksV2 = async (
    limit: number = 20,
    tradeDate?: string
): Promise<{ stocks: RecommendationStockV2[]; trade_date: string }> => {
    const params: Record<string, any> = { limit };
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get('/recommend/stocks/short', { params });
    return response.data;
};

// V2 Get Long-Term Stocks
export const getLongTermStocksV2 = async (
    limit: number = 20,
    tradeDate?: string
): Promise<{ stocks: RecommendationStockV2[]; trade_date: string }> => {
    const params: Record<string, any> = { limit };
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get('/recommend/stocks/long', { params });
    return response.data;
};

// V2 Get Short-Term Funds
export const getShortTermFundsV2 = async (
    limit: number = 20,
    tradeDate?: string
): Promise<{ funds: RecommendationFundV2[]; trade_date: string }> => {
    const params: Record<string, any> = { limit };
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get('/recommend/funds/short', { params });
    return response.data;
};

// V2 Get Long-Term Funds
export const getLongTermFundsV2 = async (
    limit: number = 20,
    tradeDate?: string
): Promise<{ funds: RecommendationFundV2[]; trade_date: string }> => {
    const params: Record<string, any> = { limit };
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get('/recommend/funds/long', { params });
    return response.data;
};

// V2 Analyze Single Stock
export const analyzeStockV2 = async (
    code: string,
    tradeDate?: string
): Promise<{
    code: string;
    short_term: RecommendationStockV2;
    long_term: RecommendationStockV2;
    trade_date: string;
}> => {
    const params: Record<string, string> = {};
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get(`/recommend/analyze/stock/${code}`, { params });
    return response.data;
};

// V2 Analyze Single Fund
export const analyzeFundV2 = async (
    code: string,
    tradeDate?: string
): Promise<{
    code: string;
    short_term: RecommendationFundV2;
    long_term: RecommendationFundV2;
    trade_date: string;
}> => {
    const params: Record<string, string> = {};
    if (tradeDate) params.trade_date = tradeDate;
    const response = await api.get(`/recommend/analyze/fund/${code}`, { params });
    return response.data;
};

// V2 Get Recommendation Performance
export const getRecommendationPerformanceV2 = async (
    recType?: string,
    startDate?: string,
    endDate?: string
): Promise<{ performance: RecommendationPerformance[] }> => {
    const params: Record<string, string> = {};
    if (recType) params.rec_type = recType;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    const response = await api.get('/recommend/performance', { params });
    return response.data;
};

// V2 Trigger Factor Computation
export const computeFactorsV2 = async (
    targetDate?: string
): Promise<{
    message: string;
    stocks_computed: number;
    funds_computed: number;
    computation_time: number;
}> => {
    const data: Record<string, string> = {};
    if (targetDate) data.target_date = targetDate;
    const response = await api.post('/recommend/compute-factors', data);
    return response.data;
};

// V2 Get Factor Status
export const getFactorStatusV2 = async (): Promise<FactorStatus> => {
    const response = await api.get('/recommend/factor-status');
    return response.data;
};
