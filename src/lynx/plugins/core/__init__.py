"""
Core plugin system components for Lynx.

This module provides the fundamental building blocks for the Lynx plugin system:

- Base classes and protocols for creating plugins
- Plugin context for sharing state between plugins  
- Hook points for plugin lifecycle events
- Plugin manager for orchestrating plugin execution
- Plugin registry for discovery and management
- Built-in essential plugins

The core system is designed to be:
- Extensible: Easy to add new plugins and hook points
- Robust: Graceful error handling and plugin isolation  
- Performant: Efficient plugin loading and execution
- Flexible: Support for different loading strategies and configurations

Usage:
    from lynx.plugins.core import Plugin, PluginManager, HookPoint
    
    class MyPlugin(Plugin):
        name = "my_plugin"
        version = "1.0.0" 
        order = 100
        
        def configure(self, options):
            self.enabled = options.get("enabled", True)
            
        def supports(self, hook):
            return hook in {HookPoint.BEFORE_SCAN, HookPoint.AFTER_SCAN}
            
        def on_hook(self, hook, ctx):
            if hook == HookPoint.BEFORE_SCAN:
                ctx.state["my_plugin_data"] = "initialized"
"""

import logging
from typing import Dict, List, Optional, Type, Any, Union

# Import base components
from .base import (
    Plugin,
    PluginContext,
    HookPoint
)

from .manager import PluginManager
from .registry import REGISTRY, PluginRegistry

# Import built-in plugins
from .builtins import (
    LanguageParsingPlugin,
    # Add other built-in plugins as they are created
)

logger = logging.getLogger(__name__)

# Core system version
__version__ = "1.0.0"
__author__ = "Gentry Rolofson"

class CorePluginError(Exception):
    """Base exception for core plugin system errors."""
    pass

class PluginExecutionError(CorePluginError):
    """Raised when plugin execution fails."""
    pass

class PluginManagerError(CorePluginError):
    """Raised when plugin manager encounters an error."""
    pass

class HookExecutionError(CorePluginError):
    """Raised when hook execution fails."""
    pass

def create_plugin_manager(
    plugins: List[Union[Plugin, Type[Plugin]]] = None,
    enabled_names: List[str] = None,
    options: Dict[str, Dict[str, Any]] = None
) -> PluginManager:
    """
    Create a plugin manager with flexible plugin specification.
    
    Args:
        plugins: List of plugin instances or classes
        enabled_names: List of plugin names to load from registry
        options: Configuration options for each plugin
        
    Returns:
        Configured PluginManager instance
        
    Example:
        # Create manager with specific plugin instances
        manager = create_plugin_manager([MyPlugin(), AnotherPlugin()])
        
        # Create manager from registry
        manager = create_plugin_manager(
            enabled_names=["language_bridge"],
            options={"language_bridge": {"max_elements": 100}}
        )
    """
    if plugins is not None:
        # Direct plugin specification
        plugin_instances = []
        for plugin in plugins:
            if isinstance(plugin, type):
                # Instantiate plugin class
                try:
                    instance = plugin()
                    if options and hasattr(instance, 'name'):
                        plugin_options = options.get(instance.name, {})
                        instance.configure(plugin_options)
                    plugin_instances.append(instance)
                except Exception as e:
                    raise PluginExecutionError(f"Failed to instantiate plugin {plugin}: {e}")
            else:
                # Already instantiated
                plugin_instances.append(plugin)
        
        return PluginManager(plugin_instances)
    
    elif enabled_names is not None:
        # Load from registry by names
        return PluginManager.from_config(enabled_names, options or {})
    
    else:
        # Default to built-in plugins
        builtin_names = get_builtin_plugin_names()
        return PluginManager.from_config(builtin_names, options or {})

def get_builtin_plugin_names() -> List[str]:
    """Get names of all built-in plugins."""
    builtin_names = []
    
    # Check for language bridge plugin
    if REGISTRY.get("language_bridge"):
        builtin_names.append("language_bridge")
    
    # Add other built-in plugins as they are created
    # Example:
    # if REGISTRY.get("code_metrics"):
    #     builtin_names.append("code_metrics")
    
    return builtin_names

def register_builtin_plugins() -> int:
    """
    Ensure all built-in plugins are registered.
    
    Returns:
        Number of plugins registered
    """
    plugins_registered = 0
    
    builtin_classes = [
        LanguageParsingPlugin,
        # Add other built-in plugin classes here
    ]
    
    for plugin_class in builtin_classes:
        if plugin_class is not None:
            try:
                REGISTRY.register(plugin_class)
                plugins_registered += 1
                logger.debug(f"Registered built-in plugin: {getattr(plugin_class, 'name', plugin_class.__name__)}")
            except Exception as e:
                logger.warning(f"Failed to register built-in plugin {plugin_class}: {e}")
    
    return plugins_registered

def validate_hook_point(hook: Any) -> bool:
    """
    Validate that a value is a valid HookPoint.
    
    Args:
        hook: Value to validate
        
    Returns:
        True if valid HookPoint, False otherwise
    """
    return isinstance(hook, HookPoint)

