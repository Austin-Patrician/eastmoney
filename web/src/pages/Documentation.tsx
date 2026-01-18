import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
    Box,
    Typography,
    List,
    ListItemButton,
    ListItemText,
    ListItemIcon,
    TextField,
    InputAdornment,
    IconButton,
    Button
} from '@mui/material';
import RocketLaunchIcon from '@mui/icons-material/RocketLaunch';
import StorageIcon from '@mui/icons-material/Storage';
import ExtensionIcon from '@mui/icons-material/Extension';
import PsychologyIcon from '@mui/icons-material/Psychology';
import HelpOutlineIcon from '@mui/icons-material/HelpOutline';
import GavelIcon from '@mui/icons-material/Gavel';
import SearchIcon from '@mui/icons-material/Search';
import CloseIcon from '@mui/icons-material/Close';
import MenuBookIcon from '@mui/icons-material/MenuBook';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import HomeIcon from '@mui/icons-material/Home';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// --- Content Data (Markdown) ---

const CONTENT_QUICK_START = `
## 配置 API 密钥

本系统使用 Google Gemini 或 OpenAI 作为 AI 分析引擎。您需要先获取相应的 API 密钥才能使用 AI 分析功能。

### 步骤 1: 获取 Gemini API 密钥

访问 [Google AI Studio](https://aistudio.google.com/app/apikey) 创建您的 API 密钥。Gemini API 提供免费额度，适合个人用户使用。

### 步骤 2: 配置密钥到系统

进入 **系统设置** 页面，在 LLM 配置区域选择提供商并填入您的 API 密钥。

\`\`\`
系统设置 → LLM 提供商 → 选择 Gemini → 填入 API Key → 保存
\`\`\`

### 步骤 3: 验证配置

保存后，系统会自动验证 API 密钥是否有效。您可以在 AI 推荐或报告页面尝试生成内容来确认配置成功。

> **提示：** Gemini API 每分钟有 15 次免费调用额度。如果需要更高频率，可以升级付费版或切换使用 OpenAI API。

---

## 拉取第一个数据

系统启动后会自动从 Akshare 获取市场数据。您可以通过以下步骤确认数据已正常加载：

1. **查看市场指数** - 页面顶部导航栏应显示上证指数、深证成指、创业板指的实时行情
2. **访问仪表盘** - 仪表盘页面会展示市场概览数据，包括系统状态和最新报告
3. **添加关注标的** - 进入基金管理或股票管理页面，搜索并添加您关注的基金或股票

---

## 生成第一份报告

配置好 API 密钥并添加关注标的后，您可以开始使用 AI 分析功能：

- **AI 智能推荐** - 进入"AI 精选"页面，点击"生成推荐"按钮，系统会分析全市场数据并推荐优质股票和基金
- **投资分析报告** - 在"情报"页面可以为您关注的基金生成盘前分析或盘后复盘报告
- **市场情绪分析** - 在"情绪"页面获取当前市场整体情绪判断，辅助投资决策
`;

const CONTENT_DATA_SOURCES = `
## Akshare 数据源

本系统使用 [Akshare](https://akshare.akfamily.xyz/) 作为核心数据源。Akshare 是一个优秀的开源金融数据接口库，提供 A 股、港股、美股等多市场的全面数据支持。

| 属性 | 说明 |
| :--- | :--- |
| **数据来源** | 东方财富、新浪财经、同花顺等 |
| **更新频率** | 实时行情 / 每日收盘更新 |
| **数据类型** | 行情、财务、资金流向、板块 |
| **覆盖范围** | A股、港股、基金、期货、外汇 |

---

## 市场行情数据

系统获取的市场行情数据包括以下核心指标：

- 股票实时行情：最新价、涨跌幅、成交量、成交额、换手率、振幅
- 历史 K 线数据：日线、周线历史走势，支持技术分析
- 资金流向数据：主力净流入、散户净流入、大单成交占比
- 估值指标：市盈率(PE)、市净率(PB)、市销率(PS)、总市值、流通市值
- 财务数据：ROE、净利润增长率、营收增长率等核心财务指标
- 基金净值：单位净值、累计净值、日增长率、历史净值走势

---

## 行业指数覆盖

系统覆盖申万一级行业分类，支持以下行业板块的数据分析：

科技、医药生物、食品饮料、银行、非银金融、房地产、电力设备、汽车、机械设备、电子、通信、计算机、传媒、国防军工、建筑材料、建筑装饰、化工、有色金属、钢铁、煤炭、石油石化、公用事业、交通运输、农林牧渔、家用电器、轻工制造、纺织服饰、商贸零售、社会服务、美容护理

---

## 基金数据说明

系统支持多种类型基金的数据获取和分析：

| 基金类型 | 数据涵盖 |
| :--- | :--- |
| **股票型基金** | 净值走势、重仓股、行业配置、基金经理 |
| **混合型基金** | 资产配置比例、历史业绩、风险指标 |
| **指数型基金** | 跟踪指数、跟踪误差、规模变化 |
| **ETF 基金** | 实时价格、折溢价率、成交量 |
| **债券型基金** | 久期、到期收益率、信用评级分布 |
| **QDII 基金** | 投资区域、汇率影响、海外持仓 |
`;

