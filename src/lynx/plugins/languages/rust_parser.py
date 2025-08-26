"""Comprehensive Rust language parser with advanced pattern matching."""

import re
from typing import List, Dict, Any
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class RustParser(BaseLanguageParser):
    """Advanced Rust language parser."""
    
    language_name = "rust"
    supported_extensions = [".rs"]
    
    def __init__(self):
        # Comprehensive Rust patterns
        self.patterns = {
            'function': re.compile(
                r'^(\s*)((?:pub\s+)?(?:unsafe\s+)?(?:async\s+)?(?:extern\s+(?:"[^"]*"\s+)?)?fn)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:<[^>]*>)?\s*\([^{]*?\)(?:\s*->[^{]+)?\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            'struct': re.compile(
                r'^(\s*)((?:pub\s+)?struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:<[^>]*>)?(?:\([^)]*\)|\s*\{[^}]*\}|\s*;)',
                re.MULTILINE | re.DOTALL
            ),
            'enum': re.compile(
                r'^(\s*)((?:pub\s+)?enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:<[^>]*>)?\s*\{',
                re.MULTILINE
            ),
            'trait': re.compile(
                r'^(\s*)((?:pub\s+)?trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:<[^>]*>)?(?:\s*:\s*[^{]+)?\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            'impl': re.compile(
                r'^(\s*)(impl)(?:<[^>]*>)?\s+'
                r'(?:([a-zA-Z_][a-zA-Z0-9_]*(?:<[^>]*>)?)\s+for\s+)?'
                r'([a-zA-Z_][a-zA-Z0-9_]*(?:<[^>]*>)?)\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            'mod': re.compile(
                r'^(\s*)((?:pub\s+)?mod)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:\s*\{|\s*;)',
                re.MULTILINE
            ),
            'const': re.compile(
                r'^(\s*)((?:pub\s+)?const)\s+([A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=',
                re.MULTILINE
            ),
            'static': re.compile(
                r'^(\s*)((?:pub\s+)?static)\s+(?:mut\s+)?([A-Z_][A-Z0-9_]*)\s*:\s*[^=]+=',
                re.MULTILINE
            ),
            'use': re.compile(
                r'^(\s*)use\s+([^;]+);',
                re.MULTILINE
            ),
            'macro': re.compile(
                r'^(\s*)macro_rules!\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            )
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Rust code elements comprehensively."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'use':  # Handle imports separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_element_from_match(
                        match, pattern_name, lines, content
                    )
                    if element:
                        elements.append(element)
                except Exception as e:
                    # Log error but continue parsing
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_element_from_match(self, match, pattern_name: str, 
                                 lines: List[str], content: str) -> ParsedElement:
        """Create a ParsedElement from a regex match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        
        # Extract name based on pattern
        if pattern_name == 'function':
            name = groups[2] if len(groups) > 2 else "anonymous"
            element_type = ElementType.FUNCTION
        elif pattern_name in ['struct', 'enum', 'trait', 'mod']:
            name = groups[2] if len(groups) > 2 else "unnamed"
            element_type = getattr(ElementType, pattern_name.upper(), ElementType.CLASS)
        elif pattern_name == 'impl':
            trait_name = groups[2] if len(groups) > 2 and groups[2] else None
            struct_name = groups[3] if len(groups) > 3 else "Unknown"
            name = f"impl {trait_name} for {struct_name}" if trait_name else f"impl {struct_name}"
            element_type = ElementType.CLASS  # Treat impl as class-like
        elif pattern_name in ['const', 'static']:
            name = groups[2] if len(groups) > 2 else "UNNAMED"
            element_type = ElementType.CONSTANT
        elif pattern_name == 'macro':
            name = groups[1] if len(groups) > 1 else "unnamed_macro"
            element_type = ElementType.FUNCTION  # Treat macros as function-like
        else:
            return None
        
        start_line = content[:match.start()].count('\n')
        
        # Find end of block
        if pattern_name in ['function', 'struct', 'enum', 'trait', 'impl', 'macro']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name == 'mod':
            # Check if it's a module declaration or definition
            if '{' in match.group(0):
                end_line = self._find_block_end(lines, start_line, 'brace')
            else:
                end_line = start_line + 1
        else:
            # Single line items
            end_line = start_line + 1
        
        # Extract visibility
        declaration = groups[1] if len(groups) > 1 else ""
        visibility = Visibility.PUBLIC if 'pub' in declaration else Visibility.PRIVATE
        
        # Extract content
        element_content = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'declaration': declaration,
            'indent_level': len(indent),
            'pattern_type': pattern_name,
            'is_async': 'async' in declaration if pattern_name == 'function' else False,
            'is_unsafe': 'unsafe' in declaration if pattern_name == 'function' else False,
            'has_generics': '<' in match.group(0) and '>' in match.group(0),
        }
        
        if pattern_name == 'function':
            # Extract function signature details
            signature = match.group(0)
            metadata.update({
                'return_type': self._extract_return_type(signature),
                'parameters': self._extract_parameters(signature),
            })
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=self.language_name,
            content=element_content,
            metadata=metadata
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract Rust use statements and extern crate declarations."""
        dependencies = []
        
        # Use statements
        use_pattern = self.patterns['use']
        for match in use_pattern.finditer(content):
            line_num = content[:match.start()].count('\n')
            use_path = match.group(2).strip()
            
            # Parse complex use statements
            if '{' in use_path and '}' in use_path:
                # Multi-import: use std::{fs, io, path::Path};
                base_path = use_path.split('{')[0]
                imports = use_path.split('{')[1].split('}')[0]
                for item in imports.split(','):
                    item = item.strip()
                    if item:
                        dependencies.append(DependencyInfo(
                            name=item,
                            import_type='use',
                            source=base_path.strip(':'),
                            line_number=line_num
                        ))
            else:
                # Simple use statement
                parts = use_path.split(' as ')
                name = parts[0].split('::')[-1]
                alias = parts[1] if len(parts) > 1 else None
                
                dependencies.append(DependencyInfo(
                    name=name,
                    import_type='use',
                    source=use_path,
                    alias=alias,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _extract_return_type(self, signature: str) -> Optional[str]:
        """Extract return type from function signature."""
        arrow_match = re.search(r'->\s*([^{]+)', signature)
        if arrow_match:
            return arrow_match.group(1).strip()
        return None
    
    def _extract_parameters(self, signature: str) -> List[str]:
        """Extract parameter list from function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1)
        if not params_str.strip():
            return []
        
        # Simple parameter extraction (could be enhanced)
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param and param != 'self' and param != '&self' and param != '&mut self':
                # Extract parameter name (before ':')
                if ':' in param:
                    param_name = param.split(':')[0].strip()
                    params.append(param_name)
        
        return params
