from __future__ import annotations

from typing import Any, Dict, Optional

from datainsight_agent.services.core.query_rewriter import OptimizedQ2QRewriter as QueryRewriter
from datainsight_agent.components.ir_builder import IRBuilder
from datainsight_agent.services.core.sql_generator import SQLGenerator as SQLGeneratorComponent
from datainsight_agent.services.core.sql_executor import SQLExecutor as SQLExecutorComponent


class SimplePipeline:
    """Decoupled minimal pipeline: rewrite → build IR → SQL → (optional) execute."""

    def __init__(self) -> None:
        from datainsight_agent.config.settings import load_settings
        settings = load_settings()
        
        self._rewriter = QueryRewriter()
        self._ir_builder = IRBuilder()
        self._sql_gen = SQLGeneratorComponent()
        self._sql_exec = SQLExecutorComponent(settings)

    def run(self, question: str, *, execute: bool = True, table: Optional[str] = None) -> Dict[str, Any]:
        rew = self._rewriter.rewrite(question)
        ir = self._ir_builder.build(rew)
        sql_text = self._sql_gen.generate(ir, table or "")
        res = self._sql_exec.execute(sql_text) if execute else None
        return {
            "rewritten": rew,
            "ir": ir,
            "sql": sql_text,
            "results": res,
        }




