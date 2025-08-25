"""Configuration management for Lynx Codex."""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, Union, Set, List
from dataclasses import dataclass, field

from ..exceptions import ConfigError

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
class CodexConfig:
    """Configuration for Codex summarization."""
    
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
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._setup_models()
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
                result[key] = [
                    {
                        'provider': m.provider,
                        'model': m.model,
                        'api_key': '***' if m.api_key else '',
                        'temperature': m.temperature,
                        'max_tokens': m.max_tokens
                    } for m in value
                ]
            else:
                result[key] = value
        return result
    
    def save_to_file(self, config_path: str) -> None:
        """Save configuration to JSON file."""
        config_dict = self.to_dict()
        # Don't save sensitive data in legacy fields
        if 'api_key' in config_dict:
            config_dict['api_key'] = '***'
            
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)
    
    def get_primary_model(self) -> ModelConfig:
        """Get the primary (first) model configuration."""
        if not self.models:
            raise ConfigError("No models configured")
        return self.models[0]
    
    def get_fallback_models(self) -> List[ModelConfig]:
        """Get fallback model configurations (all except the first)."""
        return self.models[1:] if len(self.models) > 1 else []
