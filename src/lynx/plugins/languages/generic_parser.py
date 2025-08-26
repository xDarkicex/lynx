"""Generic fallback parser for languages without specific implementations."""

import re
from typing import List, Dict, Any, Optional, Set
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class GenericParser(BaseLanguageParser):
    """Generic parser that works across multiple programming languages."""
    
    language_name = "generic"
    supported_extensions = [
        # Catch-all for unsupported extensions
        ".txt", ".md", ".rst", ".cfg", ".conf", ".ini", ".toml",
        ".xml", ".html", ".css", ".scss", ".less", ".sql",
        ".dockerfile", ".makefile", ".cmake", ".gradle"
    ]
    
    def __init__(self):
        # Generic patterns that work across many C-style languages
        self.patterns = {
            # C-style function definitions
            'c_style_function': re.compile(
                r'^(\s*)((?:public|private|protected|static|async|virtual|override|extern|inline)?\s*)*'
                r'(?:[a-zA-Z_][a-zA-Z0-9_<>,\s]*\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # Class definitions (C++, Java, C#, etc.)
            'class_definition': re.compile(
                r'^(\s*)((?:public|private|protected|abstract|final|static)?\s*)*'
                r'(class|struct|interface)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s*:\s*[^{]+)?(?:\s*implements\s+[^{]+)?(?:\s*extends\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            
            # Method definitions in classes
            'method_definition': re.compile(
                r'^(\s+)((?:public|private|protected|static|virtual|override|async)?\s*)*'
                r'(?:[a-zA-Z_][a-zA-Z0-9_<>,\s]*\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # Variable/field declarations
            'variable_declaration': re.compile(
                r'^(\s*)((?:public|private|protected|static|const|final|var|let)?\s*)*'
                r'([a-zA-Z_][a-zA-Z0-9_<>,\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[=;]',
                re.MULTILINE
            ),
            
            # Constants
            'constant_declaration': re.compile(
                r'^(\s*)(const|#define|final|static\s+final)\s+([A-Z_][A-Z0-9_]*)',
                re.MULTILINE
            ),
            
            # Namespace/package/module declarations
            'namespace': re.compile(
                r'^(\s*)(namespace|package|module)\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
                re.MULTILINE
            ),
            
            # Import/include statements
            'import_statement': re.compile(
                r'^(\s*)(#include|import|using|require|from)\s+([^;\n]+)',
                re.MULTILINE
            ),
            
            # Enum definitions
            'enum_definition': re.compile(
                r'^(\s*)(enum)\s+([A-Z][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            
            # Function-like macros or defines
            'macro_definition': re.compile(
                r'^(\s*)(#define)\s+([A-Z_][A-Z0-9_]*)\s*\(',
                re.MULTILINE
            ),
            
            # Comments for documentation extraction
            'doc_comment': re.compile(
                r'^(\s*)(///?|/\*\*|\*|#|"""|\'\'\')\s*(.*?)(?:\*/|$)',
                re.MULTILINE
            ),
        }
        
        # Language-specific adjustments based on file extension
        self.language_adjustments = {
            '.java': {'language': 'java', 'style': 'c_style'},
            '.cs': {'language': 'csharp', 'style': 'c_style'},
            '.cpp': {'language': 'cpp', 'style': 'c_style'},
            '.cc': {'language': 'cpp', 'style': 'c_style'},
            '.c': {'language': 'c', 'style': 'c_style'},
            '.h': {'language': 'c', 'style': 'c_style'},
            '.hpp': {'language': 'cpp', 'style': 'c_style'},
            '.php': {'language': 'php', 'style': 'c_style'},
            '.scala': {'language': 'scala', 'style': 'c_style'},
            '.kt': {'language': 'kotlin', 'style': 'c_style'},
            '.swift': {'language': 'swift', 'style': 'c_style'},
            '.sql': {'language': 'sql', 'style': 'sql'},
            '.html': {'language': 'html', 'style': 'markup'},
            '.xml': {'language': 'xml', 'style': 'markup'},
            '.css': {'language': 'css', 'style': 'css'},
            '.scss': {'language': 'scss', 'style': 'css'},
            '.yaml': {'language': 'yaml', 'style': 'data'},
            '.yml': {'language': 'yaml', 'style': 'data'},
            '.json': {'language': 'json', 'style': 'data'},
            '.toml': {'language': 'toml', 'style': 'data'},
            '.dockerfile': {'language': 'dockerfile', 'style': 'script'},
            '.makefile': {'language': 'makefile', 'style': 'script'},
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse code elements using generic patterns."""
        elements = []
        lines = content.split('\n')
        
        # Determine language characteristics from file extension
        file_ext = self._get_file_extension(file_path)
        lang_info = self.language_adjustments.get(file_ext, {'language': 'unknown', 'style': 'generic'})
        detected_language = lang_info['language']
        style = lang_info['style']
        
        # Skip parsing for data files and markup unless they're complex
        if style in ['data', 'markup'] and len(lines) < 50:
            return self._parse_simple_structure(content, detected_language, file_path)
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import_statement', 'doc_comment']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_generic_element(
                        match, pattern_name, lines, content, detected_language, file_path
                    )
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_generic_element(self, match, pattern_name: str, lines: List[str],
                               content: str, language: str, file_path: str) -> ParsedElement:
        """Create a generic parsed element."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        modifiers = groups[1] if len(groups) > 1 else ""
        
        # Extract name and type based on pattern
        if pattern_name == 'c_style_function':
            name = groups[2] if len(groups) > 2 else "unnamed_function"
            element_type = ElementType.FUNCTION
        elif pattern_name == 'class_definition':
            class_type = groups[2] if len(groups) > 2 else "class"
            name = groups[3] if len(groups) > 3 else "UnnamedClass"
            element_type = ElementType.CLASS if class_type == 'class' else ElementType.STRUCT
        elif pattern_name == 'method_definition':
            name = groups[2] if len(groups) > 2 else "unnamed_method"
            element_type = ElementType.METHOD
        elif pattern_name == 'variable_declaration':
            name = groups[3] if len(groups) > 3 else "unnamed_variable"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'constant_declaration':
            name = groups[2] if len(groups) > 2 else "UNNAMED_CONSTANT"
            element_type = ElementType.CONSTANT
        elif pattern_name == 'namespace':
            name = groups[2] if len(groups) > 2 else "unnamed_namespace"
            element_type = ElementType.NAMESPACE
        elif pattern_name == 'enum_definition':
            name = groups[2] if len(groups) > 2 else "UnnamedEnum"
            element_type = ElementType.ENUM
        elif pattern_name == 'macro_definition':
            name = groups[2] if len(groups) > 2 else "UNNAMED_MACRO"
            element_type = ElementType.FUNCTION  # Treat macros as function-like
        else:
            return None
        
        start_line = content[:match.start()].count('\n')
        
        # Determine visibility from modifiers
        visibility = self._extract_visibility_from_modifiers(modifiers, name)
        
        # Find block end
        if pattern_name in ['c_style_function', 'class_definition', 'method_definition', 'enum_definition']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Generic metadata
        metadata = {
            'pattern_type': pattern_name,
            'language': language,
            'modifiers': modifiers.strip().split() if modifiers else [],
            'indent_level': len(indent),
            'file_extension': self._get_file_extension(file_path),
            'is_generic_parse': True,
            'confidence': self._calculate_confidence(pattern_name, content_lines, language)
        }
        
        # Add pattern-specific metadata
        if pattern_name == 'class_definition':
            metadata.update({
                'class_type': groups[2] if len(groups) > 2 else "class",
                'inheritance': self._extract_inheritance(match.group(0))
            })
        elif pattern_name in ['c_style_function', 'method_definition']:
            metadata.update({
                'parameters': self._extract_generic_parameters(match.group(0)),
                'return_type': self._extract_generic_return_type(match.group(0), modifiers)
            })
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=visibility,
            language=language,
            content=content_lines,
            metadata=metadata
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract generic import/dependency information."""
        dependencies = []
        
        for match in self.patterns['import_statement'].finditer(content):
            line_num = content[:match.start()].count('\n')
            import_type = match.group(2).strip()
            import_path = match.group(3).strip().rstrip(';')
            
            # Clean up import path
            import_path = import_path.strip('"\'<>')
            
            # Extract name from path
            if import_type in ['#include']:
                name = import_path.split('/')[-1].split('.')[0]
            elif import_type in ['import', 'using']:
                name = import_path.split('.')[-1]
            elif import_type == 'from':
                # Handle "from X import Y" patterns
                parts = import_path.split(' import ')
                if len(parts) == 2:
                    name = parts[1].strip()
                    import_path = parts[0].strip()
                else:
                    name = import_path
            else:
                name = import_path.split('/')[-1].split('.')[-1]
            
            dependencies.append(DependencyInfo(
                name=name,
                import_type=import_type,
                source=import_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _parse_simple_structure(self, content: str, language: str, file_path: str) -> List[ParsedElement]:
        """Parse simple structure files (JSON, YAML, etc.)."""
        elements = []
        lines = content.split('\n')
        
        if language == 'json':
            elements.extend(self._parse_json_structure(content, lines))
        elif language in ['yaml', 'yml']:
            elements.extend(self._parse_yaml_structure(content, lines))
        elif language == 'dockerfile':
            elements.extend(self._parse_dockerfile_structure(content, lines))
        elif language in ['html', 'xml']:
            elements.extend(self._parse_markup_structure(content, lines, language))
        elif language == 'css':
            elements.extend(self._parse_css_structure(content, lines))
        elif language == 'sql':
            elements.extend(self._parse_sql_structure(content, lines))
        
        return elements
    
    def _parse_json_structure(self, content: str, lines: List[str]) -> List[ParsedElement]:
        """Parse JSON structure."""
        elements = []
        
        # Find top-level keys
        key_pattern = re.compile(r'^(\s*)"([^"]+)"\s*:', re.MULTILINE)
        for match in key_pattern.finditer(content):
            start_line = content[:match.start()].count('\n')
            key_name = match.group(2)
            
            elements.append(ParsedElement(
                name=key_name,
                element_type=ElementType.VARIABLE,
                start_line=start_line,
                end_line=start_line + 1,
                visibility=Visibility.PUBLIC,
                language='json',
                content=lines[start_line],
                metadata={'type': 'json_key', 'is_top_level': True}
            ))
        
        return elements
    
    def _parse_yaml_structure(self, content: str, lines: List[str]) -> List[ParsedElement]:
        """Parse YAML structure."""
        elements = []
        
        # Find top-level keys
        key_pattern = re.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\s*:', re.MULTILINE)
        for match in key_pattern.finditer(content):
            start_line = content[:match.start()].count('\n')
            key_name = match.group(1)
            
            elements.append(ParsedElement(
                name=key_name,
                element_type=ElementType.VARIABLE,
                start_line=start_line,
                end_line=start_line + 1,
                visibility=Visibility.PUBLIC,
                language='yaml',
                content=lines[start_line],
                metadata={'type': 'yaml_key', 'is_top_level': True}
            ))
        
        return elements
    
    def _parse_dockerfile_structure(self, content: str, lines: List[str]) -> List[ParsedElement]:
        """Parse Dockerfile structure."""
        elements = []
        
        # Find Dockerfile instructions
        instruction_pattern = re.compile(r'^([A-Z]+)\s+(.+)', re.MULTILINE)
        for match in instruction_pattern.finditer(content):
            start_line = content[:match.start()].count('\n')
            instruction = match.group(1)
            args = match.group(2)
            
            elements.append(ParsedElement(
                name=f"{instruction}_{start_line}",
                element_type=ElementType.FUNCTION,
                start_line=start_line,
                end_line=start_line + 1,
                visibility=Visibility.PUBLIC,
                language='dockerfile',
                content=lines[start_line],
                metadata={
                    'instruction': instruction,
                    'arguments': args,
                    'type': 'dockerfile_instruction'
                }
            ))
        
        return elements
    
    def _parse_markup_structure(self, content: str, lines: List[str], language: str) -> List[ParsedElement]:
        """Parse HTML/XML structure."""
        elements = []
        
        # Find tags
        tag_pattern = re.compile(r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*>', re.MULTILINE)
        for match in tag_pattern.finditer(content):
            start_line = content[:match.start()].count('\n')
            tag_name = match.group(1)
            
            elements.append(ParsedElement(
                name=tag_name,
                element_type=ElementType.CLASS,
                start_line=start_line,
                end_line=start_line + 1,
                visibility=Visibility.PUBLIC,
                language=language,
                content=lines[start_line],
                metadata={'type': f'{language}_tag', 'tag_name': tag_name}
            ))
        
        return elements
    
    def _parse_css_structure(self, content: str, lines: List[str]) -> List[ParsedElement]:
        """Parse CSS structure."""
        elements = []
        
        # Find CSS selectors
        selector_pattern = re.compile(r'^([^{]+)\s*\{', re.MULTILINE)
        for match in selector_pattern.finditer(content):
            start_line = content[:match.start()].count('\n')
            selector = match.group(1).strip()
            
            elements.append(ParsedElement(
                name=selector,
                element_type=ElementType.CLASS,
                start_line=start_line,
                end_line=self._find_block_end(lines, start_line, 'brace'),
                visibility=Visibility.PUBLIC,
                language='css',
                content='\n'.join(lines[start_line:self._find_block_end(lines, start_line, 'brace')]),
                metadata={'type': 'css_selector', 'selector': selector}
            ))
        
        return elements
    
    def _parse_sql_structure(self, content: str, lines: List[str]) -> List[ParsedElement]:
        """Parse SQL structure."""
        elements = []
        
        # Find SQL statements
        sql_patterns = {
            'table': re.compile(r'CREATE\s+TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE | re.MULTILINE),
            'function': re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?(?:FUNCTION|PROCEDURE)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE | re.MULTILINE),
            'view': re.compile(r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE | re.MULTILINE),
            'index': re.compile(r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE | re.MULTILINE),
        }
        
        for element_type, pattern in sql_patterns.items():
            for match in pattern.finditer(content):
                start_line = content[:match.start()].count('\n')
                name = match.group(1)
                
                elements.append(ParsedElement(
                    name=name,
                    element_type=ElementType.CLASS if element_type == 'table' else ElementType.FUNCTION,
                    start_line=start_line,
                    end_line=start_line + 10,  # Rough estimate
                    visibility=Visibility.PUBLIC,
                    language='sql',
                    content=lines[start_line],
                    metadata={'type': f'sql_{element_type}', 'sql_type': element_type}
                ))
        
        return elements
    
    def _get_file_extension(self, file_path: str) -> str:
        """Get file extension from path."""
        if not file_path:
            return ""
        return Path(file_path).suffix.lower() if hasattr(Path, 'suffix') else ""
    
    def _extract_visibility_from_modifiers(self, modifiers: str, name: str) -> Visibility:
        """Extract visibility from modifiers string."""
        if not modifiers:
            # Use naming conventions
            if name.startswith('_'):
                return Visibility.PRIVATE
            elif name.isupper():
                return Visibility.PUBLIC  # Constants are typically public
            else:
                return Visibility.PUBLIC  # Default to public for generic parsing
        
        modifiers_lower = modifiers.lower()
        if 'private' in modifiers_lower:
            return Visibility.PRIVATE
        elif 'protected' in modifiers_lower:
            return Visibility.PROTECTED
        elif 'public' in modifiers_lower:
            return Visibility.PUBLIC
        else:
            return Visibility.PUBLIC
    
    def _extract_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from class definition."""
        inheritance = []
        
        # C++ style inheritance
        if ':' in class_def:
            parts = class_def.split(':')[-1].split('{')[0].strip()
            inheritance.extend([base.strip() for base in parts.split(',')])
        
        # Java/C# style inheritance
        extends_match = re.search(r'extends\s+([^{]+)', class_def)
        if extends_match:
            inheritance.append(extends_match.group(1).strip())
        
        implements_match = re.search(r'implements\s+([^{]+)', class_def)
        if implements_match:
            interfaces = implements_match.group(1).strip()
            inheritance.extend([i.strip() for i in interfaces.split(',')])
        
        return inheritance
    
    def _extract_generic_parameters(self, signature: str) -> List[str]:
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
            if param:
                # Take the last word as parameter name
                words = param.split()
                if words:
                    params.append(words[-1])
        
        return params
    
    def _extract_generic_return_type(self, signature: str, modifiers: str) -> str:
        """Extract return type from function signature."""
        # Look for return type before function name
        parts = signature.split('(')[0].strip().split()
        if len(parts) >= 2:
            # Exclude modifiers
            modifier_words = {'public', 'private', 'protected', 'static', 'virtual', 'async', 'override'}
            type_parts = [p for p in parts[:-1] if p.lower() not in modifier_words]
            if type_parts:
                return ' '.join(type_parts)
        
        return 'void'  # Default assumption
    
    def _calculate_confidence(self, pattern_name: str, content: str, language: str) -> float:
        """Calculate confidence score for the parse."""
        # Base confidence
        confidence = 0.7
        
        # Adjust based on pattern type
        pattern_confidence = {
            'class_definition': 0.9,
            'c_style_function': 0.8,
            'method_definition': 0.8,
            'namespace': 0.9,
            'enum_definition': 0.9,
            'constant_declaration': 0.7,
            'variable_declaration': 0.6,
            'macro_definition': 0.8
        }
        
        confidence = pattern_confidence.get(pattern_name, confidence)
        
        # Adjust based on language specificity
        if language != 'unknown':
            confidence += 0.1
        
        # Adjust based on content characteristics
        if '{' in content and '}' in content:
            confidence += 0.1
        
        return min(confidence, 1.0)
