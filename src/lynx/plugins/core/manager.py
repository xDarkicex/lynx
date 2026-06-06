# lynx/plugins/core/manager.py
from __future__ import annotations
import logging
from collections import deque
from typing import Dict, Any, List, Optional, Set
from .base import Plugin, PluginContext, HookPoint
from .registry import REGISTRY

logger = logging.getLogger(__name__)


class PluginCycleError(Exception):
    """Raised when plugin dependencies contain a cycle."""
    pass


class PluginManager:
    def __init__(self, plugins: List[Plugin]):
        # stable ordering by .order then .name (only used as tiebreaker in same dependency level)
        self._plugins = plugins

    @classmethod
    def from_config(
        cls,
        enabled: List[str],
        options: Dict[str, Dict[str, Any]],
        dependencies: Optional[Dict[str, List[str]]] = None,
    ) -> "PluginManager":
        """Create PluginManager with topologically-sorted plugins.

        Args:
            enabled: List of enabled plugin names
            options: Dict mapping plugin name -> options dict
            dependencies: Dict mapping plugin name -> list of plugin names it depends on
        """
        deps = dependencies or {}
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

        # Topological sort respecting dependencies
        sorted_plugins = cls._topological_sort(instances, deps)
        manager = cls.__new__(cls)
        manager._plugins = sorted_plugins
        return manager

    @classmethod
    def _topological_sort(cls, plugins: List[Plugin], dependencies: Dict[str, List[str]]) -> List[Plugin]:
        """Sort plugins by dependencies using Kahn's algorithm.

        A plugin runs after all its dependencies. If A depends on B, B appears before A.
        """
        # Build lookup: plugin_name -> plugin instance
        by_name: Dict[str, Plugin] = {p.name: p for p in plugins}
        plugin_names: Set[str] = set(by_name.keys())

        # in_degree[plugin] = number of plugins this plugin depends on that are in our set
        # We want to start with plugins that have all deps satisfied
        in_degree: Dict[str, int] = {name: 0 for name in plugin_names}
        # adj[dep] = list of plugins that depend on dep
        adj: Dict[str, List[str]] = {name: [] for name in plugin_names}

        for plugin_name, plugin_deps in dependencies.items():
            if plugin_name not in plugin_names:
                continue
            for dep in plugin_deps:
                if dep in plugin_names:
                    in_degree[plugin_name] += 1
                    adj[dep].append(plugin_name)

        # Kahn's algorithm: start with plugins that have no unmet dependencies
        queue = deque([name for name in plugin_names if in_degree[name] == 0])
        sorted_names: List[str] = []

        while queue:
            current = queue.popleft()
            sorted_names.append(current)
            for dependent in adj[current]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        # Check for cycles
        if len(sorted_names) != len(plugin_names):
            # Find plugins not in sorted list to report cycle
            remaining = plugin_names - set(sorted_names)
            cycle_plugins = sorted(remaining)
            raise PluginCycleError(
                f"Plugin dependency cycle detected involving: {cycle_plugins}. "
                f"Check dependencies for these plugins."
            )

        # Convert names back to plugins, keeping original order within same dependency level
        # Use the original plugin list order as tiebreaker for stable ordering
        name_to_plugin = {p.name: p for p in plugins}
        result = [name_to_plugin[name] for name in sorted_names]

        # Within each dependency level, sort by .order then .name for stable ordering
        # We do a secondary stable sort to respect the order field
        result = sorted(result, key=lambda p: (getattr(p, "order", 100), getattr(p, "name", "")))

        return result

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
