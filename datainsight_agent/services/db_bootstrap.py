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
			CREATE TABLE IF NOT EXISTS dws_user_activity (
				user_id TEXT,
				month TEXT,
				active INTEGER
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity (user_id, month, active) VALUES
			('u1', '2022-01', 1),
			('u2', '2022-01', 1),
			('u1', '2022-02', 0),
			('u3', '2022-02', 1);
			"""
		))
	return db_url


def init_sqlite_dw_lite(db_path: Path) -> str:
	"""Create/widen fact table with dimensions and seed demo rows."""
	from sqlalchemy import create_engine, text
	db_url = f"sqlite:///{db_path}"
	engine = create_engine(db_url)
	with engine.begin() as conn:
		conn.execute(text("DROP TABLE IF EXISTS dws_user_activity"))
		conn.execute(text(
			"""
			CREATE TABLE dws_user_activity (
				user_id varchar(64) NOT NULL,
				month varchar(7) NOT NULL,
				active tinyint NOT NULL,
				channel_code varchar(32),
				device_type varchar(32),
				region varchar(32)
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity (user_id, month, active, channel_code, device_type, region) VALUES
			('u1', '2022-01', 1, 'web', 'desktop', 'north'),
			('u2', '2022-01', 1, 'mobile', 'mobile', 'south'),
			('u1', '2022-02', 0, 'web', 'desktop', 'north'),
			('u3', '2022-02', 1, 'mobile', 'mobile', 'east');
			"""
		))
	return db_url


def init_mysql_min(database_url: str) -> None:
	"""Create MySQL table with extended dimensions support."""
	from sqlalchemy import create_engine, text
	engine = create_engine(database_url)
	with engine.begin() as conn:
		conn.execute(text("DROP TABLE IF EXISTS dws_user_activity"))
		conn.execute(text(
			"""
			CREATE TABLE dws_user_activity (
				user_id varchar(64) NOT NULL,
				month char(7) NOT NULL,
				date date NOT NULL,
				active tinyint NOT NULL,
				page_view_id varchar(64),
				channel varchar(32),
				device_type varchar(32),
				region varchar(32),
				platform varchar(32),
				created_hour int,
				quarter varchar(8),
				PRIMARY KEY (user_id, month, date, page_view_id),
				INDEX idx_month (month),
				INDEX idx_date (date),
				INDEX idx_channel (channel),
				INDEX idx_device_type (device_type),
				INDEX idx_region (region),
				INDEX idx_quarter (quarter),
				INDEX idx_hour (created_hour)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity VALUES
			-- 修复数据以匹配测试期望：
			-- 2025年8月数据（test_001: mau=2）
			('u1', '2025-08', '2025-08-01', 1, 'pv001', 'web', 'desktop', 'north', 'web', 9, 'Q3'),
			('u2', '2025-08', '2025-08-01', 1, 'pv002', 'mobile', 'mobile', 'south', 'android', 14, 'Q3'),
			
			-- 2025年9月数据（test_002: dau=4）
			('u1', '2025-09', '2025-09-01', 1, 'pv003', 'web', 'desktop', 'north', 'web', 10, 'Q3'),
			('u2', '2025-09', '2025-09-01', 1, 'pv004', 'mobile', 'mobile', 'south', 'android', 15, 'Q3'),
			('u3', '2025-09', '2025-09-01', 1, 'pv005', 'mobile', 'mobile', 'east', 'ios', 16, 'Q3'),
			('u4', '2025-09', '2025-09-01', 1, 'pv006', 'web', 'desktop', 'west', 'web', 17, 'Q3'),
			
			-- 2025年第三季度数据（Q3: Jul-Sep, test_003等案例）
			('u1', '2025-07', '2025-07-01', 1, 'pv005', 'web', 'desktop', 'north', 'web', 11, 'Q3'),
			('u2', '2025-07', '2025-07-01', 1, 'pv006', 'mobile', 'mobile', 'south', 'android', 16, 'Q3'),

			
			-- 2025年第一季度数据（Q1: Jan-Mar, test_018季度对比）
			('u1', '2025-01', '2025-01-01', 1, 'pv008', 'web', 'desktop', 'north', 'web', 12, 'Q1'),
			('u2', '2025-02', '2025-02-01', 1, 'pv009', 'mobile', 'mobile', 'south', 'android', 13, 'Q1'),
			('u3', '2025-03', '2025-03-01', 1, 'pv010', 'mobile', 'mobile', 'east', 'ios', 14, 'Q1'),
			
			-- 2025年第二季度数据（Q2: Apr-Jun）
			('u1', '2025-04', '2025-04-01', 1, 'pv011', 'web', 'desktop', 'north', 'web', 15, 'Q2'),
			('u2', '2025-05', '2025-05-01', 1, 'pv012', 'mobile', 'mobile', 'south', 'android', 16, 'Q2'),
			('u3', '2025-06', '2025-06-01', 1, 'pv013', 'mobile', 'mobile', 'east', 'ios', 17, 'Q2'),
			
			-- 2025年第四季度数据（Q4: Oct-Dec）
			('u1', '2025-10', '2025-10-01', 1, 'pv014', 'web', 'desktop', 'north', 'web', 18, 'Q4'),
			('u2', '2025-11', '2025-11-01', 1, 'pv015', 'mobile', 'mobile', 'south', 'android', 19, 'Q4'),
			('u3', '2025-12', '2025-12-01', 1, 'pv016', 'mobile', 'mobile', 'east', 'ios', 20, 'Q4')
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
			CREATE TABLE IF NOT EXISTS dws_user_activity (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32)
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity (user_id, month, active, channel_code, device, region) VALUES
			('u1', '2022-01-01', TRUE, 'web', 'desktop', 'north'),
			('u2', '2022-01-01', TRUE, 'mobile', 'mobile', 'south'),
			('u1', '2022-02-01', FALSE, 'web', 'desktop', 'north'),
			('u3', '2022-02-01', TRUE, 'mobile', 'mobile', 'east');
			"""
		))


def copy_mysql_dw(database_url: str, csv_paths: Iterable[Path]) -> None:
	"""Copy CSV files into MySQL table."""
	from sqlalchemy import create_engine, text
	engine = create_engine(database_url)
	with engine.begin() as conn:
		conn.execute(text(
			"""
			CREATE TABLE IF NOT EXISTS dws_user_activity (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32),
				PRIMARY KEY (user_id, month)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))

	for csv_path in csv_paths:
		table_name = csv_path.stem.replace("-", "_")
		conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
		conn.execute(text(
			f"""
			CREATE TABLE {table_name} (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32),
				PRIMARY KEY (user_id, month)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))

		with open(csv_path, "r") as csv_file:
			conn.execute(
				text(
					f"""
					LOAD DATA LOCAL INFILE '{csv_path}'
					INTO TABLE {table_name}
					FIELDS TERMINATED BY ','
					ENCLOSED BY '"'
					LINES TERMINATED BY '
'
					IGNORE 1 ROWS;
					"""
				)
			)


def copy_postgresql_dw(database_url: str, csv_paths: Iterable[Path]) -> None:
	"""Copy CSV files into PostgreSQL table."""
	from sqlalchemy import create_engine, text
	engine = create_engine(database_url)
	with engine.begin() as conn:
		conn.execute(text(
			"""
			CREATE TABLE IF NOT EXISTS dws_user_activity (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32),
				PRIMARY KEY (user_id, month)
			);
			"""
		))

	for csv_path in csv_paths:
		table_name = csv_path.stem.replace("-", "_")
		conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
		conn.execute(text(
			f"""
			CREATE TABLE {table_name} (
				user_id VARCHAR(64) NOT NULL,
				month DATE NOT NULL,
				active BOOLEAN NOT NULL,
				channel_code VARCHAR(32),
				device VARCHAR(32),
				region VARCHAR(32),
				PRIMARY KEY (user_id, month)
			);
			"""
		))

		with open(csv_path, "r") as csv_file:
			conn.execute(
				text(
					f"""
					COPY {table_name} FROM '{csv_path}'
					WITH CSV HEADER;
					"""
				)
			)