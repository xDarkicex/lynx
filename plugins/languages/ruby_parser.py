"""Comprehensive Ruby language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class RubyParser(BaseLanguageParser):
    """Advanced Ruby language parser."""
    
    language_name = "ruby"
    supported_extensions = [".rb"]
    
    def __init__(self):
        self.patterns = {
            'class': re.compile(
                r'^(\s*)class\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s*<\s*[^;\n]+)?(?:\s*;|\s*$|\s*\n)',
                re.MULTILINE
            ),
            'module': re.compile(
                r'^(\s*)module\s+([A-Z][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            'method': re.compile(
                r'^(\s*)def\s+(?:(self\.)|([a-zA-Z_][a-zA-Z0-9_]*\.))?([a-zA-Z_][a-zA-Z0-9_!?]*)'
                r'(?:\([^)]*\))?',
                re.MULTILINE
            ),
            'attr': re.compile(
                r'^(\s*)(attr_(?:reader|writer|accessor))\s+(.+)',
                re.MULTILINE
            ),
            'constant': re.compile(
                r'^(\s*)([A-Z_][A-Z0-9_]*)\s*=',
                re.MULTILINE
            ),
            'require': re.compile(
                r'^(?:require|require_relative|load)\s*[\'"]([^\'"]+)[\'"]',
                re.MULTILINE
            ),
            'include': re.compile(
                r'^(\s*)(?:include|extend|prepend)\s+([A-Z][a-zA-Z0-9_:]*)',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Ruby code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['require', 'include']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_ruby_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_ruby_element(self, match, pattern_name: str, 
                            lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Ruby match."""
        groups = match.groups()
        start_line = content[:match.start()].count('\n')
        indent = groups[0] if len(groups) > 0 else ""
        
        if pattern_name == 'class':
            name = groups[1] if len(groups) > 1 else "UnnamedClass"
            element_type = ElementType.CLASS
        elif pattern_name == 'module':
            name = groups[1] if len(groups) > 1 else "UnnamedModule"
            element_type = ElementType.MODULE
        elif pattern_name == 'method':
            method_name = groups[3] if len(groups) > 3 else "unnamed_method"
            if groups[1]:  # self.method
                name = f"self.{method_name}"
            elif groups[2]:  # Class.method
                name = f"{groups[2]}{method_name}"
            else:
                name = method_name
            element_type = ElementType.METHOD
        elif pattern_name == 'attr':
            attr_type = groups[1] if len(groups) > 1 else "attr_accessor"
            attr_names = groups[2] if len(groups) > 2 else ""
            name = f"{attr_type}({attr_names})"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'constant':
            name = groups[1] if len(groups) > 1 else "UNNAMED_CONSTANT"
            element_type = ElementType.CONSTANT
        else:
            return None
        
        # Extract visibility (Ruby uses private/protected keywords)
        visibility = self._extract_ruby_visibility(indent, start_line, lines)
        
        # Find block end
        if pattern_name in ['class', 'module', 'method']:
            end_line = self._find_ruby_block_end(lines, start_line, pattern_name)
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'pattern_type': pattern_name,
            'indent_level': len(indent),
            'is_class_method': bool(groups[1] if pattern_name == 'method' and len(groups) > 1 else False),
            'ends_with_punctuation': name.endswith(('!', '?')) if pattern_name == 'method' else False,
        }
        
        if pattern_name == 'class':
            metadata.update({
                'inheritance': self._extract_ruby_inheritance(match.group(0))
            })
        elif pattern_name == 'method':
            metadata.update({
                'parameters': self._extract_ruby_parameters(match.group(0))
            })
        elif pattern_name == 'attr':
            metadata.update({
                'attr_type': groups[1] if len(groups) > 1 else "attr_accessor",
                'attributes': self._extract_attr_names(groups[2] if len(groups) > 2 else "")
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
        """Extract Ruby require, include, and extend statements."""
        dependencies = []
        
        # Require statements
        require_matches = self.patterns['require'].finditer(content)
        for match in require_matches:
            line_num = content[:match.start()].count('\n')
            require_path = match.group(1).strip()
            
            import_type = 'require'
            if 'require_relative' in match.group(0):
                import_type = 'require_relative'
            elif 'load' in match.group(0):
                import_type = 'load'
            
            dependencies.append(DependencyInfo(
                name=require_path.split('/')[-1].replace('.rb', ''),
                import_type=import_type,
                source=require_path,
                line_number=line_num
            ))
        
        # Include/extend/prepend statements
        include_matches = self.patterns['include'].finditer(content)
        for match in include_matches:
            line_num = content[:match.start()].count('\n')
            module_name = match.group(1).strip()
            
            import_type = 'include'
            if 'extend' in match.group(0):
                import_type = 'extend'
            elif 'prepend' in match.group(0):
                import_type = 'prepend'
            
            dependencies.append(DependencyInfo(
                name=module_name.split('::')[-1],
                import_type=import_type,
                source=module_name,
                line_number=line_num
            ))
        
        return dependencies
    
    def _extract_ruby_visibility(self, indent: str, start_line: int, lines: List[str]) -> Visibility:
        """Extract visibility from Ruby code context."""
        # Look backwards for visibility modifiers
        for i in range(start_line - 1, max(0, start_line - 10), -1):
            line = lines[i].strip()
            if line == 'private':
                return Visibility.PRIVATE
            elif line == 'protected':
                return Visibility.PROTECTED
            elif line == 'public':
                return Visibility.PUBLIC
            elif line.startswith('def ') or line.startswith('class ') or line.startswith('module '):
                break
        
        return Visibility.PUBLIC  # Default in Ruby
    
    def _find_ruby_block_end(self, lines: List[str], start_line: int, pattern_name: str) -> int:
        """Find the end of a Ruby block (looking for 'end' keyword)."""
        if start_line >= len(lines):
            return start_line
        
        level = 1
        keywords_that_increase = {'class', 'module', 'def', 'if', 'unless', 'while', 'until', 'for', 'begin', 'case'}
        
        for i in range(start_line + 1, len(lines)):
            line = lines[i].strip()
            
            # Count keywords that increase nesting
            for keyword in keywords_that_increase:
                if re.match(rf'\b{keyword}\b', line):
                    level += 1
                    break
            
            # Count 'end' keywords
            if re.match(r'\bend\b', line):
                level -= 1
                if level == 0:
                    return i + 1
        
        return len(lines)
    
    def _extract_ruby_inheritance(self, class_def: str) -> List[str]:
        """Extract inheritance information from Ruby class definition."""
        inheritance_match = re.search(r'<\s*([^\s\n;]+)', class_def)
        if inheritance_match:
            return [inheritance_match.group(1)]
        return []
    
    def _extract_ruby_parameters(self, signature: str) -> List[str]:
        """Extract parameters from Ruby method signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        
        if paren_match:
            params_str = paren_match.group(1).strip()
        else:
            # Ruby methods can have parameters without parentheses
            method_match = re.search(r'def\s+(?:self\.)?[a-zA-Z_][a-zA-Z0-9_!?]*\s+(.+)', signature)
            if method_match:
                params_str = method_match.group(1).strip()
            else:
                return []
        
        if not params_str:
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Handle various Ruby parameter types
                if param.startswith('**'):  # keyword splat
                    params.append(param)
                elif param.startswith('*'):  # splat
                    params.append(param)
                elif param.startswith('&'):  # block
                    params.append(param)
                elif '=' in param:  # default value
                    params.append(param.split('=')[0].strip())
                else:
                    params.append(param)
        
        return params
    
    def _extract_attr_names(self, attr_str: str) -> List[str]:
        """Extract attribute names from attr_* declarations."""
        # Handle symbols and strings
        attr_matches = re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)|[\'"]([a-zA-Z_][a-zA-Z0-9_]*)[\'"]', attr_str)
        attrs = []
        for match in attr_matches:
            attrs.append(match[0] if match[0] else match[1])
        return attrs
