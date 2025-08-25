"""Comprehensive C++ language parser extending C parser."""

import re
from typing import List, Dict, Any, Optional
from .c_parser import CParser
from .base import ParsedElement, DependencyInfo, ElementType, Visibility

class CppParser(CParser):
    """Advanced C++ parser extending C parser functionality."""
    
    language_name = "cpp"
    supported_extensions = [".cpp", ".cxx", ".cc", ".hpp", ".hxx", ".hh"]
    
    def __init__(self):
        super().__init__()
        
        # Extend patterns with C++-specific ones
        self.patterns.update({
            # Classes
            'class': re.compile(
                r'^(\s*)((?:template\s*<[^>]*>\s*)?class)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*(?::\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            # Constructors
            'constructor': re.compile(
                r'^(\s*)((?:explicit\s+)?(?:inline\s+)?)([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^{]*\)\s*'
                r'(?::\s*[^{]+)?\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            # Destructors
            'destructor': re.compile(
                r'^(\s*)((?:virtual\s+)?~)([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*(?:override|final)?\s*\{',
                re.MULTILINE
            ),
            # Member functions with access specifiers
            'member_function': re.compile(
                r'^(\s*)((?:virtual\s+|static\s+|inline\s+|explicit\s+)*[a-zA-Z_][a-zA-Z0-9_*&<>,:\s]*)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^{]*\)\s*(?:const|override|final|noexcept)*\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            # Templates
            'template': re.compile(
                r'^(\s*)(template\s*<[^>]*>)\s*$',
                re.MULTILINE
            ),
            # Namespaces
            'namespace': re.compile(
                r'^(\s*)(namespace)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            # Using declarations
            'using': re.compile(
                r'^(\s*)(using)\s+([^;]+);',
                re.MULTILINE
            ),
            # Access specifiers
            'access_specifier': re.compile(
                r'^(\s*)(private|protected|public)\s*:',
                re.MULTILINE
            ),
        })
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse C++ code elements."""
        elements = []
        lines = content.split('\n')
        
        # Track current access level within classes
        current_access = 'private'  # Default for class
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['include', 'using']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_cpp_element(match, pattern_name, lines, content, file_path)
                    if element and pattern_name != 'access_specifier':
                        # Apply current access level for class members
                        if self._is_class_member(element, content):
                            element.visibility = self._access_to_visibility(current_access)
                        elements.append(element)
                    elif pattern_name == 'access_specifier':
                        current_access = match.group(2)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_cpp_element(self, match, pattern_name: str, lines: List[str],
                           content: str, file_path: str) -> ParsedElement:
        """Create ParsedElement from C++ match."""
        groups = match.groups()
        
        # Handle C++-specific patterns
        if pattern_name in ['class', 'constructor', 'destructor', 'member_function', 'namespace']:
            return self._create_cpp_specific_element(match, pattern_name, lines, content, file_path)
        elif pattern_name == 'template':
            return None  # Templates are handled as modifiers to other elements
        else:
            # Use parent C logic for other patterns
            return super()._create_c_element(match, pattern_name, lines, content, file_path)
    
    def _create_cpp_specific_element(self, match, pattern_name: str, lines: List[str],
                                   content: str, file_path: str) -> ParsedElement:
        """Create C++-specific elements."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Map C++ constructs to element types
        type_mapping = {
            'class': ElementType.CLASS,
            'constructor': ElementType.METHOD,
            'destructor': ElementType.METHOD,
            'member_function': ElementType.METHOD,
            'namespace': ElementType.NAMESPACE
        }
        
        element_type = type_mapping.get(pattern_name, ElementType.FUNCTION)
        
        # Determine visibility (will be overridden for class members)
        if 'static' in declaration and file_path.endswith(('.cpp', '.cc', '.cxx')):
            visibility = Visibility.PRIVATE
        elif file_path.endswith(('.hpp', '.hh', '.hxx')):
            visibility = Visibility.PUBLIC
        else:
            visibility = Visibility.INTERNAL
        
        # Find block end
        if pattern_name in ['class', 'namespace']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name in ['constructor', 'destructor', 'member_function']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Extract C++-specific metadata
        metadata = {
            'declaration': declaration.strip(),
            'indent_level': len(indent),
            'pattern_type': pattern_name,
            'is_virtual': 'virtual' in declaration,
            'is_static': 'static' in declaration,
            'is_inline': 'inline' in declaration,
            'is_explicit': 'explicit' in declaration,
            'is_const': 'const' in match.group(0),
            'is_override': 'override' in match.group(0),
            'is_final': 'final' in match.group(0),
            'is_noexcept': 'noexcept' in match.group(0),
        }
        
        if pattern_name == 'class':
            metadata.update({
                'inheritance': self._extract_cpp_inheritance(match.group(0)),
                'is_template': self._is_template_class(content, start_line),
                'template_params': self._extract_template_params(content, start_line)
            })
        elif pattern_name in ['constructor', 'destructor', 'member_function']:
            metadata.update({
                'return_type': self._extract_cpp_return_type(declaration, name, pattern_name),
                'parameters': self._extract_cpp_parameters(match.group(0)),
                'initializer_list': self._extract_initializer_list(match.group(0)) if pattern_name == 'constructor' else None
            })
        elif pattern_name == 'namespace':
            metadata.update({
                'is_anonymous': name == '' or name.isspace(),
                'nested_namespaces': self._count_nested_namespaces(content_lines)
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
        """Extract C++ includes and using statements."""
        dependencies = super().extract_dependencies(content)
        
        # Add using declarations
        for match in self.patterns['using'].finditer(content):
            line_num = content[:match.start()].count('\n')
            using_stmt = match.group(3).strip()
            
            if using_stmt.startswith('namespace'):
                # using namespace std;
                namespace = using_stmt.replace('namespace', '').strip()
                dependencies.append(DependencyInfo(
                    name=namespace,
                    import_type='using_namespace',
                    source=using_stmt,
                    line_number=line_num
                ))
            else:
                # using std::vector;
                dependencies.append(DependencyInfo(
                    name=using_stmt.split('::')[-1] if '::' in using_stmt else using_stmt,
                    import_type='using',
                    source=using_stmt,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _is_class_member(self, element: ParsedElement, content: str) -> bool:
        """Check if element is a class member."""
        # Simple heuristic: if element is indented and within a class
        return element.metadata.get('indent_level', 0) > 0
    
    def _access_to_visibility(self, access_level: str) -> Visibility:
        """Convert C++ access level to Visibility enum."""
        mapping = {
            'private': Visibility.PRIVATE,
            'protected': Visibility.PROTECTED,
            'public': Visibility.PUBLIC
        }
        return mapping.get(access_level, Visibility.PRIVATE)
    
    def _extract_cpp_inheritance(self, match_text: str) -> List[Dict[str, str]]:
        """Extract C++ inheritance information."""
        inheritance = []
        colon_match = re.search(r':\s*([^{]+)', match_text)
        if not colon_match:
            return inheritance
        
        inheritance_text = colon_match.group(1).strip()
        for item in inheritance_text.split(','):
            item = item.strip()
            parts = item.split()
            
            access = 'private'  # Default for class
            class_name = parts[-1]
            
            if len(parts) >= 2:
                if parts[0] in ['public', 'protected', 'private']:
                    access = parts[0]
                    if len(parts) >= 3 and parts[1] == 'virtual':
                        inheritance.append({
                            'class': class_name,
                            'access': access,
                            'virtual': True
                        })
                    else:
                        inheritance.append({
                            'class': class_name,
                            'access': access,
                            'virtual': False
                        })
                elif parts[0] == 'virtual':
                    access = parts[1] if len(parts) >= 3 else 'private'
                    inheritance.append({
                        'class': class_name,
                        'access': access,
                        'virtual': True
                    })
            else:
                inheritance.append({
                    'class': class_name,
                    'access': access,
                    'virtual': False
                })
        
        return inheritance
    
    def _is_template_class(self, content: str, class_start_line: int) -> bool:
        """Check if class is preceded by template declaration."""
        lines = content.split('\n')
        # Check previous non-empty line
        for i in range(class_start_line - 1, -1, -1):
            if lines[i].strip():
                return lines[i].strip().startswith('template')
        return False
    
    def _extract_template_params(self, content: str, class_start_line: int) -> List[str]:
        """Extract template parameters from template declaration."""
        lines = content.split('\n')
        template_params = []
        
        # Look for template declaration above class
        for i in range(class_start_line - 1, -1, -1):
            line = lines[i].strip()
            if line.startswith('template'):
                template_match = re.search(r'template\s*<([^>]*)>', line)
                if template_match:
                    params_str = template_match.group(1)
                    for param in params_str.split(','):
                        param = param.strip()
                        # Simple parameter name extraction
                        if ' ' in param:
                            template_params.append(param.split()[-1])
                        else:
                            template_params.append(param)
                break
            elif line and not line.startswith('//'):
                break
        
        return template_params
    
    def _extract_cpp_return_type(self, declaration: str, func_name: str, pattern_name: str) -> str:
        """Extract return type from C++ function declaration."""
        if pattern_name in ['constructor', 'destructor']:
            return 'void'  # Constructors and destructors don't have return types
        
        # Remove function name and everything after it
        before_name = declaration.split(func_name)[0].strip()
        # Remove C++ keywords
        return_type = before_name
        for keyword in ['virtual', 'static', 'inline', 'explicit']:
            return_type = return_type.replace(keyword, '')
        
        return return_type.strip() or 'void'
    
    def _extract_cpp_parameters(self, signature: str) -> List[Dict[str, str]]:
        """Extract parameters from C++ function signature."""
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
                # Handle default parameters
                param_parts = param.split('=')
                param_decl = param_parts[0].strip()
                default_value = param_parts[1].strip() if len(param_parts) > 1 else None
                
                # Simple parameter parsing
                parts = param_decl.split()
                if parts:
                    param_name = parts[-1].strip('*&')
                    param_type = ' '.join(parts[:-1]) if len(parts) > 1 else 'auto'
                    
                    param_info = {
                        'name': param_name,
                        'type': param_type,
                        'has_default': default_value is not None
                    }
                    
                    if default_value:
                        param_info['default'] = default_value
                    
                    params.append(param_info)
        
        return params
    
    def _extract_initializer_list(self, signature: str) -> List[str]:
        """Extract member initializer list from constructor."""
        colon_match = re.search(r':\s*([^{]+)', signature)
        if not colon_match:
            return []
        
        init_text = colon_match.group(1).strip()
        initializers = []
        
        # Simple parsing of initializer list
        for init in init_text.split(','):
            init = init.strip()
            if '(' in init:
                member_name = init.split('(')[0].strip()
                initializers.append(member_name)
        
        return initializers
    
    def _count_nested_namespaces(self, content: str) -> int:
        """Count nested namespace declarations."""
        return content.count('namespace ')
