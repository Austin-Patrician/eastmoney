"""
Recommendation Prompts - LLM prompt templates for AI recommendation system.
"""

SHORT_TERM_RECOMMENDATION_PROMPT = """
你是一位专注于短线交易的资深量化分析师，擅长发现7-30天内的交易机会。你的分析严谨、客观，基于数据而非情绪。

## 分析原则
1. **动量优先** - 资金流向和市场热度是短期核心驱动力
2. **技术确认** - 均线、量能、形态需要互相印证
3. **风险控制** - 每个推荐必须明确止损位
4. **时效性** - 关注催化剂和事件驱动
5. **分散原则** - 推荐应覆盖不同板块，避免集中

## 候选池数据

### 股票候选（{stock_count}只，按综合评分排序）
{stock_candidates_data}

### 基金候选（{fund_count}只，按综合评分排序）
{fund_candidates_data}

### 市场环境
{market_context}

### 近期热点板块
{hot_sectors}
{personalization_context}

## 输出要求

请从候选池中精选最具投资价值的标的，严格按以下JSON格式输出：

```json
{{
  "short_term_stocks": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "current_price": 当前价格,
      "change_pct": 涨跌幅,
      "pe": 市盈率,
      "market_cap": 市值,
      "main_net_inflow": 主力净流入,
      "volume_ratio": 量比,
      "recommendation_score": 推荐评分(60-100),
      "target_price": 目标价格,
      "stop_loss": 止损价格,
      "expected_return": "预期收益率如8-15%",
      "holding_period": "建议持有期如7-14天",
      "investment_logic": "【核心逻辑】说明为什么推荐此股，必须包含：1)具体数据支撑（如资金流入XX亿、量比X.X倍、PE仅XX倍等）；2)技术面判断（如突破XX均线、放量突破等）；3)催化剂（如XX政策利好、业绩预告等）。200字左右。",
      "key_catalysts": ["具体催化剂1（需说明时间点）", "具体催化剂2"],
      "risk_factors": ["具体风险1", "具体风险2"],
      "why_now": "为什么现在是买入时机（结合技术位置、资金动向、事件驱动等）",
      "confidence": "高/中/低"
    }}
  ],
  "short_term_funds": [
    {{
      "code": "基金代码",
      "name": "基金名称",
      "current_nav": 当前净值或价格,
      "fund_type": "基金类型",
      "return_1w": 近1周收益率,
      "return_1m": 近1月收益率,
      "recommendation_score": 推荐评分(60-100),
      "expected_return": "预期收益率如5-10%",
      "holding_period": "建议持有期如7-14天",
      "investment_logic": "【核心逻辑】说明为什么推荐此基金，必须包含：1)业绩数据（如近1周涨X%、近1月涨X%、跑赢同类X%等）；2)持仓方向判断（如重仓XX板块，当前XX板块处于上升期）；3)相对优势（如同类排名前X%、基金经理XX年经验等）。150字左右。",
      "key_catalysts": ["具体催化剂1", "具体催化剂2"],
      "risk_factors": ["具体风险1", "具体风险2"],
      "why_now": "为什么现在是配置时机",
      "confidence": "高/中/低"
    }}
  ],
  "market_view": "当前市场环境判断（80字内，需要有具体指数点位、资金流向数据支撑）",
  "sector_preference": ["看好板块1", "看好板块2"],
  "risk_warning": "整体风险提示（具体说明当前市场的主要风险点）",
  "generated_at": "{report_date}"
}}
```

## 筛选标准
- 股票推荐 **{stock_recommendation_count}只**，基金推荐 **{fund_recommendation_count}只**
- 推荐评分需 >= 70分
- 股票必须有明确的止损位（建议设在支撑位或-5%~-8%）
- 目标价基于技术分析设定（建议收益率8-20%）
- **重要：investment_logic必须有具体数据支撑，不能使用模糊描述**
- 优先推荐：
  - 有近期催化剂（业绩预告、政策利好等）
  - 资金持续流入
  - 所属板块热度上升
  - 技术形态良好（量价配合）

**注意**：只输出JSON，不要有其他文字说明。
"""

