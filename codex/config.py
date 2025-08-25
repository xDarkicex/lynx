"""Enhanced configuration management for Lynx Codex with comprehensive plugin support."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, Set, List
from dataclasses import dataclass, field, asdict
from enum import Enum

from ..exceptions import ConfigError

class PluginLoadStrategy(Enum):
    """Strategy for loading plugins."""
    LAZY = "lazy"
    EAGER = "eager"
    ON_DEMAND = "on_demand"

@dataclass
class ModelConfig:
    """Configuration for a single AI model."""
    provider: str  # 'openai', 'perplexity', 'anthropic'
    model: str     # Model name
    api_key: str   # API key for this provider
    temperature: float = 0.0
    max_tokens: int = 16000
    
    def __post_init__(self):
        if not self.provider:
            raise ConfigError("Provider is required for model config")
        if not self.model:
            raise ConfigError("Model name is required for model config")
        if not self.api_key:
            raise ConfigError("API key is required for model config")

@dataclass
class PluginConfig:
    """Configuration for individual plugins."""
    name: str
    enabled: bool = True
    priority: int = 100  # Lower numbers = higher priority
    options: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    load_strategy: PluginLoadStrategy = PluginLoadStrategy.LAZY
    
    def __post_init__(self):
        if not self.name:
            raise ConfigError("Plugin name is required")

@dataclass
class LanguageParserConfig:
    """Configuration for language parsers."""
    language: str
    parser_class: str
    enabled: bool = True
    priority: int = 100
    options: Dict[str, Any] = field(default_factory=dict)
    file_extensions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if not self.language:
            raise ConfigError("Language is required for parser config")
        if not self.parser_class:
            raise ConfigError("Parser class is required")

@dataclass
class PluginSystemConfig:
    """Configuration for the plugin system."""
    enabled: bool = True
    auto_discover: bool = True
    discovery_paths: List[str] = field(default_factory=lambda: [
        "lynx.plugins.core.builtins",
        "lynx.plugins.languages"
    ])
    load_strategy: PluginLoadStrategy = PluginLoadStrategy.LAZY
    max_load_retries: int = 3
    plugin_timeout: float = 30.0
    enable_plugin_metrics: bool = True
    
    # Plugin-specific configurations
    plugins: Dict[str, PluginConfig] = field(default_factory=dict)
    language_parsers: Dict[str, LanguageParserConfig] = field(default_factory=dict)
    
    # Built-in plugin configurations
    builtin_plugins: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "language_bridge": {
            "enabled": True,
            "priority": 50,
            "options": {
                "max_elements_per_file": 200,
                "analyze_dependencies": True,
                "cache_parsed_results": True,
                "enable_semantic_hints": True
            }
        }
    })

@dataclass
class CodexConfig:
    """Enhanced configuration for Codex summarization with plugin support."""
    
    # Required settings
    codebase_path: str = ""
    
    # Multi-model configuration - list of models in fallback order
    models: List[ModelConfig] = field(default_factory=list)
    
    # Legacy single model support (for backwards compatibility)
    api_key: str = ""
    model: str = "sonar-large-chat"
    temperature: float = 0.0
    max_tokens_per_request: int = 16000
    
    # Chunking settings
    chunk_size: int = 2000
    chunk_overlap: int = 400
    max_chunks_per_file: int = 10
    
    # File filtering
    include_patterns: Set[str] = field(default_factory=lambda: {'*.py', '*.rs', '*.go', '*.js', '*.ts'})
    exclude_patterns: Set[str] = field(default_factory=lambda: {
        '*/__pycache__/*', '*/node_modules/*', '*/.git/*',
        '*/target/*', '*/build/*', '*/dist/*', '*test*'
    })
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    
    # Output settings
    output_dest: str = "master_summary.md"
    output_format: str = "markdown"  # markdown, json, text
    
    # Processing settings
    max_workers: int = 8
    timeout_seconds: int = 30
    retry_attempts: int = 3
    
    # Advanced options
    semantic_chunking: bool = True
    preserve_code_structure: bool = True
    include_metrics: bool = True
    fallback_enabled: bool = True
    
    # Plugin system configuration (new)
    plugin_system: PluginSystemConfig = field(default_factory=PluginSystemConfig)
    
    # Language-specific configurations (new)
    language_configs: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "python": {
            "use_ast_parsing": True,
            "detect_test_files": True,
            "extract_docstrings": True,
            "analyze_imports": True
        },
        "javascript": {
            "parse_jsx": True,
            "detect_react_components": True,
            "analyze_es6_modules": True
        },
        "typescript": {
            "parse_types": True,
            "extract_interfaces": True,
            "analyze_decorators": True
        },
        "rust": {
            "parse_macros": True,
            "extract_traits": True,
            "analyze_ownership": False  # Advanced feature
        },
        "go": {
            "analyze_interfaces": True,
            "detect_goroutines": False,
            "extract_structs": True
        }
    })
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._setup_models()
        self._setup_default_plugins()
        self.validate()
    
    def _setup_models(self):
        """Setup models list from legacy config or multi-model config."""
        if not self.models and self.api_key:
            # Legacy single model configuration
            provider = self._detect_provider_from_model(self.model)
            self.models = [ModelConfig(
                provider=provider,
                model=self.model,
                api_key=self.api_key,
                temperature=self.temperature,
                max_tokens=self.max_tokens_per_request
            )]
        elif not self.models:
            # No configuration provided, try environment variables
            self._load_from_environment()
    
    def _setup_default_plugins(self):
        """Setup default plugin configurations."""
        if not self.plugin_system.plugins:
            # Setup built-in plugins
            for plugin_name, plugin_config in self.plugin_system.builtin_plugins.items():
                self.plugin_system.plugins[plugin_name] = PluginConfig(
                    name=plugin_name,
                    enabled=plugin_config.get("enabled", True),
                    priority=plugin_config.get("priority", 100),
                    options=plugin_config.get("options", {}),
                    load_strategy=PluginLoadStrategy(plugin_config.get("load_strategy", "lazy"))
                )
        
        # Setup default language parsers
        if not self.plugin_system.language_parsers:
            self._setup_default_language_parsers()
    
    def _setup_default_language_parsers(self):
        """Setup default language parser configurations."""
        default_parsers = {
            "python": {
                "parser_class": "lynx.plugins.languages.python_parser.PythonParser",
                "extensions": [".py", ".pyw"],
                "priority": 10
            },
            "javascript": {
                "parser_class": "lynx.plugins.languages.javascript_parser.JavaScriptParser",
                "extensions": [".js", ".jsx", ".mjs", ".cjs"],
                "priority": 10
            },
            "typescript": {
                "parser_class": "lynx.plugins.languages.typescript_parser.TypeScriptParser",
                "extensions": [".ts", ".tsx", ".d.ts"],
                "priority": 10
            },
            "rust": {
                "parser_class": "lynx.plugins.languages.rust_parser.RustParser",
                "extensions": [".rs"],
                "priority": 10
            },
            "go": {
                "parser_class": "lynx.plugins.languages.go_parser.GoParser",
                "extensions": [".go"],
                "priority": 10
            },
            "java": {
                "parser_class": "lynx.plugins.languages.java_parser.JavaParser",
                "extensions": [".java"],
                "priority": 10
            },
            "kotlin": {
                "parser_class": "lynx.plugins.languages.kotlin_parser.KotlinParser",
                "extensions": [".kt", ".kts"],
                "priority": 10
            },
            "swift": {
                "parser_class": "lynx.plugins.languages.swift_parser.SwiftParser",
                "extensions": [".swift"],
                "priority": 10
            },
            "csharp": {
                "parser_class": "lynx.plugins.languages.csharp_parser.CSharpParser",
                "extensions": [".cs"],
                "priority": 10
            },
            "cpp": {
                "parser_class": "lynx.plugins.languages.cpp_parser.CppParser",
                "extensions": [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"],
                "priority": 10
            },
            "c": {
                "parser_class": "lynx.plugins.languages.c_parser.CParser",
                "extensions": [".c", ".h"],
                "priority": 10
            },
            "ruby": {
                "parser_class": "lynx.plugins.languages.ruby_parser.RubyParser",
                "extensions": [".rb"],
                "priority": 10
            },
            "php": {
                "parser_class": "lynx.plugins.languages.php_parser.PhpParser",
                "extensions": [".php"],
                "priority": 10
            },
            "html": {
                "parser_class": "lynx.plugins.languages.html_parser.HtmlParser",
                "extensions": [".html", ".htm", ".xhtml"],
                "priority": 20
            },
            "css": {
                "parser_class": "lynx.plugins.languages.css_parser.CssParser",
                "extensions": [".css", ".scss", ".sass", ".less"],
                "priority": 20
            },
            "sql": {
                "parser_class": "lynx.plugins.languages.sql_parser.SqlParser",
                "extensions": [".sql"],
                "priority": 15
            },
            "bash": {
                "parser_class": "lynx.plugins.languages.bash_parser.BashParser",
                "extensions": [".sh", ".bash", ".zsh", ".fish", ".ksh"],
                "priority": 15
            },
            "react": {
                "parser_class": "lynx.plugins.languages.react_parser.ReactParser",
                "extensions": [".jsx", ".tsx"],
                "priority": 5  # Higher priority than base JS/TS
            },
            "nextjs": {
                "parser_class": "lynx.plugins.languages.nextjs_parser.NextjsParser",
                "extensions": [".js", ".jsx", ".ts", ".tsx"],
                "priority": 3  # Highest priority for Next.js files
            },
            "flutter": {
                "parser_class": "lynx.plugins.languages.flutter_parser.FlutterParser",
                "extensions": [".dart"],
                "priority": 5
            },
            "generic": {
                "parser_class": "lynx.plugins.languages.generic_parser.GenericParser",
                "extensions": ["*"],  # Fallback for all extensions
                "priority": 1000  # Lowest priority (fallback)
            }
        }
        
        for lang, config in default_parsers.items():
            self.plugin_system.language_parsers[lang] = LanguageParserConfig(
                language=lang,
                parser_class=config["parser_class"],
                file_extensions=config["extensions"],
                priority=config["priority"],
                enabled=True
            )
    
    def _detect_provider_from_model(self, model_name: str) -> str:
        """Detect provider based on model name."""
        if model_name.startswith('gpt-'):
            return 'openai'
        elif model_name.startswith('claude-'):
            return 'anthropic'
        elif model_name.startswith('sonar-'):
            return 'perplexity'
        else:
            return 'openai'  # Default to OpenAI
    
    def _load_from_environment(self):
        """Load model configuration from environment variables."""
        env_models = []
        
        # Try Perplexity first
        pplx_key = os.getenv('PPLX_API_KEY') or os.getenv('PERPLEXITY_API_KEY')
        if pplx_key:
            env_models.append(ModelConfig(
                provider='perplexity',
                model='sonar-large-chat',
                api_key=pplx_key,
                temperature=0.0,
                max_tokens=16000
            ))
        
        # Try OpenAI
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key:
            env_models.append(ModelConfig(
                provider='openai',
                model='gpt-4',
                api_key=openai_key,
                temperature=0.0,
                max_tokens=8000
            ))
        
        # Try Anthropic
        anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        if anthropic_key:
            env_models.append(ModelConfig(
                provider='anthropic',
                model='claude-3-sonnet-20240229',
                api_key=anthropic_key,
                temperature=0.0,
                max_tokens=100000
            ))
        
        self.models = env_models
    
    def validate(self) -> None:
        """Validate configuration settings."""
        if not self.codebase_path:
            raise ConfigError("codebase_path is required")
            
        if not Path(self.codebase_path).exists():
            raise ConfigError(f"Codebase path does not exist: {self.codebase_path}")
        
        if not self.models:
            raise ConfigError(
                "No AI models configured. Please provide model configuration or set "
                "environment variables (PPLX_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
            )
            
        if self.chunk_size <= 0:
            raise ConfigError("chunk_size must be positive")
            
        if self.max_workers <= 0:
            raise ConfigError("max_workers must be positive")
        
        # Validate each model config
        for i, model_config in enumerate(self.models):
            try:
                # This will raise ConfigError if invalid
                if not model_config.provider or not model_config.model or not model_config.api_key:
                    raise ConfigError("Invalid model configuration")
            except Exception as e:
                raise ConfigError(f"Invalid model configuration at index {i}: {e}")
        
        # Validate plugin system configuration
        self._validate_plugin_system()
    
    def _validate_plugin_system(self):
        """Validate plugin system configuration."""
        if not self.plugin_system.enabled:
            return
        
        # Validate plugin configurations
        for plugin_name, plugin_config in self.plugin_system.plugins.items():
            if not plugin_config.name:
                raise ConfigError(f"Plugin name is required for plugin configuration")
            
            # Validate dependencies
            for dep in plugin_config.dependencies:
                if dep not in self.plugin_system.plugins:
                    raise ConfigError(f"Plugin {plugin_name} depends on {dep} which is not configured")
        
        # Validate language parser configurations
        for lang, parser_config in self.plugin_system.language_parsers.items():
            if not parser_config.language:
                raise ConfigError(f"Language is required for parser {lang}")
            if not parser_config.parser_class:
                raise ConfigError(f"Parser class is required for language {lang}")
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CodexConfig':
        """Create config from dictionary."""
        # Handle set conversion for patterns
        if 'include_patterns' in data and isinstance(data['include_patterns'], list):
            data['include_patterns'] = set(data['include_patterns'])
        if 'exclude_patterns' in data and isinstance(data['exclude_patterns'], list):
            data['exclude_patterns'] = set(data['exclude_patterns'])
        
        # Handle models list
        if 'models' in data and isinstance(data['models'], list):
            models = []
            for model_data in data['models']:
                if isinstance(model_data, dict):
                    models.append(ModelConfig(**model_data))
                else:
                    models.append(model_data)
            data['models'] = models
        
        # Handle plugin system configuration
        if 'plugin_system' in data:
            plugin_data = data['plugin_system']
            
            # Convert plugin configurations
            if 'plugins' in plugin_data:
                plugins = {}
                for name, config in plugin_data['plugins'].items():
                    if isinstance(config, dict):
                        # Handle load_strategy enum
                        if 'load_strategy' in config:
                            config['load_strategy'] = PluginLoadStrategy(config['load_strategy'])
                        plugins[name] = PluginConfig(name=name, **config)
                    else:
                        plugins[name] = config
                plugin_data['plugins'] = plugins
            
            # Convert language parser configurations
            if 'language_parsers' in plugin_data:
                parsers = {}
                for lang, config in plugin_data['language_parsers'].items():
                    if isinstance(config, dict):
                        parsers[lang] = LanguageParserConfig(**config)
                    else:
                        parsers[lang] = config
                plugin_data['language_parsers'] = parsers
            
            # Handle load_strategy enum
            if 'load_strategy' in plugin_data:
                plugin_data['load_strategy'] = PluginLoadStrategy(plugin_data['load_strategy'])
            
            data['plugin_system'] = PluginSystemConfig(**plugin_data)
            
        return cls(**data)
    
    @classmethod
    def from_file(cls, config_path: str) -> 'CodexConfig':
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            raise ConfigError(f"Config file not found: {config_path}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config file: {e}")
            
        return cls.from_dict(data)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, set):
                result[key] = list(value)
            elif key == 'models' and isinstance(value, list):
                # Maintain original behavior for models list
                result[key] = [
                    {
                        'provider': m.provider,
                        'model': m.model,
                        'api_key': '***' if m.api_key else '',
                        'temperature': m.temperature,
                        'max_tokens': m.max_tokens
                    } for m in value
                ]
            elif hasattr(value, '__dataclass_fields__'):
                # Handle dataclass objects
                result[key] = asdict(value)
            elif isinstance(value, dict) and key == 'plugin_system':
                # Special handling for plugin system to convert enums
                plugin_dict = asdict(value)
                # Convert enums to strings
                if 'load_strategy' in plugin_dict:
                    plugin_dict['load_strategy'] = plugin_dict['load_strategy'].value
                for plugin_name, plugin_config in plugin_dict.get('plugins', {}).items():
                    if 'load_strategy' in plugin_config:
                        plugin_config['load_strategy'] = plugin_config['load_strategy'].value
                result[key] = plugin_dict
            else:
                result[key] = value
        return result
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to JSON file."""
        config_dict = self.to_dict()
        # Don't save sensitive data in legacy fields
        if 'api_key' in config_dict:
            config_dict['api_key'] = '***'
        
        # Sanitize API keys in models (already handled in to_dict)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, default=str)
    
    def get_primary_model(self) -> ModelConfig:
        """Get the primary (first) model configuration."""
        if not self.models:
            raise ConfigError("No models configured")
        return self.models[0]
    
    def get_fallback_models(self) -> List[ModelConfig]:
        """Get fallback model configurations (all except the first)."""
        return self.models[1:] if len(self.models) > 1 else []
    
    # New plugin management methods
    def enable_plugin(self, plugin_name: str) -> None:
        """Enable a plugin."""
        if plugin_name in self.plugin_system.plugins:
            self.plugin_system.plugins[plugin_name].enabled = True
        else:
            raise ConfigError(f"Plugin {plugin_name} not found in configuration")
    
    def disable_plugin(self, plugin_name: str) -> None:
        """Disable a plugin."""
        if plugin_name in self.plugin_system.plugins:
            self.plugin_system.plugins[plugin_name].enabled = False
        else:
            raise ConfigError(f"Plugin {plugin_name} not found in configuration")
    
    def add_plugin(self, plugin_config: PluginConfig) -> None:
        """Add a new plugin configuration."""
        self.plugin_system.plugins[plugin_config.name] = plugin_config
    
    def remove_plugin(self, plugin_name: str) -> None:
        """Remove a plugin configuration."""
        if plugin_name in self.plugin_system.plugins:
            del self.plugin_system.plugins[plugin_name]
        else:
            raise ConfigError(f"Plugin {plugin_name} not found in configuration")
    
    def get_enabled_plugins(self) -> List[str]:
        """Get list of enabled plugin names."""
        return [name for name, config in self.plugin_system.plugins.items() if config.enabled]
    
    def get_language_parser_config(self, language: str) -> Optional[LanguageParserConfig]:
        """Get language parser configuration for a specific language."""
        return self.plugin_system.language_parsers.get(language)
    
    def get_language_config(self, language: str) -> Dict[str, Any]:
        """Get language-specific configuration."""
        return self.language_configs.get(language, {})
    
    def update_language_config(self, language: str, config: Dict[str, Any]) -> None:
        """Update language-specific configuration."""
        if language in self.language_configs:
            self.language_configs[language].update(config)
        else:
            self.language_configs[language] = config

