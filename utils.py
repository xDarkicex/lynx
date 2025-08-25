"""Utility functions for file operations and text processing."""

import os
import hashlib
import logging
import functools
import json
import copy
from pathlib import Path
from typing import List, Dict, Set, Optional, Union
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)

@dataclass
class FileInfo:
    """Metadata for processed files."""
    path: Path
    relative_path: str
    size: int
    extension: str
    language: str
    encoding: str = 'utf-8'
    hash: str = ''

# Model to tokenizer mapping
MODEL_TOKENIZER_MAP = {
    # OpenAI models
    'gpt-4': 'cl100k_base',
    'gpt-4-turbo': 'cl100k_base',
    'gpt-4o': 'cl100k_base',
    'gpt-3.5-turbo': 'cl100k_base',
    'gpt-3.5-turbo-16k': 'cl100k_base',
    
    # Perplexity models (use OpenAI tokenizers)
    'sonar-large-chat': 'cl100k_base',
    'sonar-medium-chat': 'cl100k_base',
    'sonar-small-chat': 'cl100k_base',
    'sonar-large-online': 'cl100k_base',
    'sonar-medium-online': 'cl100k_base',
    
    # Anthropic models (use cl100k_base as approximation)
    'claude-3-opus-20240229': 'cl100k_base',
    'claude-3-sonnet-20240229': 'cl100k_base',
    'claude-3-haiku-20240307': 'cl100k_base',
    'claude-2.1': 'cl100k_base',
    'claude-2.0': 'cl100k_base',
    'claude-instant-1.2': 'cl100k_base',
}

# Cache encodings so we only pay the setup cost once per model
@functools.lru_cache(maxsize=16)
def _get_encoder(model: str):
    """Get tiktoken encoder for a specific model with caching."""
    # First try to get encoding by model name
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        pass
    
    # Fall back to our model mapping
    encoding_name = MODEL_TOKENIZER_MAP.get(model, 'cl100k_base')
    try:
        return tiktoken.get_encoding(encoding_name)
    except Exception:
        # Ultimate fallback
        logger.warning(f"Unknown model '{model}', using cl100k_base encoding")
        return tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str, model: str = "gpt-4") -> int:
    """
    Count exact tokens using tiktoken for the specified model.
    
    Args:
        text: Text to count tokens for
        model: Model name to use for tokenization (defaults to gpt-4)
        
    Returns:
        Exact token count as an integer
    """
    if not text:
        return 0
    
    encoder = _get_encoder(model)
    return len(encoder.encode(text))

def estimate_tokens(text: str) -> int:
    """
    Legacy function for backwards compatibility.
    Now uses accurate tiktoken counting with gpt-4 encoding.
    """
    return count_tokens(text, "gpt-4")

def get_model_context_limit(model: str) -> int:
    """Get the context limit for a specific model."""
    context_limits = {
        # OpenAI models
        'gpt-4': 8192,
        'gpt-4-turbo': 128000,
        'gpt-4o': 128000,
        'gpt-3.5-turbo': 4096,
        'gpt-3.5-turbo-16k': 16384,
        
        # Perplexity models
        'sonar-large-chat': 16384,
        'sonar-medium-chat': 16384,
        'sonar-small-chat': 16384,
        'sonar-large-online': 16384,
        'sonar-medium-online': 16384,
        
        # Anthropic models
        'claude-3-opus-20240229': 200000,
        'claude-3-sonnet-20240229': 200000,
        'claude-3-haiku-20240307': 200000,
        'claude-2.1': 200000,
        'claude-2.0': 100000,
        'claude-instant-1.2': 100000,
    }
    return context_limits.get(model, 4096)  # Default to safe 4k limit

