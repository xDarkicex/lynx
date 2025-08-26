"""Comprehensive Go language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class GoParser(BaseLanguageParser):
    """Advanced Go language parser."""
    
    language_name = "go"
    supported_extensions = [".go"]
    
    def __init__(self):
        self.patterns = {
            'function': re.compile(
                r'^func\s+(?:\([^)]*\)\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'(?:\[.*?\])?\s*\([^)]*\)(?:\s*\([^)]*\)|\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'method': re.compile(
                r'^func\s+\(([^)]+)\)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'\([^)]*\)(?:\s*\([^)]*\)|\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'type_struct': re.compile(
                r'^type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+struct\s*\{',
                re.MULTILINE
            ),
            'type_interface': re.compile(
                r'^type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+interface\s*\{',
                re.MULTILINE
            ),
            'type_alias': re.compile(
                r'^type\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+(?!struct|interface)([^{]+)$',
                re.MULTILINE
            ),
            'var_block': re.compile(
                r'^var\s*\(',
                re.MULTILINE
            ),
            'var_single': re.compile(
                r'^var\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'const_block': re.compile(
                r'^const\s*\(',
                re.MULTILINE
            ),
            'const_single': re.compile(
                r'^const\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'import': re.compile(
                r'^import\s*(?:\(\s*|"([^"]+)"|([a-zA-Z_][a-zA-Z0-9_]*)\s+"([^"]+)")',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Go code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'import':  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_go_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_go_element(self, match, pattern_name: str, 
                          lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Go match."""
        start_line = content[:match.start()].count('\n')
        
        if pattern_name == 'function':
            name = match.group(1)
            element_type = ElementType.FUNCTION
            visibility = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
        elif pattern_name == 'method':
            receiver = match.group(1)
            name = match.group(2)
            element_type = ElementType.METHOD
            visibility = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
        elif pattern_name.startswith('type_'):
            name = match.group(1)
            if 'struct' in pattern_name:
                element_type = ElementType.STRUCT
            elif 'interface' in pattern_name:
                element_type = ElementType.INTERFACE
            else:
                element_type = ElementType.CLASS  # Type alias
            visibility = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
        elif pattern_name.startswith('var'):
            name = match.group(1) if match.groups() else "variables"
            element_type = ElementType.VARIABLE
            visibility = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
        elif pattern_name.startswith('const'):
            name = match.group(1) if match.groups() else "constants"
            element_type = ElementType.CONSTANT
            visibility = Visibility.PUBLIC if name[0].isupper() else Visibility.PRIVATE
        else:
            return None
        
        # Find block end
        if pattern_name in ['function', 'method', 'type_struct', 'type_interface']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name.endswith('_block'):
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        metadata = {
            'pattern_type': pattern_name,
            'is_exported': name[0].isupper() if name else False,
        }
        
        if pattern_name == 'method':
            metadata['receiver'] = receiver
        
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
        """Extract Go import statements."""
        dependencies = []
        
        # Handle import blocks and single imports
        import_blocks = re.finditer(r'^import\s*\(\s*$(.*?)^\)', content, re.MULTILINE | re.DOTALL)
        for block_match in import_blocks:
            block_content = block_match.group(1)
            for line in block_content.split('\n'):
                line = line.strip()
                if line and not line.startswith('//'):
                    dep = self._parse_import_line(line, content[:block_match.start()].count('\n'))
                    if dep:
                        dependencies.append(dep)
        
        # Single import statements
        single_imports = re.finditer(r'^import\s+"([^"]+)"', content, re.MULTILINE)
        for imp in single_imports:
            line_num = content[:imp.start()].count('\n')
            dependencies.append(DependencyInfo(
                name=imp.group(1).split('/')[-1],
                import_type='import',
                source=imp.group(1),
                line_number=line_num
            ))
        
        return dependencies
    
    def _parse_import_line(self, line: str, base_line: int) -> DependencyInfo:
        """Parse a single import line."""
        # Handle aliased imports: alias "package"
        alias_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s+"([^"]+)"', line)
        if alias_match:
            return DependencyInfo(
                name=alias_match.group(2).split('/')[-1],
                import_type='import',
                source=alias_match.group(2),
                alias=alias_match.group(1),
                line_number=base_line
            )
        
        # Regular import: "package"
        regular_match = re.match(r'^"([^"]+)"', line)
        if regular_match:
            return DependencyInfo(
                name=regular_match.group(1).split('/')[-1],
                import_type='import',
                source=regular_match.group(1),
                line_number=base_line
            )
        
        return None