const CONTENT_MODULES = `
## 仪表盘模块

仪表盘是系统的核心入口，提供市场概览和快速导航功能。登录后默认进入此页面。

### 主要功能

- **市场指数实时展示** - 顶部显示上证指数、深证成指、创业板指的实时行情，每 60 秒自动刷新
- **投资组合概览** - 展示已关注的基金和股票数量、最新报告数量、系统配置状态
- **最新报告入口** - 快速访问最近生成的分析报告，支持直接查看报告内容

> **使用技巧：** 仪表盘数据每分钟自动刷新，您也可以点击刷新按钮手动更新数据。

---

## 基金管理模块

基金管理模块用于管理您的基金关注列表，是生成基金分析报告的基础。支持全市场公募基金的搜索和管理。

### 核心功能

- **智能搜索** - 支持基金代码、基金名称、拼音首字母多种方式搜索，快速定位目标基金
- **一键添加** - 搜索结果直接点击添加到关注列表，自动获取基金详细信息
- **详情查看** - 查看基金净值走势图、持仓明细、基金经理信息、历史业绩等详细数据
- **定时分析** - 为每只基金设置盘前/盘后分析时间，系统将按时自动生成分析报告

### 操作说明

1. 点击"添加基金"按钮打开搜索对话框
2. 输入基金代码或名称进行搜索
3. 点击搜索结果添加到列表
4. 在列表中可以查看详情、编辑设置或删除

---

## 股票管理模块

股票管理模块用于管理您的自选股列表，支持 A 股全市场股票（沪市、深市、北交所）的搜索、添加和分析。

### 核心功能

- **全市场搜索** - 支持股票代码、股票名称搜索，覆盖沪深北三大交易所全部股票
- **实时行情** - 显示股票最新价、涨跌幅、成交量等实时行情数据
- **K线图表** - 查看股票历史 K 线走势，支持日线、周线等多种周期
- **个股分析** - 为单只股票生成 AI 分析报告，包括技术面和基本面分析

> **提示：** 股票数据存在约 15-30 分钟延迟，这是数据源的限制。如需实时行情，请使用专业行情软件。

---

## AI 推荐模块

AI 推荐模块是系统的核心功能，通过量化筛选 + AI 分析，从全市场中精选优质股票和基金推荐给您。

### 推荐类型

**短期推荐 (7-30天)**

关注动量和资金流向，适合短线交易者：

- 主力资金持续流入的标的
- 技术形态良好，量价配合
- 有近期催化剂（业绩、政策等）

**长期推荐 (3个月+)**

关注基本面和估值，适合价值投资者：

- 行业龙头或细分冠军
- 估值处于历史合理区间
- ROE 较高或有改善趋势

### 个性化配置

点击页面右上角的设置图标，可以配置您的个性化投资偏好：风险偏好、市值范围、行业偏好、估值限制等。

### 使用方法

1. 选择推荐模式（全部/短期/长期）
2. 点击"生成推荐"按钮启动分析
3. 等待 AI 分析完成（通常需要 30-60 秒）
4. 查看推荐结果，悬停 Tab 可预览另一类别

---

## 报告生成模块

报告生成模块（情报页面）用于为您关注的基金生成专业的 AI 分析报告，帮助您做出更明智的投资决策。

### 报告类型

**盘前分析报告**

适合开盘前阅读，帮助制定当日投资计划：

- 隔夜全球市场回顾
- 今日重点关注事件
- 持仓标的开盘预判
- 今日操作建议

**盘后复盘报告**

适合收盘后阅读，总结当日市场表现：

- 当日市场走势回顾
- 持仓标的表现分析
- 板块轮动情况
- 下一个交易日展望与建议

### 报告管理

- 所有报告自动保存，可随时查看历史报告
- 报告按日期分组展示，方便查找
- 支持删除不需要的历史报告

---

## 市场情绪模块

市场情绪模块通过分析市场数据和多种指标，综合判断当前市场的整体情绪倾向，为您的投资决策提供参考。

### 分析维度

- **乐观** - 市场情绪积极，可适当进取
- **中性** - 市场情绪平稳，宜观望为主
- **悲观** - 市场情绪低迷，注意风险控制

### 参考指标

- 涨跌家数比：上涨股票数量与下跌股票数量的比值
- 涨停跌停数：涨停板和跌停板股票数量
- 成交量变化：与近期平均成交量的对比
- 北向资金：外资流入流出情况

---

## 商品分析模块

商品分析模块提供贵金属等大宗商品的行情数据和分析报告，帮助您了解全球资产配置机会。

### 支持商品

- **黄金** - 国际金价走势
- **白银** - 国际银价走势
- **原油** - 布伦特/WTI 原油

### 主要功能

- 实时价格走势图表展示
- 生成商品分析报告
- 历史报告查看和管理

---

## 系统设置模块

系统设置模块用于配置系统核心参数，包括 AI 服务提供商、API 密钥等关键设置。

### 配置项

| 配置项 | 说明 |
| :--- | :--- |
| **LLM 提供商** | 支持 Google Gemini 和 OpenAI 两种 AI 服务提供商，可根据需要切换 |
| **Gemini API Key** | 配置 Google Gemini API 密钥，支持免费额度使用 |
| **OpenAI API Key** | 配置 OpenAI API 密钥，需要有效的付费账户 |
| **Tavily API Key** | 配置 Tavily 搜索 API，用于获取实时新闻和市场信息（可选） |

> **安全提示：** API 密钥是敏感信息，请妥善保管，不要泄露给他人。系统会对密钥进行脱敏显示。
`;

