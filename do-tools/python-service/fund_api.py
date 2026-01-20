"""
基金数据接口 - 使用 AkShare
"""
import akshare as ak
from typing import List, Dict


def search_funds(query: str, limit: int = 10) -> List[Dict]:
    """
    搜索基金（代码或名称模糊匹配）
    
    Args:
        query: 搜索关键词
        limit: 返回结果数量限制
        
    Returns:
        基金列表 [{'code': '...', 'name': '...', 'type': '...', 'pinyin': '...'}]
    """
    query = query.strip().lower()
    
    if not query:
        return []
    
    try:
        # 获取全市场基金列表
        df = ak.fund_name_em()
        
        if df.empty:
            return []
        
        # 重命名列以保持一致性
        df = df.rename(columns={
            '基金代码': 'code',
            '基金简称': 'name',
            '基金类型': 'type',
            '拼音缩写': 'pinyin'
        })
        
        results = []
        
        # 优先级 1: 精确代码匹配
        exact_code = df[df['code'] == query]
        if not exact_code.empty:
            results.extend(exact_code.to_dict('records'))
        
        # 优先级 2: 代码开头匹配
        if len(results) < limit:
            code_starts = df[
                (df['code'].str.startswith(query)) & 
                (~df['code'].isin([r['code'] for r in results]))
            ]
            results.extend(code_starts.head(limit - len(results)).to_dict('records'))
        
        # 优先级 3: 名称包含
        if len(results) < limit:
            name_contains = df[
                (df['name'].str.lower().str.contains(query, na=False)) &
                (~df['code'].isin([r['code'] for r in results]))
            ]
            results.extend(name_contains.head(limit - len(results)).to_dict('records'))
        
        # 优先级 4: 拼音包含
        if len(results) < limit:
            pinyin_contains = df[
                (df['pinyin'].str.lower().str.contains(query, na=False)) &
                (~df['code'].isin([r['code'] for r in results]))
            ]
            results.extend(pinyin_contains.head(limit - len(results)).to_dict('records'))
        
        return results[:limit]
        
    except Exception as e:
        print(f"Error searching funds: {e}")
        return []


def get_fund_info(fund_code: str) -> Dict:
    """
    获取基金详细信息
    
    Args:
        fund_code: 基金代码
        
    Returns:
        基金信息字典
    """
    try:
        # 获取基金净值走势
        df = ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势")
        
        if df is None or df.empty:
            return {}
        
        # 标准化列名
        if '净值日期' not in df.columns:
            cols = list(df.columns)
            if len(cols) >= 3:
                df = df.rename(columns={
                    cols[0]: '净值日期',
                    cols[1]: '单位净值',
                    cols[2]: '日增长率',
                })
        
        # 获取最新净值
        latest = df.iloc[0] if not df.empty else {}
        
        return {
            'code': fund_code,
            'latest_nav': float(latest.get('单位净值', 0)) if latest else 0,
            'nav_date': str(latest.get('净值日期', '')) if latest else '',
            'daily_growth': float(latest.get('日增长率', 0)) if latest else 0,
        }
        
    except Exception as e:
        print(f"Error fetching fund info for {fund_code}: {e}")
        return {}
