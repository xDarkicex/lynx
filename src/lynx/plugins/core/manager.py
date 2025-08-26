# lynx/plugins/core/manager.py
from __future__ import annotations
import logging
from typing import Dict, Any, List
from .base import Plugin, PluginContext, HookPoint
from .registry import REGISTRY

logger = logging.getLogger(__name__)

class PluginManager:
    def __init__(self, plugins: List[Plugin]):
        # stable ordering by .order then .name
        self._plugins = sorted(plugins, key=lambda p: (getattr(p, "order", 100), getattr(p, "name", "")))

    @classmethod
    def from_config(cls, enabled: List[str], options: Dict[str, Dict[str, Any]]) -> "PluginManager":
        instances: List[Plugin] = []
        for name in enabled or []:
            plugin_cls = REGISTRY.get(name)
            if not plugin_cls:
                logger.warning(f"Plugin not found: {name}")
                continue
            try:
                plugin = plugin_cls()  # type: ignore
                plugin.configure(options.get(name, {}) if options else {})
                instances.append(plugin)
            except Exception as e:
                logger.error(f"Failed to init plugin {name}: {e}")
        return cls(instances)

    def emit(self, hook: HookPoint, ctx: PluginContext) -> None:
        for p in self._plugins:
            if not p.supports(hook):
                continue
            try:
                p.on_hook(hook, ctx)
            except Exception as e:
                logger.warning(f"Plugin {getattr(p,'name',p)} failed on {hook}: {e}")
                # Notify all plugins that care about errors
                err_ctx = ctx
                err_ctx.state.setdefault("errors", []).append({"plugin": getattr(p, 'name', str(p)), "hook": hook.name, "error": str(e)})
                for q in self._plugins:
                    if q.supports(HookPoint.ON_ERROR) and q is not p:
                        try:
                            q.on_hook(HookPoint.ON_ERROR, err_ctx)
                        except Exception:
                            pass
