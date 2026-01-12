import sys
import os
from datetime import datetime

# Add project root to sys.path if run directly
if __name__ == "__main__":
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.analysis.sentiment.market_cycle import MarketCycleAnalyst
from src.analysis.sentiment.news_mining import NewsMiner
from src.analysis.sentiment.social_media import SocialSentinel
from src.analysis.sentiment.money_flow import MoneyFlowAnalyst
from src.llm.client import get_llm_client

class SentimentDashboard:
    def __init__(self):
        self.llm = get_llm_client()
        self.cycle_analyst = MarketCycleAnalyst()
        self.news_miner = NewsMiner()
        self.social_sentinel = SocialSentinel()
        self.money_analyst = MoneyFlowAnalyst()

    def run_analysis(self):
        print("1. Analyzing Market Cycle...")
        cycle_data = self.cycle_analyst.get_cycle_metrics()
        cycle_phase = self.cycle_analyst.determine_cycle_phase(cycle_data)
        
        print("2. Mining News...")
        news_items = self.news_miner.fetch_recent_news(limit=15)
        news_report = self.news_miner.analyze_news_sentiment(news_items)
        
        print("3. Checking Social Sentiment...")
        social_data = self.social_sentinel.get_social_sentiment()
        
        print("4. Tracking Money Flow...")
        money_data = self.money_analyst.get_money_flow()
        
        print("5. Generating Final Dashboard Report...")
        final_report = self.generate_final_report(cycle_data, cycle_phase, news_report, social_data, money_data)
        
        return final_report

    def generate_final_report(self, cycle, phase, news_analysis, social, money):
        def _fmt_list(items, limit: int = 5, format_str: str = "{i}. {name}") -> str:
            if not items:
                return "(无数据)"
            lines = []
            for i, item in enumerate(items[:limit], 1):
                if isinstance(item, dict):
                    # Smart format based on available keys
                    name = item.get("name") or item.get("股票名称") or item.get("title") or "N/A"
                    code = item.get("code") or item.get("股票代码")
                    pct = item.get("pct") or item.get("pct_change")
                    net_in = item.get("net_in") # Inflow
                    net_out = item.get("net_out") # Outflow
                    net_buy = item.get("net_buy")
                    turnover = item.get("turnover") # ETF volume
                    
                    parts = [f"{i}. {name}"]
                    if code: parts.append(f"({code})")
                    if pct is not None: parts.append(f"涨跌:{pct}%")
                    if net_in is not None: parts.append(f"主力净流入:{net_in}")
                    if net_out is not None: parts.append(f"主力净流出:{net_out}")
                    if net_buy is not None: parts.append(f"净买:{net_buy}亿")
                    if turnover is not None: 
                        # Format turnover to Yi
                        try:
                             parts.append(f"成交:{round(float(turnover)/1e8, 2)}亿")
                        except:
                             parts.append(f"成交:{turnover}")
                    
                    lines.append(" ".join(parts))
                else:
                    lines.append(f"{i}. {item}")
            return "\n".join(lines)

        report_date = datetime.now().strftime('%Y-%m-%d')
        
        # --- Data Unpacking ---
        # Cycle
        zt_count = cycle.get('zt_count', 0)
        zb_count = cycle.get('zb_count', 0)
        seal_rate = cycle.get('seal_rate', 0)
        market_height = cycle.get('market_height', 0)
        
        # Breadth
        breadth = money.get('market_breadth', {})
        up_count = breadth.get('up', 0)
        down_count = breadth.get('down', 0)
        limit_up_real = breadth.get('limit_up', 0)
        limit_down_real = breadth.get('limit_down', 0)
        
        # Money Flow
        sector_inflow = money.get('sector_inflow', [])
        sector_outflow = money.get('sector_outflow', [])
        etf_active = money.get('etf_active', [])
        north_money = money.get('north_money', 0)
        
        # Social
        top_hot = (social or {}).get('top_hot', [])
        
        # Calculations for context
        炸板率 = 100 - seal_rate if seal_rate else 0
        market_mood_desc = "震荡市"
        if up_count > down_count * 2: market_mood_desc = "送钱行情"
        elif down_count > up_count * 2: market_mood_desc = "绞肉机"
        
        north_desc = "看戏"
        if north_money > 20: north_desc = "抢筹"
        elif north_money < -20: north_desc = "跑路"

        prompt = f"""
        【角色设定】
        你叫“老张”，一个在A股摸爬滚打20年的“老法师”。你的嘴很毒，眼很尖。
        你最看不起那些只会看K线图画线的“股评家”，也看不起无脑追涨杀跌的“韭菜”。
        你只信奉一样东西：**真金白银的资金流向**。
        
        你的说话风格：
        1. **毒舌犀利**：拒绝文绉绉的金融术语，用最接地气的大白话、股市黑话（比如“关灯吃面”、“核按钮”、“骗炮”、“诱多”、“大面一碗”）。
        2. **爱吐槽**：对主力机构的猥琐操作极尽嘲讽，对散户的盲目狂热无情打击。
        3. **一针见血**：透过现象看本质，直接指出今天是“真涨”还是“老乡别走”。
        
        请结合下面的实时数据，给你的“老铁们”写一篇【老张分析日记】。

        ---
        【📊 盘面数据底稿】
        1. **市场强弱**:
           - 涨跌对比: {up_count}家红盘 vs {down_count}家绿盘 (老张评: {market_mood_desc})
           - 极端个股: {limit_up_real}家涨停 vs {limit_down_real}家跌停
           - 情绪周期: {phase} (涨停{zt_count}家，炸板率{炸板率}% -> {"主力这吃相太难看" if 炸板率 > 30 else "合力还算凑合"})
        
        2. **💸 谁在干活 (资金面)**
           - **北向(外资)**: 净流入 {north_money} 亿元 (老张评: 洋鬼子在{north_desc})
           - **ETF动向 (机构阵地)**: 
             {_fmt_list(etf_active, 5)}
        
        3. **🌊 板块轮动**
           - **主力在买啥 (净流入Top5)**:
             {_fmt_list(sector_inflow, 5)}
           - **主力在抛啥 (净流出Top5)**:
             {_fmt_list(sector_outflow, 5)}
             
        4. **🔥 韭菜大本营 (散户热度)**
           - 社区人气榜 (人多的地方不去):
             {_fmt_list(top_hot, 5)}
             
        5. **📰 消息面**
           {news_analysis}

        ---
        【写作要求】
        请输出 Markdown 格式，标题要起得惊悚一点，吸引眼球。包含以下模块：

        # 🥤 老张毒舌复盘 ({report_date})

        ## 1. 今天的盘面，老张有话说
        - 不要报数字，直接喷！结合“涨跌家数”和“外资”态度，给今天定个调。是“牛回速归”还是“ICU排队”？
        - 别整虚的，直接告诉我今天赚钱效应在哪？是在抱团妖股，还是在搞权重护盘？

        ## 2. 资金流向（跟庄操作）
        - 看看【主力加仓榜】，这帮机构在买什么？是真看好还是在做防御？（结合具体板块名字来骂/夸）
        - 看看【主力出逃榜】，谁被抛弃了？如果你手里有这些板块，老张会怎么劝你？
        - 看看【ETF】，大资金是在抄底宽基（护盘），还是在猛干某个赛道？

        ## 3. 韭菜心理按摩
        - 看看【社区人气榜】里的票，是不是有些票已经热得烫手了？警告大家别去接最后一棒。
        - 结合【情绪周期】（{phase}），告诉大家现在是该“贪婪”还是该“瑟瑟发抖”？

        ## 4. 老张的剧本
        - 下一个交易日会怎么走？大胆预测，错了也没事，老张脸皮厚。
        - **重点盯防**：给出一个具体的方向或板块，告诉大家明天盯着它看，它是死是活决定大盘命运。

        (结尾记得加一句老张的招牌结束语，比如“股市有风险，入市需吃药”之类的自嘲。)
        """
        
        return self.llm.generate_content(prompt)

if __name__ == "__main__":
    dashboard = SentimentDashboard()
    report = dashboard.run_analysis()
    
    # Ensure reports dir exists
    os.makedirs("reports", exist_ok=True)
    filename = f"reports/sentiment_{datetime.now().strftime('%Y%m%d')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {os.path.abspath(filename)}")
