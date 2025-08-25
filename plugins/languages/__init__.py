"""Language parser registry and management."""

import logging
from typing import Dict, Type, Optional, List

from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

logger = logging.getLogger(__name__)

# Import all parser classes with error handling
# Core parsers
try:
    from .python_parser import PythonParser
except ImportError:
    logger.warning("PythonParser not available")
    PythonParser = None

try:
    from .javascript_parser import JavaScriptParser
except ImportError:
    logger.warning("JavaScriptParser not available")
    JavaScriptParser = None

try:
    from .typescript_parser import TypeScriptParser
except ImportError:
    logger.warning("TypeScriptParser not available")
    TypeScriptParser = None

try:
    from .rust_parser import RustParser
except ImportError:
    logger.warning("RustParser not available")
    RustParser = None

try:
    from .go_parser import GoParser
except ImportError:
    logger.warning("GoParser not available")
    GoParser = None

try:
    from .java_parser import JavaParser
except ImportError:
    logger.warning("JavaParser not available")
    JavaParser = None

try:
    from .kotlin_parser import KotlinParser
except ImportError:
    logger.warning("KotlinParser not available")
    KotlinParser = None

try:
    from .ruby_parser import RubyParser
except ImportError:
    logger.warning("RubyParser not available")
    RubyParser = None

# C/C++ parsers
try:
    from .c_parser import CParser
except ImportError:
    logger.warning("CParser not available")
    CParser = None

try:
    from .cpp_parser import CppParser
except ImportError:
    logger.warning("CppParser not available")
    CppParser = None

# .NET parsers
try:
    from .csharp_parser import CSharpParser
except ImportError:
    logger.warning("CSharpParser not available")
    CSharpParser = None

# Web development parsers
try:
    from .html_parser import HtmlParser
except ImportError:
    logger.warning("HtmlParser not available")
    HtmlParser = None

try:
    from .css_parser import CssParser
except ImportError:
    logger.warning("CssParser not available")
    CssParser = None

try:
    from .react_parser import ReactParser
except ImportError:
    logger.warning("ReactParser not available")
    ReactParser = None

try:
    from .nextjs_parser import NextjsParser
except ImportError:
    logger.warning("NextjsParser not available")
    NextjsParser = None

# Server-side parsers
try:
    from .php_parser import PhpParser
except ImportError:
    logger.warning("PhpParser not available")
    PhpParser = None

# Database and query parsers
try:
    from .sql_parser import SqlParser
except ImportError:
    logger.warning("SqlParser not available")
    SqlParser = None

# Mobile development parsers
try:
    from .swift_parser import SwiftParser
except ImportError:
    logger.warning("SwiftParser not available")
    SwiftParser = None

try:
    from .flutter_parser import FlutterParser
except ImportError:
    logger.warning("FlutterParser not available")
    FlutterParser = None

# Shell scripting parser
try:
    from .bash_parser import BashParser
except ImportError:
    logger.warning("BashParser not available")
    BashParser = None

# Generic fallback parser
try:
    from .generic_parser import GenericParser
except ImportError:
    logger.warning("GenericParser not available")
    GenericParser = None


