"""Codex: AI-powered codebase analysis and summarization."""

from .config import CodexConfig
from .summarizer import CodexSummarizer
from ..exceptions import LynxError, ProcessingError

class Codex:
    """Main Codex class for codebase summarization."""
    
    def __init__(self, config: CodexConfig):
        """Initialize Codex with configuration."""
        self.config = config
        self._summarizer = None
    
    @classmethod
    def New(cls, cfg):
        """
        Factory method to create a Codex instance (Go-style constructor).
        
        Args:
            cfg: Configuration dict, file path, or CodexConfig instance
            
        Returns:
            Codex instance
        """
        if isinstance(cfg, str):
            # Assume it's a config file path
            config = CodexConfig.from_file(cfg)
        elif isinstance(cfg, dict):
            config = CodexConfig.from_dict(cfg)
        elif isinstance(cfg, CodexConfig):
            config = cfg
        else:
            raise ValueError("Config must be a dict, file path, or CodexConfig instance")
        
        return cls(config)
    
    @property
    def summarizer(self) -> CodexSummarizer:
        """Lazy initialization of summarizer."""
        if self._summarizer is None:
            self._summarizer = CodexSummarizer(self.config)
        return self._summarizer
    
    def summarize(self):
        """
        Perform codebase summarization.
        
        Returns:
            Summary results dictionary
        """
        return self.summarizer.summarize_codebase()
    
    def get_config(self) -> CodexConfig:
        """Get current configuration."""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """Update configuration parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                raise ValueError(f"Unknown config parameter: {key}")
        
        # Re-validate configuration
        self.config.validate()
        
        # Reset summarizer to pick up new config
        self._summarizer = None

__all__ = ['Codex', 'CodexConfig', 'CodexSummarizer']
