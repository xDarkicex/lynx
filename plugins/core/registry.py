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
        self._register_builtin_plugins()

    def _register_builtin_plugins(self):
        """Register built-in plugins automatically."""
        try:
            # Import and register the language bridge plugin
            from .builtins.language_bridge import LanguageParsingPlugin
            self.register(LanguageParsingPlugin)
            logger.info("Registered built-in language bridge plugin")
        except ImportError as e:
            logger.warning(f"Could not register language bridge plugin: {e}")

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
