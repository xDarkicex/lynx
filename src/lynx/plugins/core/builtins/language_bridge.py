from __future__ import annotations
from typing import Dict, Any, Optional
from lynx.plugins.languages import get_parser_for_language, get_parser_for_file, get_supported_languages
from lynx.plugins.core.base import Plugin, PluginContext, HookPoint


class LanguageParsingPlugin(Plugin):
    name = "language_bridge"
    version = "1.0.0"
    order = 50

    def __init__(self):
        self.max_elements_per_file = 200
        self.analyze_dependencies = True

    def configure(self, options: Dict[str, Any]) -> None:
        self.max_elements_per_file = int(options.get("max_elements_per_file", self.max_elements_per_file))
        self.analyze_dependencies = bool(options.get("analyze_dependencies", self.analyze_dependencies))

    def supports(self, hook: HookPoint) -> bool:
        return hook in {
            HookPoint.AFTER_SCAN,
            HookPoint.BEFORE_CHUNK,
        }

    def on_hook(self, hook: HookPoint, ctx: PluginContext) -> None:
        if hook == HookPoint.AFTER_SCAN:
            # annotate files with parsed info indexable by relative_path
            parsed: Dict[str, Dict[str, Any]] = {}
            for fi in ctx.state.get("files", []) or []:
                parser = get_parser_for_language(fi.language) or get_parser_for_file(fi.extension)
                if not parser:
                    continue
                try:
                    content = open(fi.path, "r", encoding=getattr(fi, "encoding", "utf-8")).read()
                except Exception:
                    continue
                elements = parser.parse_elements(content, fi.relative_path)[: self.max_elements_per_file]
                deps = parser.extract_dependencies(content) if self.analyze_dependencies else []
                parsed[fi.relative_path] = {
                    "language": fi.language,
                    "elements": elements,
                    "dependencies": deps,
                    "lines": content.count('\n') + 1,  # Fixed line
                }
            ctx.state["language_analysis"] = parsed

        elif hook == HookPoint.BEFORE_CHUNK and ctx.content and ctx.file_info:
            # attach per-file language hints to help chunkers/prompts
            per_file = (ctx.state.get("language_analysis") or {}).get(ctx.file_info.relative_path)
            if per_file:
                ctx.state.setdefault("chunk_hints", {})[ctx.file_info.relative_path] = {
                    "top_k_elements": [e.name for e in per_file["elements"][:20]],
                    "dependency_count": len(per_file.get("dependencies", [])),
                    "language": per_file.get("language"),
                }