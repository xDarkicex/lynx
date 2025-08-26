"""Comprehensive Java language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class JavaParser(BaseLanguageParser):
    """Advanced Java language parser."""
    
    language_name = "java"
    supported_extensions = [".java"]
    
    def __init__(self):
        self.patterns = {
            'class': re.compile(
                r'^(\s*)((?:public|private|protected|abstract|final|static)?\s*)*'
                r'(class|interface|enum)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s*extends\s+[^{]+)?(?:\s*implements\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'method': re.compile(
                r'^(\s*)((?:public|private|protected|static|abstract|final|synchronized)?\s*)*'
                r'(?:[a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'\([^)]*\)(?:\s*throws\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'constructor': re.compile(
                r'^(\s*)((?:public|private|protected)?\s*)*'
                r'([A-Z][a-zA-Z0-9_]*)\s*\([^)]*\)(?:\s*throws\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'field': re.compile(
                r'^(\s*)((?:public|private|protected|static|final|volatile)?\s*)*'
                r'([a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
                r'(?:\s*=\s*[^;]+)?;',
                re.MULTILINE
            ),
            'annotation': re.compile(
                r'^(\s*)@([A-Z][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'import': re.compile(
                r'^import\s+(?:static\s+)?([^;]+);',
                re.MULTILINE
            ),
            'package': re.compile(
                r'^package\s+([^;]+);',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Java code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'package']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_java_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_java_element(self, match, pattern_name: str, 
                            lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Java match."""
        groups = match.groups()
        start_line = content[:match.start()].count('\n')
        indent = groups[0] if len(groups) > 0 else ""
        modifiers = groups[1] if len(groups) > 1 else ""
        
        if pattern_name in ['class']:
            class_type = groups[2] if len(groups) > 2 else "class"
            name = groups[3] if len(groups) > 3 else "UnnamedClass"
            if class_type == 'interface':
                element_type = ElementType.INTERFACE
            elif class_type == 'enum':
                element_type = ElementType.ENUM
            else:
                element_type = ElementType.CLASS
        elif pattern_name == 'method':
            name = groups[2] if len(groups) > 2 else "unnamedMethod"
            element_type = ElementType.METHOD
        elif pattern_name == 'constructor':
            name = groups[2] if len(groups) > 2 else "Constructor"
            element_type = ElementType.METHOD
        elif pattern_name == 'field':
            name = groups[3] if len(groups) > 3 else "unnamedField"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'annotation':
            name = groups[1] if len(groups) > 1 else "UnnamedAnnotation"
            element_type = ElementType.CLASS
        else:
            return None
        
        # Extract visibility
        visibility = self._extract_java_visibility(modifiers)
        
        # Find block end
        if pattern_name in ['class', 'method', 'constructor']:
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
            'is_final': 'final' in modifiers if modifiers else False,
            'is_abstract': 'abstract' in modifiers if modifiers else False,
        }
        
        if pattern_name == 'class':
            metadata.update({
                'class_type': class_type,
                'inheritance': self._extract_inheritance(match.group(0))
            })
        elif pattern_name in ['method', 'constructor']:
            metadata.update({
                'parameters': self._extract_java_parameters(match.group(0)),
                'return_type': self._extract_java_return_type(match.group(0)) if pattern_name == 'method' else name,
                'throws': self._extract_throws(match.group(0))
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
        """Extract Java import and package statements."""
        dependencies = []
        
        # Package declaration
        package_matches = self.patterns['package'].finditer(content)
        for match in package_matches:
            line_num = content[:match.start()].count('\n')
            package_name = match.group(1).strip()
            dependencies.append(DependencyInfo(
                name=package_name.split('.')[-1],
                import_type='package',
                source=package_name,
                line_number=line_num
            ))
        
        # Import statements
        import_matches = self.patterns['import'].finditer(content)
        for match in import_matches:
            line_num = content[:match.start()].count('\n')
            import_path = match.group(1).strip()
            
            # Handle static imports
            import_type = 'static_import' if 'static' in match.group(0) else 'import'
            
            # Handle wildcard imports
            if import_path.endswith('*'):
                name = import_path.split('.')[-2] + ".*"
            else:
                name = import_path.split('.')[-1]
            
            dependencies.append(DependencyInfo(
                name=name,
                import_type=import_type,
                source=import_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_java_visibility(self, modifiers: str) -> Visibility:
        """Extract visibility from Java modifiers."""
        if not modifiers:
            return Visibility.INTERNAL  # Package-private in Java
        
        if 'public' in modifiers:
            return Visibility.PUBLIC
        elif 'private' in modifiers:
            return Visibility.PRIVATE
        elif 'protected' in modifiers:
            return Visibility.PROTECTED
        else:
            return Visibility.INTERNAL
    
    def _extract_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from class definition."""
        inheritance = []
        
        # extends
        extends_match = re.search(r'extends\s+([^{,\s]+)', class_def)
        if extends_match:
            inheritance.append(f"extends {extends_match.group(1)}")
        
        # implements
        implements_match = re.search(r'implements\s+([^{]+)', class_def)
        if implements_match:
            interfaces = implements_match.group(1).strip()
            for interface in interfaces.split(','):
                inheritance.append(f"implements {interface.strip()}")
        
        return inheritance
    
    def _extract_java_parameters(self, signature: str) -> List[str]:
        """Extract parameters from Java method signature."""
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
                # Extract parameter name (last word)
                words = param.split()
                if words:
                    params.append(words[-1])
        
        return params
    
    def _extract_java_return_type(self, signature: str) -> str:
        """Extract return type from Java method signature."""
        # Look for return type before method name
        method_match = re.search(r'(?:public|private|protected|static|final|abstract|synchronized|\s)+([a-zA-Z_][a-zA-Z0-9_<>,\[\]\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', signature)
        if method_match:
            return method_match.group(1).strip()
        return 'void'
    
    def _extract_throws(self, signature: str) -> List[str]:
        """Extract throws clause from method signature."""
        throws_match = re.search(r'throws\s+([^{]+)', signature)
        if throws_match:
            exceptions = throws_match.group(1).strip()
            return [exc.strip() for exc in exceptions.split(',')]
        return []
