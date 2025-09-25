from __future__ import annotations

import logging
import os
from logging import Logger
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

import structlog

from datainsight_agent.config.settings import Settings


def configure_logging(settings: Settings) -> None:
	"""Configure structlog and stdlib logging.

	- Console and file outputs
	- Log level from settings
	"""
	log_dir = Path(settings.log_dir)
	log_dir.mkdir(parents=True, exist_ok=True)
	# 使用配置化的日志文件名
	log_file = log_dir / settings.log_files.get("main", "datainsight_agent.log")

	logging.basicConfig(
		level=getattr(logging, settings.log_level, logging.INFO),
		format="%(message)s",
		handlers=[
			logging.StreamHandler(),
			RotatingFileHandler(str(log_file), maxBytes=5_000_000, backupCount=3),
		],
	)

	structlog.configure(
		processors=[
			structlog.processors.TimeStamper(fmt="ISO", utc=True),
			structlog.stdlib.add_log_level,
			structlog.processors.StackInfoRenderer(),
			structlog.processors.format_exc_info,
			structlog.processors.UnicodeDecoder(),
			structlog.processors.JSONRenderer(),
		],
		logger_factory=structlog.stdlib.LoggerFactory(),
		cache_logger_on_first_use=True,
	)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
	"""Return a structlog logger with an optional name bound."""
	logger = structlog.get_logger()
	return logger.bind(logger=name) if name else logger
