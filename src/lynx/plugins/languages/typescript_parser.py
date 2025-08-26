"""Comprehensive TypeScript language parser extending JavaScript support."""

import re
from typing import List, Dict, Any
from .javascript_parser import JavaScriptParser
from .base import ParsedElement, DependencyInfo, ElementType, Visibility

class TypeScriptParser(JavaScriptParser):
    """Advanced TypeScript parser extending JavaScript parser."""
    
    language_name = "typescript"
    supported_extensions = [".ts", ".tsx", ".d.ts"]
    
    def __init__(self):
        super().__init__()
        
        # Extend patterns with TypeScript-specific ones
        self.patterns.update({
            # Interfaces
            'interface': re.compile(
                r'^(\s*)((?:export\s+)?interface)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]*>)?\s*(?:extends\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Type aliases
            'type_alias': re.compile(
                r'^(\s*)((?:export\s+)?type)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]*>)?\s*=',
                re.MULTILINE
            ),
            # Enums
            'enum': re.compile(
                r'^(\s*)((?:export\s+)?(?:const\s+)?enum)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\{',
                re.MULTILINE
            ),
            # Namespaces/Modules
            'namespace': re.compile(
                r'^(\s*)((?:export\s+)?(?:namespace|module))\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_.$]*)\s*\{',
                re.MULTILINE
            ),
            # Abstract classes
            'abstract_class': re.compile(
                r'^(\s*)((?:export\s+)?abstract\s+class)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]*>)?\s*(?:extends\s+[a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\{',
                re.MULTILINE
            ),
            # Typed functions (enhanced)
            'typed_function': re.compile(
                r'^(\s*)((?:export\s+)?(?:async\s+)?function)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:<[^>]*>)?\s*\([^)]*\)\s*:\s*[^{]+\s*\{',
                re.MULTILINE
            ),
            # Decorators
            'decorator': re.compile(
                r'^(\s*)(@[a-zA-Z_$][a-zA-Z0-9_$]*(?:\.[a-zA-Z_$][a-zA-Z0-9_$]*)*)',
                re.MULTILINE
            ),
        })
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse TypeScript code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'require']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_ts_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_ts_element(self, match, pattern_name: str,
                          lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from TypeScript match."""
        groups = match.groups()
        
        # Handle TypeScript-specific patterns
        if pattern_name in ['interface', 'type_alias', 'enum', 'namespace', 'abstract_class']:
            return self._create_ts_specific_element(match, pattern_name, lines, content)
        elif pattern_name == 'typed_function':
            return self._create_typed_function_element(match, lines, content)
        else:
            # Use parent JavaScript logic
            return super()._create_js_element(match, pattern_name, lines, content)
    
    def _create_ts_specific_element(self, match, pattern_name: str,
                                   lines: List[str], content: str) -> ParsedElement:
        """Create TypeScript-specific elements."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Map TypeScript constructs to element types
        type_mapping = {
            'interface': ElementType.INTERFACE,
            'type_alias': ElementType.CLASS,  # Treat as class-like
            'enum': ElementType.ENUM,
            'namespace': ElementType.NAMESPACE,
            'abstract_class': ElementType.CLASS
        }
        
        element_type = type_mapping.get(pattern_name, ElementType.CLASS)
        
        # Determine visibility
        if name.startswith('_'):
            visibility = Visibility.PRIVATE
        elif 'export' in declaration:
            visibility = Visibility.PUBLIC
        else:
            visibility = Visibility.INTERNAL
        
        # Find block end
        if pattern_name == 'type_alias':
            end_line = start_line + 1  # Type aliases are usually single line
        else:
            end_line = self._find_block_end(lines, start_line, 'brace')
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # TypeScript-specific metadata
        metadata = {
            'declaration': declaration.strip(),
            'indent_level': len(indent),
            'is_exported': 'export' in declaration,
            'pattern_type': pattern_name,
            'has_generics': '<' in match.group(0) and '>' in match.group(0),
        }
        
        if pattern_name == 'interface':
            metadata.update({
                'extends': self._extract_extends(match.group(0)),
                'is_interface': True
            })
        elif pattern_name == 'enum':
            metadata.update({
                'is_const_enum': 'const enum' in declaration,
                'enum_values': self._extract_enum_values(content_lines)
            })
        elif pattern_name == 'abstract_class':
            metadata.update({
                'is_abstract': True,
                'parent_class': self._extract_parent_class(match.group(0))
            })
        elif pattern_name == 'namespace':
            metadata.update({
                'is_namespace': True,
                'namespace_type': 'module' if 'module' in declaration else 'namespace'
            })
        
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
    
    def _create_typed_function_element(self, match, lines: List[str], content: str) -> ParsedElement:
        """Create element for TypeScript typed functions."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        end_line = self._find_block_end(lines, start_line, 'brace')
        
        visibility = Visibility.PUBLIC if 'export' in declaration else Visibility.INTERNAL
        if name.startswith('_'):
            visibility = Visibility.PRIVATE
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        metadata = {
            'declaration': declaration.strip(),
            'is_exported': 'export' in declaration,
            'is_async': 'async' in declaration,
            'has_generics': '<' in match.group(0) and '>' in match.group(0),
            'return_type': self._extract_return_type(match.group(0)),
            'parameters': self._extract_typed_parameters(match.group(0)),
            'pattern_type': 'typed_function'
        }
        
        return ParsedElement(
            name=name,
            element_type=ElementType.FUNCTION,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract TypeScript imports (extends JavaScript)."""
        dependencies = super().extract_dependencies(content)
        
        # Add TypeScript-specific imports
        # Triple-slash directives
        triple_slash_pattern = re.compile(r'^\s*///\s*<reference\s+path\s*=\s*[\'"]([^\'"]+)[\'"]\s*/>', re.MULTILINE)
        for match in triple_slash_pattern.finditer(content):
            line_num = content[:match.start()].count('\n')
            dependencies.append(DependencyInfo(
                name=match.group(1).split('/')[-1],
                import_type='reference',
                source=match.group(1),
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_extends(self, match_text: str) -> List[str]:
        """Extract extended interfaces/classes."""
        extends_match = re.search(r'extends\s+([^{]+)', match_text)
        if not extends_match:
            return []
        
        extends_text = extends_match.group(1).strip()
        return [ext.strip() for ext in extends_text.split(',')]
    
    def _extract_enum_values(self, content: str) -> List[str]:
        """Extract enum values from enum content."""
        values = []
        lines = content.split('\n')[1:-1]  # Skip first and last lines (enum declaration and closing brace)
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('//'):
                value_match = re.match(r'^([a-zA-Z_$][a-zA-Z0-9_$]*)', line)
                if value_match:
                    values.append(value_match.group(1))
        
        return values
    
    def _extract_return_type(self, signature: str) -> Optional[str]:
        """Extract return type from TypeScript function signature."""
        return_match = re.search(r':\s*([^{]+)\s*\{', signature)
        return return_match.group(1).strip() if return_match else None
    
    def _extract_typed_parameters(self, signature: str) -> List[Dict[str, str]]:
        """Extract typed parameters from TypeScript function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if ':' in param:
                name_part, type_part = param.split(':', 1)
                name = name_part.strip()
                param_type = type_part.strip()
                
                # Handle optional parameters
                is_optional = name.endswith('?')
                if is_optional:
                    name = name[:-1]
                
                params.append({
                    'name': name,
                    'type': param_type,
                    'optional': is_optional
                })
            else:
                params.append({
                    'name': param,
                    'type': 'any',
                    'optional': False
                })
        
        return params
