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
