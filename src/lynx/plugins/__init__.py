"""
Lynx Plugin System - Comprehensive plugin architecture for code analysis.

The Lynx plugin system provides extensible functionality for code analysis,
language parsing, and custom processing workflows. It supports:

- Language-specific parsers for syntax analysis
- Hook-based event system for processing pipelines  
- Plugin discovery and registration
- Configurable plugin loading strategies
- Error handling and plugin isolation

Architecture:
- Core: Base classes, plugin manager, and registry
- Languages: Language-specific parsers and analyzers
- Builtins: Essential plugins included with Lynx

Usage:
    from lynx.plugins import get_plugin_manager, register_plugin
    from lynx.plugins.languages import get_parser_for_language
    
    # Get parser for Python files
    parser = get_parser_for_language("python")
    
    # Register custom plugin
    register_plugin(MyCustomPlugin)
"""

import logging
from typing import Dict, List, Optional, Type, Any

# Import core plugin system components
from .core.base import (
    Plugin,
    PluginContext, 
    HookPoint,
    # Re-export for convenience
    Plugin as PluginProtocol
)

from .core.manager import PluginManager
from .core.registry import REGISTRY, PluginRegistry

# Import built-in plugins
from .core.builtins import (
    LanguageParsingPlugin,
    # Add other built-in plugins as they're created
)

# Import language parsers (with error handling)
try:
    from .languages import (
        get_parser_for_language,
        get_parser_for_file,
        get_parser,
        get_supported_languages,
        get_supported_extensions,
        is_language_supported,
        is_extension_supported,
        register_language_parser,
        BaseLanguageParser,
        ParsedElement,
        language_registry,
        clear_parser_cache,
        get_parser_info
    )
    LANGUAGES_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Language parsers not available: {e}")
    LANGUAGES_AVAILABLE = False
    # Create stub functions
    def get_parser_for_language(language: str): return None
    def get_parser_for_file(extension: str): return None
    def get_parser(lang_or_ext: str): return None
    def get_supported_languages(): return []
    def get_supported_extensions(): return []
    def is_language_supported(language: str): return False
    def is_extension_supported(extension: str): return False
    def register_language_parser(parser_class): pass
    def clear_parser_cache(): pass
    def get_parser_info(): return {}
    BaseLanguageParser = None
    ParsedElement = None
    language_registry = None

logger = logging.getLogger(__name__)

# Plugin system version
__version__ = "1.0.0"
__author__ = "Gentry Rolofson"

class PluginSystemError(Exception):
    """Base exception for plugin system errors."""
    pass

class PluginLoadError(PluginSystemError):
    """Raised when a plugin fails to load."""
    pass

class PluginConfigurationError(PluginSystemError):
    """Raised when a plugin has invalid configuration."""
    pass

def get_plugin_manager(
    enabled_plugins: List[str] = None,
    plugin_options: Dict[str, Dict[str, Any]] = None
) -> PluginManager:
    """
    Create and configure a plugin manager.
    
    Args:
        enabled_plugins: List of plugin names to enable
        plugin_options: Configuration options for each plugin
        
    Returns:
        Configured PluginManager instance
        
    Example:
        manager = get_plugin_manager(
            enabled_plugins=["language_bridge"],
            plugin_options={
                "language_bridge": {
                    "max_elements_per_file": 200,
                    "analyze_dependencies": True
                }
            }
        )
    """
    if enabled_plugins is None:
        enabled_plugins = get_available_builtin_plugins()
    
    return PluginManager.from_config(enabled_plugins, plugin_options or {})

def get_plugin_registry() -> PluginRegistry:
    """Get the global plugin registry."""
    return REGISTRY

def register_plugin(plugin_class: Type[Plugin]) -> None:
    """
    Register a plugin class with the global registry.
    
    Args:
        plugin_class: Plugin class to register
        
    Raises:
        PluginConfigurationError: If plugin class is invalid
        
    Example:
        @register_plugin
        class MyCustomPlugin:
            name = "my_custom_plugin"
            version = "1.0.0"
            order = 100
            
            def configure(self, options): pass
            def supports(self, hook): return hook == HookPoint.BEFORE_SCAN
            def on_hook(self, hook, ctx): pass
    """
    try:
        REGISTRY.register(plugin_class)
        logger.info(f"Registered plugin: {getattr(plugin_class, 'name', plugin_class.__name__)}")
    except Exception as e:
        raise PluginConfigurationError(f"Failed to register plugin {plugin_class}: {e}")

def get_available_plugins() -> List[str]:
    """Get list of all available plugin names."""
    return REGISTRY.available()

def get_available_builtin_plugins() -> List[str]:
    """Get list of available built-in plugin names."""
    builtin_plugins = []
    
    # Language bridge is always available if the plugin system works
    if REGISTRY.get("language_bridge"):
        builtin_plugins.append("language_bridge")
    
    # Add other built-in plugins as they're created
    # Example: if REGISTRY.get("code_metrics"): builtin_plugins.append("code_metrics")
    
    return builtin_plugins

