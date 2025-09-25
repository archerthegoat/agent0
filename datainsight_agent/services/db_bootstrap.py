from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional


def init_sqlite_min(db_path: Path) -> str:
	"""Create minimal demo table (user_id, month, active) and seed rows.

	Returns SQLAlchemy URL string.
	"""
	from sqlalchemy import create_engine, text
	db_url = f"sqlite:///{db_path}"
	engine = create_engine(db_url)
	with engine.begin() as conn:
		conn.execute(text(
			"""
			CREATE TABLE IF NOT EXISTS dws_user_activity_monthly (
				user_id TEXT,
				month TEXT,
				active INTEGER
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity_monthly"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity_monthly (user_id, month, active) VALUES
			('u1', '2025-08', 1),
			('u2', '2025-08', 1),
			('u1', '2025-09', 1),
			('u3', '2025-09', 1);
			"""
		))
	return db_url


def init_sqlite_dw_lite(db_path: Path) -> str:
	"""Create/widen fact table with dimensions and seed demo rows."""
	from sqlalchemy import create_engine, text
	db_url = f"sqlite:///{db_path}"
	engine = create_engine(db_url)
	with engine.begin() as conn:
		conn.execute(text("DROP TABLE IF EXISTS dws_user_activity_monthly"))
		conn.execute(text(
			"""
			CREATE TABLE dws_user_activity_monthly (
				user_id TEXT,
				month TEXT,
				active INTEGER,
				channel_code TEXT,
				device TEXT,
				region TEXT,
				user_level TEXT,
				app_version TEXT,
				campaign TEXT,
				-- new dimensions
				device_model TEXT,
				os_version TEXT,
				country TEXT,
				city TEXT,
				network_type TEXT,
				channel_subtype TEXT,
				ab_bucket TEXT,
				user_segment TEXT
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity_monthly"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity_monthly (
				user_id, month, active, channel_code, device, region, user_level, app_version, campaign,
				device_model, os_version, country, city, network_type, channel_subtype, ab_bucket, user_segment
			) VALUES
			('u1', '2025-09', 1, 'wechat', 'ios', 'east', 'vip', '1.0.0', 'c1', 'iphone', 'iOS17', 'CN', 'shanghai', 'wifi', 'qrcode', 'A', 'active'),
			('u2', '2025-09', 1, 'wechat', 'android', 'east', 'normal', '1.0.1', 'c2', 'mi', 'Android13', 'CN', 'shanghai', '5g', 'organic', 'B', 'new'),
			('u3', '2025-09', 1, 'appstore', 'ios', 'north', 'vip', '1.0.0', 'c1', 'iphone', 'iOS16', 'CN', 'beijing', 'wifi', 'paid', 'A', 'active'),
			('u4', '2025-09', 1, 'appstore', 'android', 'south', 'normal', '1.0.2', 'c3', 'pixel', 'Android12', 'CN', 'shenzhen', '4g', 'referral', 'B', 'churn_risk'),
			('u5', '2025-09', 1, 'web', 'web', 'west', 'normal', 'web', 'c0', 'pc', 'web', 'CN', 'hangzhou', 'ethernet', 'organic', 'A', 'active'),
			('u1', '2025-08', 1, 'wechat', 'ios', 'east', 'vip', '0.9.9', 'c0', 'iphone', 'iOS16', 'CN', 'shanghai', 'wifi', 'qrcode', 'A', 'active'),
			('u2', '2025-08', 1, 'wechat', 'android', 'east', 'normal', '0.9.9', 'c0', 'mi', 'Android12', 'CN', 'shanghai', '4g', 'organic', 'B', 'new')
			"""
		))
	return db_url


def init_mysql_min(database_url: str) -> None:
	"""Create MySQL table (minimal) and seed demo rows using DATABASE_URL."""
	from sqlalchemy import create_engine, text
	engine = create_engine(database_url)
	with engine.begin() as conn:
		conn.execute(text(
			"""
			CREATE TABLE IF NOT EXISTS dws_user_activity_monthly (
				user_id varchar(64) NOT NULL,
				month char(7) NOT NULL,
				active tinyint NOT NULL,
				PRIMARY KEY (user_id, month)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity_monthly"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity_monthly (user_id, month, active) VALUES
			('u1', '2025-08', 1),
			('u2', '2025-08', 1),
			('u1', '2025-09', 1),
			('u3', '2025-09', 1)
			ON DUPLICATE KEY UPDATE active=VALUES(active);
			"""
		))


