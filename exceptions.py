"""Custom exceptions for Lynx toolkit."""

class LynxError(Exception):
    """Base exception for all Lynx-related errors."""
    pass

class ConfigError(LynxError):
    """Raised for configuration-related errors."""
    pass

class ProcessingError(LynxError):
    """Raised during file processing or AI interaction errors."""
    pass

class ChunkingError(LynxError):
    """Raised during intelligent chunking operations."""
    pass

class AIInterfaceError(LynxError):
    """Raised for AI service communication errors."""
    pass