def discover_plugins(entry_point_group: str = "lynx.plugins") -> int:
    """
    Discover and register plugins from entry points.
    
    Args:
        entry_point_group: Entry point group to search
        
    Returns:
        Number of plugins discovered and registered
    """
    initial_count = len(get_available_plugins())
    REGISTRY.discover_entry_points(entry_point_group)
    final_count = len(get_available_plugins())
    
    discovered = final_count - initial_count
    if discovered > 0:
        logger.info(f"Discovered {discovered} plugins via entry points")
    
    return discovered

def validate_plugin_class(plugin_class: Type) -> List[str]:
    """
    Validate that a class implements the Plugin protocol correctly.
    
    Args:
        plugin_class: Class to validate
        
    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    
    # Check required attributes
    required_attrs = ['name', 'version', 'order']
    for attr in required_attrs:
        if not hasattr(plugin_class, attr):
            errors.append(f"Missing required attribute: {attr}")
    
    # Check required methods
    required_methods = ['configure', 'supports', 'on_hook']
    for method in required_methods:
        if not hasattr(plugin_class, method):
            errors.append(f"Missing required method: {method}")
        elif not callable(getattr(plugin_class, method)):
            errors.append(f"Attribute {method} is not callable")
    
    # Check attribute types
    if hasattr(plugin_class, 'name') and not isinstance(plugin_class.name, str):
        errors.append("'name' attribute must be a string")
    
    if hasattr(plugin_class, 'version') and not isinstance(plugin_class.version, str):
        errors.append("'version' attribute must be a string")
    
    if hasattr(plugin_class, 'order') and not isinstance(plugin_class.order, int):
        errors.append("'order' attribute must be an integer")
    
    return errors

def create_plugin_context(config, **kwargs) -> PluginContext:
    """
    Create a plugin context with optional initial state.
    
    Args:
        config: Codex configuration
        **kwargs: Additional context attributes
        
    Returns:
        PluginContext instance
    """
    ctx = PluginContext(config=config)
    
    # Set any provided attributes
    for key, value in kwargs.items():
        if hasattr(ctx, key):
            setattr(ctx, key, value)
        else:
            ctx.state[key] = value
    
    return ctx

def get_system_info() -> Dict[str, Any]:
    """
    Get comprehensive information about the plugin system.
    
    Returns:
        Dictionary with system information
    """
    return {
        "version": __version__,
        "available_plugins": get_available_plugins(),
        "builtin_plugins": get_available_builtin_plugins(),
        "languages_available": LANGUAGES_AVAILABLE,
        "supported_languages": get_supported_languages() if LANGUAGES_AVAILABLE else [],
        "supported_extensions": get_supported_extensions() if LANGUAGES_AVAILABLE else [],
        "hook_points": [hook.name for hook in HookPoint],
        "registry_info": {
            "total_plugins": len(get_available_plugins()),
            "builtin_count": len(get_available_builtin_plugins())
        }
    }

def reset_plugin_system():
    """Reset the plugin system to initial state (useful for testing)."""
    # Clear any cached instances in the registry
    REGISTRY.__init__()  # Re-initialize registry
    
    if LANGUAGES_AVAILABLE:
        clear_parser_cache()
    
    logger.info("Plugin system reset")

# Export everything needed for the plugin system
__all__ = [
    # Core plugin system
    "Plugin",
    "PluginProtocol", 
    "PluginContext",
    "HookPoint",
    "PluginManager",
    "PluginRegistry", 
    "REGISTRY",
    
    # Built-in plugins
    "LanguageParsingPlugin",
    
    # Language parsing system (if available)
    "get_parser_for_language",
    "get_parser_for_file", 
    "get_parser",
    "get_supported_languages",
    "get_supported_extensions",
    "is_language_supported",
    "is_extension_supported", 
    "register_language_parser",
    "BaseLanguageParser",
    "ParsedElement",
    "language_registry",
    "clear_parser_cache",
    "get_parser_info",
    
    # Management functions
    "get_plugin_manager",
    "get_plugin_registry",
    "register_plugin", 
    "get_available_plugins",
    "get_available_builtin_plugins",
    "discover_plugins",
    "validate_plugin_class",
    "create_plugin_context",
    "get_system_info",
    "reset_plugin_system",
    
    # Exceptions
    "PluginSystemError",
    "PluginLoadError", 
    "PluginConfigurationError",
    
    # Constants
    "LANGUAGES_AVAILABLE",
]

# Log initialization
logger.info(f"Lynx Plugin System v{__version__} initialized")
logger.info(f"Available plugins: {len(get_available_plugins())}")
if LANGUAGES_AVAILABLE:
    logger.info(f"Language support: {len(get_supported_languages())} languages")
else:
    logger.warning("Language parsing system not available")
