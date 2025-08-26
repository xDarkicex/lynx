"""Comprehensive CSS language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class CssParser(BaseLanguageParser):
    """Advanced CSS language parser."""
    
    language_name = "css"
    supported_extensions = [".css", ".scss", ".sass", ".less"]
    
    def __init__(self):
        self.patterns = {
            'rule': re.compile(
                r'([^{}]+?)\s*\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}',
                re.DOTALL
            ),
            'at_rule': re.compile(
                r'@([a-zA-Z-]+)\s*([^{;]+)?(?:\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}|;)',
                re.DOTALL
            ),
            'import': re.compile(
                r'@import\s+(?:url\()?["\']?([^"\')\s]+)["\']?\)?',
                re.IGNORECASE
            ),
            'media_query': re.compile(
                r'@media\s+([^{]+)',
                re.IGNORECASE
            ),
            'keyframes': re.compile(
                r'@(?:-\w+-)?keyframes\s+([a-zA-Z_][a-zA-Z0-9_-]*)',
                re.IGNORECASE
            ),
            'variable': re.compile(
                r'--([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*([^;]+);',
                re.MULTILINE
            ),
        }
        
        # CSS selector specificity and types
        self.selector_types = {
            'id': re.compile(r'#[a-zA-Z_][a-zA-Z0-9_-]*'),
            'class': re.compile(r'\.[a-zA-Z_][a-zA-Z0-9_-]*'),
            'element': re.compile(r'\b[a-zA-Z][a-zA-Z0-9]*\b'),
            'attribute': re.compile(r'\[[^\]]+\]'),
            'pseudo': re.compile(r':+[a-zA-Z-]+(?:\([^)]*\))?'),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse CSS elements."""
        elements = []
        lines = content.split('\n')
        
        # Parse at-rules first
        at_rule_matches = self.patterns['at_rule'].finditer(content)
        for match in at_rule_matches:
            try:
                element = self._create_at_rule_element(match, lines, content)
                if element:
                    elements.append(element)
            except Exception:
                continue
        
        # Parse regular CSS rules
        rule_matches = self.patterns['rule'].finditer(content)
        for match in rule_matches:
            try:
                # Skip if this is part of an at-rule (already processed)
                if self._is_inside_at_rule(content, match.start()):
                    continue
                
                element = self._create_css_rule_element(match, lines, content)
                if element:
                    elements.append(element)
            except Exception:
                continue
        
        # Parse CSS custom properties (variables)
        var_matches = self.patterns['variable'].finditer(content)
        for match in var_matches:
            try:
                element = self._create_variable_element(match, lines, content)
                if element:
                    elements.append(element)
            except Exception:
                continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_at_rule_element(self, match, lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from CSS at-rule match."""
        start_line = content[:match.start()].count('\n')
        end_line = content[:match.end()].count('\n') + 1
        
        at_rule_name = match.group(1)
        at_rule_params = match.group(2).strip() if match.group(2) else ""
        at_rule_body = match.group(3) if match.group(3) else ""
        
        # Determine element type based on at-rule
        if at_rule_name.lower() in ['media', 'supports', 'container']:
            element_type = ElementType.CLASS
            name = f"@{at_rule_name} {at_rule_params}"
        elif at_rule_name.lower() in ['keyframes', '-webkit-keyframes', '-moz-keyframes']:
            element_type = ElementType.FUNCTION
            # Extract animation name
            name_match = self.patterns['keyframes'].search(match.group(0))
            name = name_match.group(1) if name_match else f"@{at_rule_name}"
        elif at_rule_name.lower() in ['font-face', 'page']:
            element_type = ElementType.STRUCT
            name = f"@{at_rule_name}"
        else:
            element_type = ElementType.VARIABLE
            name = f"@{at_rule_name}"
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'type': 'at_rule',
            'at_rule': at_rule_name,
            'parameters': at_rule_params,
            'has_body': bool(at_rule_body),
            'body_length': len(at_rule_body.strip()) if at_rule_body else 0,
        }
        
        if at_rule_name.lower() == 'media':
            metadata.update({
                'media_query': at_rule_params,
                'breakpoints': self._extract_breakpoints(at_rule_params)
            })
        elif at_rule_name.lower() in ['keyframes', '-webkit-keyframes', '-moz-keyframes']:
            metadata.update({
                'animation_name': name_match.group(1) if name_match else 'unnamed',
                'keyframe_selectors': self._extract_keyframe_selectors(at_rule_body)
            })
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=Visibility.PUBLIC,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def _create_css_rule_element(self, match, lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from CSS rule match."""
        start_line = content[:match.start()].count('\n')
        end_line = content[:match.end()].count('\n') + 1
        
        selector = match.group(1).strip()
        declarations = match.group(2).strip()
        
        # Analyze selector
        selector_analysis = self._analyze_selector(selector)
        
        # Clean up selector for name
        clean_selector = re.sub(r'\s+', ' ', selector).strip()
        if len(clean_selector) > 50:
            clean_selector = clean_selector[:47] + "..."
        
        name = clean_selector
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'type': 'css_rule',
            'selector': selector,
            'selector_specificity': self._calculate_specificity(selector),
            'selector_types': selector_analysis,
            'declaration_count': len([d for d in declarations.split(';') if d.strip()]),
            'properties': self._extract_properties(declarations),
            'is_responsive': any(prop in declarations.lower() for prop in ['width', 'height', 'flex', 'grid', 'margin', 'padding']),
            'has_animations': any(prop in declarations.lower() for prop in ['animation', 'transition', 'transform']),
        }
        
        # Determine element type based on selector
        if selector_analysis.get('id', 0) > 0:
            element_type = ElementType.CLASS
        elif selector_analysis.get('class', 0) > 0:
            element_type = ElementType.CLASS
        elif selector_analysis.get('element', 0) > 0:
            element_type = ElementType.STRUCT
        else:
            element_type = ElementType.VARIABLE
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=Visibility.PUBLIC,
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def _create_variable_element(self, match, lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from CSS custom property match."""
        start_line = content[:match.start()].count('\n')
        
        var_name = match.group(1)
        var_value = match.group(2).strip()
        
        return ParsedElement(
            name=f"--{var_name}",
            element_type=ElementType.VARIABLE,
            start_line=start_line,
            end_line=start_line + 1,
            visibility=Visibility.PUBLIC,
            language=self.language_name,
            content=match.group(0),
            metadata={
                'type': 'css_variable',
                'variable_name': var_name,
                'value': var_value,
                'is_color': self._is_color_value(var_value),
                'is_size': self._is_size_value(var_value),
            }
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract CSS dependencies (@import statements, url() references, etc.)."""
        dependencies = []
        
        # @import statements
        import_matches = self.patterns['import'].finditer(content)
        for match in import_matches:
            line_num = content[:match.start()].count('\n')
            import_path = match.group(1)
            dependencies.append(DependencyInfo(
                name=import_path.split('/')[-1],
                import_type='import',
                source=import_path,
                line_number=line_num
            ))
        
        # url() references (fonts, images, etc.)
        url_matches = re.finditer(r'url\(["\']?([^"\')\s]+)["\']?\)', content, re.IGNORECASE)
        for match in url_matches:
            line_num = content[:match.start()].count('\n')
            url_path = match.group(1)
            
            # Determine resource type
            resource_type = 'resource'
            if any(ext in url_path.lower() for ext in ['.woff', '.woff2', '.ttf', '.otf', '.eot']):
                resource_type = 'font'
            elif any(ext in url_path.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp']):
                resource_type = 'image'
            elif url_path.startswith('data:'):
                resource_type = 'data_url'
            
            dependencies.append(DependencyInfo(
                name=url_path.split('/')[-1],
                import_type=resource_type,
                source=url_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _is_inside_at_rule(self, content: str, position: int) -> bool:
        """Check if position is inside an at-rule block."""
        # Simple check - look backwards for unclosed at-rule
        before_content = content[:position]
        at_rules = re.finditer(r'@[a-zA-Z-]+[^{]*\{', before_content)
        open_braces = 0
        
        for at_rule_match in at_rules:
            # Count braces between at-rule start and current position
            between_content = content[at_rule_match.end():position]
            open_braces += between_content.count('{') - between_content.count('}')
        
        return open_braces > 0
    
    def _analyze_selector(self, selector: str) -> Dict[str, int]:
        """Analyze CSS selector and count different types."""
        analysis = {'id': 0, 'class': 0, 'element': 0, 'attribute': 0, 'pseudo': 0}
        
        for selector_type, pattern in self.selector_types.items():
            matches = pattern.findall(selector)
            analysis[selector_type] = len(matches)
        
        return analysis
    
    def _calculate_specificity(self, selector: str) -> int:
        """Calculate CSS specificity score."""
        analysis = self._analyze_selector(selector)
        # CSS specificity calculation: inline(1000) + id(100) + class/attribute/pseudo(10) + element(1)
        return analysis['id'] * 100 + (analysis['class'] + analysis['attribute'] + analysis['pseudo']) * 10 + analysis['element']
    
    def _extract_properties(self, declarations: str) -> List[str]:
        """Extract CSS property names from declarations."""
        properties = []
        for declaration in declarations.split(';'):
            declaration = declaration.strip()
            if declaration and ':' in declaration:
                prop_name = declaration.split(':')[0].strip()
                properties.append(prop_name)
        return properties
    
    def _extract_breakpoints(self, media_query: str) -> List[str]:
        """Extract breakpoint values from media query."""
        breakpoints = []
        
        # Look for common breakpoint patterns
        width_matches = re.findall(r'(?:min-width|max-width):\s*([0-9]+(?:px|em|rem))', media_query)
        breakpoints.extend(width_matches)
        
        height_matches = re.findall(r'(?:min-height|max-height):\s*([0-9]+(?:px|em|rem))', media_query)
        breakpoints.extend(height_matches)
        
        return breakpoints
    
    def _extract_keyframe_selectors(self, keyframes_body: str) -> List[str]:
        """Extract keyframe selectors (0%, 50%, 100%, from, to)."""
        if not keyframes_body:
            return []
        
        selectors = []
        # Match percentage and keyword selectors
        selector_matches = re.findall(r'\b(?:from|to|\d+%)\b', keyframes_body)
        selectors.extend(selector_matches)
        
        return list(set(selectors))  # Remove duplicates
    
    def _is_color_value(self, value: str) -> bool:
        """Check if CSS value represents a color."""
        color_patterns = [
            r'#[0-9a-fA-F]{3,8}',  # hex colors
            r'rgb\(',  # rgb functions
            r'rgba\(',  # rgba functions
            r'hsl\(',  # hsl functions
            r'hsla\(',  # hsla functions
        ]
        
        color_keywords = [
            'red', 'green', 'blue', 'yellow', 'orange', 'purple', 'pink', 'brown',
            'black', 'white', 'gray', 'grey', 'transparent', 'currentColor'
        ]
        
        value_lower = value.lower()
        
        # Check patterns
        for pattern in color_patterns:
            if re.search(pattern, value):
                return True
        
        # Check keywords
        for keyword in color_keywords:
            if keyword in value_lower:
                return True
        
        return False
    
    def _is_size_value(self, value: str) -> bool:
        """Check if CSS value represents a size/dimension."""
        size_patterns = [
            r'\d+(?:px|em|rem|%|vh|vw|vmin|vmax|pt|pc|in|cm|mm|ch|ex)',
            r'\d+\.?\d*(?:px|em|rem|%|vh|vw|vmin|vmax|pt|pc|in|cm|mm|ch|ex)',
        ]
        
        for pattern in size_patterns:
            if re.search(pattern, value):
                return True
        
        return False