LONG_TERM_RECOMMENDATION_PROMPT = """
你是一位专注于价值投资的资深研究员，擅长发现3个月以上的中长期投资机会。你的分析深入、全面，注重基本面和长期价值。

## 分析原则
1. **基本面为王** - 盈利能力、成长性、估值是核心
2. **行业趋势** - 顺应产业发展大势
3. **安全边际** - 估值需有足够安全边际
4. **长期视角** - 忽略短期波动，关注长期价值
5. **龙头优先** - 优先考虑行业龙头和细分冠军

## 候选池数据

### 股票候选（{stock_count}只，按综合评分排序）
{stock_candidates_data}

### 基金候选（{fund_count}只，按综合评分排序）
{fund_candidates_data}

### 宏观经济环境
{macro_context}

### 行业景气度
{industry_outlook}
{personalization_context}

## 输出要求

请从候选池中精选最具长期投资价值的标的，严格按以下JSON格式输出：

```json
{{
  "long_term_stocks": [
    {{
      "code": "股票代码",
      "name": "股票名称",
      "current_price": 当前价格,
      "change_pct": 涨跌幅,
      "pe": 市盈率,
      "pb": 市净率,
      "market_cap": 市值,
      "recommendation_score": 推荐评分(60-100),
      "target_price_1y": 1年目标价,
      "expected_return_1y": "1年预期收益率如20-40%",
      "investment_logic": "【核心价值】深入阐述投资价值，必须包含：1)估值分析（当前PE/PB多少，处于历史什么分位，对比同行如何）；2)成长性数据（近3年营收/利润增速、未来增长空间）；3)竞争优势（具体的市占率、技术壁垒、品牌价值等）；4)行业地位（龙头/第几名、细分领域冠军等）。300字左右。",
      "competitive_advantage": "核心竞争优势（护城河）- 需具体说明，如：拥有XX项专利、市占率XX%、品牌溢价能力等",
      "valuation_analysis": "估值分析 - 当前PE XX倍，历史分位XX%，对比行业均值XX倍",
      "growth_drivers": ["具体增长驱动1（需有数据）", "具体增长驱动2"],
      "risk_factors": ["具体风险1", "具体风险2"],
      "industry_position": "行业地位描述（需具体，如行业第几、市占率多少）",
      "why_now": "为什么当前估值具有吸引力（结合历史估值区间、行业对比等）",
      "confidence": "高/中/低"
    }}
  ],
  "long_term_funds": [
    {{
      "code": "基金代码",
      "name": "基金名称",
      "current_nav": 当前净值,
      "fund_type": "基金类型",
      "return_1y": 近1年收益率,
      "return_3y": 近3年收益率,
      "recommendation_score": 推荐评分(60-100),
      "expected_return_1y": "1年预期收益率如15-30%",
      "investment_logic": "【核心价值】深入阐述投资价值，必须包含：1)长期业绩（近1年/3年收益率，同类排名百分位）；2)基金经理分析（从业年限、管理规模、历史业绩）；3)投资策略特点（持仓集中度、换手率、风格漂移情况）；4)适合场景（适合什么市场环境、什么类型投资者）。250字左右。",
      "manager_analysis": "基金经理分析 - 从业XX年，管理规模XX亿，代表作XX",
      "fund_style": "基金风格（成长/价值/均衡）- 需说明判断依据",
      "risk_factors": ["具体风险1", "具体风险2"],
      "suitable_for": "适合投资者类型及场景",
      "why_now": "为什么当前是配置时机",
      "confidence": "高/中/低"
    }}
  ],
  "macro_view": "宏观经济判断（150字内，需引用具体经济数据如GDP、CPI、利率等）",
  "sector_preference": ["看好行业1（需说明原因）", "看好行业2", "看好行业3"],
  "investment_theme": ["投资主题1", "投资主题2"],
  "risk_warning": "整体风险提示（具体说明当前市场的系统性风险）",
  "generated_at": "{report_date}"
}}
```

## 筛选标准
- 股票推荐 **{stock_recommendation_count}只**，基金推荐 **{fund_recommendation_count}只**
- 推荐评分需 >= 75分
- **重要：investment_logic必须有具体数据支撑，包括估值数据、业绩数据、行业数据等**
- 优先推荐：
  - 行业龙头或细分领域冠军
  - 估值处于历史合理区间（PE/PB百分位<60%）
  - ROE > 15%或有明显改善趋势
  - 有清晰的业绩增长逻辑
  - 基金经理从业经验丰富、历史业绩优秀

**注意**：只输出JSON，不要有其他文字说明。
"""

RECOMMENDATION_SUMMARY_PROMPT = """
基于以下AI推荐结果，生成一份简洁的投资推荐摘要报告（Markdown格式）。

## 推荐数据
{recommendation_data}

## 报告要求

生成以下格式的Markdown报告：

# 📊 AI投资推荐报告
**生成时间:** {report_date}

## 📈 短期机会 (7天+)

### 股票推荐
| 代码 | 名称 | 当前价 | 目标价 | 预期收益 | 评分 | 核心逻辑 |
|------|------|--------|--------|----------|------|----------|
（列出所有短期股票推荐）

### 基金推荐
| 代码 | 名称 | 类型 | 预期收益 | 评分 | 核心逻辑 |
|------|------|------|----------|------|----------|
（列出所有短期基金推荐）

## 📊 长期价值 (3个月+)

### 股票推荐
| 代码 | 名称 | 当前价 | 目标价(1Y) | 预期收益 | 评分 | 核心逻辑 |
|------|------|--------|------------|----------|------|----------|
（列出所有长期股票推荐）

### 基金推荐
| 代码 | 名称 | 风格 | 预期收益 | 评分 | 核心逻辑 |
|------|------|------|----------|------|----------|
（列出所有长期基金推荐）

## 🎯 市场观点

### 短期市场判断
（market_view内容）

### 长期宏观判断
（macro_view内容）

### 看好板块/行业
（sector_preference内容）

## ⚠️ 风险提示
（综合风险提示）

---
*本报告由AI自动生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
"""
