import sqlite3
import json
import os
from typing import List, Dict, Optional
from datetime import datetime

# Define paths relative to this file
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Allow overriding via environment variable for Docker volumes
DB_PATH = os.environ.get("DB_FILE_PATH", os.path.join(BASE_DIR, "funds.db"))
FUNDS_JSON_PATH = os.path.join(BASE_DIR, "config", "funds.json")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # 1. Create Users Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            hashed_password TEXT,
            provider TEXT DEFAULT 'local', -- local, google, github
            provider_id TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Create Funds Table (Original)
    c.execute('''
        CREATE TABLE IF NOT EXISTS funds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            style TEXT,
            focus TEXT,
            pre_market_time TEXT,
            post_market_time TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id),
            UNIQUE(user_id, code)
        )
    ''')

    # 4. Create Stocks Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            market TEXT,
            sector TEXT,
            pre_market_time TEXT DEFAULT '08:30',
            post_market_time TEXT DEFAULT '15:30',
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(id),
            UNIQUE(user_id, code)
        )
    ''')

    # 5. Create Recommendations Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            mode TEXT NOT NULL,
            asset_type TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            recommendation_score REAL,
            target_price REAL,
            stop_loss REAL,
            expected_return TEXT,
            holding_period TEXT,
            investment_logic TEXT,
            risk_factors TEXT,
            confidence TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            valid_until TIMESTAMP,
            status TEXT DEFAULT 'active',
            UNIQUE(user_id, mode, code, generated_at)
        )
    ''')

    # 6. Create Recommendation Reports Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS recommendation_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            mode TEXT NOT NULL,
            report_content TEXT,
            recommendations_json TEXT,
            market_context TEXT,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 7. Create User Investment Preferences Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_investment_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE REFERENCES users(id),
            preferences_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 8. Create Dashboard Layouts Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS dashboard_layouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id),
            name TEXT NOT NULL,
            layout_json TEXT NOT NULL,
            is_default BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, name)
        )
    ''')

    # 9. Create User News Status Table (bookmarks, read status)
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_news_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            news_hash TEXT NOT NULL,
            news_title TEXT,
            news_source TEXT,
            news_url TEXT,
            news_category TEXT,
            is_read BOOLEAN DEFAULT 0,
            is_bookmarked BOOLEAN DEFAULT 0,
            read_at TIMESTAMP,
            bookmarked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, news_hash)
        )
    ''')

    # 10. Create News Cache Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cache_key TEXT UNIQUE NOT NULL,
            cache_data TEXT NOT NULL,
            source TEXT,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 11. Create News Analysis Cache Table (AI sentiment/summary)
    c.execute('''
        CREATE TABLE IF NOT EXISTS news_analysis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            news_hash TEXT UNIQUE NOT NULL,
            sentiment TEXT,
            sentiment_score REAL,
            summary TEXT,
            key_points TEXT,
            related_stocks TEXT,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 12. Create Stock Basic Table (TuShare stock_basic cache)
    c.execute('''
        CREATE TABLE IF NOT EXISTS stock_basic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            area TEXT,
            industry TEXT,
            market TEXT,
            list_date TEXT,
            list_status TEXT DEFAULT 'L',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create indexes for stock_basic search
    c.execute('CREATE INDEX IF NOT EXISTS idx_stock_basic_symbol ON stock_basic(symbol)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_stock_basic_name ON stock_basic(name)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_stock_basic_industry ON stock_basic(industry)')

    # 13. Create Fund Positions Table (user holdings)
    c.execute('''
        CREATE TABLE IF NOT EXISTS fund_positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            fund_code TEXT NOT NULL,
            fund_name TEXT,
            shares REAL NOT NULL,
            cost_basis REAL NOT NULL,
            purchase_date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, fund_code, purchase_date)
        )
    ''')

    # Create indexes for fund_positions
    c.execute('CREATE INDEX IF NOT EXISTS idx_fund_positions_user ON fund_positions(user_id)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_fund_positions_code ON fund_positions(fund_code)')

    # 14. Create Fund Diagnosis Cache Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fund_diagnosis_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fund_code TEXT NOT NULL UNIQUE,
            diagnosis_json TEXT NOT NULL,
            score INTEGER,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')

    # 15. Create Index Valuation Cache Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS index_valuation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            index_code TEXT NOT NULL,
            pe REAL,
            pb REAL,
            pe_percentile REAL,
            pb_percentile REAL,
            signal TEXT CHECK(signal IN ('green', 'yellow', 'red')),
            trade_date TEXT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(index_code, trade_date)
        )
    ''')

    # 3. Migration: Add user_id to funds if not exists
    try:
        c.execute('ALTER TABLE funds ADD COLUMN user_id INTEGER REFERENCES users(id)')
    except sqlite3.OperationalError:
        pass

    # Migration: Add scheduling columns to stocks if not exists
    for col, default in [('pre_market_time', "'08:30'"), ('post_market_time', "'15:30'"), ('is_active', '1')]:
        try:
            c.execute(f'ALTER TABLE stocks ADD COLUMN {col} TEXT DEFAULT {default}')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

    migrate_from_json_if_needed()

def migrate_from_json_if_needed():
    # Only runs if funds table is empty
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT count(*) FROM funds')
    count = cursor.fetchone()[0]
    
    if count == 0 and os.path.exists(FUNDS_JSON_PATH):
        print("Migrating funds.json to SQLite (Assigning to Admin/Null User)...")
        try:
            with open(FUNDS_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for fund in data:
                    cursor.execute('''
                        INSERT INTO funds (code, name, style, focus, pre_market_time, post_market_time, user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        fund.get('code'),
                        fund.get('name'),
                        fund.get('style', ''),
                        json.dumps(fund.get('focus', []), ensure_ascii=False),
                        "08:30",
                        "15:30",
                        1 # Default to user 1 if migrating
                    ))
            conn.commit()
            print("Migration complete.")
        except Exception as e:
            print(f"Migration failed: {e}")
    
    conn.close()