const CONTENT_AI_LOGIC = `
## 评分体系概述

AI 推荐系统采用多维度评分体系，满分 100 分。系统首先通过量化指标筛选候选池，然后由 AI 进行深度分析并给出最终推荐。

| 维度 | 权重 | 说明 |
| :--- | :--- | :--- |
| **动量得分** | 25% | 价格趋势强度、均线排列、突破信号 |
| **资金得分** | 25% | 主力净流入、大单占比、资金持续性 |
| **估值得分** | 20% | PE/PB 历史百分位、同行业对比、性价比 |
| **基本面得分** | 20% | ROE、盈利增长、营收增长、行业地位 |
| **情绪得分** | 10% | 市场热度、板块轮动、新闻舆情 |

---

## 短期策略逻辑

> **投资周期：** 7-30 天 | **核心关注：** 动量和资金流向

短期策略适合捕捉市场短线交易机会，优先考虑以下因素：

- 资金持续流入：连续 3 日以上主力净流入，表明机构看好
- 所属板块热度上升：板块整体表现强势，有带动效应
- 技术形态良好：放量突破、均线多头排列、MACD 金叉
- 有近期催化剂：业绩预告、政策利好、新产品发布等
- 量比 > 1.5：交易活跃度提升，关注度增加

\`\`\`
IF 主力净流入 > 0 AND 量比 > 1.5 AND 板块热度排名 < 20 THEN 加入候选池
\`\`\`

---

## 长期策略逻辑

> **投资周期：** 3 个月以上 | **核心关注：** 基本面和估值

长期策略适合价值投资，优先考虑以下因素：

- 行业龙头或细分领域冠军：市场份额领先，竞争壁垒高
- 估值处于历史合理区间：PE/PB 百分位 < 60%，有安全边际
- ROE > 15%：盈利能力强，或有明显改善趋势
- 清晰的业绩增长逻辑：行业景气、产品升级、产能扩张等
- 护城河明显：品牌优势、技术专利、规模效应、网络效应

\`\`\`
IF ROE > 15% AND PE百分位 < 60% AND 市值 > 100亿 THEN 加入候选池
\`\`\`

---

## 个性化推荐

系统支持根据您的投资偏好进行个性化推荐。您可以在 AI 推荐页面配置以下偏好设置：

| 偏好类型 | 说明 |
| :--- | :--- |
| **风险偏好** | 保守型 / 稳健型 / 积极型 / 投机型 四档可选 |
| **市值偏好** | 设置最小/最大市值范围，过滤不符合的标的 |
| **估值偏好** | 设置 PE/PB 范围限制，控制估值风险 |
| **行业偏好** | 设置偏好行业和排除行业 |
| **基金类型偏好** | 选择偏好的基金类型（股票型/混合型/指数型等） |
| **特殊规则** | 排除 ST 股票、排除次新股、要求盈利等 |
`;

