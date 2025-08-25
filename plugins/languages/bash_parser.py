"""Comprehensive Bash/Shell script parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class BashParser(BaseLanguageParser):
    """Advanced Bash/Shell script parser."""
    
    language_name = "bash"
    supported_extensions = [".sh", ".bash", ".zsh", ".fish", ".ksh"]
    
    def __init__(self):
        self.patterns = {
            # Functions
            'function': re.compile(
                r'^(\s*)(function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*\)\s*\{',
                re.MULTILINE
            ),
            
            # Alternative function syntax
            'function_alt': re.compile(
                r'^(\s*)function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            
            # Variable assignments
            'variable': re.compile(
                r'^(\s*)([A-Z_][A-Z0-9_]*)\s*=',
                re.MULTILINE
            ),
            
            # Local variables
            'local_variable': re.compile(
                r'^(\s*)(local|declare)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            
            # Arrays
            'array': re.compile(
                r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*\(',
                re.MULTILINE
            ),
            
            # Aliases
            'alias': re.compile(
                r'^(\s*)alias\s+([a-zA-Z_][a-zA-Z0-9_-]*)\s*=',
                re.MULTILINE
            ),
            
            # Source/Include statements
            'source': re.compile(
                r'^(\s*)(source|\.|bash)\s+([^\s;]+)',
                re.MULTILINE
            ),
            
            # Exported variables
            'export': re.compile(
                r'^(\s*)export\s+([A-Z_][A-Z0-9_]*)',
                re.MULTILINE
            ),
            
            # Conditionals (for complexity analysis)
            'conditional': re.compile(
                r'^(\s*)(if|elif|case)\s+',
                re.MULTILINE
            ),
            
            # Loops
            'loop': re.compile(
                r'^(\s*)(for|while|until)\s+',
                re.MULTILINE
            ),
            
            # Command substitutions
            'command_sub': re.compile(
                r'\$\(([^)]+)\)',
                re.MULTILINE
            ),
            
            # Here documents
            'heredoc': re.compile(
                r'<<\s*([A-Z_]+)',
                re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Bash script elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['source', 'command_sub', 'heredoc']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_bash_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_bash_element(self, match, pattern_name: str,
                            lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from Bash match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        
        # Extract name based on pattern
        if pattern_name in ['function', 'function_alt']:
            if pattern_name == 'function':
                name = groups[2] if len(groups) > 2 else "unnamed"
            else:  # function_alt
                name = groups[1] if len(groups) > 1 else "unnamed"
            element_type = ElementType.FUNCTION
        elif pattern_name in ['variable', 'export']:
            name = groups[1] if len(groups) > 1 else "unnamed"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'local_variable':
            declaration = groups[1] if len(groups) > 1 else ""
            name = groups[2] if len(groups) > 2 else "unnamed"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'array':
            name = groups[1] if len(groups) > 1 else "unnamed"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'alias':
            name = groups[1] if len(groups) > 1 else "unnamed"
            element_type = ElementType.CONSTANT
        else:
            return None
        
        start_line = content[:match.start()].count('\n')
        
        # Determine visibility (Bash doesn't have formal visibility, use conventions)
        if pattern_name == 'export':
            visibility = Visibility.PUBLIC
        elif name.startswith('_'):
            visibility = Visibility.PRIVATE
        elif pattern_name == 'local_variable':
            visibility = Visibility.PRIVATE
        else:
            visibility = Visibility.INTERNAL
        
        # Find block end
        if pattern_name in ['function', 'function_alt']:
            end_line = self._find_function_end(lines, start_line)
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Bash-specific metadata
        metadata = {
            'pattern_type': pattern_name,
            'indent_level': len(indent),
            'is_exported': pattern_name == 'export',
            'is_local': pattern_name == 'local_variable',
            'is_array': pattern_name == 'array',
            'shell_type': self._detect_shell_type(content_lines),
        }
        
        if pattern_name in ['function', 'function_alt']:
            metadata.update({
                'parameters': self._extract_function_params(content_lines),
                'uses_local': 'local ' in content_lines,
                'command_count': self._count_commands(content_lines),
                'has_conditionals': bool(re.search(r'\bif\b|\bcase\b', content_lines)),
                'has_loops': bool(re.search(r'\bfor\b|\bwhile\b|\buntil\b', content_lines)),
                'exit_codes': self._extract_exit_codes(content_lines)
            })
        elif pattern_name in ['variable', 'export', 'local_variable']:
            metadata.update({
                'initial_value': self._extract_variable_value(match.group(0)),
                'is_readonly': 'readonly' in content_lines,
                'variable_type': self._detect_variable_type(match.group(0))
            })
        elif pattern_name == 'array':
            metadata.update({
                'array_elements': self._count_array_elements(match.group(0)),
                'is_associative': self._is_associative_array(content_lines)
            })
        elif pattern_name == 'alias':
            metadata.update({
                'alias_command': self._extract_alias_command(match.group(0))
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
        """Extract Bash dependencies (source files, external commands)."""
        dependencies = []
        
        # Source files
        for match in self.patterns['source'].finditer(content):
            line_num = content[:match.start()].count('\n')
            source_type = match.group(2)  # source, ., or bash
            source_file = match.group(3)
            
            dependencies.append(DependencyInfo(
                name=source_file.split('/')[-1],
                import_type=source_type,
                source=source_file,
                line_number=line_num
            ))
        
        # External commands (heuristic detection)
        external_commands = self._extract_external_commands(content)
        for cmd in external_commands:
            dependencies.append(DependencyInfo(
                name=cmd,
                import_type='external_command',
                source=cmd,
                line_number=0  # Could be improved to find actual line
            ))
        
        return dependencies
    
    def _find_function_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a Bash function."""
        if start_line >= len(lines):
            return start_line
        
        brace_count = 0
        in_function = False
        
        for i in range(start_line, len(lines)):
            line = lines[i].strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Count braces
            brace_count += line.count('{') - line.count('}')
            
            if '{' in line:
                in_function = True
            
            if in_function and brace_count <= 0 and i > start_line:
                return i + 1
        
        return len(lines)
    
    def _detect_shell_type(self, content: str) -> str:
        """Detect shell type from shebang or content patterns."""
        if '#!/bin/bash' in content:
            return 'bash'
        elif '#!/bin/zsh' in content:
            return 'zsh'
        elif '#!/bin/sh' in content:
            return 'sh'
        elif '#!/usr/bin/fish' in content:
            return 'fish'
        elif '#!/bin/ksh' in content:
            return 'ksh'
        else:
            return 'bash'  # Default assumption
    
    def _extract_function_params(self, content: str) -> List[str]:
        """Extract function parameters (Bash uses $1, $2, etc.)."""
        params = set()
        param_pattern = r'\$([1-9]\d*|\*|@|#)'
        
        for match in re.finditer(param_pattern, content):
            param = match.group(1)
            params.add(f"${param}")
        
        return sorted(list(params))
    
    def _count_commands(self, content: str) -> int:
        """Count the number of commands in function content."""
        lines = [line.strip() for line in content.split('\n') 
                if line.strip() and not line.strip().startswith('#')]
        
        # Simple heuristic: count non-empty, non-comment lines
        # This is a rough estimate as Bash can have multiple commands per line
        return len(lines)
    
    def _extract_exit_codes(self, content: str) -> List[int]:
        """Extract exit codes used in the function."""
        exit_codes = set()
        exit_pattern = r'exit\s+(\d+)'
        
        for match in re.finditer(exit_pattern, content):
            code = int(match.group(1))
            exit_codes.add(code)
        
        return sorted(list(exit_codes))
    
    def _extract_variable_value(self, assignment: str) -> str:
        """Extract the initial value of a variable."""
        if '=' in assignment:
            value_part = assignment.split('=', 1)[1].strip()
            # Remove quotes if present
            if value_part.startswith('"') and value_part.endswith('"'):
                return value_part[1:-1]
            elif value_part.startswith("'") and value_part.endswith("'"):
                return value_part[1:-1]
            return value_part
        return ""
    
    def _detect_variable_type(self, assignment: str) -> str:
        """Detect the type of variable based on its value."""
        value = self._extract_variable_value(assignment)
        
        if value.isdigit():
            return 'integer'
        elif value.lower() in ['true', 'false']:
            return 'boolean'
        elif value.startswith('$'):
            return 'reference'
        elif '/' in value:
            return 'path'
        else:
            return 'string'
    
    def _count_array_elements(self, array_def: str) -> int:
        """Count elements in array definition."""
        if '(' in array_def and ')' in array_def:
            array_content = array_def.split('(')[1].split(')')[0]
            # Simple count of space-separated elements
            elements = [e.strip() for e in array_content.split() if e.strip()]
            return len(elements)
        return 0
    
    def _is_associative_array(self, content: str) -> bool:
        """Check if array is associative (uses declare -A)."""
        return 'declare -A' in content or 'typeset -A' in content
    
    def _extract_alias_command(self, alias_def: str) -> str:
        """Extract the command from alias definition."""
        if '=' in alias_def:
            command_part = alias_def.split('=', 1)[1].strip()
            # Remove quotes
            if command_part.startswith('"') and command_part.endswith('"'):
                return command_part[1:-1]
            elif command_part.startswith("'") and command_part.endswith("'"):
                return command_part[1:-1]
            return command_part
        return ""
    
    def _extract_external_commands(self, content: str) -> List[str]:
        """Extract external commands used in the script."""
        # Common external commands to look for
        common_commands = {
            'awk', 'sed', 'grep', 'find', 'xargs', 'sort', 'uniq', 'cut',
            'curl', 'wget', 'ssh', 'scp', 'rsync', 'tar', 'gzip', 'zip',
            'git', 'docker', 'kubectl', 'npm', 'pip', 'make', 'cmake',
            'python', 'node', 'java', 'gcc', 'clang'
        }
        
        commands_found = set()
        
        for cmd in common_commands:
            # Look for command at start of line or after common separators
            pattern = rf'\b{cmd}\b'
            if re.search(pattern, content):
                commands_found.add(cmd)
        
        return list(commands_found)