# --- User Operations ---

def create_user(user_data: Dict) -> int:
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT INTO users (username, email, hashed_password, provider, provider_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            user_data['username'],
            user_data.get('email'),
            user_data.get('hashed_password'),
            user_data.get('provider', 'local'),
            user_data.get('provider_id')
        ))
        user_id = c.lastrowid
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError("Username already exists")
    finally:
        conn.close()

def get_user_by_username(username: str) -> Optional[Dict]:
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

# --- Fund Operations (Multi-tenant) ---

def _parse_focus(fund_row: Dict) -> Dict:
    d = dict(fund_row)
    if d.get('focus') and isinstance(d['focus'], str):
        try:
            d['focus'] = json.loads(d['focus'])
        except:
            d['focus'] = []
    return d

def get_all_funds(user_id: int = None) -> List[Dict]:
    conn = get_db_connection()
    if user_id:
        funds = conn.execute('SELECT * FROM funds WHERE user_id = ?', (user_id,)).fetchall()
    else:
        # Admin or Scheduler context: fetch all
        funds = conn.execute('SELECT * FROM funds').fetchall()
    conn.close()
    return [_parse_focus(f) for f in funds]

def get_active_funds(user_id: int = None) -> List[Dict]:
    conn = get_db_connection()
    sql = 'SELECT * FROM funds WHERE is_active = 1'
    params = []
    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)
        
    funds = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    return [_parse_focus(f) for f in funds]

def get_fund_by_code(code: str, user_id: int = None) -> Optional[Dict]:
    # Note: Code might not be unique globally anymore if different users can watch same fund?
    # For now, let's assume users can have same funds. So we MUST filter by user_id if provided.
    conn = get_db_connection()
    sql = 'SELECT * FROM funds WHERE code = ?'
    params = [code]
    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)
        
    fund = conn.execute(sql, tuple(params)).fetchone()
    conn.close()
    return _parse_focus(fund) if fund else None

def upsert_fund(fund_data: Dict, user_id: int):
    """
    Insert or Update a fund for a specific user.
    """
    if not user_id:
        raise ValueError("user_id is required for upserting funds")
        
    conn = get_db_connection()
    c = conn.cursor()
    
    focus_json = json.dumps(fund_data.get('focus', []), ensure_ascii=False)
    
    # Check if exists for THIS user
    exists = c.execute('SELECT 1 FROM funds WHERE code = ? AND user_id = ?', 
                      (fund_data['code'], user_id)).fetchone()
    
    if exists:
        c.execute('''
            UPDATE funds 
            SET name=?, style=?, focus=?, pre_market_time=?, post_market_time=?, is_active=?
            WHERE code=? AND user_id=?
        ''', (
            fund_data['name'],
            fund_data.get('style', ''),
            focus_json,
            fund_data.get('pre_market_time'),
            fund_data.get('post_market_time'),
            fund_data.get('is_active', 1),
            fund_data['code'],
            user_id
        ))
    else:
        c.execute('''
            INSERT INTO funds (code, name, style, focus, pre_market_time, post_market_time, is_active, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            fund_data['code'],
            fund_data['name'],
            fund_data.get('style', ''),
            focus_json,
            fund_data.get('pre_market_time'),
            fund_data.get('post_market_time'),
            fund_data.get('is_active', 1),
            user_id
        ))
    
    conn.commit()
    conn.close()

def delete_fund(code: str, user_id: int):
    if not user_id:
        raise ValueError("user_id required")
    conn = get_db_connection()
    conn.execute('DELETE FROM funds WHERE code = ? AND user_id = ?', (code, user_id))
    conn.commit()
    conn.close()

# --- Stock Operations ---

def get_all_stocks(user_id: int) -> List[Dict]:
    if not user_id:
        return []
    conn = get_db_connection()
    stocks = conn.execute('SELECT * FROM stocks WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return [dict(s) for s in stocks]


def get_active_stocks(user_id: int = None) -> List[Dict]:
    """Get stocks with is_active = 1 for scheduled analysis."""
    conn = get_db_connection()
    sql = 'SELECT * FROM stocks WHERE is_active = 1'
    params = []
    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)

    stocks = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    return [dict(s) for s in stocks]


def get_stock_by_code(code: str, user_id: int = None) -> Optional[Dict]:
    """Get a single stock by code."""
    conn = get_db_connection()
    sql = 'SELECT * FROM stocks WHERE code = ?'
    params = [code]
    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)

    stock = conn.execute(sql, tuple(params)).fetchone()
    conn.close()
    return dict(stock) if stock else None


def upsert_stock(stock_data: Dict, user_id: int):
    if not user_id:
        raise ValueError("user_id required")

    conn = get_db_connection()
    c = conn.cursor()

    exists = c.execute('SELECT 1 FROM stocks WHERE code = ? AND user_id = ?',
                      (stock_data['code'], user_id)).fetchone()

    if exists:
        c.execute('''
            UPDATE stocks
            SET name=?, market=?, sector=?, pre_market_time=?, post_market_time=?, is_active=?
            WHERE code=? AND user_id=?
        ''', (
            stock_data['name'],
            stock_data.get('market', ''),
            stock_data.get('sector', ''),
            stock_data.get('pre_market_time', '08:30'),
            stock_data.get('post_market_time', '15:30'),
            stock_data.get('is_active', 1),
            stock_data['code'],
            user_id
        ))
    else:
        c.execute('''
            INSERT INTO stocks (code, name, market, sector, pre_market_time, post_market_time, is_active, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            stock_data['code'],
            stock_data['name'],
            stock_data.get('market', ''),
            stock_data.get('sector', ''),
            stock_data.get('pre_market_time', '08:30'),
            stock_data.get('post_market_time', '15:30'),
            stock_data.get('is_active', 1),
            user_id
        ))

    conn.commit()
    conn.close()

