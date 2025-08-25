# lynx/plugins/core/registry.py
from __future__ import annotations
import logging
from typing import Dict, Type, List, Optional
from importlib import import_module
try:
    # Python 3.10+: stdlib
    from importlib.metadata import entry_points
except Exception:
    entry_points = None

from .base import Plugin

logger = logging.getLogger(__name__)

class PluginRegistry:
    def __init__(self):
        self._by_name: Dict[str, Type[Plugin]] = {}

    def register(self, plugin_cls: Type[Plugin]) -> None:
        name = getattr(plugin_cls, "name", plugin_cls.__name__)
        self._by_name[name] = plugin_cls

    def get(self, name: str) -> Optional[Type[Plugin]]:
        return self._by_name.get(name)

    def available(self) -> List[str]:
        return sorted(self._by_name.keys())

    def discover_entry_points(self, group: str = "lynx.plugins") -> None:
        if not entry_points:
            return
        for ep in entry_points().get(group, []):
            try:
                plugin_cls = ep.load()
                self.register(plugin_cls)
                logger.info(f"Registered plugin via entry point: {ep.name}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {ep.name}: {e}")

REGISTRY = PluginRegistry()