def validate_config(config: Dict) -> List[str]:
    """
    Validate configuration and return list of issues found.
    
    Returns:
        List of validation error messages (empty if valid)
    """
    issues = []
    
    # Check for required fields
    if "models" not in config and "api_key" not in config:
        issues.append("Either 'models' (multi-model) or 'api_key' (legacy) required")
    
    # Validate models array
    if "models" in config:
        if not isinstance(config["models"], list) or not config["models"]:
            issues.append("'models' must be a non-empty list")
        else:
            for i, model in enumerate(config["models"]):
                if not isinstance(model, dict):
                    issues.append(f"Model {i} must be a dictionary")
                    continue
                
                required_fields = ["provider", "model", "api_key"]
                for field in required_fields:
                    if field not in model:
                        issues.append(f"Model {i} missing required field: {field}")
                
                # Validate provider
                valid_providers = {"perplexity", "openai", "anthropic"}
                if model.get("provider") not in valid_providers:
                    issues.append(f"Model {i} has invalid provider. Must be one of: {valid_providers}")
    
    # Validate numeric fields
    numeric_fields = {
        "chunk_size": (100, 50000),
        "max_workers": (1, 32),
        "max_file_size": (1024, 100 * 1024 * 1024),  # 1KB to 100MB
        "timeout_seconds": (5, 300),
        "retry_attempts": (0, 10)
    }
    
    for field, (min_val, max_val) in numeric_fields.items():
        if field in config:
            val = config[field]
            if not isinstance(val, int) or val < min_val or val > max_val:
                issues.append(f"'{field}' must be integer between {min_val} and {max_val}")
    
    return issues