def delete_stock(code: str, user_id: int):
    if not user_id:
        raise ValueError("user_id required")
    conn = get_db_connection()
    conn.execute('DELETE FROM stocks WHERE code = ? AND user_id = ?', (code, user_id))
    conn.commit()
    conn.close()


# --- Recommendation Operations ---

def save_recommendation(rec_data: Dict, user_id: int = None) -> int:
    """Save a single recommendation to the database."""
    conn = get_db_connection()
    c = conn.cursor()

    risk_factors = rec_data.get('risk_factors', [])
    if isinstance(risk_factors, list):
        risk_factors = json.dumps(risk_factors, ensure_ascii=False)

    c.execute('''
        INSERT INTO recommendations (
            user_id, mode, asset_type, code, name,
            recommendation_score, target_price, stop_loss,
            expected_return, holding_period, investment_logic,
            risk_factors, confidence, valid_until, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        rec_data.get('mode', 'short'),
        rec_data.get('asset_type', 'stock'),
        rec_data.get('code'),
        rec_data.get('name'),
        rec_data.get('recommendation_score'),
        rec_data.get('target_price'),
        rec_data.get('stop_loss'),
        rec_data.get('expected_return'),
        rec_data.get('holding_period'),
        rec_data.get('investment_logic'),
        risk_factors,
        rec_data.get('confidence', '中'),
        rec_data.get('valid_until'),
        rec_data.get('status', 'active'),
    ))

    rec_id = c.lastrowid
    conn.commit()
    conn.close()
    return rec_id


def save_recommendation_report(report_data: Dict, user_id: int = None) -> int:
    """Save a recommendation report."""
    conn = get_db_connection()
    c = conn.cursor()

    recommendations_json = report_data.get('recommendations_json')
    if isinstance(recommendations_json, dict):
        recommendations_json = json.dumps(recommendations_json, ensure_ascii=False)

    market_context = report_data.get('market_context')
    if isinstance(market_context, dict):
        market_context = json.dumps(market_context, ensure_ascii=False)

    c.execute('''
        INSERT INTO recommendation_reports (
            user_id, mode, report_content, recommendations_json, market_context
        ) VALUES (?, ?, ?, ?, ?)
    ''', (
        user_id,
        report_data.get('mode', 'all'),
        report_data.get('report_content'),
        recommendations_json,
        market_context,
    ))

    report_id = c.lastrowid
    conn.commit()
    conn.close()
    return report_id


def get_recommendations(
    user_id: int = None,
    mode: str = None,
    asset_type: str = None,
    status: str = 'active',
    limit: int = 50
) -> List[Dict]:
    """Get recommendations with optional filters."""
    conn = get_db_connection()

    sql = 'SELECT * FROM recommendations WHERE 1=1'
    params = []

    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)

    if mode:
        sql += ' AND mode = ?'
        params.append(mode)

    if asset_type:
        sql += ' AND asset_type = ?'
        params.append(asset_type)

    if status:
        sql += ' AND status = ?'
        params.append(status)

    sql += ' ORDER BY generated_at DESC LIMIT ?'
    params.append(limit)

    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        # Parse risk_factors JSON
        if d.get('risk_factors'):
            try:
                d['risk_factors'] = json.loads(d['risk_factors'])
            except:
                pass
        results.append(d)

    return results


def get_recommendation_reports(
    user_id: int = None,
    mode: str = None,
    limit: int = 20
) -> List[Dict]:
    """Get recommendation reports."""
    conn = get_db_connection()

    sql = 'SELECT * FROM recommendation_reports WHERE 1=1'
    params = []

    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)

    if mode:
        sql += ' AND mode = ?'
        params.append(mode)

    sql += ' ORDER BY generated_at DESC LIMIT ?'
    params.append(limit)

    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        # Parse recommendations_json
        if d.get('recommendations_json'):
            try:
                d['recommendations_json'] = json.loads(d['recommendations_json'])
            except:
                pass
        results.append(d)

    return results


def get_latest_recommendation_report(user_id: int = None, mode: str = None) -> Optional[Dict]:
    """Get the most recent recommendation report."""
    reports = get_recommendation_reports(user_id=user_id, mode=mode, limit=1)
    return reports[0] if reports else None


def update_recommendation_status(rec_id: int, status: str):
    """Update recommendation status (active, expired, hit_target, hit_stop)."""
    conn = get_db_connection()
    conn.execute('UPDATE recommendations SET status = ? WHERE id = ?', (status, rec_id))
    conn.commit()
    conn.close()


def expire_old_recommendations(days: int = 30):
    """Mark old recommendations as expired."""
    conn = get_db_connection()
    conn.execute('''
        UPDATE recommendations
        SET status = 'expired'
        WHERE status = 'active'
        AND generated_at < datetime('now', ?)
    ''', (f'-{days} days',))
    conn.commit()
    conn.close()


# --- User Investment Preferences Operations ---

def get_user_preferences(user_id: int) -> Optional[Dict]:
    """Get user investment preferences."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM user_investment_preferences WHERE user_id = ?',
        (user_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    # Parse JSON
    if result.get('preferences_json'):
        try:
            result['preferences'] = json.loads(result['preferences_json'])
        except:
            result['preferences'] = {}
    return result


def save_user_preferences(user_id: int, preferences: Dict):
    """Save or update user investment preferences."""
    conn = get_db_connection()
    c = conn.cursor()

    preferences_json = json.dumps(preferences, ensure_ascii=False)

    # Check if exists
    exists = c.execute(
        'SELECT 1 FROM user_investment_preferences WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if exists:
        c.execute('''
            UPDATE user_investment_preferences
            SET preferences_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (preferences_json, user_id))
    else:
        c.execute('''
            INSERT INTO user_investment_preferences (user_id, preferences_json)
            VALUES (?, ?)
        ''', (user_id, preferences_json))

    conn.commit()
    conn.close()