def init_postgresql_dw(database_url: str) -> None:
	"""Create PostgreSQL table and seed demo rows."""
	from sqlalchemy import create_engine, text
	engine = create_engine(database_url)
	with engine.begin() as conn:
		conn.execute(text(
			"""
			CREATE TABLE IF NOT EXISTS dws_user_activity_monthly (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32),
				user_level VARCHAR(32),
				app_version VARCHAR(32),
				campaign VARCHAR(32),
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				PRIMARY KEY (user_id, month)
			);
			"""
		))
		# 创建索引
		conn.execute(text(
			"CREATE INDEX IF NOT EXISTS idx_dws_user_activity_monthly_month ON dws_user_activity_monthly(month);"
		))
		conn.execute(text("DELETE FROM dws_user_activity_monthly"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity_monthly (user_id, month, active, channel_code, device, region, user_level, app_version, campaign) VALUES
			('u1', '2024-01', true, 'organic', 'mobile', 'beijing', 'premium', '1.0.0', 'spring2024'),
			('u2', '2024-01', true, 'paid', 'desktop', 'shanghai', 'basic', '1.0.0', 'spring2024'),
			('u1', '2024-02', true, 'organic', 'mobile', 'beijing', 'premium', '1.0.1', 'spring2024'),
			('u3', '2024-02', true, 'social', 'tablet', 'guangzhou', 'basic', '1.0.0', 'spring2024'),
			('u2', '2024-03', false, 'paid', 'desktop', 'shanghai', 'basic', '1.0.1', 'spring2024'),
			('u4', '2024-03', true, 'organic', 'mobile', 'shenzhen', 'premium', '1.0.1', 'spring2024')
			ON CONFLICT (user_id, month) DO UPDATE SET 
				active = EXCLUDED.active,
				channel_code = EXCLUDED.channel_code,
				device = EXCLUDED.device,
				region = EXCLUDED.region,
				user_level = EXCLUDED.user_level,
				app_version = EXCLUDED.app_version,
				campaign = EXCLUDED.campaign;
			"""
		))


def init_clickhouse_dw(database_url: str) -> None:
	"""Create ClickHouse table and seed demo rows."""
	try:
		from clickhouse_driver import Client
		import urllib.parse as urlparse
		
		# Parse URL to extract connection parameters
		parsed = urlparse.urlparse(database_url)
		
		client = Client(
			host=parsed.hostname or 'localhost',
			port=parsed.port or 9000,
			user=parsed.username or 'default',
			password=parsed.password or '',
			database=parsed.path.lstrip('/') or 'default'
		)
		
		# Create table
		client.execute("""
			CREATE TABLE IF NOT EXISTS dws_user_activity_monthly (
				user_id String,
				month Date,
				active UInt8,
				channel_code String,
				device String,
				region String,
				user_level String,
				app_version String,
				campaign String,
				created_at DateTime DEFAULT now()
			) ENGINE = MergeTree()
			ORDER BY (user_id, month)
		""")
		
		# Clear existing data
		client.execute("TRUNCATE TABLE dws_user_activity_monthly")
		
		# Insert demo data
		client.execute("""
			INSERT INTO dws_user_activity_monthly (user_id, month, active, channel_code, device, region, user_level, app_version, campaign) VALUES
			('u1', '2024-01-01', 1, 'organic', 'mobile', 'beijing', 'premium', '1.0.0', 'spring2024'),
			('u2', '2024-01-01', 1, 'paid', 'desktop', 'shanghai', 'basic', '1.0.0', 'spring2024'),
			('u1', '2024-02-01', 1, 'organic', 'mobile', 'beijing', 'premium', '1.0.1', 'spring2024'),
			('u3', '2024-02-01', 1, 'social', 'tablet', 'guangzhou', 'basic', '1.0.0', 'spring2024'),
			('u2', '2024-03-01', 0, 'paid', 'desktop', 'shanghai', 'basic', '1.0.1', 'spring2024'),
			('u4', '2024-03-01', 1, 'organic', 'mobile', 'shenzhen', 'premium', '1.0.1', 'spring2024')
		""")
		
	except ImportError:
		raise ImportError(
			"ClickHouse initialization requires clickhouse-driver. "
			"Install with: pip install clickhouse-driver"
		)