# Factory functions for common configurations
def create_plugin_enabled_config(**kwargs) -> CodexConfig:
    """Create a configuration with all plugins enabled."""
    config = CodexConfig(**kwargs)
    config.plugin_system.enabled = True
    config.plugin_system.auto_discover = True
    return config

def create_minimal_plugin_config(**kwargs) -> CodexConfig:
    """Create a minimal configuration with only essential plugins."""
    config = CodexConfig(**kwargs)
    config.plugin_system.enabled = True
    config.plugin_system.auto_discover = False
    
    # Only enable language bridge plugin
    essential_plugins = ["language_bridge"]
    for plugin_name in list(config.plugin_system.plugins.keys()):
        if plugin_name not in essential_plugins:
            config.plugin_system.plugins[plugin_name].enabled = False
    
    return config

def create_language_specific_config(languages: List[str], **kwargs) -> CodexConfig:
    """Create a configuration optimized for specific languages."""
    config = CodexConfig(**kwargs)
    
    # Enable only specified language parsers
    for lang, parser_config in config.plugin_system.language_parsers.items():
        parser_config.enabled = lang in languages or lang == "generic"  # Keep generic as fallback
    
    # Update include patterns based on languages
    extensions = set()
    for lang in languages:
        if lang in config.plugin_system.language_parsers:
            extensions.update(config.plugin_system.language_parsers[lang].file_extensions)
    
    if extensions:
        config.include_patterns = extensions
    
    return config