const CONTENT_FAQ = `
## 429 错误处理

> **错误代码 429** 表示 API 请求频率超过限制（Rate Limit Exceeded）

### 常见原因

- Gemini API 免费版每分钟 15 次请求限制
- 短时间内连续生成多份报告
- Akshare 数据接口调用过于频繁

### 解决方案

- 等待 1-2 分钟后重试
- 升级到 Gemini API 付费版本，获得更高配额
- 切换使用 OpenAI API（按用量计费，无请求频率限制）
- 减少并发请求，避免短时间内连续操作

---

## API 调用限制

| API 提供商 | 免费额度 | 限制说明 |
| :--- | :--- | :--- |
| **Gemini** | 15 RPM | 每分钟 15 次请求，每日有总量限制 |
| **OpenAI** | 按用量计费 | 无免费额度，按 token 数量计费 |
| **Akshare** | 无明确限制 | 建议请求间隔 1 秒以上，避免被封禁 |

---

## 数据延迟问题

**Q: 为什么数据不是实时更新的？**

A: Akshare 获取的行情数据存在约 15-30 分钟延迟，这是免费数据源的通用限制。如需实时行情，需要接入付费行情数据源（如 Wind、同花顺 iFinD 等）。

**Q: 基金净值为什么是昨天的？**

A: 基金净值在每个交易日收盘后约 19:00-22:00 才会更新。如果当前时间早于净值更新时间，显示的是上一个交易日的净值数据。

---

## 其他常见问题

**Q: 为什么搜索不到某些股票/基金？**

A: 请确保输入正确的代码或名称。新上市的股票/基金可能数据源尚未收录，通常在上市后 1-2 天内会更新。

**Q: AI 分析报告生成失败怎么办？**

A: 请检查：1) API 密钥是否正确配置；2) 网络连接是否正常；3) 是否触发了调用频率限制。如持续失败，尝试切换 LLM 提供商。

**Q: 如何清除历史数据重新开始？**

A: 您可以在基金/股票管理页面逐个删除已添加的标的，或者联系系统管理员清空数据库。
`;

const CONTENT_DISCLAIMER = `
## 投资风险提示

- 股票、基金等金融产品存在市场风险，价格可能大幅波动，甚至可能损失全部本金
- 过往业绩不代表未来表现，历史收益率不能保证未来收益
- 投资者应根据自身风险承受能力、投资经验和财务状况做出独立决策
- 请勿将全部资产投入单一产品，建议分散投资以降低风险
- 建议在做出重大投资决策前咨询专业的持牌财务顾问

---

## AI 分析局限性

AI 分析系统存在以下固有局限性，请务必了解：

- AI 模型基于历史数据训练，无法预测突发事件（黑天鹅）的影响
- 市场受政策变化、地缘政治、投资者情绪等非量化因素影响
- 大语言模型可能产生"幻觉"，生成看似合理但实际不准确的分析
- 推荐评分仅为参考指标，不能保证推荐标的一定会上涨
- 系统无法替代专业投资顾问的综合判断和个性化建议
- AI 对市场的理解基于训练数据，可能存在认知偏差

---

## 数据准确性

关于数据准确性的重要说明：

- 数据来源于第三方免费接口（Akshare），可能存在延迟或误差
- 系统尽力保证数据准确，但不对数据的完整性和及时性承担责任
- 重要投资决策请以官方数据为准（如交易所官网、基金公司官网）
- 财务数据来源于公开披露的定期报告，可能未反映最新情况
- 如发现数据明显异常，请及时反馈，我们将尽快核实处理

---

## 法律声明

使用本系统即表示您已阅读、理解并同意以下条款：

1. 本系统提供的所有信息、分析和推荐仅供参考和学习交流目的，不构成投资建议、财务建议或任何形式的投资推荐。

2. 用户基于本系统信息做出的任何投资决策及其后果，风险由用户自行承担，系统开发者和运营者不承担任何责任。

3. 本系统不对因使用系统信息而导致的任何直接或间接损失（包括但不限于投资亏损、数据丢失、业务中断等）承担赔偿责任。

4. 用户应遵守所在国家和地区的法律法规，合法、合规地使用本系统，不得将系统用于任何非法目的。

5. 本系统保留随时修改、更新或终止服务的权利，以及修改本免责声明条款的权利。
`;