def load_config_file(config_path: str) -> Dict:
    """
    Load and validate configuration from JSON file.
    
    Args:
        config_path: Path to JSON config file
        
    Returns:
        Loaded configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in config file: {e}")
    
    # Validate the config
    issues = validate_config(config)
    if issues:
        raise ValueError(f"Invalid configuration:\n" + "\n".join(f"- {issue}" for issue in issues))
    
    logger.info(f"Loaded configuration from: {config_path}")
    return config

def merge_configs(base_config: Dict, override_config: Dict) -> Dict:
    """
    Merge two configurations, with override_config taking precedence.
    
    Args:
        base_config: Base configuration (e.g., from template)
        override_config: Override configuration (user customizations)
        
    Returns:
        Merged configuration
    """
    merged = copy.deepcopy(base_config)
    
    for key, value in override_config.items():
        if key == "models" and key in merged and isinstance(value, list):
            # For models, replace entirely rather than merge
            merged[key] = value
        elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            # Recursively merge dictionaries
            merged[key] = merge_configs(merged[key], value)
        else:
            # Direct override
            merged[key] = value
    
    return merged

def create_default_config_template(
    config_type: str = "multi-model",
    include_all_providers: bool = True,
    save_to_file: Optional[str] = None
) -> Dict:
    """
    Create a default configuration template for Lynx.
    
    Args:
        config_type: Type of config - "multi-model", "single-model", or "minimal"
        include_all_providers: Whether to include all supported AI providers
        save_to_file: Optional path to save the config to a JSON file
        
    Returns:
        Dictionary containing the default configuration
    """
    
    # Base configuration shared by all types
    base_config = {
        "chunk_size": 2000,
        "max_workers": 8,
        "include_patterns": ["*.py", "*.rs", "*.go", "*.js", "*.ts", "*.java", "*.cpp", "*.c", "*.h"],
        "exclude_patterns": [
            "*/__pycache__/*", 
            "*/node_modules/*", 
            "*/.git/*", 
            "*/target/*", 
            "*/build/*", 
            "*/dist/*", 
            "*test*",
            "*.pyc",
            "*.log"
        ],
        "output_format": "markdown",
        "semantic_chunking": True,
        "include_metrics": True,
        "fallback_enabled": True,
        "max_file_size": 10485760,  # 10MB
        "timeout_seconds": 30,
        "retry_attempts": 3
    }
    
    if config_type == "multi-model":
        # Multi-model configuration with fallback support
        models = []
        
        # Add Perplexity (often most cost-effective)
        models.append({
            "provider": "perplexity",
            "model": "sonar-large-chat",
            "api_key": "pplx-your-api-key-here",
            "temperature": 0.0,
            "max_tokens": 16000
        })
        
        if include_all_providers:
            # Add OpenAI as fallback
            models.append({
                "provider": "openai", 
                "model": "gpt-4o",
                "api_key": "sk-your-openai-key-here",
                "temperature": 0.0,
                "max_tokens": 8000
            })
            
            # Add Anthropic as second fallback
            models.append({
                "provider": "anthropic",
                "model": "claude-3-sonnet-20240229", 
                "api_key": "sk-ant-your-anthropic-key-here",
                "temperature": 0.0,
                "max_tokens": 100000
            })
        
        config = {**base_config, "models": models}
        
    elif config_type == "single-model":
        # Legacy single model configuration (backwards compatible)
        config = {
            **base_config,
            "api_key": "pplx-your-api-key-here",
            "model": "sonar-large-chat", 
            "temperature": 0.0,
            "max_tokens_per_request": 16000
        }
        
    elif config_type == "minimal":
        # Minimal configuration for quick setup
        config = {
            "models": [{
                "provider": "perplexity",
                "model": "sonar-large-chat",
                "api_key": "pplx-your-api-key-here",
                "temperature": 0.0,
                "max_tokens": 16000
            }],
            "chunk_size": 2000,
            "include_patterns": ["*.py", "*.js", "*.ts", "*.go", "*.rs"],
            "output_format": "markdown",
            "fallback_enabled": False
        }
    
    else:
        raise ValueError(f"Unknown config_type: {config_type}. Must be 'multi-model', 'single-model', or 'minimal'")
    
    # Add helpful comments as a special key
    config["_comments"] = {
        "setup_instructions": [
            "1. Replace API keys with your actual keys from the respective providers",
            "2. Remove any providers you don't want to use",
            "3. Set your codebase_path when initializing Lynx",
            "4. Adjust include_patterns and exclude_patterns for your project"
        ],
        "environment_variables": [
            "You can also set API keys via environment variables:",
            "- PPLX_API_KEY or PERPLEXITY_API_KEY for Perplexity",
            "- OPENAI_API_KEY for OpenAI", 
            "- ANTHROPIC_API_KEY for Anthropic"
        ],
        "provider_notes": {
            "perplexity": "Cost-effective, good for most code analysis tasks",
            "openai": "High quality, good for complex analysis, more expensive", 
            "anthropic": "Excellent for large codebases, very large context window"
        }
    }
    
    # Save to file if requested
    if save_to_file:
        # Create a clean version for saving (without comments)
        save_config = {k: v for k, v in config.items() if k != "_comments"}
        
        try:
            with open(save_to_file, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, indent=2)
            logger.info(f"Configuration template saved to: {save_to_file}")
        except Exception as e:
            logger.error(f"Failed to save config template: {e}")
    
    return config

def create_config_from_environment() -> Dict:
    """
    Create a configuration automatically from environment variables.
    
    Returns:
        Dictionary containing configuration based on available API keys
    """
    models = []
    
    # Check for Perplexity
    pplx_key = os.getenv('PPLX_API_KEY') or os.getenv('PERPLEXITY_API_KEY')
    if pplx_key:
        models.append({
            "provider": "perplexity",
            "model": "sonar-large-chat",
            "api_key": pplx_key,
            "temperature": 0.0,
            "max_tokens": 16000
        })
    
    # Check for OpenAI
    openai_key = os.getenv('OPENAI_API_KEY')
    if openai_key:
        models.append({
            "provider": "openai",
            "model": "gpt-4o",
            "api_key": openai_key,
            "temperature": 0.0,
            "max_tokens": 8000
        })
    
    # Check for Anthropic
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    if anthropic_key:
        models.append({
            "provider": "anthropic", 
            "model": "claude-3-sonnet-20240229",
            "api_key": anthropic_key,
            "temperature": 0.0,
            "max_tokens": 100000
        })
    
    if not models:
        raise ValueError(
            "No API keys found in environment variables. Please set one of: "
            "PPLX_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY"
        )
    
    config = create_default_config_template("minimal")
    config["models"] = models
    
    logger.info(f"Auto-configured with {len(models)} provider(s) from environment")
    return config

def get_recommended_config_for_codebase(codebase_path: str) -> Dict:
    """
    Analyze a codebase and recommend optimal configuration settings.
    
    Args:
        codebase_path: Path to the codebase to analyze
        
    Returns:
        Dictionary with recommended configuration
    """
    from pathlib import Path
    
    if not Path(codebase_path).exists():
        raise FileNotFoundError(f"Codebase path not found: {codebase_path}")
    
    # Quick scan to determine codebase characteristics
    languages = set()
    total_files = 0
    total_size = 0
    
    for file_path in Path(codebase_path).rglob('*'):
        if file_path.is_file() and is_text_file(file_path):
            total_files += 1
            try:
                size = file_path.stat().st_size
                total_size += size
                lang = detect_language(file_path)
                if lang != 'unknown':
                    languages.add(lang)
            except OSError:
                continue
    
    # Create base config
    config = create_default_config_template("multi-model", include_all_providers=False)
    config["codebase_path"] = codebase_path
    
    # Adjust based on codebase size
    if total_files > 1000 or total_size > 100 * 1024 * 1024:  # Large codebase
        config["max_workers"] = 12
        config["chunk_size"] = 3000
        # Recommend Anthropic for large codebases due to context window
        config["models"].append({
            "provider": "anthropic",
            "model": "claude-3-sonnet-20240229",
            "api_key": "sk-ant-your-anthropic-key-here",
            "temperature": 0.0,
            "max_tokens": 100000
        })
    elif total_files < 50:  # Small codebase
        config["max_workers"] = 4
        config["chunk_size"] = 1500
        config["fallback_enabled"] = False  # Simpler setup for small projects
    
    # Adjust include patterns based on detected languages
    if languages:
        patterns = []
        lang_patterns = {
            'python': '*.py',
            'javascript': '*.js',
            'typescript': '*.ts',
            'rust': '*.rs',
            'golang': '*.go',
            'java': '*.java',
            'cpp': ['*.cpp', '*.hpp', '*.cc'],
            'c': ['*.c', '*.h'],
            'csharp': '*.cs',
            'php': '*.php',
            'ruby': '*.rb',
            'markdown': '*.md'
        }
        
        for lang in languages:
            if lang in lang_patterns:
                pattern = lang_patterns[lang]
                if isinstance(pattern, list):
                    patterns.extend(pattern)
                else:
                    patterns.append(pattern)
        
        if patterns:
            config["include_patterns"] = patterns
    
    # Add metadata about the analysis
    config["_analysis"] = {
        "total_files": total_files,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "detected_languages": list(languages),
        "recommendations": []
    }
    
    # Add specific recommendations
    recommendations = config["_analysis"]["recommendations"]
    
    if total_files > 500:
        recommendations.append("Large codebase detected - consider using parallel processing")
    
    if 'python' in languages and 'javascript' in languages:
        recommendations.append("Multi-language project - semantic chunking will help maintain context")
        
    if total_size > 50 * 1024 * 1024:
        recommendations.append("Large codebase - Anthropic Claude recommended for better context handling")
    
    return config

# Language detection mappings  
LANGUAGE_MAP = {
    '.py': 'python',
    '.rs': 'rust', 
    '.go': 'golang',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.java': 'java',
    '.cpp': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.php': 'php',
    '.rb': 'ruby',
    '.sh': 'bash',
    '.sql': 'sql',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.json': 'json',
    '.xml': 'xml',
    '.html': 'html',
    '.css': 'css',
    '.md': 'markdown',
    '.txt': 'text'
}

# Binary file extensions to skip
BINARY_EXTENSIONS = {
    '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
    '.mp3', '.mp4', '.avi', '.mov', '.wav', '.pdf', '.zip',
    '.tar', '.gz', '.rar', '.7z', '.pkg', '.deb', '.rpm'
}

def detect_language(file_path: Path) -> str:
    """Detect programming language from file extension."""
    ext = file_path.suffix.lower()
    return LANGUAGE_MAP.get(ext, 'unknown')

def is_text_file(file_path: Path) -> bool:
    """Check if file is likely a text file based on extension and content."""
    ext = file_path.suffix.lower()
    
    # Skip known binary extensions
    if ext in BINARY_EXTENSIONS:
        return False
    
    # Known text extensions
    if ext in LANGUAGE_MAP:
        return True
    
    # For unknown extensions, try to read first few bytes
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(512)
            # Check for null bytes (common in binaries)
            return b'\x00' not in chunk
    except (IOError, OSError):
        return False

def scan_directory(root_path: str, 
                  include_patterns: Optional[Set[str]] = None,
                  exclude_patterns: Optional[Set[str]] = None,
                  max_file_size: int = 10 * 1024 * 1024) -> List[FileInfo]:
    """
    Recursively scan directory for text files.
    
    Args:
        root_path: Root directory to scan
        include_patterns: File patterns to include (e.g., {'*.py', '*.rs'})
        exclude_patterns: Patterns to exclude (e.g., {'*test*', '*.log'})
        max_file_size: Maximum file size in bytes
    
    Returns:
        List of FileInfo objects
    """
    root = Path(root_path)
    if not root.exists():
        raise FileNotFoundError(f"Directory not found: {root_path}")
    
    files = []
    exclude_patterns = exclude_patterns or {
        '*/__pycache__/*', '*/node_modules/*', '*/.git/*', 
        '*/.vscode/*', '*/target/*', '*/build/*', '*/dist/*'
    }
    
    for file_path in root.rglob('*'):
        if not file_path.is_file():
            continue
            
        # Check exclusion patterns
        rel_path = file_path.relative_to(root)
        if any(rel_path.match(pattern) for pattern in exclude_patterns):
            continue
            
        # Check file size
        try:
            size = file_path.stat().st_size
            if size > max_file_size:
                logger.warning(f"Skipping large file: {rel_path} ({size} bytes)")
                continue
        except OSError:
            continue
            
        # Check if it's a text file
        if not is_text_file(file_path):
            continue
            
        # Include patterns filter
        if include_patterns and not any(rel_path.match(pattern) for pattern in include_patterns):
            continue
            
        # Create file info
        language = detect_language(file_path)
        file_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:8]
        
        files.append(FileInfo(
            path=file_path,
            relative_path=str(rel_path),
            size=size,
            extension=file_path.suffix.lower(),
            language=language,
            hash=file_hash
        ))
    
    logger.info(f"Found {len(files)} text files in {root_path}")
    return files

def truncate_text(text: str, max_tokens: int, model: str = "gpt-4") -> str:
    """
    Safely truncate text to exact token limit using tiktoken.
    
    Args:
        text: Text to truncate
        max_tokens: Maximum number of tokens allowed
        model: Model to use for tokenization
        
    Returns:
        Truncated text that fits within the token limit
    """
    if count_tokens(text, model) <= max_tokens:
        return text
    
    encoder = _get_encoder(model)
    tokens = encoder.encode(text)
    
    if len(tokens) <= max_tokens:
        return text
    
    # Truncate tokens and decode back to text
    truncated_tokens = tokens[:max_tokens - 10]  # Leave room for truncation message
    truncated_text = encoder.decode(truncated_tokens)
    
    return truncated_text + "\n... [truncated]"
