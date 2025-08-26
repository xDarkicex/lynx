"""Comprehensive Kotlin language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class KotlinParser(BaseLanguageParser):
    """Advanced Kotlin language parser."""
    
    language_name = "kotlin"
    supported_extensions = [".kt", ".kts"]
    
    def __init__(self):
        self.patterns = {
            'package': re.compile(
                r'^package\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
                re.MULTILINE
            ),
            'class': re.compile(
                r'^(\s*)((?:public|private|protected|internal|abstract|final|open|sealed|data|inline|annotation|enum)?\s*)*'
                r'(class|interface|object|enum\s+class)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s*<[^>]*>)?(?:\s*\([^)]*\))?(?:\s*:\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            'function': re.compile(
                r'^(\s*)((?:public|private|protected|internal|inline|suspend|infix|operator|override|open)?\s*)*'
                r'fun\s+(?:<[^>]*>\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'(?:\([^)]*\))?(?:\s*:\s*[^{=]+)?(?:\s*=|\s*\{)',
                re.MULTILINE
            ),
            'property': re.compile(
                r'^(\s*)((?:public|private|protected|internal|const|lateinit|override)?\s*)*'
                r'(val|var)\s+(?:<[^>]*>\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*'
                r'(?::\s*[^={\n]+)?(?:\s*=\s*[^{\n]+)?(?:\s*\{[^}]*\})?',
                re.MULTILINE
            ),
            'companion': re.compile(
                r'^(\s*)companion\s+object(?:\s+([A-Z][a-zA-Z0-9_]*))?\s*\{',
                re.MULTILINE
            ),
            'import': re.compile(
                r'^import\s+([^;\n]+)',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Kotlin code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'package']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_kotlin_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_kotlin_element(self, match, pattern_name: str, 
                              lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Kotlin match."""
        groups = match.groups()
        start_line = content[:match.start()].count('\n')
        indent = groups[0] if len(groups) > 0 else ""
        modifiers = groups[1] if len(groups) > 1 else ""
        
        if pattern_name == 'class':
            class_type = groups[2] if len(groups) > 2 else "class"
            name = groups[3] if len(groups) > 3 else "UnnamedClass"
            
            if 'interface' in class_type:
                element_type = ElementType.INTERFACE
            elif 'enum' in class_type:
                element_type = ElementType.ENUM
            elif 'object' in class_type:
                element_type = ElementType.CLASS  # Kotlin object is like a singleton class
            else:
                element_type = ElementType.CLASS
        elif pattern_name == 'function':
            name = groups[2] if len(groups) > 2 else "unnamedFunction"
            element_type = ElementType.METHOD if indent.strip() else ElementType.FUNCTION
        elif pattern_name == 'property':
            prop_type = groups[2] if len(groups) > 2 else "val"
            name = groups[3] if len(groups) > 3 else "unnamedProperty"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'companion':
            name = groups[1] if len(groups) > 1 and groups[1] else "Companion"
            element_type = ElementType.CLASS
        else:
            return None
        
        # Extract visibility
        visibility = self._extract_kotlin_visibility(modifiers)
        
        # Find block end
        if pattern_name in ['class', 'function', 'companion'] or (pattern_name == 'property' and '{' in match.group(0)):
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'pattern_type': pattern_name,
            'modifiers': modifiers.strip().split() if modifiers else [],
            'indent_level': len(indent),
            'is_suspend': 'suspend' in modifiers if modifiers else False,
            'is_inline': 'inline' in modifiers if modifiers else False,
            'is_operator': 'operator' in modifiers if modifiers else False,
            'is_infix': 'infix' in modifiers if modifiers else False,
            'is_override': 'override' in modifiers if modifiers else False,
            'is_open': 'open' in modifiers if modifiers else False,
            'is_abstract': 'abstract' in modifiers if modifiers else False,
            'is_sealed': 'sealed' in modifiers if modifiers else False,
            'is_data': 'data' in modifiers if modifiers else False,
        }
        
        if pattern_name == 'class':
            metadata.update({
                'class_type': class_type,
                'inheritance': self._extract_kotlin_inheritance(match.group(0))
            })
        elif pattern_name == 'function':
            metadata.update({
                'parameters': self._extract_kotlin_parameters(match.group(0)),
                'return_type': self._extract_kotlin_return_type(match.group(0)),
                'is_extension': self._is_extension_function(match.group(0))
            })
        elif pattern_name == 'property':
            metadata.update({
                'property_type': prop_type,
                'kotlin_type': self._extract_property_type(match.group(0)),
                'has_getter_setter': '{' in match.group(0)
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
        """Extract Kotlin import and package statements."""
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
            
            # Handle import aliases
            if ' as ' in import_path:
                actual_path, alias = import_path.split(' as ', 1)
                dependencies.append(DependencyInfo(
                    name=actual_path.strip().split('.')[-1],
                    import_type='import',
                    source=actual_path.strip(),
                    alias=alias.strip(),
                    line_number=line_num
                ))
            else:
                dependencies.append(DependencyInfo(
                    name=import_path.split('.')[-1],
                    import_type='import',
                    source=import_path,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _extract_kotlin_visibility(self, modifiers: str) -> Visibility:
        """Extract visibility from Kotlin modifiers."""
        if not modifiers:
            return Visibility.PUBLIC  # Default in Kotlin
        
        if 'public' in modifiers:
            return Visibility.PUBLIC
        elif 'private' in modifiers:
            return Visibility.PRIVATE
        elif 'protected' in modifiers:
            return Visibility.PROTECTED
        elif 'internal' in modifiers:
            return Visibility.INTERNAL
        else:
            return Visibility.PUBLIC
    
    def _extract_kotlin_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from Kotlin class definition."""
        colon_match = re.search(r':\s*([^{]+)', class_def)
        if colon_match:
            inheritance_list = colon_match.group(1).strip()
            return [base.strip() for base in inheritance_list.split(',')]
        return []
    
    def _extract_kotlin_parameters(self, signature: str) -> List[str]:
        """Extract parameters from Kotlin function signature."""
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
                # Extract parameter name (first word)
                words = param.split()
                if words:
                    param_name = words[0]
                    # Handle vararg parameters
                    if param_name == 'vararg' and len(words) > 1:
                        param_name = f"vararg {words[1]}"
                    params.append(param_name)
        
        return params
    
    def _extract_kotlin_return_type(self, signature: str) -> str:
        """Extract return type from Kotlin function signature."""
        # Look for return type after colon
        colon_match = re.search(r'\):\s*([^{=\n]+)', signature)
        if colon_match:
            return colon_match.group(1).strip()
        return 'Unit'  # Default return type in Kotlin
    
    def _extract_property_type(self, property_def: str) -> str:
        """Extract property type from Kotlin property definition."""
        # Look for type after colon
        type_match = re.search(r':\s*([^={\n]+)', property_def)
        if type_match:
            return type_match.group(1).strip()
        return 'inferred'
    
    def _is_extension_function(self, signature: str) -> bool:
        """Check if function is an extension function."""
        return '.' in signature.split('fun')[1].split('(')[0] if 'fun' in signature else False