// --- Configuration ---

const DOC_SECTIONS = [
    { id: 'quick-start', title: '快速开始', titleEn: 'Quick Start', icon: RocketLaunchIcon, content: CONTENT_QUICK_START },
    { id: 'data-sources', title: '数据说明', titleEn: 'Data Sources', icon: StorageIcon, content: CONTENT_DATA_SOURCES },
    { id: 'modules', title: '模块介绍', titleEn: 'Modules', icon: ExtensionIcon, content: CONTENT_MODULES },
    { id: 'ai-logic', title: 'AI 逻辑', titleEn: 'AI Logic', icon: PsychologyIcon, content: CONTENT_AI_LOGIC },
    { id: 'faq', title: '常见问题', titleEn: 'FAQ', icon: HelpOutlineIcon, content: CONTENT_FAQ },
    { id: 'disclaimer', title: '免责声明', titleEn: 'Disclaimer', icon: GavelIcon, content: CONTENT_DISCLAIMER },
];

// Generate slug from text
const generateSlug = (text: string) => {
    return text
        .toLowerCase()
        .replace(/[^a-z0-9\u4e00-\u9fa5]+/g, '-')
        .replace(/^-|-$/g, '');
};

export default function DocumentationPage() {
    const [activeSection, setActiveSection] = useState('quick-start');
    const [searchQuery, setSearchQuery] = useState('');
    const [toc, setToc] = useState<{ id: string; text: string; level: number }[]>([]);
    const [visibleHeaders, setVisibleHeaders] = useState<Set<string>>(new Set());
    const contentRef = useRef<HTMLDivElement>(null);
    const isScrollingRef = useRef(false);

    // Filtered sections based on search
    const filteredSections = useMemo(() => {
        if (!searchQuery) return DOC_SECTIONS;
        const q = searchQuery.toLowerCase();
        return DOC_SECTIONS.filter(s =>
            s.title.toLowerCase().includes(q) ||
            s.titleEn.toLowerCase().includes(q) ||
            s.content.toLowerCase().includes(q)
        );
    }, [searchQuery]);

    const activeDoc = useMemo(() =>
        DOC_SECTIONS.find(s => s.id === activeSection) || DOC_SECTIONS[0],
        [activeSection]);

    // Parse Markdown headers for Table of Contents
    useEffect(() => {
        const lines = activeDoc.content.split('\n');
        const headers = lines
            .filter(line => line.startsWith('#'))
            .map(line => {
                const level = line.match(/^#+/)?.[0].length || 0;
                const text = line.replace(/^#+\s+/, '').trim();
                const id = generateSlug(text);
                return { id, text, level };
            });
        setToc(headers);
        setVisibleHeaders(new Set());
    }, [activeDoc]);

    // Scroll Spy - track visible headers
    useEffect(() => {
        const handleScroll = () => {
            if (!contentRef.current || isScrollingRef.current) return;

            const container = contentRef.current;
            const containerRect = container.getBoundingClientRect();
            const headers = container.querySelectorAll('h2, h3');
            const newVisibleHeaders = new Set<string>();

            headers.forEach((header) => {
                const rect = header.getBoundingClientRect();
                // Check if header is in the visible area of the container
                const isVisible = rect.top >= containerRect.top - 100 && rect.top <= containerRect.bottom - 100;
                if (isVisible && header.id) {
                    newVisibleHeaders.add(header.id);
                }
            });

            // If no headers visible, find the one above the viewport
            if (newVisibleHeaders.size === 0) {
                let lastAbove = '';
                headers.forEach((header) => {
                    const rect = header.getBoundingClientRect();
                    if (rect.top < containerRect.top + 100 && header.id) {
                        lastAbove = header.id;
                    }
                });
                if (lastAbove) {
                    newVisibleHeaders.add(lastAbove);
                }
            }

            setVisibleHeaders(newVisibleHeaders);
        };

        const el = contentRef.current;
        if (el) {
            el.addEventListener('scroll', handleScroll, { passive: true });
            // Initial check
            setTimeout(handleScroll, 100);
            return () => el.removeEventListener('scroll', handleScroll);
        }
    }, [activeDoc]);

    const scrollToHeader = useCallback((id: string) => {
        const element = document.getElementById(id);
        if (element && contentRef.current) {
            isScrollingRef.current = true;

            const containerTop = contentRef.current.getBoundingClientRect().top;
            const elementTop = element.getBoundingClientRect().top;
            const offset = elementTop - containerTop + contentRef.current.scrollTop - 32;

            contentRef.current.scrollTo({ top: offset, behavior: 'smooth' });

            setTimeout(() => {
                isScrollingRef.current = false;
                setVisibleHeaders(new Set([id]));
            }, 500);
        }
    }, []);

    const handleSectionChange = useCallback((sectionId: string) => {
        setActiveSection(sectionId);
        setSearchQuery('');
        if (contentRef.current) {
            contentRef.current.scrollTo({ top: 0, behavior: 'instant' });
        }
    }, []);

    // Custom Components for ReactMarkdown with improved typography
    const components = useMemo(() => ({
        h1: ({ children, ...props }: any) => (
            <h1
                id={generateSlug(String(children))}
                className="text-3xl font-bold text-slate-900 mt-12 mb-6 tracking-tight leading-tight"
                {...props}
            >
                {children}
            </h1>
        ),
        h2: ({ children, ...props }: any) => (
            <h2
                id={generateSlug(String(children))}
                className="text-2xl font-bold text-slate-800 mt-16 mb-6 pb-3 border-b border-slate-200 leading-tight first:mt-0"
                {...props}
            >
                {children}
            </h2>
        ),
        h3: ({ children, ...props }: any) => (
            <h3
                id={generateSlug(String(children))}
                className="text-lg font-semibold text-slate-700 mt-10 mb-4 leading-snug"
                {...props}
            >
                {children}
            </h3>
        ),
        p: ({ children, ...props }: any) => (
            <p className="text-base text-slate-600 mb-6 leading-relaxed" {...props}>
                {children}
            </p>
        ),
        ul: ({ children, ...props }: any) => (
            <ul className="my-6 ml-6 space-y-3" {...props}>
                {children}
            </ul>
        ),
        ol: ({ children, ...props }: any) => (
            <ol className="my-6 ml-6 space-y-3 list-decimal" {...props}>
                {children}
            </ol>
        ),
        li: ({ children, ...props }: any) => (
            <li className="text-slate-600 leading-relaxed pl-2" {...props}>
                <span className="relative">
                    {children}
                </span>
            </li>
        ),
        blockquote: ({ children, ...props }: any) => (
            <blockquote
                className="my-8 pl-6 py-4 pr-6 border-l-4 border-indigo-400 bg-indigo-50/50 rounded-r-lg"
                {...props}
            >
                <div className="text-slate-700 text-sm leading-relaxed [&>p]:mb-0">
                    {children}
                </div>
            </blockquote>
        ),
        code: ({ inline, children, ...props }: any) => {
            if (inline) {
                return (
                    <code
                        className="px-1.5 py-0.5 bg-slate-100 text-indigo-600 text-sm font-mono rounded"
                        {...props}
                    >
                        {children}
                    </code>
                );
            }
            return (
                <div className="my-8 rounded-xl overflow-hidden bg-slate-900 shadow-lg">
                    <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 border-b border-slate-700">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <div className="w-3 h-3 rounded-full bg-yellow-500" />
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <span className="ml-3 text-xs text-slate-400 font-mono">terminal</span>
                    </div>
                    <pre className="p-5 overflow-x-auto">
                        <code className="text-emerald-400 font-mono text-sm leading-relaxed" {...props}>
                            {children}
                        </code>
                    </pre>
                </div>
            );
        },
        table: ({ children, ...props }: any) => (
            <div className="my-8 overflow-x-auto rounded-xl border border-slate-200 shadow-sm">
                <table className="w-full text-sm" {...props}>
                    {children}
                </table>
            </div>
        ),
        thead: ({ children, ...props }: any) => (
            <thead className="bg-slate-50 border-b border-slate-200" {...props}>
                {children}
            </thead>
        ),
        tbody: ({ children, ...props }: any) => (
            <tbody className="divide-y divide-slate-100" {...props}>
                {children}
            </tbody>
        ),
        tr: ({ children, ...props }: any) => (
            <tr className="hover:bg-slate-50/50 transition-colors" {...props}>
                {children}
            </tr>
        ),
        th: ({ children, ...props }: any) => (
            <th className="px-5 py-3.5 text-left font-semibold text-slate-700 whitespace-nowrap" {...props}>
                {children}
            </th>
        ),
        td: ({ children, ...props }: any) => (
            <td className="px-5 py-4 text-slate-600" {...props}>
                {children}
            </td>
        ),
        a: ({ children, ...props }: any) => (
            <a
                className="text-indigo-600 font-medium hover:text-indigo-700 hover:underline underline-offset-2 transition-colors"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
            >
                {children}
            </a>
        ),
        hr: () => <hr className="my-12 border-t border-slate-200" />,
        strong: ({ children, ...props }: any) => (
            <strong className="font-semibold text-slate-800" {...props}>
                {children}
            </strong>
        ),
    }), []);

    const currentIdx = DOC_SECTIONS.findIndex(s => s.id === activeSection);
    const prevSection = DOC_SECTIONS[currentIdx - 1];
    const nextSection = DOC_SECTIONS[currentIdx + 1];

    return (
        <div className="flex h-screen bg-white">
            {/* Left Sidebar */}
            <aside className="w-72 flex-shrink-0 border-r border-slate-200 bg-slate-50 flex flex-col">
                {/* Header */}
                <div className="h-16 flex items-center justify-between px-5 border-b border-slate-200 bg-white">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center">
                            <MenuBookIcon className="text-white" sx={{ fontSize: 18 }} />
                        </div>
                        <div>
                            <div className="text-sm font-bold text-slate-800 leading-none">VibeAlpha</div>
                            <div className="text-xs text-slate-400 mt-0.5">Documentation</div>
                        </div>
                    </div>
                    <IconButton
                        size="small"
                        onClick={() => window.location.href = '/'}
                        sx={{ color: '#64748b' }}
                    >
                        <HomeIcon fontSize="small" />
                    </IconButton>
                </div>

                {/* Search */}
                <div className="p-4 border-b border-slate-200 bg-white">
                    <TextField
                        fullWidth
                        placeholder="搜索文档..."
                        size="small"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon sx={{ fontSize: 18, color: '#94a3b8' }} />
                                </InputAdornment>
                            ),
                            endAdornment: searchQuery && (
                                <InputAdornment position="end">
                                    <IconButton size="small" onClick={() => setSearchQuery('')}>
                                        <CloseIcon sx={{ fontSize: 16 }} />
                                    </IconButton>
                                </InputAdornment>
                            ),
                            sx: {
                                borderRadius: '10px',
                                fontSize: '0.875rem',
                                bgcolor: '#f8fafc',
                                '& fieldset': { borderColor: '#e2e8f0' },
                                '&:hover fieldset': { borderColor: '#cbd5e1' },
                            }
                        }}
                    />
                </div>

                {/* Navigation */}
                <nav className="flex-1 overflow-y-auto py-3 px-3">
                    <List disablePadding>
                        {filteredSections.map((section) => {
                            const isActive = activeSection === section.id;
                            const IconComponent = section.icon;
                            return (
                                <ListItemButton
                                    key={section.id}
                                    selected={isActive}
                                    onClick={() => handleSectionChange(section.id)}
                                    sx={{
                                        borderRadius: '10px',
                                        mb: 0.5,
                                        py: 1.25,
                                        px: 1.5,
                                        '&.Mui-selected': {
                                            bgcolor: '#eef2ff',
                                            '&:hover': { bgcolor: '#e0e7ff' },
                                        },
                                        '&:hover': { bgcolor: '#f1f5f9' }
                                    }}
                                >
                                    <ListItemIcon sx={{ minWidth: 36 }}>
                                        <IconComponent
                                            sx={{
                                                fontSize: 20,
                                                color: isActive ? '#4f46e5' : '#94a3b8'
                                            }}
                                        />
                                    </ListItemIcon>
                                    <ListItemText
                                        primary={section.title}
                                        secondary={section.titleEn}
                                        primaryTypographyProps={{
                                            fontSize: '0.875rem',
                                            fontWeight: isActive ? 600 : 500,
                                            color: isActive ? '#4f46e5' : '#475569'
                                        }}
                                        secondaryTypographyProps={{
                                            fontSize: '0.7rem',
                                            color: '#94a3b8',
                                            mt: 0.25
                                        }}
                                    />
                                </ListItemButton>
                            );
                        })}
                    </List>
                </nav>

                {/* Footer */}
                <div className="p-4 border-t border-slate-200 bg-white">
                    <Typography variant="caption" className="text-slate-400 block text-center">
                        v2.1 · VibeAlpha Terminal
                    </Typography>
                </div>
            </aside>

            {/* Main Content */}
            <main ref={contentRef} className="flex-1 overflow-y-auto">
                <div className="max-w-3xl mx-auto px-8 py-12">
                    {/* Breadcrumb */}
                    <div className="flex items-center gap-2 text-sm text-slate-400 mb-8">
                        <span>Docs</span>
                        <ChevronRightIcon sx={{ fontSize: 16 }} />
                        <span className="text-indigo-600 font-medium">{activeDoc.title}</span>
                    </div>

                    {/* Title */}
                    <div className="mb-12">
                        <h1 className="text-4xl font-bold text-slate-900 tracking-tight mb-3">
                            {activeDoc.title}
                        </h1>
                        <p className="text-lg text-slate-500">
                            {activeDoc.titleEn}
                        </p>
                    </div>

                    {/* Content */}
                    <article className="prose-doc">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={components}
                        >
                            {activeDoc.content}
                        </ReactMarkdown>
                    </article>

                    {/* Navigation Footer */}
                    <div className="mt-20 pt-8 border-t border-slate-200 flex justify-between items-center">
                        {prevSection ? (
                            <Button
                                onClick={() => handleSectionChange(prevSection.id)}
                                startIcon={<ChevronLeftIcon />}
                                sx={{
                                    textTransform: 'none',
                                    color: '#64748b',
                                    '&:hover': { bgcolor: '#f1f5f9' }
                                }}
                            >
                                <Box className="text-left">
                                    <Typography variant="caption" className="block text-slate-400">
                                        上一章
                                    </Typography>
                                    <Typography className="font-medium text-slate-700">
                                        {prevSection.title}
                                    </Typography>
                                </Box>
                            </Button>
                        ) : <div />}
                        {nextSection && (
                            <Button
                                onClick={() => handleSectionChange(nextSection.id)}
                                endIcon={<ChevronRightIcon />}
                                sx={{
                                    textTransform: 'none',
                                    color: '#64748b',
                                    '&:hover': { bgcolor: '#f1f5f9' }
                                }}
                            >
                                <Box className="text-right">
                                    <Typography variant="caption" className="block text-slate-400">
                                        下一章
                                    </Typography>
                                    <Typography className="font-medium text-slate-700">
                                        {nextSection.title}
                                    </Typography>
                                </Box>
                            </Button>
                        )}
                    </div>
                </div>
            </main>

            {/* Right Sidebar - Table of Contents */}
            <aside className="w-56 flex-shrink-0 border-l border-slate-200 bg-white hidden xl:block">
                <div className="sticky top-0 p-5">
                    <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
                        本页目录
                    </div>
                    <nav className="space-y-1">
                        {toc.map((item) => {
                            const isVisible = visibleHeaders.has(item.id);
                            const indent = (item.level - 2) * 12;
                            return (
                                <button
                                    key={item.id}
                                    onClick={() => scrollToHeader(item.id)}
                                    style={{ paddingLeft: indent + 12 }}
                                    className={`
                                        w-full text-left py-1.5 pr-3 text-sm rounded-r
                                        transition-all duration-150 relative
                                        ${isVisible
                                            ? 'text-slate-900 font-medium'
                                            : 'text-slate-400 hover:text-slate-600'
                                        }
                                    `}
                                >
                                    {/* Black indicator bar */}
                                    <span
                                        className={`
                                            absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 rounded-full
                                            transition-all duration-150
                                            ${isVisible ? 'bg-slate-800' : 'bg-transparent'}
                                        `}
                                    />
                                    <span className="line-clamp-1">{item.text}</span>
                                </button>
                            );
                        })}
                    </nav>
                </div>
            </aside>
        </div>
    );
}
