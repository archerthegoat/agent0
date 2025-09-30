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
				region varchar(32),
				-- 新增业务指标字段
				revenue_amount decimal(10,2) DEFAULT 0,
				retention_flag tinyint DEFAULT 0,
				roi_ratio decimal(8,4) DEFAULT 0,
				is_return_visitor tinyint DEFAULT 0,
				page_view_id varchar(64),
				created_hour int DEFAULT 0,
				platform varchar(32) DEFAULT 'web',
				user_revenue decimal(10,2) DEFAULT 0,
				conversion_flag tinyint DEFAULT 0,
				session_duration_minutes decimal(8,2) DEFAULT 0,
				bounce_flag tinyint DEFAULT 0,
				is_new_user tinyint DEFAULT 0,
				is_churn tinyint DEFAULT 0,
				pages_per_session int DEFAULT 0,
				search_success tinyint DEFAULT 0,
				recommendation_clicked tinyint DEFAULT 0,
				satisfaction_score decimal(3,2) DEFAULT 0,
				nps_score decimal(3,2) DEFAULT 0
			);
			"""
		))
		conn.execute(text("DELETE FROM dws_user_activity"))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity (user_id, month, active, channel_code, device_type, region, revenue_amount, retention_flag, roi_ratio, is_return_visitor, page_view_id, created_hour, platform, user_revenue, conversion_flag, session_duration_minutes, bounce_flag, is_new_user, is_churn, pages_per_session, search_success, recommendation_clicked, satisfaction_score, nps_score) VALUES
			-- 2022年测试数据（保留原有）
			('u1', '2022-01', 1, 'web', 'desktop', 'north', 100.00, 1, 2.5, 1, 'pv001', 9, 'web', 100.00, 1, 12.5, 0, 0, 0, 4, 1, 1, 4.2, 8.5),
			('u2', '2022-01', 1, 'mobile', 'mobile', 'south', 120.00, 1, 2.2, 0, 'pv002', 14, 'android', 120.00, 1, 8.3, 1, 0, 0, 3, 0, 0, 3.8, 7.2),
			('u1', '2022-02', 0, 'web', 'desktop', 'north', 0.00, 0, 0.0, 0, 'pv003', 10, 'web', 0.00, 0, 0.0, 1, 0, 0, 0, 0, 0, 0.0, 0.0),
			('u3', '2022-02', 1, 'mobile', 'mobile', 'east', 110.00, 1, 2.3, 1, 'pv004', 15, 'ios', 110.00, 1, 9.8, 0, 0, 0, 3, 1, 1, 4.1, 8.3),
			-- 2025年8月测试数据（test_001: mau=2）
			('u1', '2025-08', 1, 'web', 'desktop', 'north', 150.00, 1, 2.5, 1, 'pv005', 9, 'web', 150.00, 1, 12.5, 0, 0, 0, 4, 1, 1, 4.2, 8.5),
			('u2', '2025-08', 1, 'mobile', 'mobile', 'south', 120.00, 1, 2.2, 0, 'pv006', 14, 'android', 120.00, 1, 8.3, 1, 0, 0, 3, 0, 0, 3.8, 7.2),
			-- 2025年9月测试数据（test_002: dau=4）
			('u1', '2025-09', 1, 'web', 'desktop', 'north', 180.00, 1, 2.8, 1, 'pv007', 10, 'web', 180.00, 1, 15.2, 0, 0, 0, 5, 1, 1, 4.5, 9.1),
			('u2', '2025-09', 1, 'mobile', 'mobile', 'south', 140.00, 1, 2.4, 0, 'pv008', 15, 'android', 140.00, 1, 9.8, 1, 0, 0, 3, 0, 0, 3.9, 7.8),
			('u3', '2025-09', 1, 'mobile', 'mobile', 'east', 160.00, 1, 2.6, 1, 'pv009', 16, 'ios', 160.00, 1, 11.2, 0, 0, 0, 4, 1, 1, 4.1, 8.3),
			('u4', '2025-09', 1, 'web', 'desktop', 'west', 170.00, 1, 2.7, 1, 'pv010', 17, 'web', 170.00, 1, 13.7, 0, 0, 0, 4, 1, 1, 4.3, 8.7),
			-- 2025年7月测试数据（Q3季度查询）
			('u1', '2025-07', 1, 'web', 'desktop', 'north', 165.00, 1, 2.6, 1, 'pv011', 11, 'web', 165.00, 1, 14.1, 0, 0, 0, 4, 1, 1, 4.2, 8.4),
			('u2', '2025-07', 1, 'mobile', 'mobile', 'south', 135.00, 1, 2.3, 0, 'pv012', 16, 'android', 135.00, 1, 9.5, 1, 0, 0, 3, 0, 0, 3.7, 7.4),
			-- 2025年10月测试数据（test_007需要）
			('u1', '2025-10', 1, 'web', 'desktop', 'north', 190.00, 1, 2.9, 1, 'pv013', 12, 'web', 190.00, 1, 16.3, 0, 0, 0, 5, 1, 1, 4.6, 9.2),
			-- 2025年第一季度数据（Q1: Jan-Mar）
			('u1', '2025-01', 1, 'web', 'desktop', 'north', 200.00, 1, 3.0, 1, 'pv014', 8, 'web', 200.00, 1, 18.5, 0, 0, 0, 6, 1, 1, 4.8, 9.5),
			('u2', '2025-01', 1, 'mobile', 'mobile', 'south', 130.00, 1, 2.1, 0, 'pv015', 13, 'android', 130.00, 1, 7.8, 1, 0, 0, 2, 0, 0, 3.5, 7.0),
			('u3', '2025-01', 1, 'mobile', 'mobile', 'east', 145.00, 1, 2.4, 1, 'pv016', 14, 'ios', 145.00, 1, 10.2, 0, 0, 0, 3, 1, 1, 4.0, 8.0),
			('u1', '2025-02', 1, 'web', 'desktop', 'north', 175.00, 1, 2.7, 1, 'pv017', 9, 'web', 175.00, 1, 15.8, 0, 0, 0, 5, 1, 1, 4.4, 8.8),
			('u2', '2025-02', 1, 'mobile', 'mobile', 'south', 125.00, 1, 2.0, 0, 'pv018', 14, 'android', 125.00, 1, 7.2, 1, 0, 0, 2, 0, 0, 3.3, 6.6),
			('u3', '2025-02', 1, 'mobile', 'mobile', 'east', 140.00, 1, 2.3, 1, 'pv019', 15, 'ios', 140.00, 1, 9.5, 0, 0, 0, 3, 1, 1, 3.9, 7.8),
			('u1', '2025-03', 1, 'web', 'desktop', 'north', 185.00, 1, 2.8, 1, 'pv020', 10, 'web', 185.00, 1, 16.7, 0, 0, 0, 5, 1, 1, 4.5, 9.0),
			('u2', '2025-03', 1, 'mobile', 'mobile', 'south', 135.00, 1, 2.2, 0, 'pv021', 15, 'android', 135.00, 1, 8.1, 1, 0, 0, 3, 0, 0, 3.6, 7.2),
			('u3', '2025-03', 1, 'mobile', 'mobile', 'east', 150.00, 1, 2.5, 1, 'pv022', 16, 'ios', 150.00, 1, 10.8, 0, 0, 0, 4, 1, 1, 4.2, 8.4),
			-- 2025年第二季度数据（Q2: Apr-Jun）
			('u1', '2025-04', 1, 'web', 'desktop', 'north', 195.00, 1, 2.9, 1, 'pv023', 11, 'web', 195.00, 1, 17.6, 0, 0, 0, 6, 1, 1, 4.7, 9.4),
			('u2', '2025-04', 1, 'mobile', 'mobile', 'south', 140.00, 1, 2.3, 0, 'pv024', 16, 'android', 140.00, 1, 8.4, 1, 0, 0, 3, 0, 0, 3.7, 7.4),
			('u3', '2025-04', 1, 'mobile', 'mobile', 'east', 155.00, 1, 2.6, 1, 'pv025', 17, 'ios', 155.00, 1, 11.1, 0, 0, 0, 4, 1, 1, 4.3, 8.6),
			('u1', '2025-05', 1, 'web', 'desktop', 'north', 205.00, 1, 3.1, 1, 'pv026', 12, 'web', 205.00, 1, 18.5, 0, 0, 0, 6, 1, 1, 4.8, 9.6),
			('u2', '2025-05', 1, 'mobile', 'mobile', 'south', 145.00, 1, 2.4, 0, 'pv027', 17, 'android', 145.00, 1, 8.7, 1, 0, 0, 3, 0, 0, 3.8, 7.6),
			('u3', '2025-05', 1, 'mobile', 'mobile', 'east', 160.00, 1, 2.7, 1, 'pv028', 18, 'ios', 160.00, 1, 11.4, 0, 0, 0, 4, 1, 1, 4.4, 8.8),
			('u1', '2025-06', 1, 'web', 'desktop', 'north', 210.00, 1, 3.2, 1, 'pv029', 13, 'web', 210.00, 1, 19.0, 0, 0, 0, 6, 1, 1, 4.9, 9.8),
			('u2', '2025-06', 1, 'mobile', 'mobile', 'south', 150.00, 1, 2.5, 0, 'pv030', 18, 'android', 150.00, 1, 9.0, 1, 0, 0, 3, 0, 0, 3.9, 7.8),
			('u3', '2025-06', 1, 'mobile', 'mobile', 'east', 165.00, 1, 2.8, 1, 'pv031', 19, 'ios', 165.00, 1, 11.7, 0, 0, 0, 4, 1, 1, 4.5, 9.0),
			-- 2025年第四季度数据（Q4: Oct-Dec）
			('u1', '2025-11', 1, 'web', 'desktop', 'north', 220.00, 1, 3.3, 1, 'pv032', 14, 'web', 220.00, 1, 19.8, 0, 0, 0, 7, 1, 1, 5.0, 10.0),
			('u2', '2025-11', 1, 'mobile', 'mobile', 'south', 160.00, 1, 2.6, 0, 'pv033', 19, 'android', 160.00, 1, 9.6, 1, 0, 0, 3, 0, 0, 4.0, 8.0),
			('u3', '2025-11', 1, 'mobile', 'mobile', 'east', 175.00, 1, 2.9, 1, 'pv034', 20, 'ios', 175.00, 1, 12.3, 0, 0, 0, 4, 1, 1, 4.6, 9.2),
			('u1', '2025-12', 1, 'web', 'desktop', 'north', 225.00, 1, 3.4, 1, 'pv035', 15, 'web', 225.00, 1, 20.3, 0, 0, 0, 7, 1, 1, 5.1, 10.2),
			('u2', '2025-12', 1, 'mobile', 'mobile', 'south', 165.00, 1, 2.7, 0, 'pv036', 20, 'android', 165.00, 1, 9.9, 1, 0, 0, 3, 0, 0, 4.1, 8.2),
			('u3', '2025-12', 1, 'mobile', 'mobile', 'east', 180.00, 1, 3.0, 1, 'pv037', 21, 'ios', 180.00, 1, 12.6, 0, 0, 0, 4, 1, 1, 4.7, 9.4);
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
				-- 新增业务指标字段
				retention_flag tinyint DEFAULT 0,
				conversion_flag tinyint DEFAULT 0,
				session_duration_minutes decimal(8,2) DEFAULT 0,
				bounce_flag tinyint DEFAULT 0,
				revenue_amount decimal(10,2) DEFAULT 0,
				is_new_user tinyint DEFAULT 0,
				is_churn tinyint DEFAULT 0,
				user_revenue decimal(10,2) DEFAULT 0,
				roi_ratio decimal(8,4) DEFAULT 0,
				pages_per_session int DEFAULT 0,
				is_return_visitor tinyint DEFAULT 0,
				cart_abandoned tinyint DEFAULT 0,
				search_success tinyint DEFAULT 0,
				recommendation_clicked tinyint DEFAULT 0,
				satisfaction_score decimal(3,2) DEFAULT 0,
				nps_score decimal(3,2) DEFAULT 0,
				PRIMARY KEY (user_id, month, date, page_view_id),
				INDEX idx_month (month),
				INDEX idx_date (date),
				INDEX idx_channel (channel),
				INDEX idx_device_type (device_type),
				INDEX idx_region (region),
				INDEX idx_quarter (quarter),
				INDEX idx_hour (created_hour),
				INDEX idx_active (active),
				INDEX idx_is_new_user (is_new_user),
				INDEX idx_is_churn (is_churn)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		conn.execute(text(
			"""
			INSERT INTO dws_user_activity VALUES
			-- 2025年8月数据（test_001: mau=2）
			('u1', '2025-08', '2025-08-01', 1, 'pv001', 'web', 'desktop', 'north', 'web', 9, 'Q3', 1, 1, 12.5, 0, 150.00, 0, 0, 150.00, 2.5, 4, 1, 0, 1, 1, 4.2, 8.5),
			('u2', '2025-08', '2025-08-01', 1, 'pv002', 'mobile', 'mobile', 'south', 'android', 14, 'Q3', 1, 1, 8.3, 1, 120.00, 0, 0, 120.00, 2.2, 3, 0, 1, 0, 0, 3.8, 7.2),
			
			-- 2025年9月数据（test_002: dau=4）
			('u1', '2025-09', '2025-09-01', 1, 'pv003', 'web', 'desktop', 'north', 'web', 10, 'Q3', 1, 1, 15.2, 0, 180.00, 0, 0, 180.00, 2.8, 5, 1, 0, 1, 1, 4.5, 9.1),
			('u2', '2025-09', '2025-09-01', 1, 'pv004', 'mobile', 'mobile', 'south', 'android', 15, 'Q3', 1, 1, 9.8, 1, 140.00, 0, 0, 140.00, 2.4, 3, 0, 1, 0, 0, 3.9, 7.8),
			('u3', '2025-09', '2025-09-01', 1, 'pv005', 'mobile', 'mobile', 'east', 'ios', 16, 'Q3', 1, 1, 11.2, 0, 160.00, 0, 0, 160.00, 2.6, 4, 1, 0, 1, 1, 4.1, 8.3),
			('u4', '2025-09', '2025-09-01', 1, 'pv006', 'web', 'desktop', 'west', 'web', 17, 'Q3', 1, 1, 13.7, 0, 170.00, 0, 0, 170.00, 2.7, 4, 1, 0, 1, 1, 4.3, 8.7),
			
			-- 2025年第三季度数据（Q3: Jul-Sep）
			('u1', '2025-07', '2025-07-01', 1, 'pv007', 'web', 'desktop', 'north', 'web', 11, 'Q3', 1, 1, 14.1, 0, 165.00, 0, 0, 165.00, 2.6, 4, 1, 0, 1, 1, 4.2, 8.4),
			('u2', '2025-07', '2025-07-01', 1, 'pv008', 'mobile', 'mobile', 'south', 'android', 16, 'Q3', 1, 1, 9.5, 1, 135.00, 0, 0, 135.00, 2.3, 3, 0, 1, 0, 0, 3.7, 7.4),
			
			-- 2025年第一季度数据（Q1: Jan-Mar）
			('u1', '2025-01', '2025-01-01', 1, 'pv009', 'web', 'desktop', 'north', 'web', 12, 'Q1', 1, 1, 16.3, 0, 200.00, 1, 0, 200.00, 3.0, 5, 1, 0, 1, 1, 4.6, 9.2),
			('u2', '2025-02', '2025-02-01', 1, 'pv010', 'mobile', 'mobile', 'south', 'android', 13, 'Q1', 1, 1, 10.2, 1, 145.00, 1, 0, 145.00, 2.5, 3, 0, 1, 0, 0, 3.8, 7.6),
			('u3', '2025-03', '2025-03-01', 1, 'pv011', 'mobile', 'mobile', 'east', 'ios', 14, 'Q1', 1, 1, 12.8, 0, 175.00, 1, 0, 175.00, 2.7, 4, 1, 0, 1, 1, 4.2, 8.4),
			
			-- 2025年第二季度数据（Q2: Apr-Jun）
			('u1', '2025-04', '2025-04-01', 1, 'pv012', 'web', 'desktop', 'north', 'web', 15, 'Q2', 1, 1, 15.7, 0, 185.00, 0, 0, 185.00, 2.8, 4, 1, 0, 1, 1, 4.4, 8.8),
			('u2', '2025-05', '2025-05-01', 1, 'pv013', 'mobile', 'mobile', 'south', 'android', 16, 'Q2', 1, 1, 9.9, 1, 130.00, 0, 0, 130.00, 2.4, 3, 0, 1, 0, 0, 3.6, 7.2),
			('u3', '2025-06', '2025-06-01', 1, 'pv014', 'mobile', 'mobile', 'east', 'ios', 17, 'Q2', 1, 1, 11.5, 0, 155.00, 0, 0, 155.00, 2.5, 4, 1, 0, 1, 1, 4.0, 8.0),
			
			-- 2025年第四季度数据（Q4: Oct-Dec）
			('u1', '2025-10', '2025-10-01', 1, 'pv015', 'web', 'desktop', 'north', 'web', 18, 'Q4', 1, 1, 17.2, 0, 210.00, 0, 0, 210.00, 3.1, 5, 1, 0, 1, 1, 4.7, 9.4),
			('u2', '2025-11', '2025-11-01', 1, 'pv016', 'mobile', 'mobile', 'south', 'android', 19, 'Q4', 1, 1, 10.8, 1, 150.00, 0, 0, 150.00, 2.6, 3, 0, 1, 0, 0, 3.9, 7.8),
			('u3', '2025-12', '2025-12-01', 1, 'pv017', 'mobile', 'mobile', 'east', 'ios', 20, 'Q4', 1, 1, 13.1, 0, 180.00, 0, 0, 180.00, 2.8, 4, 1, 0, 1, 1, 4.3, 8.6)
			ON DUPLICATE KEY UPDATE active=VALUES(active);
			"""
		))
		
		# 创建其他业务表
		conn.execute(text("DROP TABLE IF EXISTS dws_orders"))
		conn.execute(text(
			"""
			CREATE TABLE dws_orders (
				order_id varchar(64) NOT NULL,
				user_id varchar(64) NOT NULL,
				order_date date NOT NULL,
				month char(7) NOT NULL,
				order_amount decimal(10,2) NOT NULL,
				is_repeat_purchase tinyint DEFAULT 0,
				is_refunded tinyint DEFAULT 0,
				refund_date date,
				channel varchar(32),
				region varchar(32),
				PRIMARY KEY (order_id),
				INDEX idx_user_id (user_id),
				INDEX idx_order_date (order_date),
				INDEX idx_month (month),
				INDEX idx_channel (channel),
				INDEX idx_region (region)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		
		# 插入订单测试数据
		conn.execute(text(
			"""
			INSERT INTO dws_orders VALUES
			-- 2025年8月订单数据
			('ord001', 'u1', '2025-08-01', '2025-08', 150.00, 0, 0, NULL, 'web', 'north'),
			('ord002', 'u2', '2025-08-02', '2025-08', 200.00, 1, 0, NULL, 'mobile', 'south'),
			('ord003', 'u3', '2025-08-03', '2025-08', 120.00, 0, 0, NULL, 'mobile', 'east'),
			('ord004', 'u1', '2025-08-04', '2025-08', 180.00, 1, 0, NULL, 'web', 'north'),
			('ord005', 'u2', '2025-08-05', '2025-08', 160.00, 0, 0, NULL, 'mobile', 'south'),
			
			-- 2025年9月订单数据
			('ord006', 'u1', '2025-09-01', '2025-09', 170.00, 0, 0, NULL, 'web', 'north'),
			('ord007', 'u2', '2025-09-02', '2025-09', 190.00, 1, 0, NULL, 'mobile', 'south'),
			('ord008', 'u3', '2025-09-03', '2025-09', 140.00, 0, 0, NULL, 'mobile', 'east'),
			('ord009', 'u4', '2025-09-04', '2025-09', 210.00, 0, 0, NULL, 'web', 'west'),
			
			-- 2025年第三季度其他月份数据
			('ord010', 'u1', '2025-07-01', '2025-07', 160.00, 0, 0, NULL, 'web', 'north'),
			('ord011', 'u2', '2025-07-02', '2025-07', 180.00, 1, 0, NULL, 'mobile', 'south'),
			
			-- 2025年其他季度数据
			('ord012', 'u1', '2025-01-01', '2025-01', 200.00, 0, 0, NULL, 'web', 'north'),
			('ord013', 'u2', '2025-02-01', '2025-02', 150.00, 1, 0, NULL, 'mobile', 'south'),
			('ord014', 'u3', '2025-03-01', '2025-03', 175.00, 0, 0, NULL, 'mobile', 'east'),
			('ord015', 'u1', '2025-04-01', '2025-04', 185.00, 0, 0, NULL, 'web', 'north'),
			('ord016', 'u2', '2025-05-01', '2025-05', 130.00, 1, 0, NULL, 'mobile', 'south'),
			('ord017', 'u3', '2025-06-01', '2025-06', 155.00, 0, 0, NULL, 'mobile', 'east'),
			('ord018', 'u1', '2025-10-01', '2025-10', 210.00, 0, 0, NULL, 'web', 'north'),
			('ord019', 'u2', '2025-11-01', '2025-11', 150.00, 1, 0, NULL, 'mobile', 'south'),
			('ord020', 'u3', '2025-12-01', '2025-12', 180.00, 0, 0, NULL, 'mobile', 'east')
			ON DUPLICATE KEY UPDATE order_amount=VALUES(order_amount);
			"""
		))
		
		conn.execute(text("DROP TABLE IF EXISTS dws_email_campaign"))
		conn.execute(text(
			"""
			CREATE TABLE dws_email_campaign (
				campaign_id varchar(64) NOT NULL,
				user_id varchar(64) NOT NULL,
				sent_at date NOT NULL,
				month char(7) NOT NULL,
				is_opened tinyint DEFAULT 0,
				is_clicked tinyint DEFAULT 0,
				region varchar(32),
				PRIMARY KEY (campaign_id),
				INDEX idx_user_id (user_id),
				INDEX idx_sent_at (sent_at),
				INDEX idx_month (month),
				INDEX idx_region (region)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		
		conn.execute(text("DROP TABLE IF EXISTS dws_app_performance"))
		conn.execute(text(
			"""
			CREATE TABLE dws_app_performance (
				event_id varchar(64) NOT NULL,
				user_id varchar(64) NOT NULL,
				event_time date NOT NULL,
				month char(7) NOT NULL,
				is_crashed tinyint DEFAULT 0,
				device_type varchar(32),
				PRIMARY KEY (event_id),
				INDEX idx_user_id (user_id),
				INDEX idx_event_time (event_time),
				INDEX idx_month (month),
				INDEX idx_device_type (device_type)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		
		conn.execute(text("DROP TABLE IF EXISTS dws_marketing_cost"))
		conn.execute(text(
			"""
			CREATE TABLE dws_marketing_cost (
				cost_id varchar(64) NOT NULL,
				channel varchar(32) NOT NULL,
				date date NOT NULL,
				acquisition_cost decimal(10,2) NOT NULL,
				PRIMARY KEY (cost_id),
				INDEX idx_channel (channel),
				INDEX idx_date (date)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
			"""
		))
		
		# 插入测试数据
		conn.execute(text(
			"""
			INSERT INTO dws_orders VALUES
			('o1', 'u1', '2025-08-01', '2025-08', 100.00, 0, 0, NULL, 'web', 'north'),
			('o2', 'u2', '2025-08-01', '2025-08', 150.00, 1, 0, NULL, 'mobile', 'south'),
			('o3', 'u1', '2025-08-02', '2025-08', 200.00, 1, 0, NULL, 'web', 'north'),
			('o4', 'u3', '2025-08-02', '2025-08', 80.00, 0, 1, '2025-08-03', 'mobile', 'east'),
			('o5', 'u2', '2025-09-01', '2025-09', 120.00, 1, 0, NULL, 'mobile', 'south'),
			('o6', 'u4', '2025-09-01', '2025-09', 90.00, 0, 0, NULL, 'web', 'west'),
			('o7', 'u1', '2025-04-01', '2025-04', 110.00, 0, 0, NULL, 'web', 'north'),
			('o8', 'u2', '2025-05-01', '2025-05', 160.00, 1, 0, NULL, 'mobile', 'south'),
			('o9', 'u3', '2025-06-01', '2025-06', 95.00, 0, 0, NULL, 'mobile', 'east');
			"""
		))
		
		conn.execute(text(
			"""
			INSERT INTO dws_email_campaign VALUES
			('e1', 'u1', '2025-08-01', '2025-08', 1, 0, 'north'),
			('e2', 'u2', '2025-08-01', '2025-08', 0, 0, 'south'),
			('e3', 'u1', '2025-08-02', '2025-08', 1, 1, 'north'),
			('e4', 'u3', '2025-08-02', '2025-08', 0, 0, 'east'),
			('e5', 'u2', '2025-09-01', '2025-09', 1, 0, 'south'),
			('e6', 'u4', '2025-09-01', '2025-09', 1, 1, 'west');
			"""
		))
		
		conn.execute(text(
			"""
			INSERT INTO dws_app_performance VALUES
			('a1', 'u1', '2025-09-01', '2025-09', 0, 'desktop'),
			('a2', 'u2', '2025-09-01', '2025-09', 1, 'mobile'),
			('a3', 'u3', '2025-09-01', '2025-09', 0, 'mobile'),
			('a4', 'u4', '2025-09-01', '2025-09', 0, 'desktop');
			"""
		))
		
		conn.execute(text(
			"""
			INSERT INTO dws_marketing_cost VALUES
			('c1', 'organic', '2025-08-01', 15.50),
			('c2', 'paid', '2025-08-01', 25.80),
			('c3', 'organic', '2025-08-02', 16.00),
			('c4', 'paid', '2025-08-02', 26.20),
			('c5', 'organic', '2025-09-01', 14.80),
			('c6', 'paid', '2025-09-01', 24.50);
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