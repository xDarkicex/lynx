"""Enhanced Python language parser with AST and test-aware support."""

import ast
import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class PythonParser(BaseLanguageParser):
    """Advanced Python parser using AST with pattern fallback."""
    
    language_name = "python"
    supported_extensions = [".py", ".pyw"]
    
    def __init__(self):
        # Fallback patterns for when AST parsing fails
        self.patterns = {
            'function': re.compile(
                r'^(\s*)((?:async\s+)?def)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^:]*\)(?:\s*->\s*[^:]+)?\s*:',
                re.MULTILINE
            ),
            'class': re.compile(
                r'^(\s*)(class)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*:',
                re.MULTILINE
            ),
            'import': re.compile(
                r'^(\s*)(from\s+[^\s]+\s+)?import\s+([^#\n]+)',
                re.MULTILINE
            ),
            'decorator': re.compile(
                r'^(\s*)@([a-zA-Z_][a-zA-Z0-9_.]*)',
                re.MULTILINE
            )
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Python code using AST with pattern fallback."""
        try:
            return self._parse_with_ast(content, file_path)
        except SyntaxError:
            # Fallback to pattern-based parsing for invalid syntax
            return self._parse_with_patterns(content, file_path)
        except Exception:
            # Ultimate fallback
            return self._parse_with_patterns(content, file_path)
    
    def _parse_with_ast(self, content: str, file_path: str) -> List[ParsedElement]:
        """Parse using Python's AST module."""
        elements = []
        lines = content.split('\n')
        tree = ast.parse(content)
        
        # Walk the AST and extract elements
        for node in ast.walk(tree):
            element = None
            
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                element = self._create_function_element(node, lines, file_path)
            elif isinstance(node, ast.ClassDef):
                element = self._create_class_element(node, lines, file_path)
            
            if element:
                elements.append(element)
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_function_element(self, node: ast.FunctionDef, lines: List[str], file_path: str) -> ParsedElement:
        """Create ParsedElement from AST function node."""
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', start_line + 10) or start_line + 10
        
        # Extract decorators
        decorators = [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list]
        
        # Determine if it's a test function
        is_test = (
            node.name.startswith('test_') or
            any('test' in dec.lower() for dec in decorators) or
            'test' in file_path.lower()
        )
        
        # Extract function details
        args = [arg.arg for arg in node.args.args] if node.args else []
        returns = ast.unparse(node.returns) if node.returns and hasattr(ast, 'unparse') else None
        
        # Determine visibility (Python convention)
        if node.name.startswith('__') and node.name.endswith('__'):
            visibility = Visibility.PUBLIC  # Magic methods are public
        elif node.name.startswith('_'):
            visibility = Visibility.PRIVATE
        else:
            visibility = Visibility.PUBLIC
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        metadata = {
            'is_async': isinstance(node, ast.AsyncFunctionDef),
            'decorators': decorators,
            'arguments': args,
            'return_type': returns,
            'is_test': is_test,
            'test_framework': self._detect_test_framework(lines, decorators),
            'docstring': ast.get_docstring(node),
            'line_complexity': len([l for l in content_lines.split('\n') if l.strip()])
        }
        
        if is_test:
            metadata.update({
                'test_type': self._detect_test_type(node.name),
                'assertions_count': self._count_assertions(content_lines)
            })
        
        return ParsedElement(
            name=node.name,
            element_type=ElementType.FUNCTION,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def _create_class_element(self, node: ast.ClassDef, lines: List[str], file_path: str) -> ParsedElement:
        """Create ParsedElement from AST class node."""
        start_line = node.lineno - 1
        end_line = getattr(node, 'end_lineno', start_line + 20) or start_line + 20
        
        # Extract base classes
        bases = []
        for base in node.bases:
            if hasattr(base, 'id'):
                bases.append(base.id)
            elif hasattr(base, 'attr'):
                bases.append(base.attr)
        
        # Check if it's a test class
        is_test_class = (
            node.name.startswith('Test') or
            any('test' in base.lower() for base in bases) or
            'test' in file_path.lower()
        )
        
        # Count methods
        methods = [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        test_methods = [m for m in methods if m.name.startswith('test_')] if is_test_class else []
        
        visibility = Visibility.PRIVATE if node.name.startswith('_') else Visibility.PUBLIC
        content_lines = '\n'.join(lines[start_line:end_line])
        
        metadata = {
            'base_classes': bases,
            'decorators': [d.id if hasattr(d, 'id') else str(d) for d in node.decorator_list],
            'methods_count': len(methods),
            'is_test_class': is_test_class,
            'test_methods_count': len(test_methods),
            'docstring': ast.get_docstring(node)
        }
        
        return ParsedElement(
            name=node.name,
            element_type=ElementType.CLASS,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def _parse_with_patterns(self, content: str, file_path: str) -> List[ParsedElement]:
        """Fallback pattern-based parsing."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'import':  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_pattern_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_pattern_element(self, match, pattern_name: str, lines: List[str], content: str) -> ParsedElement:
        """Create element from regex pattern match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        end_line = self._find_block_end(lines, start_line, 'indent')
        
        element_type = ElementType.FUNCTION if pattern_name == 'function' else ElementType.CLASS
        visibility = Visibility.PRIVATE if name.startswith('_') else Visibility.PUBLIC
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        metadata = {
            'pattern_based': True,
            'indent_level': len(indent),
            'is_async': 'async' in groups[1] if len(groups) > 1 else False
        }
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract Python import statements."""
        dependencies = []
        
        # Parse import statements
        for match in self.patterns['import'].finditer(content):
            line_num = content[:match.start()].count('\n')
            from_part = match.group(2)  # "from ... " part
            import_part = match.group(3).strip()  # imported items
            
            if from_part:  # from ... import ...
                module = from_part.replace('from', '').replace('import', '').strip()
                # Handle multiple imports
                for item in import_part.split(','):
                    item = item.strip()
                    if ' as ' in item:
                        name, alias = item.split(' as ', 1)
                        dependencies.append(DependencyInfo(
                            name=name.strip(),
                            import_type='from',
                            source=module,
                            alias=alias.strip(),
                            line_number=line_num
                        ))
                    else:
                        dependencies.append(DependencyInfo(
                            name=item,
                            import_type='from',
                            source=module,
                            line_number=line_num
                        ))
            else:  # import ...
                for item in import_part.split(','):
                    item = item.strip()
                    if ' as ' in item:
                        name, alias = item.split(' as ', 1)
                        dependencies.append(DependencyInfo(
                            name=name.strip(),
                            import_type='import',
                            source=name.strip(),
                            alias=alias.strip(),
                            line_number=line_num
                        ))
                    else:
                        dependencies.append(DependencyInfo(
                            name=item,
                            import_type='import',
                            source=item,
                            line_number=line_num
                        ))
        
        return dependencies
    
    def _detect_test_framework(self, lines: List[str], decorators: List[str]) -> str:
        """Detect the test framework being used."""
        content = '\n'.join(lines)
        
        if 'import pytest' in content or 'from pytest' in content or any('pytest' in d for d in decorators):
            return 'pytest'
        elif 'import unittest' in content or 'from unittest' in content:
            return 'unittest'
        elif 'import nose' in content:
            return 'nose'
        elif 'import doctest' in content:
            return 'doctest'
        return 'unknown'
    
    def _detect_test_type(self, name: str) -> str:
        """Detect type of test based on naming."""
        name_lower = name.lower()
        if 'integration' in name_lower or 'e2e' in name_lower:
            return 'integration'
        elif 'unit' in name_lower:
            return 'unit'
        elif 'performance' in name_lower or 'perf' in name_lower:
            return 'performance'
        return 'unit'  # Default assumption
    
    def _count_assertions(self, content: str) -> int:
        """Count assertion statements in test code."""
        assertion_patterns = [
            r'assert\s+',
            r'self\.assert\w+\(',
            r'self\.assertEqual\(',
            r'self\.assertTrue\(',
            r'self\.assertFalse\(',
        ]
        
        count = 0
        for pattern in assertion_patterns:
            count += len(re.findall(pattern, content))
        
        return count