def get_available_hook_points() -> List[HookPoint]:
    """Get all available hook points."""
    return list(HookPoint)

def get_hook_point_info() -> Dict[str, str]:
    """
    Get information about all hook points.
    
    Returns:
        Dictionary mapping hook names to descriptions
    """
    return {
        HookPoint.BEFORE_SCAN.name: "Called before directory scanning begins",
        HookPoint.AFTER_SCAN.name: "Called after directory scanning completes", 
        HookPoint.BEFORE_CHUNK.name: "Called before file chunking begins",
        HookPoint.AFTER_CHUNK.name: "Called after file chunking completes",
        HookPoint.BEFORE_AI_REQUEST.name: "Called before AI summarization request",
        HookPoint.AFTER_AI_RESPONSE.name: "Called after AI summarization response",
        HookPoint.BEFORE_AGGREGATE.name: "Called before summary aggregation",
        HookPoint.AFTER_AGGREGATE.name: "Called after summary aggregation",
        HookPoint.BEFORE_OUTPUT.name: "Called before output generation", 
        HookPoint.AFTER_OUTPUT.name: "Called after output generation",
        HookPoint.ON_ERROR.name: "Called when an error occurs"
    }

def create_context(config, **initial_state) -> PluginContext:
    """
    Create a plugin context with initial state.
    
    Args:
        config: Codex configuration object
        **initial_state: Initial state values
        
    Returns:
        PluginContext instance
    """
    ctx = PluginContext(config=config)
    ctx.state.update(initial_state)
    return ctx

def execute_hook_safely(
    manager: PluginManager, 
    hook: HookPoint, 
    context: PluginContext,
    continue_on_error: bool = True
) -> List[Exception]:
    """
    Execute a hook with comprehensive error handling.
    
    Args:
        manager: Plugin manager to use
        hook: Hook point to execute
        context: Plugin context
        continue_on_error: Whether to continue after plugin errors
        
    Returns:
        List of exceptions that occurred (empty if none)
    """
    errors = []
    
    try:
        if continue_on_error:
            # Use manager's built-in error handling
            manager.emit(hook, context)
            
            # Check for errors stored in context
            if "errors" in context.state:
                errors.extend([
                    Exception(f"Plugin {err.get('plugin', 'unknown')}: {err.get('error', 'unknown error')}")
                    for err in context.state["errors"]
                ])
        else:
            # Fail fast on first error
            for plugin in manager._plugins:
                if plugin.supports(hook):
                    try:
                        plugin.on_hook(hook, context)
                    except Exception as e:
                        error = HookExecutionError(f"Plugin {getattr(plugin, 'name', plugin)} failed on {hook.name}: {e}")
                        errors.append(error)
                        raise error
                        
    except Exception as e:
        if not isinstance(e, HookExecutionError):
            error = HookExecutionError(f"Hook execution failed: {e}")
            errors.append(error)
            if not continue_on_error:
                raise error
    
    return errors

def get_plugin_dependency_order(plugins: List[Plugin]) -> List[Plugin]:
    """
    Sort plugins by dependency order and execution priority.
    
    Args:
        plugins: List of plugin instances
        
    Returns:
        Sorted list of plugins
        
    Note:
        Currently sorts by order attribute. Future versions may support
        explicit dependency declarations.
    """
    return sorted(plugins, key=lambda p: (getattr(p, "order", 100), getattr(p, "name", "")))

def get_core_system_info() -> Dict[str, Any]:
    """
    Get information about the core plugin system.
    
    Returns:
        Dictionary with system information
    """
    return {
        "version": __version__,
        "available_plugins": REGISTRY.available(),
        "builtin_plugins": get_builtin_plugin_names(),
        "hook_points": [hook.name for hook in HookPoint],
        "hook_descriptions": get_hook_point_info(),
        "registry_size": len(REGISTRY.available())
    }

def reset_core_system():
    """Reset the core plugin system (useful for testing)."""
    # Re-initialize the registry
    REGISTRY._by_name.clear()
    
    # Re-register built-in plugins
    register_builtin_plugins()
    
    logger.info("Core plugin system reset")

# Ensure built-in plugins are registered on import
_builtin_count = register_builtin_plugins()
logger.info(f"Registered {_builtin_count} built-in plugins")

# Export all core components
__all__ = [
    # Base classes and types
    "Plugin", 
    "PluginContext",
    "HookPoint",
    
    # Management classes
    "PluginManager",
    "PluginRegistry",
    "REGISTRY",
    
    # Built-in plugins
    "LanguageParsingPlugin",
    
    # Factory and utility functions
    "create_plugin_manager",
    "get_builtin_plugin_names", 
    "register_builtin_plugins",
    "validate_hook_point",
    "get_available_hook_points",
    "get_hook_point_info",
    "create_context",
    "execute_hook_safely",
    "get_plugin_dependency_order",
    "get_core_system_info",
    "reset_core_system",
    
    # Exceptions
    "CorePluginError",
    "PluginExecutionError", 
    "PluginManagerError",
    "HookExecutionError",
]

logger.debug(f"Core plugin system v{__version__} loaded with {len(REGISTRY.available())} plugins")
