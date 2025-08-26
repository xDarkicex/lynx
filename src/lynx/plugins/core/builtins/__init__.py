"""
Built-in plugins for the Lynx plugin system.

This module contains essential plugins that are included with Lynx by default.
These plugins provide core functionality that most users will want enabled:

- Language Bridge: Integrates language-specific parsers with the plugin system
- [Future plugins will be added here]

Built-in plugins are:
- Automatically registered with the plugin registry
- Enabled by default in most configurations  
- Well-tested and maintained as part of the core system
- Designed to work together seamlessly

Usage:
    from lynx.plugins.core.builtins import LanguageParsingPlugin
    
    # Plugin is automatically registered and can be used by name
    manager = PluginManager.from_config(["language_bridge"])
    
    # Or instantiate directly
    plugin = LanguageParsingPlugin()
    plugin.configure({"max_elements_per_file": 200})
"""

import logging
from typing import Dict, List, Type, Any, Optional

# Import built-in plugin classes
from .language_bridge import LanguageParsingPlugin

# Add other built-in plugins as they are created
# Example:
# from .code_metrics import CodeMetricsPlugin
# from .dependency_analyzer import DependencyAnalyzerPlugin

logger = logging.getLogger(__name__)

# Module metadata
__version__ = "1.0.0"
__author__ = "Gentry Rolofson"

class BuiltinPluginError(Exception):
    """Base exception for built-in plugin errors."""
    pass

class PluginNotAvailableError(BuiltinPluginError):
    """Raised when a built-in plugin is not available."""
    pass

# Registry of all built-in plugins
BUILTIN_PLUGINS = {
    "language_bridge": LanguageParsingPlugin,
    # Add other built-in plugins here as they are created:
    # "code_metrics": CodeMetricsPlugin,
    # "dependency_analyzer": DependencyAnalyzerPlugin,
}

def get_builtin_plugins() -> Dict[str, Type]:
    """
    Get dictionary of all built-in plugin classes.
    
    Returns:
        Dictionary mapping plugin names to plugin classes
    """
    return BUILTIN_PLUGINS.copy()

def get_builtin_plugin_names() -> List[str]:
    """
    Get list of all built-in plugin names.
    
    Returns:
        List of plugin names
    """
    return list(BUILTIN_PLUGINS.keys())

def get_builtin_plugin_class(name: str) -> Optional[Type]:
    """
    Get a built-in plugin class by name.
    
    Args:
        name: Plugin name
        
    Returns:
        Plugin class or None if not found
    """
    return BUILTIN_PLUGINS.get(name)

def is_builtin_plugin(name: str) -> bool:
    """
    Check if a plugin name refers to a built-in plugin.
    
    Args:
        name: Plugin name to check
        
    Returns:
        True if built-in plugin exists, False otherwise
    """
    return name in BUILTIN_PLUGINS

def create_builtin_plugin(name: str, options: Dict[str, Any] = None) -> Optional[object]:
    """
    Create an instance of a built-in plugin.
    
    Args:
        name: Plugin name
        options: Configuration options for the plugin
        
    Returns:
        Plugin instance or None if plugin not found
        
    Raises:
        BuiltinPluginError: If plugin instantiation fails
    """
    plugin_class = get_builtin_plugin_class(name)
    if plugin_class is None:
        return None
    
    try:
        plugin = plugin_class()
        if options:
            plugin.configure(options)
        return plugin
    except Exception as e:
        raise BuiltinPluginError(f"Failed to create built-in plugin '{name}': {e}")

