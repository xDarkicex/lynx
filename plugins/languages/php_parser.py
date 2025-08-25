"""Comprehensive PHP language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class PhpParser(BaseLanguageParser):
    """Advanced PHP language parser."""
    
    language_name = "php"
    supported_extensions = [".php"]
    
    def __init__(self):
        self.patterns = {
            'namespace': re.compile(
                r'^namespace\s+([a-zA-Z_][a-zA-Z0-9_\\]*);',
                re.MULTILINE
            ),
            'class': re.compile(
                r'^(\s*)((?:abstract|final)?\s*)?(class|interface|trait)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s+extends\s+[^{]+)?(?:\s+implements\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'function': re.compile(
                r'^(\s*)((?:public|private|protected|static|abstract|final)?\s*)*'
                r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)(?:\s*:\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'property': re.compile(
                r'^(\s*)((?:public|private|protected|static|var)?\s*)*'
                r'\$([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'constant': re.compile(
                r'^(\s*)((?:public|private|protected)?\s*)*'
                r'const\s+([A-Z_][A-Z0-9_]*)',
                re.MULTILINE
            ),
            'use': re.compile(
                r'^use\s+([^;]+);',
                re.MULTILINE
            ),
            'require': re.compile(
                r'^(?:require|include)(?:_once)?\s*\(?[\'"]([^\'"]+)[\'"]',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse PHP code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['use', 'require', 'namespace']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_php_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_php_element(self, match, pattern_name: str, 
                           lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from PHP match."""
        groups = match.groups()
        start_line = content[:match.start()].count('\n')
        indent = groups[0] if len(groups) > 0 else ""
        
        if pattern_name == 'class':
            modifiers = groups[1] if len(groups) > 1 else ""
            class_type = groups[2] if len(groups) > 2 else "class"
            name = groups[3] if len(groups) > 3 else "UnnamedClass"
            if class_type == 'interface':
                element_type = ElementType.INTERFACE
            elif class_type == 'trait':
                element_type = ElementType.TRAIT
            else:
                element_type = ElementType.CLASS
        elif pattern_name == 'function':
            modifiers = groups[1] if len(groups) > 1 else ""
            name = groups[2] if len(groups) > 2 else "unnamedFunction"
            element_type = ElementType.METHOD if indent.strip() else ElementType.FUNCTION
        elif pattern_name == 'property':
            modifiers = groups[1] if len(groups) > 1 else ""
            name = f"${groups[2]}" if len(groups) > 2 else "$unnamedProperty"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'constant':
            modifiers = groups[1] if len(groups) > 1 else ""
            name = groups[2] if len(groups) > 2 else "UNNAMED_CONSTANT"
            element_type = ElementType.CONSTANT
        else:
            return None
        
        # Extract visibility
        visibility = self._extract_php_visibility(modifiers if 'modifiers' in locals() else "")
        
        # Find block end
        if pattern_name in ['class', 'function']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'pattern_type': pattern_name,
            'modifiers': modifiers.strip().split() if 'modifiers' in locals() and modifiers else [],
            'indent_level': len(indent),
            'is_static': 'static' in modifiers if 'modifiers' in locals() and modifiers else False,
            'is_abstract': 'abstract' in modifiers if 'modifiers' in locals() and modifiers else False,
            'is_final': 'final' in modifiers if 'modifiers' in locals() and modifiers else False,
        }
        
        if pattern_name == 'class':
            metadata.update({
                'class_type': class_type,
                'inheritance': self._extract_php_inheritance(match.group(0))
            })
        elif pattern_name == 'function':
            metadata.update({
                'parameters': self._extract_php_parameters(match.group(0)),
                'return_type': self._extract_php_return_type(match.group(0))
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
        """Extract PHP use, require, and namespace statements."""
        dependencies = []
        
        # Namespace declaration
        namespace_matches = self.patterns['namespace'].finditer(content)
        for match in namespace_matches:
            line_num = content[:match.start()].count('\n')
            namespace_name = match.group(1).strip()
            dependencies.append(DependencyInfo(
                name=namespace_name.split('\\')[-1],
                import_type='namespace',
                source=namespace_name,
                line_number=line_num
            ))
        
        # Use statements
        use_matches = self.patterns['use'].finditer(content)
        for match in use_matches:
            line_num = content[:match.start()].count('\n')
            use_path = match.group(1).strip()
            
            # Handle use aliases
            if ' as ' in use_path:
                actual_path, alias = use_path.split(' as ', 1)
                dependencies.append(DependencyInfo(
                    name=actual_path.strip().split('\\')[-1],
                    import_type='use',
                    source=actual_path.strip(),
                    alias=alias.strip(),
                    line_number=line_num
                ))
            else:
                dependencies.append(DependencyInfo(
                    name=use_path.split('\\')[-1],
                    import_type='use',
                    source=use_path,
                    line_number=line_num
                ))
        
        # Require/include statements
        require_matches = self.patterns['require'].finditer(content)
        for match in require_matches:
            line_num = content[:match.start()].count('\n')
            require_path = match.group(1).strip()
            dependencies.append(DependencyInfo(
                name=require_path.split('/')[-1].split('.')[0],
                import_type='require',
                source=require_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_php_visibility(self, modifiers: str) -> Visibility:
        """Extract visibility from PHP modifiers."""
        if not modifiers:
            return Visibility.PUBLIC  # Default in PHP
        
        if 'public' in modifiers:
            return Visibility.PUBLIC
        elif 'private' in modifiers:
            return Visibility.PRIVATE
        elif 'protected' in modifiers:
            return Visibility.PROTECTED
        else:
            return Visibility.PUBLIC
    
    def _extract_php_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from PHP class definition."""
        inheritance = []
        
        # extends
        extends_match = re.search(r'extends\s+([^\s{,]+)', class_def)
        if extends_match:
            inheritance.append(f"extends {extends_match.group(1)}")
        
        # implements
        implements_match = re.search(r'implements\s+([^{]+)', class_def)
        if implements_match:
            interfaces = implements_match.group(1).strip()
            for interface in interfaces.split(','):
                inheritance.append(f"implements {interface.strip()}")
        
        return inheritance
    
    def _extract_php_parameters(self, signature: str) -> List[str]:
        """Extract parameters from PHP function signature."""
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
                # Extract parameter name (starts with $)
                param_match = re.search(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', param)
                if param_match:
                    params.append(f"${param_match.group(1)}")
        
        return params
    
    def _extract_php_return_type(self, signature: str) -> str:
        """Extract return type from PHP function signature."""
        # Look for return type after colon
        type_match = re.search(r':\s*([^{]+)', signature)
        if type_match:
            return type_match.group(1).strip()
        return 'mixed'
