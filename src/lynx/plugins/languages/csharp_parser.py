"""Comprehensive C# language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class CSharpParser(BaseLanguageParser):
    """Advanced C# language parser."""
    
    language_name = "csharp"
    supported_extensions = [".cs"]
    
    def __init__(self):
        self.patterns = {
            'namespace': re.compile(
                r'^(\s*)namespace\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s*\{',
                re.MULTILINE
            ),
            'class': re.compile(
                r'^(\s*)((?:public|private|protected|internal|abstract|sealed|static|partial)?\s*)*'
                r'(class|interface|struct|enum)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s*:\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'method': re.compile(
                r'^(\s*)((?:public|private|protected|internal|static|virtual|override|abstract|sealed|async)?\s*)*'
                r'(?:[a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'\([^)]*\)(?:\s*where\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'property': re.compile(
                r'^(\s*)((?:public|private|protected|internal|static|virtual|override|abstract)?\s*)*'
                r'([a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'(?:\{(?:\s*get\s*;|\s*set\s*;|\s*get\s*\{[^}]*\}|\s*set\s*\{[^}]*\})*\s*\}|=>)',
                re.MULTILINE
            ),
            'field': re.compile(
                r'^(\s*)((?:public|private|protected|internal|static|readonly|const|volatile)?\s*)*'
                r'([a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:\s*=\s*[^;]+)?;',
                re.MULTILINE
            ),
            'attribute': re.compile(
                r'^(\s*)\[([A-Z][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'using': re.compile(
                r'^using\s+(?:static\s+)?([^;=]+)(?:\s*=\s*[^;]+)?;',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse C# code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'using':  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_csharp_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_csharp_element(self, match, pattern_name: str, 
                              lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from C# match."""
        groups = match.groups()
        start_line = content[:match.start()].count('\n')
        indent = groups[0] if len(groups) > 0 else ""
        modifiers = groups[1] if len(groups) > 1 else ""
        
        if pattern_name == 'namespace':
            name = groups[1] if len(groups) > 1 else "UnnamedNamespace"
            element_type = ElementType.NAMESPACE
        elif pattern_name == 'class':
            class_type = groups[2] if len(groups) > 2 else "class"
            name = groups[3] if len(groups) > 3 else "UnnamedClass"
            if class_type == 'interface':
                element_type = ElementType.INTERFACE
            elif class_type == 'struct':
                element_type = ElementType.STRUCT
            elif class_type == 'enum':
                element_type = ElementType.ENUM
            else:
                element_type = ElementType.CLASS
        elif pattern_name == 'method':
            name = groups[2] if len(groups) > 2 else "UnnamedMethod"
            element_type = ElementType.METHOD
        elif pattern_name == 'property':
            name = groups[3] if len(groups) > 3 else "UnnamedProperty"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'field':
            name = groups[3] if len(groups) > 3 else "unnamedField"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'attribute':
            name = groups[1] if len(groups) > 1 else "UnnamedAttribute"
            element_type = ElementType.CLASS
        else:
            return None
        
        # Extract visibility
        visibility = self._extract_csharp_visibility(modifiers)
        
        # Find block end
        if pattern_name in ['namespace', 'class', 'method']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'pattern_type': pattern_name,
            'modifiers': modifiers.strip().split() if modifiers else [],
            'indent_level': len(indent),
            'is_static': 'static' in modifiers if modifiers else False,
            'is_abstract': 'abstract' in modifiers if modifiers else False,
            'is_sealed': 'sealed' in modifiers if modifiers else False,
            'is_virtual': 'virtual' in modifiers if modifiers else False,
            'is_override': 'override' in modifiers if modifiers else False,
            'is_async': 'async' in modifiers if modifiers else False,
        }
        
        if pattern_name == 'class':
            metadata.update({
                'class_type': class_type,
                'inheritance': self._extract_csharp_inheritance(match.group(0))
            })
        elif pattern_name == 'method':
            metadata.update({
                'parameters': self._extract_csharp_parameters(match.group(0)),
                'return_type': self._extract_csharp_return_type(match.group(0)),
                'constraints': self._extract_constraints(match.group(0))
            })
        elif pattern_name == 'property':
            metadata.update({
                'property_type': groups[2] if len(groups) > 2 else "object",
                'accessors': self._extract_property_accessors(match.group(0))
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
        """Extract C# using statements."""
        dependencies = []
        
        using_matches = self.patterns['using'].finditer(content)
        for match in using_matches:
            line_num = content[:match.start()].count('\n')
            using_path = match.group(1).strip()
            
            # Handle static using
            import_type = 'static_using' if 'static' in match.group(0) else 'using'
            
            # Handle using aliases
            if '=' in using_path:
                alias, actual_path = using_path.split('=', 1)
                dependencies.append(DependencyInfo(
                    name=actual_path.strip().split('.')[-1],
                    import_type='using_alias',
                    source=actual_path.strip(),
                    alias=alias.strip(),
                    line_number=line_num
                ))
            else:
                dependencies.append(DependencyInfo(
                    name=using_path.split('.')[-1],
                    import_type=import_type,
                    source=using_path,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _extract_csharp_visibility(self, modifiers: str) -> Visibility:
        """Extract visibility from C# modifiers."""
        if not modifiers:
            return Visibility.INTERNAL  # Default in C#
        
        if 'public' in modifiers:
            return Visibility.PUBLIC
        elif 'private' in modifiers:
            return Visibility.PRIVATE
        elif 'protected' in modifiers:
            return Visibility.PROTECTED
        elif 'internal' in modifiers:
            return Visibility.INTERNAL
        else:
            return Visibility.INTERNAL
    
    def _extract_csharp_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from C# class definition."""
        colon_match = re.search(r':\s*([^{]+)', class_def)
        if colon_match:
            inheritance_list = colon_match.group(1).strip()
            return [base.strip() for base in inheritance_list.split(',')]
        return []
    
    def _extract_csharp_parameters(self, signature: str) -> List[str]:
        """Extract parameters from C# method signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Extract parameter name (last word, handling ref/out/in)
                words = param.split()
                if words:
                    params.append(words[-1])
        
        return params
    
    def _extract_csharp_return_type(self, signature: str) -> str:
        """Extract return type from C# method signature."""
        # Look for return type before method name
        method_match = re.search(r'(?:public|private|protected|internal|static|virtual|override|abstract|sealed|async|\s)+([a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', signature)
        if method_match:
            return method_match.group(1).strip()
        return 'void'
    
    def _extract_constraints(self, signature: str) -> List[str]:
        """Extract generic constraints from method signature."""
        where_match = re.search(r'where\s+([^{]+)', signature)
        if where_match:
            constraints = where_match.group(1).strip()
            return [constraint.strip() for constraint in constraints.split(',')]
        return []
    
    def _extract_property_accessors(self, property_def: str) -> List[str]:
        """Extract property accessors (get/set)."""
        accessors = []
        if 'get' in property_def:
            accessors.append('get')
        if 'set' in property_def:
            accessors.append('set')
        return accessors
