"""
Database operations for Silver Metrics Tracker.
Handles SQLite database creation, CRUD operations, and data queries.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from scripts.config import DB_PATH, DATA_DIR

logger = logging.getLogger(__name__)


def ensure_directories():
    """Create necessary directories if they don't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    """Context manager for database connections."""
    ensure_directories()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()


def init_database():
    """Initialize database with required tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Spot prices table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS spot_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                price_usd REAL NOT NULL,
                change_24h REAL,
                change_pct_24h REAL
            )
        """)
        
        # Physical premiums table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS premiums (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                product_type TEXT NOT NULL,
                spot_price REAL NOT NULL,
                physical_price REAL NOT NULL,
                premium_usd REAL NOT NULL,
                premium_pct REAL NOT NULL
            )
        """)
        
        # COMEX inventory table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'CME',
                registered_oz REAL NOT NULL,
                eligible_oz REAL NOT NULL,
                total_oz REAL NOT NULL,
                daily_change_oz REAL
            )
        """)
        
        # Margin requirements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS margins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'CME',
                contract TEXT NOT NULL,
                initial_margin REAL NOT NULL,
                maintenance_margin REAL NOT NULL,
                margin_pct REAL
            )
        """)
        
        # Lease rates / proxy data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lease_rates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                rate_type TEXT NOT NULL,
                rate_pct REAL NOT NULL,
                tenor TEXT
            )
        """)
        
        # Shanghai Gold Exchange premium table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shanghai_premium (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'SGE',
                shanghai_spot REAL NOT NULL,
                western_spot REAL NOT NULL,
                premium_usd REAL NOT NULL,
                premium_pct REAL NOT NULL
            )
        """)
        
        # Aggregated metrics table (for dashboard snapshots)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metrics_snapshot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                spot_price REAL,
                premium_pct REAL,
                inventory_total_moz REAL,
                inventory_registered_moz REAL,
                margin_initial REAL,
                margin_days_stable INTEGER,
                lease_rate_proxy REAL,
                shanghai_premium_usd REAL,
                status_premiums TEXT,
                status_inventory TEXT,
                status_margins TEXT,
                status_lease TEXT,
                status_shanghai TEXT,
                composite_score INTEGER
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spot_timestamp ON spot_prices(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_premiums_timestamp ON premiums(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_inventory_timestamp ON inventory(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_margins_timestamp ON margins(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_shanghai_timestamp ON shanghai_premium(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshot_timestamp ON metrics_snapshot(timestamp)")
        
        logger.info("Database initialized successfully")


# === INSERT OPERATIONS ===

def insert_spot_price(source: str, price_usd: float, change_24h: float = None, 
                      change_pct_24h: float = None) -> int:
    """Insert a new spot price record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO spot_prices (source, price_usd, change_24h, change_pct_24h)
            VALUES (?, ?, ?, ?)
        """, (source, price_usd, change_24h, change_pct_24h))
        return cursor.lastrowid


def insert_premium(source: str, product_type: str, spot_price: float,
                   physical_price: float, premium_usd: float, premium_pct: float) -> int:
    """Insert a new premium record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO premiums (source, product_type, spot_price, physical_price, 
                                  premium_usd, premium_pct)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (source, product_type, spot_price, physical_price, premium_usd, premium_pct))
        return cursor.lastrowid


def insert_inventory(registered_oz: float, eligible_oz: float, total_oz: float,
                     daily_change_oz: float = None, source: str = "CME") -> int:
    """Insert a new inventory record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO inventory (source, registered_oz, eligible_oz, total_oz, daily_change_oz)
            VALUES (?, ?, ?, ?, ?)
        """, (source, registered_oz, eligible_oz, total_oz, daily_change_oz))
        return cursor.lastrowid


def insert_margin(contract: str, initial_margin: float, maintenance_margin: float,
                  margin_pct: float = None, source: str = "CME") -> int:
    """Insert a new margin record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO margins (source, contract, initial_margin, maintenance_margin, margin_pct)
            VALUES (?, ?, ?, ?, ?)
        """, (source, contract, initial_margin, maintenance_margin, margin_pct))
        return cursor.lastrowid


def insert_lease_rate(source: str, rate_type: str, rate_pct: float, tenor: str = None) -> int:
    """Insert a new lease rate record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO lease_rates (source, rate_type, rate_pct, tenor)
            VALUES (?, ?, ?, ?)
        """, (source, rate_type, rate_pct, tenor))
        return cursor.lastrowid


def insert_shanghai_premium(shanghai_spot: float, western_spot: float, 
                            premium_usd: float, premium_pct: float, source: str = "SGE") -> int:
    """Insert a new Shanghai premium record."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shanghai_premium (source, shanghai_spot, western_spot, 
                                         premium_usd, premium_pct)
            VALUES (?, ?, ?, ?, ?)
        """, (source, shanghai_spot, western_spot, premium_usd, premium_pct))
        return cursor.lastrowid


