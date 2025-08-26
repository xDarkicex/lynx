"""Comprehensive C language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class CParser(BaseLanguageParser):
    """Advanced C language parser."""
    
    language_name = "c"
    supported_extensions = [".c", ".h"]
    
    def __init__(self):
        self.patterns = {
            # Functions
            'function': re.compile(
                r'^(\s*)((?:static\s+|extern\s+|inline\s+)*[a-zA-Z_][a-zA-Z0-9_*\s]*)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^{;]*\)\s*\{',
                re.MULTILINE | re.DOTALL
            ),
            # Function declarations (prototypes)
            'function_decl': re.compile(
                r'^(\s*)((?:static\s+|extern\s+|inline\s+)*[a-zA-Z_][a-zA-Z0-9_*\s]*)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^{]*\)\s*;',
                re.MULTILINE | re.DOTALL
            ),
            # Structs
            'struct': re.compile(
                r'^(\s*)(struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            'struct_typedef': re.compile(
                r'^(\s*)(typedef\s+struct)(?:\s+([a-zA-Z_][a-zA-Z0-9_]*))?\s*\{[^}]*\}\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*;',
                re.MULTILINE | re.DOTALL
            ),
            # Unions
            'union': re.compile(
                r'^(\s*)(union)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            # Enums
            'enum': re.compile(
                r'^(\s*)(enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            'enum_typedef': re.compile(
                r'^(\s*)(typedef\s+enum)(?:\s+([a-zA-Z_][a-zA-Z0-9_]*))?\s*\{[^}]*\}\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*;',
                re.MULTILINE | re.DOTALL
            ),
            # Typedefs
            'typedef': re.compile(
                r'^(\s*)(typedef)\s+([^;]+)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;',
                re.MULTILINE
            ),
            # Global variables
            'global_var': re.compile(
                r'^(\s*)((?:static\s+|extern\s+|const\s+)*[a-zA-Z_][a-zA-Z0-9_*\s]*)\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*(?:\[[^\]]*\])*)\s*(?:=|;)',
                re.MULTILINE
            ),
            # Macros
            'macro': re.compile(
                r'^(\s*)(#define)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            # Includes
            'include': re.compile(
                r'^(\s*)(#include)\s*[<"]([^>"]+)[>"]',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse C code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name == 'include':  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_c_element(match, pattern_name, lines, content, file_path)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_c_element(self, match, pattern_name: str, lines: List[str], 
                         content: str, file_path: str) -> ParsedElement:
        """Create ParsedElement from C match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = self._extract_name(groups, pattern_name)
        
        start_line = content[:match.start()].count('\n')
        
        # Map C constructs to element types
        type_mapping = {
            'function': ElementType.FUNCTION,
            'function_decl': ElementType.FUNCTION,
            'struct': ElementType.STRUCT,
            'struct_typedef': ElementType.STRUCT,
            'union': ElementType.STRUCT,  # Treat union as struct-like
            'enum': ElementType.ENUM,
            'enum_typedef': ElementType.ENUM,
            'typedef': ElementType.CLASS,  # Treat typedef as class-like
            'global_var': ElementType.VARIABLE,
            'macro': ElementType.CONSTANT
        }
        
        element_type = type_mapping.get(pattern_name, ElementType.FUNCTION)
        
        # Determine visibility
        visibility = self._extract_c_visibility(declaration, file_path)
        
        # Find block end
        if pattern_name in ['function']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name in ['struct', 'union', 'enum']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name in ['struct_typedef', 'enum_typedef', 'typedef']:
            end_line = self._find_typedef_end(lines, start_line)
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Extract C-specific metadata
        metadata = {
            'declaration': declaration.strip(),
            'indent_level': len(indent),
            'pattern_type': pattern_name,
            'is_static': 'static' in declaration,
            'is_extern': 'extern' in declaration,
            'is_inline': 'inline' in declaration,
            'is_const': 'const' in declaration,
        }
        
        if pattern_name in ['function', 'function_decl']:
            metadata.update({
                'return_type': self._extract_c_return_type(declaration, name),
                'parameters': self._extract_c_parameters(match.group(0)),
                'is_declaration_only': pattern_name == 'function_decl'
            })
        elif pattern_name in ['struct_typedef', 'enum_typedef']:
            metadata.update({
                'typedef_name': groups[3] if len(groups) > 3 else name,
                'original_name': groups[2] if len(groups) > 2 else None
            })
        elif pattern_name == 'typedef':
            metadata.update({
                'original_type': groups[2] if len(groups) > 2 else '',
                'is_pointer': '*' in (groups[2] if len(groups) > 2 else '')
            })
        elif pattern_name == 'global_var':
            metadata.update({
                'variable_type': self._extract_variable_type(declaration, name),
                'is_array': '[' in name,
                'is_pointer': '*' in declaration
            })
        elif pattern_name == 'macro':
            metadata.update({
                'macro_value': self._extract_macro_value(match.group(0))
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
        """Extract C include statements."""
        dependencies = []
        
        for match in self.patterns['include'].finditer(content):
            line_num = content[:match.start()].count('\n')
            header_name = match.group(3)
            
            # Determine if it's a system header or local header
            include_type = 'system_include' if match.group(0).find('<') != -1 else 'local_include'
            
            dependencies.append(DependencyInfo(
                name=header_name,
                import_type=include_type,
                source=header_name,
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_name(self, groups, pattern_name: str) -> str:
        """Extract name based on pattern type."""
        if pattern_name in ['struct_typedef', 'enum_typedef']:
            # For typedef struct/enum, use the typedef name (last group)
            return groups[3] if len(groups) > 3 else (groups[2] if len(groups) > 2 else "unnamed")
        else:
            # For most patterns, name is in group 2 (0-indexed)
            return groups[2] if len(groups) > 2 else "unnamed"
    
    def _extract_c_visibility(self, declaration: str, file_path: str) -> Visibility:
        """Determine C visibility based on static keyword and file type."""
        if 'static' in declaration:
            return Visibility.PRIVATE
        elif file_path.endswith('.h'):
            return Visibility.PUBLIC  # Header file declarations are typically public
        else:
            return Visibility.INTERNAL  # C file functions without static
    
    def _extract_c_return_type(self, declaration: str, func_name: str) -> str:
        """Extract return type from C function declaration."""
        # Remove function name and everything after it
        before_name = declaration.split(func_name)[0].strip()
        # Remove storage class specifiers
        return_type = before_name.replace('static', '').replace('extern', '').replace('inline', '').strip()
        return return_type or 'void'
    
    def _extract_c_parameters(self, signature: str) -> List[Dict[str, str]]:
        """Extract parameters from C function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str or params_str == 'void':
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Simple parameter parsing - could be enhanced
                parts = param.split()
                if parts:
                    param_name = parts[-1].strip('*')
                    param_type = ' '.join(parts[:-1]) if len(parts) > 1 else 'int'
                    
                    params.append({
                        'name': param_name,
                        'type': param_type
                    })
        
        return params
    
    def _extract_variable_type(self, declaration: str, var_name: str) -> str:
        """Extract variable type from declaration."""
        # Remove variable name and everything after it
        before_name = declaration.split(var_name)[0].strip()
        # Remove storage class specifiers
        var_type = before_name.replace('static', '').replace('extern', '').replace('const', '').strip()
        return var_type or 'int'
    
    def _extract_macro_value(self, macro_line: str) -> Optional[str]:
        """Extract macro value from #define line."""
        parts = macro_line.split(None, 2)
        return parts[2] if len(parts) > 2 else None
    
    def _find_typedef_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a typedef statement."""
        if start_line >= len(lines):
            return start_line
        
        # Look for the semicolon that ends the typedef
        for i in range(start_line, len(lines)):
            if ';' in lines[i]:
                return i + 1
        
        return start_line + 1
