from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


class DataSource(BaseModel):
	layer: str
	table: str
	column: Optional[str] = None


class What(BaseModel):
	description: str
	business_process: Optional[str] = None


class Why(BaseModel):
	business_value: Optional[str] = None


class How(BaseModel):
	formula_human: Optional[str] = None
	data_source: Optional[DataSource] = None


class When(BaseModel):
	update_frequency: Optional[str] = None
	granularity: Optional[str] = None


class Where(BaseModel):
	drill_down_paths: Optional[List[str]] = Field(default=None)


class Who(BaseModel):
	business_owner: Optional[str] = None


class KBEntity(BaseModel):
	id: str
	canonical_name: str
	aliases: List[str] = Field(default_factory=list)
	type: str
	what: Optional[What] = None
	why: Optional[Why] = None
	how: Optional[How] = None
	who: Optional[Who] = None
	when: Optional[When] = None
	where: Optional[Where] = None
