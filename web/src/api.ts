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
  tavily_api_key_masked: string;
}

export interface SettingsUpdate {
  llm_provider?: string;
  gemini_api_key?: string;
  openai_api_key?: string;
  tavily_api_key?: string;
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

export const fetchSettings = async (): Promise<SettingsData> => {
  const response = await api.get('/settings');
  return response.data;
};

export const saveSettings = async (settings: SettingsUpdate): Promise<void> => {
  await api.post('/settings', settings);
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
    stop_loss?: number;
    expected_return?: string;
    recommendation_score: number;
    investment_logic?: string;
    risk_factors?: string[];
    confidence?: string;
    holding_period?: string;
    market_cap?: number;
    pe?: number;
    pb?: number;
    main_net_inflow?: number;
    volume_ratio?: number;
    score?: number;
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
    confidence?: string;
    holding_period?: string;
    score?: number;
}

export interface RecommendationResult {
    mode: string;
    generated_at: string;
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
    };
}

export interface RecommendationRequest {
    mode: 'short' | 'long' | 'all';
    force_refresh?: boolean;
}

export const generateRecommendations = async (request: RecommendationRequest): Promise<RecommendationResult> => {
    const response = await api.post('/recommend/generate', request);
    return response.data;
};

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