def get_plugin_info(name: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a built-in plugin.
    
    Args:
        name: Plugin name
        
    Returns:
        Dictionary with plugin information or None if not found
    """
    plugin_class = get_builtin_plugin_class(name)
    if plugin_class is None:
        return None
    
    try:
        # Get basic info from class attributes
        info = {
            "name": getattr(plugin_class, "name", name),
            "version": getattr(plugin_class, "version", "unknown"),
            "order": getattr(plugin_class, "order", 100),
            "class_name": plugin_class.__name__,
            "module": plugin_class.__module__,
        }
        
        # Try to get additional info by creating a temporary instance
        try:
            temp_instance = plugin_class()
            
            # Get supported hooks
            from ..base import HookPoint
            supported_hooks = []
            for hook in HookPoint:
                try:
                    if temp_instance.supports(hook):
                        supported_hooks.append(hook.name)
                except Exception:
                    pass  # Ignore errors when checking hook support
            
            info["supported_hooks"] = supported_hooks
            
        except Exception as e:
            logger.debug(f"Could not create temporary instance for {name}: {e}")
            info["supported_hooks"] = "unknown"
        
        return info
        
    except Exception as e:
        logger.warning(f"Could not get info for plugin '{name}': {e}")
        return {
            "name": name,
            "error": str(e),
            "class_name": plugin_class.__name__ if plugin_class else "unknown"
        }

def get_all_plugin_info() -> Dict[str, Dict[str, Any]]:
    """
    Get information about all built-in plugins.
    
    Returns:
        Dictionary mapping plugin names to their information
    """
    info = {}
    for name in get_builtin_plugin_names():
        plugin_info = get_plugin_info(name)
        if plugin_info:
            info[name] = plugin_info
    return info

def validate_builtin_plugins() -> Dict[str, List[str]]:
    """
    Validate all built-in plugins.
    
    Returns:
        Dictionary with validation results for each plugin
    """
    results = {}
    
    for name, plugin_class in BUILTIN_PLUGINS.items():
        errors = []
        
        # Check class attributes
        required_attrs = ["name", "version", "order"]
        for attr in required_attrs:
            if not hasattr(plugin_class, attr):
                errors.append(f"Missing required attribute: {attr}")
        
        # Check methods
        required_methods = ["configure", "supports", "on_hook"]
        for method in required_methods:
            if not hasattr(plugin_class, method):
                errors.append(f"Missing required method: {method}")
            elif not callable(getattr(plugin_class, method)):
                errors.append(f"Attribute {method} is not callable")
        
        # Try to instantiate
        try:
            plugin_class()
        except Exception as e:
            errors.append(f"Cannot instantiate: {e}")
        
        results[name] = errors
    
    return results

def register_all_builtins() -> Dict[str, bool]:
    """
    Register all built-in plugins with the global registry.
    
    Returns:
        Dictionary mapping plugin names to registration success status
    """
    from ..registry import REGISTRY
    
    results = {}
    
    for name, plugin_class in BUILTIN_PLUGINS.items():
        try:
            REGISTRY.register(plugin_class)
            results[name] = True
            logger.debug(f"Registered built-in plugin: {name}")
        except Exception as e:
            results[name] = False
            logger.warning(f"Failed to register built-in plugin '{name}': {e}")
    
    return results

def get_builtin_system_info() -> Dict[str, Any]:
    """
    Get comprehensive information about the built-in plugin system.
    
    Returns:
        Dictionary with system information
    """
    validation_results = validate_builtin_plugins()
    
    return {
        "version": __version__,
        "total_builtins": len(BUILTIN_PLUGINS),
        "available_plugins": get_builtin_plugin_names(),
        "plugin_info": get_all_plugin_info(),
        "validation_results": validation_results,
        "valid_plugins": [name for name, errors in validation_results.items() if not errors],
        "invalid_plugins": [name for name, errors in validation_results.items() if errors]
    }

# Auto-register all built-in plugins on import
def _auto_register():
    """Automatically register built-in plugins."""
    try:
        registration_results = register_all_builtins()
        successful = [name for name, success in registration_results.items() if success]
        failed = [name for name, success in registration_results.items() if not success]
        
        logger.info(f"Auto-registered {len(successful)} built-in plugins")
        if failed:
            logger.warning(f"Failed to register built-in plugins: {failed}")
            
    except Exception as e:
        logger.error(f"Failed to auto-register built-in plugins: {e}")

# Perform auto-registration
_auto_register()

# Export all built-in plugin classes and utilities
__all__ = [
    # Plugin classes
    "LanguageParsingPlugin",
    # Add other plugin classes as they are created:
    # "CodeMetricsPlugin",
    # "DependencyAnalyzerPlugin", 
    
    # Registry and info
    "BUILTIN_PLUGINS",
    "get_builtin_plugins",
    "get_builtin_plugin_names",
    "get_builtin_plugin_class",
    "is_builtin_plugin",
    
    # Factory functions
    "create_builtin_plugin",
    
    # Information and validation
    "get_plugin_info",
    "get_all_plugin_info", 
    "validate_builtin_plugins",
    "get_builtin_system_info",
    
    # Registration
    "register_all_builtins",
    
    # Exceptions
    "BuiltinPluginError",
    "PluginNotAvailableError",
]

logger.info(f"Built-in plugins system v{__version__} loaded with {len(BUILTIN_PLUGINS)} plugins")
