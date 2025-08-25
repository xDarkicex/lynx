"""Comprehensive React library parser extending JavaScript capabilities."""

import re
from typing import List, Dict, Any, Optional
from .javascript_parser import JavaScriptParser
from .base import ParsedElement, DependencyInfo, ElementType, Visibility

class ReactParser(JavaScriptParser):
    """Advanced React parser extending JavaScript parser with React-specific patterns."""
    
    language_name = "react"
    supported_extensions = [".jsx", ".tsx", ".js", ".ts"]
    
    def __init__(self):
        super().__init__()
        
        # Extend patterns with React-specific ones
        self.patterns.update({
            # React Functional Components
            'react_component': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?(?:const|let|function))\s+'
                r'([A-Z][a-zA-Z0-9_]*)\s*(?:=\s*(?:\([^)]*\)\s*=>\s*|function\s*\([^)]*\)\s*))?'
                r'(?:\{|return\s*\(|\s*<[A-Z])',
                re.MULTILINE
            ),
            
            # React Class Components
            'react_class_component': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?class)\s+'
                r'([A-Z][a-zA-Z0-9_]*)\s+extends\s+(?:React\.)?(?:Component|PureComponent)\s*\{',
                re.MULTILINE
            ),
            
            # React Hooks
            'react_hook': re.compile(
                r'^(\s*)(const|let|var)\s+(?:\[([^\]]+)\]|([a-zA-Z_$][a-zA-Z0-9_$]*))\s*=\s*'
                r'(use[A-Z][a-zA-Z0-9_]*)\s*\(',
                re.MULTILINE
            ),
            
            # Custom Hooks
            'custom_hook': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?(?:const|function))\s+'
                r'(use[A-Z][a-zA-Z0-9_]*)\s*(?:\(|\s*=)',
                re.MULTILINE
            ),
            
            # Higher Order Components
            'hoc': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?(?:const|function))\s+'
                r'(with[A-Z][a-zA-Z0-9_]*)\s*\(',
                re.MULTILINE
            ),
            
            # React Context
            'react_context': re.compile(
                r'^(\s*)(const|let|var)\s+([A-Z][a-zA-Z0-9_]*Context)\s*=\s*'
                r'(?:React\.)?createContext\s*\(',
                re.MULTILINE
            ),
            
            # React Reducers
            'react_reducer': re.compile(
                r'^(\s*)((?:export\s+(?:default\s+)?)?(?:const|function))\s+'
                r'([a-zA-Z_][a-zA-Z0-9_]*Reducer)\s*\(',
                re.MULTILINE
            ),
            
            # JSX Elements (for analysis)
            'jsx_element': re.compile(
                r'<([A-Z][a-zA-Z0-9_]*(?:\.[A-Z][a-zA-Z0-9_]*)*)[^>]*>',
                re.MULTILINE
            ),
        })
        
        # React-specific import patterns
        self.react_imports = re.compile(
            r'^(\s*)import\s+([^\'\"]+)\s+from\s+[\'\"](react|react-dom|@react/[^\'"]+)[\'\"]\s*;?',
            re.MULTILINE
        )
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse React code elements."""
        elements = []
        lines = content.split('\n')
        
        # First get JavaScript elements
        js_elements = super().parse_elements(content, file_path)
        
        # Filter and enhance JavaScript elements for React context
        for element in js_elements:
            if self._is_likely_react_component(element):
                element.metadata.update({
                    'framework': 'react',
                    'component_type': self._detect_component_type(element.content),
                    'uses_jsx': self._uses_jsx(element.content),
                    'hooks_used': self._extract_hooks_used(element.content)
                })
            elements.append(element)
        
        # Add React-specific elements
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'require', 'jsx_element']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_react_element(match, pattern_name, lines, content, file_path)
                    if element and not self._is_duplicate_element(element, elements):
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_react_element(self, match, pattern_name: str, lines: List[str],
                             content: str, file_path: str) -> ParsedElement:
        """Create React-specific elements."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        
        # Extract name based on pattern
        if pattern_name == 'react_hook':
            # For hooks like const [state, setState] = useState()
            if groups[2]:  # Array destructuring
                name = groups[2].strip()
            else:
                name = groups[3] if len(groups) > 3 else "hook"
            hook_name = groups[4] if len(groups) > 4 else "unknown"
            name = f"{name} ({hook_name})"
        else:
            name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Determine element type
        if pattern_name in ['react_component', 'react_class_component']:
            element_type = ElementType.CLASS
        elif pattern_name in ['custom_hook', 'hoc', 'react_reducer']:
            element_type = ElementType.FUNCTION
        elif pattern_name == 'react_hook':
            element_type = ElementType.VARIABLE
        elif pattern_name == 'react_context':
            element_type = ElementType.CONSTANT
        else:
            element_type = ElementType.FUNCTION
        
        # Determine visibility
        if 'export' in declaration:
            visibility = Visibility.PUBLIC
        elif name.startswith('_'):
            visibility = Visibility.PRIVATE
        else:
            visibility = Visibility.INTERNAL
        
        # Find block end
        if pattern_name in ['react_component', 'react_class_component', 'custom_hook', 'hoc', 'react_reducer']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # React-specific metadata
        metadata = {
            'framework': 'react',
            'pattern_type': pattern_name,
            'is_exported': 'export' in declaration,
            'is_default_export': 'export default' in declaration,
            'uses_jsx': self._uses_jsx(content_lines),
        }
        
        if pattern_name in ['react_component', 'react_class_component']:
            metadata.update({
                'is_component': True,
                'component_type': 'class' if pattern_name == 'react_class_component' else 'functional',
                'props': self._extract_props(content_lines),
                'state_hooks': self._extract_state_hooks(content_lines),
                'effect_hooks': self._extract_effect_hooks(content_lines),
                'jsx_elements': self._extract_jsx_elements(content_lines)
            })
        elif pattern_name in ['custom_hook']:
            metadata.update({
                'is_custom_hook': True,
                'returns_array': self._returns_array(content_lines),
                'hooks_used': self._extract_hooks_used(content_lines)
            })
        elif pattern_name == 'react_hook':
            hook_name = groups[4] if len(groups) > 4 else "unknown"
            metadata.update({
                'hook_name': hook_name,
                'is_destructured': groups[2] is not None,
                'hook_type': self._categorize_hook(hook_name)
            })
        elif pattern_name == 'hoc':
            metadata.update({
                'is_hoc': True,
                'returns_component': True
            })
        elif pattern_name == 'react_context':
            metadata.update({
                'is_context': True,
                'has_provider': 'Provider' in content_lines,
                'has_consumer': 'Consumer' in content_lines
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
        """Extract React dependencies extending JavaScript dependencies."""
        dependencies = super().extract_dependencies(content)
        
        # Add React-specific imports
        for match in self.react_imports.finditer(content):
            line_num = content[:match.start()].count('\n')
            imports = match.group(2).strip()
            module = match.group(3)
            
            # Parse React imports
            if imports.startswith('{') and imports.endswith('}'):
                # Named imports: { Component, useState, ... }
                names = imports.strip('{}').split(',')
                for name in names:
                    name = name.strip()
                    if ' as ' in name:
                        orig_name, alias = name.split(' as ')
                        dependencies.append(DependencyInfo(
                            name=orig_name.strip(),
                            import_type='react_import',
                            source=module,
                            alias=alias.strip(),
                            line_number=line_num
                        ))
                    else:
                        dependencies.append(DependencyInfo(
                            name=name,
                            import_type='react_import',
                            source=module,
                            line_number=line_num
                        ))
            else:
                # Default import (usually React)
                dependencies.append(DependencyInfo(
                    name=imports,
                    import_type='react_import',
                    source=module,
                    line_number=line_num
                ))
        
        return dependencies
    
    def _is_likely_react_component(self, element: ParsedElement) -> bool:
        """Check if element is likely a React component."""
        if element.element_type != ElementType.FUNCTION and element.element_type != ElementType.CLASS:
            return False
        
        # Check for JSX usage or React patterns
        return (element.name[0].isupper() and 
                (self._uses_jsx(element.content) or 
                 'React' in element.content or
                 'return (' in element.content))
    
    def _detect_component_type(self, content: str) -> str:
        """Detect the type of React component."""
        if 'class' in content and 'extends' in content and 'Component' in content:
            return 'class'
        elif 'function' in content or '=>' in content:
            return 'functional'
        else:
            return 'unknown'
    
    def _uses_jsx(self, content: str) -> bool:
        """Check if content uses JSX."""
        jsx_patterns = [
            r'<[A-Z][a-zA-Z0-9_]*',  # Component JSX
            r'<[a-z]+[^>]*>',        # HTML JSX
            r'return\s*\(',           # Common JSX return pattern
            r'<\w+[^>]*/>',          # Self-closing tags
        ]
        
        return any(re.search(pattern, content) for pattern in jsx_patterns)
    
    def _extract_props(self, content: str) -> List[str]:
        """Extract props from component."""
        props = []
        
        # Function component props
        func_props = re.search(r'function\s+\w+\s*\(\s*\{([^}]+)\}', content)
        if func_props:
            props_text = func_props.group(1)
            props.extend([p.strip() for p in props_text.split(',') if p.strip()])
        
        # Arrow function props
        arrow_props = re.search(r'\(\s*\{([^}]+)\}\s*\)\s*=>', content)
        if arrow_props:
            props_text = arrow_props.group(1)
            props.extend([p.strip() for p in props_text.split(',') if p.strip()])
        
        return list(set(props))  # Remove duplicates
    
    def _extract_state_hooks(self, content: str) -> List[str]:
        """Extract useState hooks."""
        state_hooks = []
        useState_pattern = r'const\s*\[([^\]]+)\]\s*=\s*useState'
        
        for match in re.finditer(useState_pattern, content):
            state_var = match.group(1).split(',')[0].strip()
            state_hooks.append(state_var)
        
        return state_hooks
    
    def _extract_effect_hooks(self, content: str) -> List[str]:
        """Extract useEffect hooks and their dependencies."""
        effects = []
        effect_pattern = r'useEffect\s*\([^,)]+,\s*\[([^\]]*)\]\s*\)'
        
        for match in re.finditer(effect_pattern, content):
            deps = match.group(1).strip()
            effects.append(deps if deps else 'no dependencies')
        
        return effects
    
    def _extract_jsx_elements(self, content: str) -> List[str]:
        """Extract JSX elements used in component."""
        elements = set()
        jsx_pattern = self.patterns['jsx_element']
        
        for match in jsx_pattern.finditer(content):
            element_name = match.group(1)
            elements.add(element_name)
        
        return list(elements)
    
    def _extract_hooks_used(self, content: str) -> List[str]:
        """Extract all hooks used in the content."""
        hooks = set()
        hook_pattern = r'(use[A-Z][a-zA-Z0-9_]*)\s*\('
        
        for match in re.finditer(hook_pattern, content):
            hook_name = match.group(1)
            hooks.add(hook_name)
        
        return list(hooks)
    
    def _returns_array(self, content: str) -> bool:
        """Check if function returns an array (common for custom hooks)."""
        return_patterns = [
            r'return\s*\[',
            r'return\s*\(',
            r'=>\s*\['
        ]
        return any(re.search(pattern, content) for pattern in return_patterns)
    
    def _categorize_hook(self, hook_name: str) -> str:
        """Categorize the type of React hook."""
        state_hooks = ['useState', 'useReducer']
        effect_hooks = ['useEffect', 'useLayoutEffect']
        context_hooks = ['useContext']
        ref_hooks = ['useRef', 'useImperativeHandle']
        memo_hooks = ['useMemo', 'useCallback']
        
        if hook_name in state_hooks:
            return 'state'
        elif hook_name in effect_hooks:
            return 'effect'
        elif hook_name in context_hooks:
            return 'context'
        elif hook_name in ref_hooks:
            return 'ref'
        elif hook_name in memo_hooks:
            return 'memoization'
        else:
            return 'custom'
    
    def _is_duplicate_element(self, element: ParsedElement, existing: List[ParsedElement]) -> bool:
        """Check if element already exists to avoid duplicates."""
        for existing_element in existing:
            if (existing_element.name == element.name and 
                existing_element.start_line == element.start_line):
                return True
        return False
