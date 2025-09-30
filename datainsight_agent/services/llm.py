from __future__ import annotations

from typing import Optional

from openai import OpenAI

from datainsight_agent.config.settings import Settings


class QwenClient:
	"""Thin wrapper for OpenAI-compatible chat completions (DeepSeek / Qwen DashScope).

	Environment variables (priority order):
	- API key: QWEN_API_KEY | DASHSCOPE_API_KEY | OPENAI_API_KEY
	- Base URL: QWEN_BASE_URL (defaults to Settings.api_endpoints["qwen"]) 
	- Model name: QWEN_MODEL (defaults to Settings.default_models["qwen_model"]) 

	Notes:
	- Qwen (DashScope) OpenAI-compatible endpoint: https://dashscope.aliyuncs.com/compatible-mode/v1
	- DeepSeek endpoint: https://api.deepseek.com/v1
	"""

	def __init__(self, settings: Settings) -> None:
		from os import getenv
		# 只使用 Qwen API keys，不回退到 OpenAI
		api_key = getenv("QWEN_API_KEY") or getenv("DASHSCOPE_API_KEY")
		
		if not api_key:
			raise RuntimeError("No Qwen API key found (set QWEN_API_KEY or DASHSCOPE_API_KEY)")
		# 使用配置化的API端点
		from datainsight_agent.config.settings import load_settings
		s = load_settings()
		# Determine Qwen base URL
		default_qwen = s.api_endpoints.get("qwen", "https://dashscope.aliyuncs.com/compatible-mode/v1")
		base_url = getenv("QWEN_BASE_URL", default_qwen)
		# Ensure /v1 suffix for OpenAI SDK compatibility
		if not base_url.rstrip("/").endswith("/v1"):
			base_url = base_url.rstrip("/") + "/v1"
		self._client = OpenAI(api_key=api_key, base_url=base_url)
		# 使用配置化的模型名称
		self._model = getenv("QWEN_MODEL", s.default_models.get("qwen_model", "qwen2.5-72b-instruct"))
		# Use env overrides if provided; fallback to Settings
		self._temperature = float(getenv("LLM_TEMPERATURE", str(settings.llm_temperature)))
		self._max_tokens = int(getenv("LLM_MAX_TOKENS", str(settings.llm_max_tokens)))
		# Timeout (seconds): configurable via env, default 15
		self._timeout_s = float(getenv("LLM_REQUEST_TIMEOUT", "15"))

	def generate_sql(self, prompt: str, system: Optional[str] = None) -> str:
		messages = []
		if system:
			messages.append({"role": "system", "content": system})
		messages.append({"role": "user", "content": prompt})
		resp = self._client.chat.completions.create(
			model=self._model,
			messages=messages,
			temperature=self._temperature,
			max_tokens=self._max_tokens,
			timeout=self._timeout_s,
		)
		text = resp.choices[0].message.content or ""
		return text.strip()

	def tool_call(self, *, system: Optional[str], user: str, tool_name: str, json_schema: dict) -> dict:
		"""Invoke OpenAI-compatible tool/function call and return parsed dict.

		Args:
		- system: optional system prompt
		- user: user content
		- tool_name: function name
		- json_schema: JSON schema for the function parameters
		"""
		messages = []
		if system:
			messages.append({"role": "system", "content": system})
		messages.append({"role": "user", "content": user})
		tools = [
			{
				"type": "function",
				"function": {
					"name": tool_name,
					"description": "Return strictly valid JSON per the provided schema.",
					"parameters": json_schema,
				},
			}
		]
		resp = self._client.chat.completions.create(
			model=self._model,
			messages=messages,
			tools=tools,
			tool_choice={"type": "function", "function": {"name": tool_name}},
			temperature=self._temperature,
			max_tokens=self._max_tokens,
			timeout=self._timeout_s,
		)
		try:
			tc = resp.choices[0].message.tool_calls[0]
			args = tc.function.arguments or "{}"
			import json as _json
			return _json.loads(args)
		except Exception:
			# Fallback to plain content parse when no tool call returned
			try:
				text = resp.choices[0].message.content or "{}"
				import json as _json
				return _json.loads(text)
			except Exception:
				return {}
