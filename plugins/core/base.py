# lynx/plugins/core/base.py
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, Protocol, runtime_checkable, List

# Avoid hard imports to keep core decoupled
try:
    from lynx.codex.config import CodexConfig
    from lynx.utils import FileInfo
    from lynx.codex.chunker import Chunk
    from lynx.codex.ai_interface import SummaryRequest, SummaryResponse
except Exception:
    CodexConfig = Any
    FileInfo = Any
    Chunk = Any
    SummaryRequest = Any
    SummaryResponse = Any

class HookPoint(Enum):
    BEFORE_SCAN = auto()
    AFTER_SCAN = auto()
    BEFORE_CHUNK = auto()
    AFTER_CHUNK = auto()
    BEFORE_AI_REQUEST = auto()
    AFTER_AI_RESPONSE = auto()
    BEFORE_AGGREGATE = auto()
    AFTER_AGGREGATE = auto()
    BEFORE_OUTPUT = auto()
    AFTER_OUTPUT = auto()
    ON_ERROR = auto()

@dataclass
class PluginContext:
    config: CodexConfig
    file_info: Optional[FileInfo] = None
    content: Optional[str] = None
    chunks: Optional[List[Chunk]] = None
    request: Optional[SummaryRequest] = None
    response: Optional[SummaryResponse] = None
    file_summaries: Optional[Dict[str, str]] = None
    master_summary: Optional[str] = None
    output_path: Optional[str] = None
    state: Dict[str, Any] = field(default_factory=dict)  # plugin-shared scratchpad

@runtime_checkable
class Plugin(Protocol):
    name: str
    version: str
    order: int  # lower runs earlier

    def configure(self, options: Dict[str, Any]) -> None: ...
    def supports(self, hook: HookPoint) -> bool: ...
    def on_hook(self, hook: HookPoint, ctx: PluginContext) -> None: ...
