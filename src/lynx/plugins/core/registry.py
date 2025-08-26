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
        self._builtin_registered = False

    def _ensure_builtin_plugins_registered(self):
        """Ensure built-in plugins are registered (called lazily)."""
        if self._builtin_registered:
            return
            
        try:
            # Import and register the language bridge plugin
            from .builtins.language_bridge import LanguageParsingPlugin
            self.register(LanguageParsingPlugin)
            logger.info("Registered built-in language bridge plugin")
        except ImportError as e:
            logger.warning(f"Could not register language bridge plugin: {e}")
        
        self._builtin_registered = True

    def register(self, plugin_cls: Type[Plugin]) -> None:
        name = getattr(plugin_cls, "name", plugin_cls.__name__)
        self._by_name[name] = plugin_cls

    def get(self, name: str) -> Optional[Type[Plugin]]:
        self._ensure_builtin_plugins_registered()
        return self._by_name.get(name)

    def available(self) -> List[str]:
        self._ensure_builtin_plugins_registered()
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

# Global registry instance - now safe from circular imports
REGISTRY = PluginRegistry()