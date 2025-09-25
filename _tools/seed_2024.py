from __future__ import annotations

import argparse
import random
import sqlite3
from typing import List, Dict, Any


def month_list_2024() -> List[str]:
	return [f"2024-{m:02d}" for m in range(1, 13)]


def gen_rows(n: int, months: List[str]) -> List[Dict[str, Any]]:
	channels = ["wechat", "appstore", "web"]
	devices = ["ios", "android", "web"]
	regions = ["east", "north", "south", "west"]
	levels = ["vip", "normal"]
	versions = ["1.0.0", "1.0.1", "1.0.2", "0.9.9", "web"]
	campaigns = ["c0", "c1", "c2", "c3", "c4"]
	device_models = ["iphone", "pixel", "mi", "huawei", "oppo", "pc"]
	os_versions = ["iOS16", "iOS17", "Android12", "Android13", "web"]
	countries = ["CN", "US", "JP"]
	cities = ["shanghai", "beijing", "shenzhen", "hangzhou", "unknown"]
	networks = ["wifi", "5g", "4g", "ethernet"]
	channel_subtypes = ["organic", "qrcode", "paid", "referral"]
	ab_buckets = ["A", "B"]
	segments = ["new", "active", "churn_risk"]
	rows: List[Dict[str, Any]] = []
	for _ in range(n):
		uid = f"u{random.randint(1, 300000)}"
		rows.append({
			"user_id": uid,
			"month": random.choice(months),
			"active": 1 if random.random() > 0.15 else 0,
			"channel_code": random.choice(channels),
			"device": random.choice(devices),
			"region": random.choice(regions),
			"user_level": random.choice(levels),
			"app_version": random.choice(versions),
			"campaign": random.choice(campaigns),
			"device_model": random.choice(device_models),
			"os_version": random.choice(os_versions),
			"country": random.choice(countries),
			"city": random.choice(cities),
			"network_type": random.choice(networks),
			"channel_subtype": random.choice(channel_subtypes),
			"ab_bucket": random.choice(ab_buckets),
			"user_segment": random.choice(segments),
		})
	return rows


def insert_rows(db_path: str, rows: List[Dict[str, Any]]) -> None:
	conn = sqlite3.connect(db_path)
	try:
		cur = conn.cursor()
		cur.executemany(
			"""
			INSERT INTO dws_user_activity_monthly (
				user_id, month, active, channel_code, device, region, user_level, app_version, campaign,
				device_model, os_version, country, city, network_type, channel_subtype, ab_bucket, user_segment
			) VALUES (
				:user_id, :month, :active, :channel_code, :device, :region, :user_level, :app_version, :campaign,
				:device_model, :os_version, :country, :city, :network_type, :channel_subtype, :ab_bucket, :user_segment
			)
			""",
			rows,
		)
		conn.commit()
	finally:
		conn.close()


def main() -> None:
	parser = argparse.ArgumentParser()
	parser.add_argument("--rows", type=int, default=15000)
	parser.add_argument("--db", type=str, default="datainsight.db")
	args = parser.parse_args()
	months = month_list_2024()
	rows = gen_rows(args.rows, months)
	insert_rows(args.db, rows)
	print(f"Inserted rows: {len(rows)} into {args.db}")


if __name__ == "__main__":
	main()