def delete_user_preferences(user_id: int):
    """Delete user investment preferences."""
    conn = get_db_connection()
    conn.execute('DELETE FROM user_investment_preferences WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


# --- Dashboard Layout Operations ---

def get_user_layouts(user_id: int) -> List[Dict]:
    """Get all dashboard layouts for a user."""
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT * FROM dashboard_layouts WHERE user_id = ? ORDER BY is_default DESC, updated_at DESC',
        (user_id,)
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        d = dict(row)
        if d.get('layout_json'):
            try:
                d['layout'] = json.loads(d['layout_json'])
            except:
                d['layout'] = {}
        results.append(d)

    return results


def get_layout_by_id(layout_id: int, user_id: int = None) -> Optional[Dict]:
    """Get a specific dashboard layout by ID."""
    conn = get_db_connection()
    sql = 'SELECT * FROM dashboard_layouts WHERE id = ?'
    params = [layout_id]

    if user_id:
        sql += ' AND user_id = ?'
        params.append(user_id)

    row = conn.execute(sql, tuple(params)).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get('layout_json'):
        try:
            result['layout'] = json.loads(result['layout_json'])
        except:
            result['layout'] = {}

    return result


def get_default_layout(user_id: int) -> Optional[Dict]:
    """Get the default dashboard layout for a user."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM dashboard_layouts WHERE user_id = ? AND is_default = 1',
        (user_id,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get('layout_json'):
        try:
            result['layout'] = json.loads(result['layout_json'])
        except:
            result['layout'] = {}

    return result


def save_layout(user_id: int, name: str, layout: Dict, is_default: bool = False) -> int:
    """Save or update a dashboard layout."""
    conn = get_db_connection()
    c = conn.cursor()

    layout_json = json.dumps(layout, ensure_ascii=False)

    # Check if exists
    exists = c.execute(
        'SELECT id FROM dashboard_layouts WHERE user_id = ? AND name = ?',
        (user_id, name)
    ).fetchone()

    if exists:
        c.execute('''
            UPDATE dashboard_layouts
            SET layout_json = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND name = ?
        ''', (layout_json, is_default, user_id, name))
        layout_id = exists[0]
    else:
        c.execute('''
            INSERT INTO dashboard_layouts (user_id, name, layout_json, is_default)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, layout_json, is_default))
        layout_id = c.lastrowid

    # If setting as default, unset other defaults
    if is_default:
        c.execute('''
            UPDATE dashboard_layouts
            SET is_default = 0
            WHERE user_id = ? AND id != ?
        ''', (user_id, layout_id))

    conn.commit()
    conn.close()
    return layout_id


def update_layout(layout_id: int, user_id: int, updates: Dict) -> bool:
    """Update a dashboard layout."""
    conn = get_db_connection()
    c = conn.cursor()

    # Verify ownership
    exists = c.execute(
        'SELECT id FROM dashboard_layouts WHERE id = ? AND user_id = ?',
        (layout_id, user_id)
    ).fetchone()

    if not exists:
        conn.close()
        return False

    set_clauses = []
    params = []

    if 'name' in updates:
        set_clauses.append('name = ?')
        params.append(updates['name'])

    if 'layout' in updates:
        set_clauses.append('layout_json = ?')
        params.append(json.dumps(updates['layout'], ensure_ascii=False))

    if 'is_default' in updates:
        set_clauses.append('is_default = ?')
        params.append(updates['is_default'])

        # If setting as default, unset other defaults
        if updates['is_default']:
            c.execute('''
                UPDATE dashboard_layouts
                SET is_default = 0
                WHERE user_id = ? AND id != ?
            ''', (user_id, layout_id))

    if set_clauses:
        set_clauses.append('updated_at = CURRENT_TIMESTAMP')
        params.append(layout_id)
        params.append(user_id)

        sql = f"UPDATE dashboard_layouts SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"
        c.execute(sql, tuple(params))

    conn.commit()
    conn.close()
    return True


def delete_layout(layout_id: int, user_id: int) -> bool:
    """Delete a dashboard layout."""
    conn = get_db_connection()
    c = conn.cursor()

    # Verify ownership
    exists = c.execute(
        'SELECT id FROM dashboard_layouts WHERE id = ? AND user_id = ?',
        (layout_id, user_id)
    ).fetchone()

    if not exists:
        conn.close()
        return False

    c.execute('DELETE FROM dashboard_layouts WHERE id = ? AND user_id = ?', (layout_id, user_id))
    conn.commit()
    conn.close()
    return True


def set_default_layout(user_id: int, layout_id: int) -> bool:
    """Set a layout as the default for a user."""
    conn = get_db_connection()
    c = conn.cursor()

    # Verify ownership
    exists = c.execute(
        'SELECT id FROM dashboard_layouts WHERE id = ? AND user_id = ?',
        (layout_id, user_id)
    ).fetchone()

    if not exists:
        conn.close()
        return False

    # Unset all defaults for this user
    c.execute('UPDATE dashboard_layouts SET is_default = 0 WHERE user_id = ?', (user_id,))

    # Set the new default
    c.execute('UPDATE dashboard_layouts SET is_default = 1 WHERE id = ?', (layout_id,))

    conn.commit()
    conn.close()
    return True


# --- News Status Operations ---

def get_news_status(user_id: int, news_hash: str) -> Optional[Dict]:
    """Get the read/bookmark status for a specific news item."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM user_news_status WHERE user_id = ? AND news_hash = ?',
        (user_id, news_hash)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_bookmarked_news(user_id: int, limit: int = 50, offset: int = 0) -> List[Dict]:
    """Get all bookmarked news for a user."""
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT * FROM user_news_status
           WHERE user_id = ? AND is_bookmarked = 1
           ORDER BY bookmarked_at DESC
           LIMIT ? OFFSET ?''',
        (user_id, limit, offset)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_user_read_news_hashes(user_id: int) -> set:
    """Get all read news hashes for a user (for quick lookup)."""
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT news_hash FROM user_news_status WHERE user_id = ? AND is_read = 1',
        (user_id,)
    ).fetchall()
    conn.close()
    return {row['news_hash'] for row in rows}


def mark_news_read(user_id: int, news_hash: str, news_title: str = None,
                   news_source: str = None, news_url: str = None, news_category: str = None):
    """Mark a news item as read."""
    conn = get_db_connection()
    c = conn.cursor()

    exists = c.execute(
        'SELECT id FROM user_news_status WHERE user_id = ? AND news_hash = ?',
        (user_id, news_hash)
    ).fetchone()

    if exists:
        c.execute('''
            UPDATE user_news_status
            SET is_read = 1, read_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND news_hash = ?
        ''', (user_id, news_hash))
    else:
        c.execute('''
            INSERT INTO user_news_status
            (user_id, news_hash, news_title, news_source, news_url, news_category, is_read, read_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (user_id, news_hash, news_title, news_source, news_url, news_category))

    conn.commit()
    conn.close()


def toggle_news_bookmark(user_id: int, news_hash: str, news_title: str = None,
                         news_source: str = None, news_url: str = None,
                         news_category: str = None) -> bool:
    """Toggle bookmark status for a news item. Returns new bookmark state."""
    conn = get_db_connection()
    c = conn.cursor()

    exists = c.execute(
        'SELECT id, is_bookmarked FROM user_news_status WHERE user_id = ? AND news_hash = ?',
        (user_id, news_hash)
    ).fetchone()

    if exists:
        new_state = 0 if exists['is_bookmarked'] else 1
        c.execute('''
            UPDATE user_news_status
            SET is_bookmarked = ?, bookmarked_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE bookmarked_at END
            WHERE user_id = ? AND news_hash = ?
        ''', (new_state, new_state, user_id, news_hash))
    else:
        new_state = 1
        c.execute('''
            INSERT INTO user_news_status
            (user_id, news_hash, news_title, news_source, news_url, news_category, is_bookmarked, bookmarked_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
        ''', (user_id, news_hash, news_title, news_source, news_url, news_category))

    conn.commit()
    conn.close()
    return bool(new_state)


def set_news_bookmark(user_id: int, news_hash: str, bookmarked: bool,
                      news_title: str = None, news_source: str = None,
                      news_url: str = None, news_category: str = None):
    """Set bookmark status explicitly."""
    conn = get_db_connection()
    c = conn.cursor()

    exists = c.execute(
        'SELECT id FROM user_news_status WHERE user_id = ? AND news_hash = ?',
        (user_id, news_hash)
    ).fetchone()

    if exists:
        c.execute('''
            UPDATE user_news_status
            SET is_bookmarked = ?, bookmarked_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE bookmarked_at END
            WHERE user_id = ? AND news_hash = ?
        ''', (bookmarked, bookmarked, user_id, news_hash))
    else:
        c.execute('''
            INSERT INTO user_news_status
            (user_id, news_hash, news_title, news_source, news_url, news_category, is_bookmarked, bookmarked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END)
        ''', (user_id, news_hash, news_title, news_source, news_url, news_category, bookmarked, bookmarked))

    conn.commit()
    conn.close()


# --- News Cache Operations ---

def get_news_cache(cache_key: str) -> Optional[Dict]:
    """Get cached news data if not expired."""
    conn = get_db_connection()
    row = conn.execute(
        '''SELECT * FROM news_cache
           WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP''',
        (cache_key,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get('cache_data'):
        try:
            result['data'] = json.loads(result['cache_data'])
        except:
            result['data'] = None
    return result


def set_news_cache(cache_key: str, data: any, source: str, ttl_seconds: int = 600):
    """Set news cache with TTL."""
    conn = get_db_connection()
    c = conn.cursor()

    cache_data = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data

    c.execute('''
        INSERT OR REPLACE INTO news_cache (cache_key, cache_data, source, expires_at)
        VALUES (?, ?, ?, datetime('now', '+' || ? || ' seconds'))
    ''', (cache_key, cache_data, source, ttl_seconds))

    conn.commit()
    conn.close()


def clear_expired_news_cache():
    """Remove expired cache entries."""
    conn = get_db_connection()
    conn.execute('DELETE FROM news_cache WHERE expires_at < CURRENT_TIMESTAMP')
    conn.commit()
    conn.close()


# --- News Analysis Cache Operations ---

def get_news_analysis(news_hash: str) -> Optional[Dict]:
    """Get cached AI analysis for a news item."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM news_analysis_cache WHERE news_hash = ?',
        (news_hash,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get('key_points'):
        try:
            result['key_points'] = json.loads(result['key_points'])
        except:
            pass
    if result.get('related_stocks'):
        try:
            result['related_stocks'] = json.loads(result['related_stocks'])
        except:
            pass
    return result


def save_news_analysis(news_hash: str, sentiment: str, sentiment_score: float,
                       summary: str, key_points: List[str] = None,
                       related_stocks: List[Dict] = None):
    """Save AI analysis results for a news item."""
    conn = get_db_connection()
    c = conn.cursor()

    key_points_json = json.dumps(key_points, ensure_ascii=False) if key_points else None
    related_stocks_json = json.dumps(related_stocks, ensure_ascii=False) if related_stocks else None

    c.execute('''
        INSERT OR REPLACE INTO news_analysis_cache
        (news_hash, sentiment, sentiment_score, summary, key_points, related_stocks, analyzed_at)
        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (news_hash, sentiment, sentiment_score, summary, key_points_json, related_stocks_json))

    conn.commit()
    conn.close()


def get_multiple_news_analysis(news_hashes: List[str]) -> Dict[str, Dict]:
    """Get cached AI analysis for multiple news items."""
    if not news_hashes:
        return {}

    conn = get_db_connection()
    placeholders = ','.join('?' * len(news_hashes))
    rows = conn.execute(
        f'SELECT * FROM news_analysis_cache WHERE news_hash IN ({placeholders})',
        tuple(news_hashes)
    ).fetchall()
    conn.close()

    result = {}
    for row in rows:
        d = dict(row)
        news_hash = d['news_hash']
        if d.get('key_points'):
            try:
                d['key_points'] = json.loads(d['key_points'])
            except:
                pass
        if d.get('related_stocks'):
            try:
                d['related_stocks'] = json.loads(d['related_stocks'])
            except:
                pass
        result[news_hash] = d

    return result


# --- Stock Basic Operations (TuShare stock_basic cache) ---

def upsert_stock_basic_batch(stocks: List[Dict]) -> int:
    """
    Batch insert/update stock basic info.

    Args:
        stocks: List of dicts with keys: ts_code, symbol, name, area, industry, market, list_date, list_status

    Returns:
        Number of stocks inserted/updated
    """
    if not stocks:
        return 0

    conn = get_db_connection()
    c = conn.cursor()

    count = 0
    for stock in stocks:
        try:
            c.execute('''
                INSERT OR REPLACE INTO stock_basic
                (ts_code, symbol, name, area, industry, market, list_date, list_status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                stock.get('ts_code'),
                stock.get('symbol'),
                stock.get('name'),
                stock.get('area'),
                stock.get('industry'),
                stock.get('market'),
                stock.get('list_date'),
                stock.get('list_status', 'L'),
            ))
            count += 1
        except Exception as e:
            print(f"Error inserting stock {stock.get('ts_code')}: {e}")
            continue

    conn.commit()
    conn.close()
    return count


def search_stock_basic(query: str, limit: int = 50) -> List[Dict]:
    """
    Search stocks by code prefix or name (fuzzy match).

    Args:
        query: Search query (code prefix or name substring)
        limit: Maximum number of results

    Returns:
        List of matching stocks with fields: code, name, industry, market, area, list_date
    """
    conn = get_db_connection()

    if not query:
        # Return first N stocks if no query
        rows = conn.execute(
            'SELECT symbol, name, industry, market, area, list_date FROM stock_basic WHERE list_status = ? ORDER BY symbol LIMIT ?',
            ('L', limit)
        ).fetchall()
    else:
        query_lower = query.lower()
        # Search by code prefix OR name contains
        rows = conn.execute('''
            SELECT symbol, name, industry, market, area, list_date
            FROM stock_basic
            WHERE list_status = 'L'
              AND (symbol LIKE ? OR LOWER(name) LIKE ? OR LOWER(industry) LIKE ?)
            ORDER BY
              CASE WHEN symbol LIKE ? THEN 0 ELSE 1 END,
              symbol
            LIMIT ?
        ''', (
            f'{query}%',           # code prefix
            f'%{query_lower}%',    # name contains
            f'%{query_lower}%',    # industry contains
            f'{query}%',           # prefer code prefix matches
            limit
        )).fetchall()

    conn.close()

    # Convert to list of dicts with frontend-friendly field names
    results = []
    for row in rows:
        results.append({
            'code': row['symbol'],
            'name': row['name'],
            'industry': row['industry'],
            'market': row['market'],
            'area': row['area'],
            'list_date': row['list_date'],
        })

    return results


def get_all_stock_basic() -> List[Dict]:
    """Get all stock basic info (listed stocks only)."""
    conn = get_db_connection()
    rows = conn.execute(
        'SELECT symbol, name, industry, market, area, list_date FROM stock_basic WHERE list_status = ?',
        ('L',)
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_stock_basic_count() -> int:
    """Get count of stocks in stock_basic table."""
    conn = get_db_connection()
    count = conn.execute('SELECT COUNT(*) FROM stock_basic WHERE list_status = ?', ('L',)).fetchone()[0]
    conn.close()
    return count


def get_stock_basic_last_updated() -> Optional[str]:
    """Get the last update timestamp from stock_basic table."""
    conn = get_db_connection()
    row = conn.execute('SELECT MAX(updated_at) FROM stock_basic').fetchone()
    conn.close()
    return row[0] if row and row[0] else None


# --- Fund Position Operations ---

def get_user_positions(user_id: int) -> List[Dict]:
    """Get all fund positions for a user."""
    if not user_id:
        return []
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT * FROM fund_positions WHERE user_id = ? ORDER BY purchase_date DESC''',
        (user_id,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_position_by_id(position_id: int, user_id: int) -> Optional[Dict]:
    """Get a specific position by ID."""
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM fund_positions WHERE id = ? AND user_id = ?',
        (position_id, user_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_positions_by_fund(fund_code: str, user_id: int) -> List[Dict]:
    """Get all positions for a specific fund."""
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT * FROM fund_positions WHERE fund_code = ? AND user_id = ? ORDER BY purchase_date DESC''',
        (fund_code, user_id)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def create_position(position_data: Dict, user_id: int) -> int:
    """Create a new fund position."""
    if not user_id:
        raise ValueError("user_id is required")

    conn = get_db_connection()
    c = conn.cursor()

    try:
        c.execute('''
            INSERT INTO fund_positions (user_id, fund_code, fund_name, shares, cost_basis, purchase_date, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            position_data['fund_code'],
            position_data.get('fund_name', ''),
            position_data['shares'],
            position_data['cost_basis'],
            position_data['purchase_date'],
            position_data.get('notes', ''),
        ))
        position_id = c.lastrowid
        conn.commit()
        return position_id
    except sqlite3.IntegrityError as e:
        conn.close()
        raise ValueError(f"Position already exists or constraint violation: {e}")
    finally:
        conn.close()


def update_position(position_id: int, user_id: int, updates: Dict) -> bool:
    """Update an existing position."""
    conn = get_db_connection()
    c = conn.cursor()

    # Verify ownership
    exists = c.execute(
        'SELECT id FROM fund_positions WHERE id = ? AND user_id = ?',
        (position_id, user_id)
    ).fetchone()

    if not exists:
        conn.close()
        return False

    set_clauses = []
    params = []

    allowed_fields = ['fund_name', 'shares', 'cost_basis', 'purchase_date', 'notes']
    for field in allowed_fields:
        if field in updates:
            set_clauses.append(f'{field} = ?')
            params.append(updates[field])

    if set_clauses:
        set_clauses.append('updated_at = CURRENT_TIMESTAMP')
        params.extend([position_id, user_id])

        sql = f"UPDATE fund_positions SET {', '.join(set_clauses)} WHERE id = ? AND user_id = ?"
        c.execute(sql, tuple(params))

    conn.commit()
    conn.close()
    return True


def delete_position(position_id: int, user_id: int) -> bool:
    """Delete a position."""
    conn = get_db_connection()
    c = conn.cursor()

    # Verify ownership
    exists = c.execute(
        'SELECT id FROM fund_positions WHERE id = ? AND user_id = ?',
        (position_id, user_id)
    ).fetchone()

    if not exists:
        conn.close()
        return False

    c.execute('DELETE FROM fund_positions WHERE id = ? AND user_id = ?', (position_id, user_id))
    conn.commit()
    conn.close()
    return True


def get_portfolio_summary(user_id: int) -> Dict:
    """Get aggregated portfolio summary for a user."""
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT fund_code, fund_name, SUM(shares) as total_shares,
           SUM(shares * cost_basis) / SUM(shares) as avg_cost,
           SUM(shares * cost_basis) as total_cost
           FROM fund_positions
           WHERE user_id = ?
           GROUP BY fund_code''',
        (user_id,)
    ).fetchall()
    conn.close()

    positions = []
    total_cost = 0
    for row in rows:
        d = dict(row)
        total_cost += d['total_cost'] or 0
        positions.append({
            'fund_code': d['fund_code'],
            'fund_name': d['fund_name'],
            'total_shares': round(d['total_shares'], 4) if d['total_shares'] else 0,
            'avg_cost': round(d['avg_cost'], 4) if d['avg_cost'] else 0,
            'total_cost': round(d['total_cost'], 2) if d['total_cost'] else 0,
        })

    return {
        'positions': positions,
        'total_cost': round(total_cost, 2),
        'position_count': len(positions),
    }


# --- Fund Diagnosis Cache Operations ---

def get_diagnosis_cache(fund_code: str) -> Optional[Dict]:
    """Get cached diagnosis for a fund if not expired."""
    conn = get_db_connection()
    row = conn.execute(
        '''SELECT * FROM fund_diagnosis_cache
           WHERE fund_code = ? AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)''',
        (fund_code,)
    ).fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get('diagnosis_json'):
        try:
            result['diagnosis'] = json.loads(result['diagnosis_json'])
        except:
            result['diagnosis'] = {}
    return result


def save_diagnosis_cache(fund_code: str, diagnosis: Dict, score: int, ttl_hours: int = 6):
    """Save diagnosis to cache with TTL."""
    conn = get_db_connection()
    c = conn.cursor()

    diagnosis_json = json.dumps(diagnosis, ensure_ascii=False)

    c.execute('''
        INSERT OR REPLACE INTO fund_diagnosis_cache
        (fund_code, diagnosis_json, score, computed_at, expires_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP, datetime('now', '+' || ? || ' hours'))
    ''', (fund_code, diagnosis_json, score, ttl_hours))

    conn.commit()
    conn.close()


def clear_diagnosis_cache(fund_code: str = None):
    """Clear diagnosis cache (all or specific fund)."""
    conn = get_db_connection()
    if fund_code:
        conn.execute('DELETE FROM fund_diagnosis_cache WHERE fund_code = ?', (fund_code,))
    else:
        conn.execute('DELETE FROM fund_diagnosis_cache')
    conn.commit()
    conn.close()


def clear_expired_diagnosis_cache():
    """Remove expired diagnosis cache entries."""
    conn = get_db_connection()
    conn.execute('DELETE FROM fund_diagnosis_cache WHERE expires_at < CURRENT_TIMESTAMP')
    conn.commit()
    conn.close()


# --- Index Valuation Cache Operations ---

def get_valuation_cache(index_code: str, trade_date: str = None) -> Optional[Dict]:
    """Get cached valuation for an index."""
    conn = get_db_connection()

    if trade_date:
        row = conn.execute(
            'SELECT * FROM index_valuation_cache WHERE index_code = ? AND trade_date = ?',
            (index_code, trade_date)
        ).fetchone()
    else:
        # Get latest
        row = conn.execute(
            'SELECT * FROM index_valuation_cache WHERE index_code = ? ORDER BY trade_date DESC LIMIT 1',
            (index_code,)
        ).fetchone()

    conn.close()
    return dict(row) if row else None


def save_valuation_cache(valuation_data: Dict):
    """Save index valuation to cache."""
    conn = get_db_connection()
    c = conn.cursor()

    c.execute('''
        INSERT OR REPLACE INTO index_valuation_cache
        (index_code, pe, pb, pe_percentile, pb_percentile, signal, trade_date, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ''', (
        valuation_data['index_code'],
        valuation_data.get('pe'),
        valuation_data.get('pb'),
        valuation_data.get('pe_percentile'),
        valuation_data.get('pb_percentile'),
        valuation_data.get('signal'),
        valuation_data.get('trade_date'),
    ))

    conn.commit()
    conn.close()


def get_valuation_history(index_code: str, limit: int = 30) -> List[Dict]:
    """Get valuation history for an index."""
    conn = get_db_connection()
    rows = conn.execute(
        '''SELECT * FROM index_valuation_cache
           WHERE index_code = ?
           ORDER BY trade_date DESC
           LIMIT ?''',
        (index_code, limit)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
