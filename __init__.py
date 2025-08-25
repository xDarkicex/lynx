"""
Lynx: Intelligent codebase summarization toolkit.
Provides AI-powered code analysis and documentation generation with multi-model fallback support.
"""

from .codex import Codex
from .exceptions import LynxError, ConfigError, ProcessingError
from .utils import (
    # Configuration management
    create_default_config_template,
    create_config_from_environment, 
    get_recommended_config_for_codebase,
    load_config_file,
    validate_config,
    merge_configs,
    
    # File and token utilities
    FileInfo,
    count_tokens,
    estimate_tokens,
    get_model_context_limit,
    scan_directory,
    truncate_text,
    detect_language,
    is_text_file
)

__version__ = "1.0.0"
__author__ = "Gentry Rolofson"

# Main entry point function for functional usage
def summarize(codebase_path: str, config=None, **kwargs):
    """
    Functional interface for quick summarization.
    
    Args:
        codebase_path: Path to codebase directory
        config: Configuration dict or path to config file
        **kwargs: Additional configuration overrides
    
    Returns:
        Summary text
    """
    cfg = config or {}
    cfg.update(kwargs)
    cfg['codebase_path'] = codebase_path
    
    codex = Codex.New(cfg)
    return codex.summarize()

def init_config(
    config_type: str = "multi-model",
    codebase_path: str = None,
    save_to_file: str = None,
    analyze_codebase: bool = True,
    **overrides
):
    """
    Initialize a Lynx configuration with smart defaults and optional codebase analysis.
    
    Args:
        config_type: Type of config - "multi-model", "single-model", "minimal", or "auto"
        codebase_path: Optional path to analyze for optimal settings
        save_to_file: Optional path to save the config file
        analyze_codebase: Whether to analyze the codebase for recommendations
        **overrides: Additional configuration overrides
        
    Returns:
        Configuration dictionary
        
    Example:
        # Auto-configure from environment variables
        config = lynx.init_config("auto")
        
        # Smart config based on codebase analysis
        config = lynx.init_config(
            codebase_path="/path/to/project",
            analyze_codebase=True,
            save_to_file="lynx-config.json"
        )
        
        # Simple multi-model setup with overrides
        config = lynx.init_config(
            "multi-model", 
            chunk_size=3000,
            max_workers=12
        )
    """
    if config_type == "auto":
        # Auto-configure from environment
        config = create_config_from_environment()
        if codebase_path:
            config['codebase_path'] = codebase_path
    elif codebase_path and analyze_codebase:
        # Get recommended config based on codebase analysis
        config = get_recommended_config_for_codebase(codebase_path)
    else:
        # Use template
        config = create_default_config_template(config_type)
        if codebase_path:
            config['codebase_path'] = codebase_path
    
    # Apply any overrides
    if overrides:
        config = merge_configs(config, overrides)
    
    # Validate the final configuration
    issues = validate_config(config)
    if issues:
        raise ConfigError(f"Configuration validation failed:\n" + "\n".join(f"- {issue}" for issue in issues))
    
    if save_to_file:
        import json
        # Remove internal fields before saving
        save_config = {k: v for k, v in config.items() if not k.startswith('_')}
        with open(save_to_file, 'w', encoding='utf-8') as f:
            json.dump(save_config, f, indent=2)
    
    return config

def quick_start(codebase_path: str, **kwargs):
    """
    Quick start function that automatically configures and runs analysis.
    
    Args:
        codebase_path: Path to codebase directory
        **kwargs: Configuration overrides
        
    Returns:
        Analysis results
        
    Example:
        results = lynx.quick_start("/path/to/project")
        results = lynx.quick_start("/path/to/project", chunk_size=3000, output="custom.md")
    """
    try:
        # Try auto-configuration first
        config = init_config("auto", codebase_path=codebase_path, **kwargs)
        print("✅ Auto-configured from environment variables")
    except ValueError:
        # Fallback to analyzing the codebase
        try:
            config = init_config(codebase_path=codebase_path, analyze_codebase=True, **kwargs)
            print("✅ Generated recommended configuration based on codebase analysis")
        except Exception:
            # Ultimate fallback to default template
            config = init_config("multi-model", codebase_path=codebase_path, **kwargs)
            print("⚠️  Using default configuration - please set API keys")
    
    return summarize(codebase_path, config)

def validate_setup():
    """
    Validate that Lynx is properly set up with API keys and dependencies.
    
    Returns:
        Dictionary with setup status information
    """
    import os
    import importlib
    
    status = {
        "api_keys_found": [],
        "missing_dependencies": [],
        "ready": False
    }
    
    # Check for API keys
    api_keys = {
        "PPLX_API_KEY": "Perplexity",
        "PERPLEXITY_API_KEY": "Perplexity", 
        "OPENAI_API_KEY": "OpenAI",
        "ANTHROPIC_API_KEY": "Anthropic"
    }
    
    for env_var, provider in api_keys.items():
        if os.getenv(env_var):
            if provider not in [item["provider"] for item in status["api_keys_found"]]:
                status["api_keys_found"].append({"env_var": env_var, "provider": provider})
    
    # Check dependencies
    required_deps = ["tiktoken", "langchain_core"]
    optional_deps = ["langchain_perplexity", "langchain_openai", "langchain_anthropic"]
    
    for dep in required_deps:
        try:
            __import__(dep)
        except ImportError:
            status["missing_dependencies"].append(f"{dep} (required)")
    
    for dep in optional_deps:
        try:
            __import__(dep)
        except ImportError:
            status["missing_dependencies"].append(f"{dep} (optional)")
    
    status["ready"] = len(status["api_keys_found"]) > 0 and not any("required" in dep for dep in status["missing_dependencies"])
    
    return status

__all__ = [
    # Main classes and functions
    'Codex', 'summarize', 'init_config', 'quick_start', 'validate_setup',
    
    # Configuration utilities
    'create_default_config_template', 'create_config_from_environment',
    'get_recommended_config_for_codebase', 'load_config_file', 
    'validate_config', 'merge_configs',
    
    # File and processing utilities
    'FileInfo', 'count_tokens', 'estimate_tokens', 'get_model_context_limit',
    'scan_directory', 'truncate_text', 'detect_language', 'is_text_file',
    
    # Exceptions
    'LynxError', 'ConfigError', 'ProcessingError'
]
