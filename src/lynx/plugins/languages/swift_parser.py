"""Comprehensive Swift language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class SwiftParser(BaseLanguageParser):
    """Advanced Swift language parser."""
    
    language_name = "swift"
    supported_extensions = [".swift"]
    
    def __init__(self):
        self.patterns = {
            # Functions
            'function': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*'
                r'(?:static\s+|class\s+)?(?:mutating\s+)?func)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*\([^{]*?\)(?:\s*(?:throws|rethrows))?\s*(?:->\s*[^{]+)?\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            # Classes
            'class': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*'
                r'(?:final\s+)?class)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Structs
            'struct': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*struct)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Protocols
            'protocol': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*protocol)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Enums
            'enum': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*'
                r'(?:indirect\s+)?enum)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Extensions
            'extension': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*extension)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Properties
            'property': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*'
                r'(?:static\s+|class\s+)?(?:lazy\s+)?(?:var|let))\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            # Initializers
            'initializer': re.compile(
                r'^(\s*)((?:@\w+\s+)*(?:private|fileprivate|internal|public|open)?\s*'
                r'(?:convenience\s+|required\s+)?init)\s*(?:<[^>]*>)?\s*\([^{]*?\)'
                r'(?:\s*(?:throws|rethrows))?\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            # Imports
            'import': re.compile(
                r'^(\s*)(import)\s+([^\n]+)',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Swift code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'import':  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_swift_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_swift_element(self, match, pattern_name: str,
                             lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Swift match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Map Swift constructs to element types
        type_mapping = {
            'function': ElementType.FUNCTION,
            'class': ElementType.CLASS,
            'struct': ElementType.STRUCT,
            'protocol': ElementType.INTERFACE,
            'enum': ElementType.ENUM,
            'extension': ElementType.CLASS,  # Treat as class-like
            'property': ElementType.VARIABLE,
            'initializer': ElementType.METHOD
        }
        
        element_type = type_mapping.get(pattern_name, ElementType.FUNCTION)
        
        # Extract visibility
        visibility = self._extract_swift_visibility(declaration)
        
        # Find block end
        if pattern_name == 'property':
            # Properties can be single line or have getters/setters
            end_line = self._find_property_end(lines, start_line)
        elif pattern_name in ['function', 'class', 'struct', 'protocol', 'enum', 'extension', 'initializer']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Extract Swift-specific metadata
        metadata = {
            'declaration': declaration.strip(),
            'indent_level': len(indent),
            'pattern_type': pattern_name,
            'attributes': self._extract_attributes(declaration),
            'access_level': self._get_access_level(declaration),
            'modifiers': self._extract_modifiers(declaration),
        }
        
        if pattern_name == 'function':
            metadata.update({
                'is_throwing': 'throws' in declaration or 'rethrows' in declaration,
                'is_mutating': 'mutating' in declaration,
                'is_static': 'static' in declaration,
                'is_class_method': 'class func' in declaration,
                'parameters': self._extract_swift_parameters(match.group(0)),
                'return_type': self._extract_swift_return_type(match.group(0))
            })
        elif pattern_name in ['class', 'struct']:
            metadata.update({
                'is_final': 'final' in declaration,
                'inheritance': self._extract_inheritance(match.group(0)),
                'has_generics': '<' in match.group(0) and '>' in match.group(0)
            })
        elif pattern_name == 'enum':
            metadata.update({
                'is_indirect': 'indirect' in declaration,
                'raw_type': self._extract_enum_raw_type(match.group(0))
            })
        elif pattern_name == 'property':
            metadata.update({
                'is_lazy': 'lazy' in declaration,
                'is_static': 'static' in declaration,
                'is_computed': self._is_computed_property(content_lines),
                'variable_type': 'var' if 'var' in declaration else 'let'
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
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract Swift import statements."""
        dependencies = []
        
        for match in self.patterns['import'].finditer(content):
            line_num = content[:match.start()].count('\n')
            import_stmt = match.group(3).strip()
            
            # Parse import types
            import_parts = import_stmt.split()
            if len(import_parts) >= 1:
                module_name = import_parts[-1]  # Last part is the module name
                import_type = 'import'
                
                # Check for specific import types
                if len(import_parts) > 1:
                    import_kind = import_parts[0]
                    if import_kind in ['struct', 'class', 'enum', 'protocol', 'typealias', 'func', 'var', 'let']:
                        import_type = f'import {import_kind}'
                
                dependencies.append(DependencyInfo(
                    name=module_name,
                    import_type=import_type,
                    source=import_stmt,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _extract_swift_visibility(self, declaration: str) -> Visibility:
        """Extract Swift access control level."""
        if 'private' in declaration:
            return Visibility.PRIVATE
        elif 'fileprivate' in declaration:
            return Visibility.PRIVATE
        elif 'internal' in declaration or (
            'public' not in declaration and 'open' not in declaration
        ):
            return Visibility.INTERNAL
        elif 'public' in declaration or 'open' in declaration:
            return Visibility.PUBLIC
        else:
            return Visibility.INTERNAL  # Default in Swift
    
    def _get_access_level(self, declaration: str) -> str:
        """Get the exact access level from declaration."""
        access_levels = ['open', 'public', 'internal', 'fileprivate', 'private']
        for level in access_levels:
            if level in declaration:
                return level
        return 'internal'  # Default
    
    def _extract_attributes(self, declaration: str) -> List[str]:
        """Extract Swift attributes (@available, @objc, etc.)."""
        attributes = []
        attr_pattern = re.findall(r'@\w+(?:\([^)]*\))?', declaration)
        return attr_pattern
    
    def _extract_modifiers(self, declaration: str) -> List[str]:
        """Extract Swift modifiers."""
        modifiers = []
        modifier_keywords = ['static', 'class', 'final', 'lazy', 'mutating', 'convenience', 'required', 'indirect']
        
        for modifier in modifier_keywords:
            if modifier in declaration:
                modifiers.append(modifier)
        
        return modifiers
    
    def _extract_swift_parameters(self, signature: str) -> List[Dict[str, str]]:
        """Extract parameters from Swift function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        params = []
        # Swift parameters can be complex: externalName internalName: Type
        for param in params_str.split(','):
            param = param.strip()
            if ':' in param:
                name_part, type_part = param.split(':', 1)
                name_part = name_part.strip()
                param_type = type_part.strip()
                
                # Handle external and internal names
                names = name_part.split()
                if len(names) == 2:
                    external_name, internal_name = names
                else:
                    external_name = internal_name = names[0] if names else ''
                
                params.append({
                    'external_name': external_name,
                    'internal_name': internal_name,
                    'type': param_type
                })
        
        return params
    
    def _extract_swift_return_type(self, signature: str) -> Optional[str]:
        """Extract return type from Swift function signature."""
        arrow_match = re.search(r'->\s*([^{]+)', signature)
        return arrow_match.group(1).strip() if arrow_match else None
    
    def _extract_inheritance(self, match_text: str) -> List[str]:
        """Extract inheritance/protocol conformance."""
        colon_match = re.search(r':\s*([^{]+)', match_text)
        if not colon_match:
            return []
        
        inheritance_text = colon_match.group(1).strip()
        return [item.strip() for item in inheritance_text.split(',')]
    
    def _extract_enum_raw_type(self, match_text: str) -> Optional[str]:
        """Extract raw type from enum declaration."""
        colon_match = re.search(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)', match_text)
        return colon_match.group(1) if colon_match else None
    
    def _find_property_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a property declaration."""
        if start_line >= len(lines):
            return start_line
        
        # Check if property has getter/setter
        current_line = lines[start_line]
        if '{' in current_line:
            return self._find_block_end(lines, start_line, 'brace')
        else:
            # Single line property
            return start_line + 1
    
    def _is_computed_property(self, content: str) -> bool:
        """Check if property is computed (has getter/setter)."""
        return 'get' in content or 'set' in content
