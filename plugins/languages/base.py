"""Base classes and interfaces for language parsers."""

import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class ElementType(Enum):
    """Types of code elements that can be parsed."""
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    STRUCT = "struct"
    INTERFACE = "interface"
    TRAIT = "trait"
    ENUM = "enum"
    CONSTANT = "constant"
    VARIABLE = "variable"
    IMPORT = "import"
    MODULE = "module"
    NAMESPACE = "namespace"

class Visibility(Enum):
    """Visibility/access levels."""
    PUBLIC = "public"
    PRIVATE = "private"
    PROTECTED = "protected"
    INTERNAL = "internal"

@dataclass
class ParsedElement:
    """Represents a parsed code element with comprehensive metadata."""
    name: str
    element_type: ElementType
    start_line: int
    end_line: int
    visibility: Visibility = Visibility.PRIVATE
    language: str = ""
    content: str = ""
    
    # Rich metadata
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1

@dataclass
class DependencyInfo:
    """Information about code dependencies."""
    name: str
    import_type: str  # 'import', 'from', 'use', 'require', etc.
    source: str       # Module/package source
    alias: Optional[str] = None
    line_number: int = 0

class BaseLanguageParser(ABC):
    """Abstract base class for all language parsers."""
    
    @property
    @abstractmethod
    def language_name(self) -> str:
        """Name of the language this parser handles."""
        pass
    
    @property
    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """File extensions this parser supports."""
        pass
    
    @abstractmethod
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """
        Parse code elements from content.
        
        Args:
            content: Source code content
            file_path: Optional file path for context
            
        Returns:
            List of parsed elements with metadata
        """
        pass
    
    @abstractmethod
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract import/dependency information."""
        pass
    
    def get_complexity_metrics(self, content: str) -> Dict[str, Any]:
        """
        Get basic complexity metrics (can be overridden).
        
        Returns:
            Dictionary with complexity indicators
        """
        lines = content.split('\n')
        return {
            'total_lines': len(lines),
            'non_empty_lines': len([l for l in lines if l.strip()]),
            'estimated_complexity': 'medium' if len(lines) > 50 else 'low'
        }
    
    def _find_block_end(self, lines: List[str], start_line: int, 
                       language_type: str = 'brace') -> int:
        """
        Find the end of a code block based on language syntax.
        
        Args:
            lines: All lines of the file
            start_line: Starting line index
            language_type: 'brace', 'indent', or 'keyword'
        """
        if start_line >= len(lines):
            return start_line
            
        if language_type == 'indent':  # Python-style
            base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            
            for i in range(start_line + 1, len(lines)):
                line = lines[i]
                if line.strip() == '':
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent and line.strip():
                    return i
            return len(lines)
            
        elif language_type == 'brace':  # C-style braces
            brace_count = 0
            for i in range(start_line, len(lines)):
                line = lines[i]
                brace_count += line.count('{') - line.count('}')
                if i > start_line and brace_count <= 0:
                    return i + 1
            return len(lines)
            
        else:  # Keyword-based (like 'end' in Ruby)
            return start_line + 10  # Simple fallback
    
    def _extract_visibility(self, match_text: str) -> Visibility:
        """Extract visibility from matched text."""
        text_lower = match_text.lower()
        if 'public' in text_lower or 'pub ' in text_lower:
            return Visibility.PUBLIC
        elif 'private' in text_lower:
            return Visibility.PRIVATE
        elif 'protected' in text_lower:
            return Visibility.PROTECTED
        return Visibility.PRIVATE