class LanguageParserRegistry:
    """Registry for language parsers with comprehensive language support."""
    
    def __init__(self):
        self._parsers: Dict[str, Type[BaseLanguageParser]] = {}
        self._instances: Dict[str, BaseLanguageParser] = {}
        self._language_to_parser: Dict[str, Type[BaseLanguageParser]] = {}
        self._extension_to_parser: Dict[str, Type[BaseLanguageParser]] = {}
        self._register_built_in_parsers()
    
    def _register_built_in_parsers(self):
        """Register all available built-in language parsers."""
        # Define all parser classes that should be registered
        parser_classes = [
            # Core language parsers
            PythonParser,
            JavaScriptParser,
            TypeScriptParser,
            JavaParser,
            KotlinParser,
            RubyParser,
            
            # Systems programming
            RustParser,
            GoParser,
            CParser,
            CppParser,
            
            # .NET ecosystem
            CSharpParser,
            
            # Web development
            HtmlParser,
            CssParser,
            ReactParser,
            NextjsParser,
            
            # Server-side
            PhpParser,
            
            # Database
            SqlParser,
            
            # Mobile development
            SwiftParser,
            FlutterParser,
            
            # Shell scripting
            BashParser,
            
            # Generic fallback (should be last)
            GenericParser,
        ]
        
        # Register each available parser
        registered_count = 0
        for parser_class in parser_classes:
            if parser_class is not None:
                try:
                    self.register_parser(parser_class)
                    registered_count += 1
                except Exception as e:
                    logger.error(f"Failed to register parser {parser_class.__name__}: {e}")
        
        logger.info(f"Registered {registered_count} language parsers")
    
    def register_parser(self, parser_class: Type[BaseLanguageParser]):
        """Register a language parser class."""
        if parser_class is None:
            return
            
        try:
            # Create temporary instance to get metadata
            temp_instance = parser_class()
            language_name = temp_instance.language_name.lower()
            
            # Register by language name
            self._language_to_parser[language_name] = parser_class
            self._parsers[language_name] = parser_class
            
            # Register by file extensions
            for ext in temp_instance.supported_extensions:
                ext_key = ext.lstrip('.').lower()
                self._extension_to_parser[ext_key] = parser_class
                self._parsers[ext_key] = parser_class
                
            logger.debug(f"Registered {parser_class.__name__} for language '{language_name}' "
                        f"and extensions {temp_instance.supported_extensions}")
                        
        except Exception as e:
            logger.error(f"Failed to register parser {parser_class.__name__}: {e}")
            raise
    
    def get_parser(self, language_or_extension: str) -> Optional[BaseLanguageParser]:
        """
        Get parser instance for a language or file extension.
        
        Args:
            language_or_extension: Language name (e.g., 'rust') or extension (e.g., 'rs', '.rs')
            
        Returns:
            Parser instance or None if not found
        """
        # Normalize input
        key = language_or_extension.lower().lstrip('.')
        
        if key not in self._parsers:
            # Try to find a generic parser as fallback
            if GenericParser is not None and 'generic' in self._parsers:
                key = 'generic'
            else:
                return None
        
        # Return cached instance or create new one
        cache_key = f"{key}_{self._parsers[key].__name__}"
        if cache_key not in self._instances:
            parser_class = self._parsers[key]
            try:
                self._instances[cache_key] = parser_class()
            except Exception as e:
                logger.error(f"Failed to instantiate parser {parser_class.__name__}: {e}")
                return None
        
        return self._instances[cache_key]
    
    def get_parser_by_language(self, language: str) -> Optional[BaseLanguageParser]:
        """Get parser specifically by language name."""
        language_key = language.lower()
        if language_key in self._language_to_parser:
            parser_class = self._language_to_parser[language_key]
            cache_key = f"lang_{language_key}_{parser_class.__name__}"
            
            if cache_key not in self._instances:
                try:
                    self._instances[cache_key] = parser_class()
                except Exception as e:
                    logger.error(f"Failed to instantiate parser for language {language}: {e}")
                    return None
            
            return self._instances[cache_key]
        return None
    
    def get_parser_by_extension(self, extension: str) -> Optional[BaseLanguageParser]:
        """Get parser specifically by file extension."""
        ext_key = extension.lstrip('.').lower()
        if ext_key in self._extension_to_parser:
            parser_class = self._extension_to_parser[ext_key]
            cache_key = f"ext_{ext_key}_{parser_class.__name__}"
            
            if cache_key not in self._instances:
                try:
                    self._instances[cache_key] = parser_class()
                except Exception as e:
                    logger.error(f"Failed to instantiate parser for extension {extension}: {e}")
                    return None
            
            return self._instances[cache_key]
        return None
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language names."""
        return sorted(list(self._language_to_parser.keys()))
    
    def get_supported_extensions(self) -> List[str]:
        """Get list of supported file extensions."""
        return sorted([f".{ext}" for ext in self._extension_to_parser.keys()])
    
    def get_parser_info(self) -> Dict[str, Dict[str, List[str]]]:
        """Get comprehensive information about registered parsers."""
        info = {}
        
        for language, parser_class in self._language_to_parser.items():
            try:
                temp_instance = parser_class()
                info[language] = {
                    'parser_class': parser_class.__name__,
                    'extensions': temp_instance.supported_extensions,
                    'language_name': temp_instance.language_name
                }
            except Exception as e:
                logger.warning(f"Could not get info for parser {parser_class.__name__}: {e}")
                info[language] = {
                    'parser_class': parser_class.__name__,
                    'extensions': [],
                    'language_name': language,
                    'error': str(e)
                }
        
        return info
    
    def is_supported(self, language_or_extension: str) -> bool:
        """Check if a language or extension is supported."""
        key = language_or_extension.lower().lstrip('.')
        return key in self._parsers
    
    def clear_cache(self):
        """Clear the parser instance cache."""
        self._instances.clear()
        logger.debug("Cleared parser instance cache")


# Global registry instance
language_registry = LanguageParserRegistry()

# Convenience functions
def get_parser_for_language(language: str) -> Optional[BaseLanguageParser]:
    """Get parser for a specific language."""
    return language_registry.get_parser_by_language(language)

def get_parser_for_file(file_extension: str) -> Optional[BaseLanguageParser]:
    """Get parser for a file extension."""
    return language_registry.get_parser_by_extension(file_extension)

def get_parser(language_or_extension: str) -> Optional[BaseLanguageParser]:
    """Get parser for a language or file extension (generic method)."""
    return language_registry.get_parser(language_or_extension)

def register_language_parser(parser_class: Type[BaseLanguageParser]):
    """Register a new language parser."""
    language_registry.register_parser(parser_class)

def get_supported_languages() -> List[str]:
    """Get list of all supported languages."""
    return language_registry.get_supported_languages()

def get_supported_extensions() -> List[str]:
    """Get list of all supported file extensions."""
    return language_registry.get_supported_extensions()

def is_language_supported(language: str) -> bool:
    """Check if a language is supported."""
    return language_registry.is_supported(language)

def is_extension_supported(extension: str) -> bool:
    """Check if a file extension is supported."""
    return language_registry.is_supported(extension)

def get_parser_info() -> Dict[str, Dict[str, List[str]]]:
    """Get information about all registered parsers."""
    return language_registry.get_parser_info()

def clear_parser_cache():
    """Clear the parser instance cache."""
    language_registry.clear_cache()

# Export all the classes and functions
__all__ = [
    # Base classes and enums
    'BaseLanguageParser', 
    'ParsedElement', 
    'DependencyInfo', 
    'ElementType', 
    'Visibility',
    
    # Registry classes
    'LanguageParserRegistry', 
    'language_registry',
    
    # Convenience functions
    'get_parser_for_language', 
    'get_parser_for_file', 
    'get_parser',
    'register_language_parser',
    'get_supported_languages',
    'get_supported_extensions',
    'is_language_supported',
    'is_extension_supported',
    'get_parser_info',
    'clear_parser_cache',
    
    # Parser classes (those that are available)
    'PythonParser',
    'JavaScriptParser', 
    'TypeScriptParser',
    'RustParser',
    'GoParser',
    'JavaParser',
    'KotlinParser',
    'RubyParser',
    'CParser',
    'CppParser',
    'CSharpParser',  # Added missing C# parser
    'HtmlParser',
    'CssParser',
    'ReactParser',
    'NextjsParser',
    'PhpParser',     # Added missing PHP parser
    'SqlParser',
    'SwiftParser',
    'FlutterParser',
    'BashParser',
    'GenericParser',
]

# Module metadata
__version__ = "1.0.0"
__author__ = "Gentry Rolofson"

# Log initialization
logger.info(f"Language parser registry initialized with {len(language_registry.get_supported_languages())} languages")
