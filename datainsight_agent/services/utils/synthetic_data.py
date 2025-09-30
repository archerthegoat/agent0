from __future__ import annotations

from typing import List

from datainsight_agent.services.llm import QwenClient
from datainsight_agent.config.settings import load_settings


def month_list(start: str, count: int) -> List[str]:
	try:
		year_str, month_str = start.split("-")
		year = int(year_str)
		month = int(month_str)
	except Exception:
		year, month = 2025, 9
	start_total = year * 12 + (month - 1)
	months_list: List[str] = []
	for i in range(count):
		t = start_total - i
		yy = t // 12
		mm = t % 12 + 1
		months_list.append(f"{yy:04d}-{mm:02d}")
	return months_list


def local_generate(n: int, month_values: List[str]) -> List[dict]:
	import random
	channels = ["wechat", "appstore", "web"]
	devices = ["ios", "android", "web"]
	regions = ["east", "north", "south", "west"]
	levels = ["vip", "normal"]
	versions = ["1.0.0", "1.0.1", "1.0.2", "0.9.9"]
	campaigns = ["c0", "c1", "c2", "c3", "c4"]
	device_models = ["iphone","pixel","mi","huawei","oppo","pc"]
	os_versions = ["iOS16","iOS17","Android12","Android13","web"]
	countries = ["CN","US","JP"]
	cities = ["shanghai","beijing","shenzhen","hangzhou","unknown"]
	networks = ["wifi","5g","4g","ethernet"]
	channel_subtypes = ["organic","qrcode","paid","referral"]
	ab_buckets = ["A","B"]
	segments = ["new","active","churn_risk"]
	out: List[dict] = []
	for _ in range(n):
		uid = f"u{random.randint(1, 200000)}"
		out.append({
			"user_id": uid,
			"month": random.choice(month_values),
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
	return out


def llm_generate(n: int, month_values: List[str]) -> List[dict]:
	s = load_settings()
	try:
		client = QwenClient(s)
	except Exception:
		return local_generate(n, month_values)
	prompt = (
		"Generate strictly NDJSON with exactly {n} lines. Each line is one JSON object with keys: "
		"user_id (string like 'u12345'), month (YYYY-MM from this set: {months}), active (0 or 1), "
		"channel_code (one of ['wechat','appstore','web']), device (one of ['ios','android','web']), "
		"region (one of ['east','north','south','west']), user_level (one of ['vip','normal']), "
		"app_version (choose realistic like '1.0.0','1.0.1','1.0.2','0.9.9'), campaign (one of ['c0','c1','c2','c3','c4']). "
		"Also include: device_model ['iphone','pixel','mi','huawei','oppo','pc'], os_version ['iOS16','iOS17','Android12','Android13','web'], "
		"country ['CN','US','JP'], city ['shanghai','beijing','shenzhen','hangzhou','unknown'], network_type ['wifi','5g','4g','ethernet'], "
		"channel_subtype ['organic','qrcode','paid','referral'], ab_bucket ['A','B'], user_segment ['new','active','churn_risk']. "
		"Output NDJSON ONLY, no code fences, no commentary."
	).format(n=n, months=month_values)
	try:
		text = client.generate_sql(prompt)
		lines = [ln for ln in text.splitlines() if ln.strip()]
		import json as _json
		rows: List[dict] = []
		for ln in lines:
			try:
				obj = _json.loads(ln)
				if isinstance(obj, dict):
					rows.append(obj)
			except Exception:
				continue
		if len(rows) < n:
			rows.extend(local_generate(n - len(rows), month_values))
		return rows[:n]
	except Exception:
		return local_generate(n, month_values)




