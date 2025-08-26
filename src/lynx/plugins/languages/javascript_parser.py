"""Comprehensive JavaScript language parser with modern ES6+ support."""

import re
from typing import List, Dict, Any
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class JavaScriptParser(BaseLanguageParser):
    """Advanced JavaScript parser supporting ES6+ features."""
    
    language_name = "javascript"
    supported_extensions = [".js", ".jsx", ".mjs", ".cjs"]
    
    def __init__(self):
        self.patterns = {
            # Functions
            'function': re.compile(
                r'^(\s*)((?:async\s+)?(?:export\s+(?:default\s+)?)?function)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            'arrow_function': re.compile(
                r'^(\s*)((?:export\s+)?(?:const|let|var))\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>\s*\{',
                re.MULTILINE
            ),
            'method': re.compile(
                r'^(\s*)((?:async\s+)?(?:static\s+)?)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            # Classes
            'class': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?class)\s+'
                r'([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?:extends\s+[a-zA-Z_$][a-zA-Z0-9_$]*)?\s*\{',
                re.MULTILINE
            ),
            # Variables and constants
            'const': re.compile(
                r'^(\s*)((?:export\s+)?const)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                re.MULTILINE
            ),
            'let': re.compile(
                r'^(\s*)(let)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                re.MULTILINE
            ),
            'var': re.compile(
                r'^(\s*)(var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)',
                re.MULTILINE
            ),
            # Imports/Exports
            'import': re.compile(
                r'^(\s*)(import)\s+([^;]+);?',
                re.MULTILINE
            ),
            'require': re.compile(
                r'^(\s*)(const|let|var)\s+([^=]+)=\s*require\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)',
                re.MULTILINE
            ),
            # Object literals
            'object_method': re.compile(
                r'^(\s*)([a-zA-Z_$][a-zA-Z0-9_$]*)\s*:\s*(?:async\s+)?function\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse JavaScript code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'require']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_js_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_js_element(self, match, pattern_name: str, 
                          lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from JavaScript match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Determine element type
        if pattern_name in ['function', 'arrow_function', 'method', 'object_method']:
            element_type = ElementType.FUNCTION
        elif pattern_name == 'class':
            element_type = ElementType.CLASS
        else:
            element_type = ElementType.CONSTANT if 'const' in declaration else ElementType.VARIABLE
        
        # Determine visibility (JavaScript conventions)
        if name.startswith('_'):
            visibility = Visibility.PRIVATE
        elif 'export' in declaration:
            visibility = Visibility.PUBLIC
        else:
            visibility = Visibility.INTERNAL
        
        # Find block end
        if pattern_name in ['function', 'arrow_function', 'method', 'class', 'object_method']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'declaration': declaration.strip(),
            'indent_level': len(indent),
            'is_exported': 'export' in declaration,
            'is_default_export': 'export default' in declaration,
            'is_async': 'async' in declaration,
            'pattern_type': pattern_name
        }
        
        if pattern_name == 'class':
            metadata.update({
                'has_extends': 'extends' in match.group(0),
                'parent_class': self._extract_parent_class(match.group(0))
            })
        elif pattern_name in ['function', 'arrow_function', 'method']:
            metadata.update({
                'is_arrow_function': pattern_name == 'arrow_function',
                'is_method': pattern_name == 'method',
                'is_static': 'static' in declaration,
                'parameters': self._extract_js_parameters(match.group(0))
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
        """Extract JavaScript import/require statements."""
        dependencies = []
        
        # ES6 imports
        for match in self.patterns['import'].finditer(content):
            line_num = content[:match.start()].count('\n')
            import_stmt = match.group(3).strip()
            
            # Parse different import patterns
            if 'from' in import_stmt:
                # import { a, b } from 'module'
                # import * as name from 'module'
                # import name from 'module'
                parts = import_stmt.split(' from ')
                if len(parts) == 2:
                    imports = parts[0].strip()
                    module = parts[1].strip().strip('\'"')
                    
                    if imports.startswith('{') and imports.endswith('}'):
                        # Named imports
                        names = imports.strip('{}').split(',')
                        for name in names:
                            name = name.strip()
                            if ' as ' in name:
                                orig_name, alias = name.split(' as ')
                                dependencies.append(DependencyInfo(
                                    name=orig_name.strip(),
                                    import_type='import',
                                    source=module,
                                    alias=alias.strip(),
                                    line_number=line_num
                                ))
                            else:
                                dependencies.append(DependencyInfo(
                                    name=name,
                                    import_type='import',
                                    source=module,
                                    line_number=line_num
                                ))
                    else:
                        # Default or namespace import
                        name = imports.replace('* as ', '').strip()
                        dependencies.append(DependencyInfo(
                            name=name,
                            import_type='import',
                            source=module,
                            line_number=line_num
                        ))
        
        # CommonJS requires
        for match in self.patterns['require'].finditer(content):
            line_num = content[:match.start()].count('\n')
            var_name = match.group(3).strip()
            module = match.group(4)
            
            dependencies.append(DependencyInfo(
                name=var_name,
                import_type='require',
                source=module,
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_parent_class(self, match_text: str) -> Optional[str]:
        """Extract parent class from extends clause."""
        extends_match = re.search(r'extends\s+([a-zA-Z_$][a-zA-Z0-9_$]*)', match_text)
        return extends_match.group(1) if extends_match else None
    
    def _extract_js_parameters(self, signature: str) -> List[str]:
        """Extract parameters from function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        # Simple parameter extraction
        params = []
        for param in params_str.split(','):
            param = param.strip()
            # Handle destructuring and default parameters
            param = param.split('=')[0].strip()  # Remove default values
            param = re.sub(r'^\.\.\.', '', param)  # Remove spread operator
            if param:
                params.append(param)
        
        return params