def insert_metrics_snapshot(data: Dict[str, Any]) -> int:
    """Insert a metrics snapshot for the dashboard."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO metrics_snapshot (
                spot_price, premium_pct, inventory_total_moz, inventory_registered_moz,
                margin_initial, margin_days_stable, lease_rate_proxy, shanghai_premium_usd,
                status_premiums, status_inventory, status_margins, status_lease, status_shanghai,
                composite_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('spot_price'),
            data.get('premium_pct'),
            data.get('inventory_total_moz'),
            data.get('inventory_registered_moz'),
            data.get('margin_initial'),
            data.get('margin_days_stable'),
            data.get('lease_rate_proxy'),
            data.get('shanghai_premium_usd'),
            data.get('status_premiums'),
            data.get('status_inventory'),
            data.get('status_margins'),
            data.get('status_lease'),
            data.get('status_shanghai'),
            data.get('composite_score')
        ))
        return cursor.lastrowid


# === QUERY OPERATIONS ===

def get_latest_spot_price() -> Optional[Dict]:
    """Get the most recent spot price."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM spot_prices ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_premium() -> Optional[Dict]:
    """Get the most recent premium data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM premiums ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_inventory() -> Optional[Dict]:
    """Get the most recent inventory data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM inventory ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_margin() -> Optional[Dict]:
    """Get the most recent margin data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM margins ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_shanghai_premium() -> Optional[Dict]:
    """Get the most recent Shanghai premium data."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM shanghai_premium ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_latest_snapshot() -> Optional[Dict]:
    """Get the most recent metrics snapshot."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM metrics_snapshot ORDER BY timestamp DESC LIMIT 1
        """)
        row = cursor.fetchone()
        return dict(row) if row else None


def get_historical_data(table: str, days: int = 30, limit: int = 1000) -> List[Dict]:
    """Get historical data from a table for the past N days."""
    valid_tables = ['spot_prices', 'premiums', 'inventory', 'margins', 
                    'lease_rates', 'shanghai_premium', 'metrics_snapshot']
    if table not in valid_tables:
        raise ValueError(f"Invalid table: {table}")
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(days=days)
        cursor.execute(f"""
            SELECT * FROM {table} 
            WHERE timestamp >= ? 
            ORDER BY timestamp ASC
            LIMIT ?
        """, (cutoff.isoformat(), limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_margin_last_change_date() -> Optional[datetime]:
    """Get the date of the last margin change."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m1.timestamp, m1.initial_margin
            FROM margins m1
            INNER JOIN (
                SELECT timestamp, initial_margin,
                       LAG(initial_margin) OVER (ORDER BY timestamp) as prev_margin
                FROM margins
                ORDER BY timestamp DESC
            ) m2 ON m1.timestamp = m2.timestamp
            WHERE m2.initial_margin != m2.prev_margin OR m2.prev_margin IS NULL
            ORDER BY m1.timestamp DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        if row:
            return datetime.fromisoformat(row['timestamp'])
        return None


def get_inventory_trend(days: int = 14) -> Dict[str, Any]:
    """Calculate inventory trend over the past N days."""
    data = get_historical_data('inventory', days=days)
    if len(data) < 2:
        return {'trend': 'unknown', 'change_moz': 0, 'data_points': len(data)}
    
    first = data[0]['total_oz']
    last = data[-1]['total_oz']
    change = last - first
    change_moz = change / 1_000_000
    
    if change_moz > 5:
        trend = 'recovering'
    elif change_moz < -5:
        trend = 'declining'
    else:
        trend = 'stable'
    
    return {
        'trend': trend,
        'change_moz': round(change_moz, 2),
        'start_moz': round(first / 1_000_000, 2),
        'end_moz': round(last / 1_000_000, 2),
        'data_points': len(data)
    }


# === UTILITY OPERATIONS ===

def cleanup_old_data(days_to_keep: int = 365):
    """Remove data older than specified days to manage database size."""
    cutoff = datetime.now() - timedelta(days=days_to_keep)
    tables = ['spot_prices', 'premiums', 'inventory', 'margins', 
              'lease_rates', 'metrics_snapshot']
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"""
                DELETE FROM {table} WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            logger.info(f"Cleaned up {cursor.rowcount} old records from {table}")


def get_database_stats() -> Dict[str, int]:
    """Get record counts for all tables."""
    tables = ['spot_prices', 'premiums', 'inventory', 'margins', 
              'lease_rates', 'metrics_snapshot']
    stats = {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            stats[table] = cursor.fetchone()['count']
    
    return stats


if __name__ == "__main__":
    # Initialize database when run directly
    logging.basicConfig(level=logging.INFO)
    init_database()
    print(f"Database initialized at: {DB_PATH}")
    print(f"Stats: {get_database_stats()}")
