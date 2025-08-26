"""Comprehensive HTML language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class HtmlParser(BaseLanguageParser):
    """Advanced HTML language parser."""
    
    language_name = "html"
    supported_extensions = [".html", ".htm", ".xhtml"]
    
    def __init__(self):
        self.patterns = {
            'tag': re.compile(
                r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*?(?:/>|>.*?</\1>)',
                re.DOTALL | re.IGNORECASE
            ),
            'self_closing_tag': re.compile(
                r'<([a-zA-Z][a-zA-Z0-9]*)[^>]*?/>',
                re.IGNORECASE
            ),
            'opening_tag': re.compile(
                r'<([a-zA-Z][a-zA-Z0-9]*)((?:\s+[^>]*?)?)>',
                re.IGNORECASE
            ),
            'script': re.compile(
                r'<script[^>]*>(.*?)</script>',
                re.DOTALL | re.IGNORECASE
            ),
            'style': re.compile(
                r'<style[^>]*>(.*?)</style>',
                re.DOTALL | re.IGNORECASE
            ),
            'comment': re.compile(
                r'<!--(.*?)-->',
                re.DOTALL
            ),
            'doctype': re.compile(
                r'<!DOCTYPE\s+([^>]+)>',
                re.IGNORECASE
            ),
        }
        
        # Important HTML elements that should be parsed
        self.important_tags = {
            'html', 'head', 'body', 'title', 'meta', 'link', 'script', 'style',
            'header', 'nav', 'main', 'section', 'article', 'aside', 'footer',
            'div', 'span', 'form', 'table', 'img', 'video', 'audio'
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse HTML elements."""
        elements = []
        lines = content.split('\n')
        
        # Parse doctype
        doctype_matches = self.patterns['doctype'].finditer(content)
        for match in doctype_matches:
            elements.append(self._create_doctype_element(match, lines, content))
        
        # Parse important tags
        tag_matches = self.patterns['opening_tag'].finditer(content)
        for match in tag_matches:
            tag_name = match.group(1).lower()
            if tag_name in self.important_tags:
                try:
                    element = self._create_html_element(match, lines, content, tag_name)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        # Parse script and style blocks separately
        for pattern_name in ['script', 'style']:
            pattern = self.patterns[pattern_name]
            for match in pattern.finditer(content):
                try:
                    element = self._create_embedded_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_doctype_element(self, match, lines: List[str], content: str) -> ParsedElement:
        """Create element for DOCTYPE declaration."""
        start_line = content[:match.start()].count('\n')
        doctype_content = match.group(1).strip()
        
        return ParsedElement(
            name="DOCTYPE",
            element_type=ElementType.MODULE,
            start_line=start_line,
            end_line=start_line + 1,
            visibility=Visibility.PUBLIC,
            language=self.language_name,
            content=match.group(0),
            metadata={
                'type': 'doctype',
                'doctype': doctype_content
            }
        )
    
    def _create_html_element(self, match, lines: List[str], content: str, tag_name: str) -> ParsedElement:
        """Create ParsedElement from HTML tag match."""
        start_line = content[:match.start()].count('\n')
        attributes_str = match.group(2) if len(match.groups()) > 1 else ""
        
        # Find the closing tag or determine if self-closing
        end_line = self._find_html_tag_end(content, match, tag_name, lines)
        
        # Extract attributes
        attributes = self._extract_attributes(attributes_str)
        
        # Determine element significance
        element_type = self._get_element_type(tag_name)
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'tag': tag_name,
            'attributes': attributes,
            'has_id': 'id' in attributes,
            'has_class': 'class' in attributes,
            'is_semantic': tag_name in {'header', 'nav', 'main', 'section', 'article', 'aside', 'footer'},
            'is_form_element': tag_name in {'form', 'input', 'button', 'select', 'textarea'},
            'is_media': tag_name in {'img', 'video', 'audio', 'source'},
        }
        
        # Add specific metadata based on tag type
        if tag_name == 'meta' and 'name' in attributes:
            metadata['meta_name'] = attributes['name']
        elif tag_name == 'link' and 'rel' in attributes:
            metadata['link_rel'] = attributes['rel']
        elif tag_name == 'script' and 'src' in attributes:
            metadata['script_src'] = attributes['src']
        elif tag_name == 'img' and 'src' in attributes:
            metadata['img_src'] = attributes['src']
        
        # Use ID as name if available, otherwise use tag name
        name = attributes.get('id', tag_name)
        if 'class' in attributes:
            name = f"{name}.{attributes['class'].split()[0]}"
        
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
    
    def _create_embedded_element(self, match, element_type: str, lines: List[str], content: str) -> ParsedElement:
        """Create element for embedded script or style blocks."""
        start_line = content[:match.start()].count('\n')
        end_line = content[:match.end()].count('\n') + 1
        
        embedded_content = match.group(1) if match.groups() else ""
        
        return ParsedElement(
            name=f"{element_type}_block",
            element_type=ElementType.FUNCTION if element_type == 'script' else ElementType.CLASS,
            start_line=start_line,
            end_line=end_line,
            visibility=Visibility.PUBLIC,
            language=self.language_name,
            content=match.group(0),
            metadata={
                'type': f'embedded_{element_type}',
                'embedded_language': 'javascript' if element_type == 'script' else 'css',
                'content_length': len(embedded_content.strip()),
                'has_content': bool(embedded_content.strip())
            }
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract HTML dependencies (links, scripts, images, etc.)."""
        dependencies = []
        
        # External stylesheets
        link_matches = re.finditer(r'<link[^>]+rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', content, re.IGNORECASE)
        for match in link_matches:
            line_num = content[:match.start()].count('\n')
            dependencies.append(DependencyInfo(
                name=match.group(1).split('/')[-1],
                import_type='stylesheet',
                source=match.group(1),
                line_number=line_num
            ))
        
        # External scripts
        script_matches = re.finditer(r'<script[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        for match in script_matches:
            line_num = content[:match.start()].count('\n')
            dependencies.append(DependencyInfo(
                name=match.group(1).split('/')[-1],
                import_type='script',
                source=match.group(1),
                line_number=line_num
            ))
        
        # Images
        img_matches = re.finditer(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.IGNORECASE)
        for match in img_matches:
            line_num = content[:match.start()].count('\n')
            dependencies.append(DependencyInfo(
                name=match.group(1).split('/')[-1],
                import_type='image',
                source=match.group(1),
                line_number=line_num
            ))
        
        # Other resources (videos, audio, iframes)
        resource_patterns = [
            (r'<video[^>]+src=["\']([^"\']+)["\']', 'video'),
            (r'<audio[^>]+src=["\']([^"\']+)["\']', 'audio'),
            (r'<iframe[^>]+src=["\']([^"\']+)["\']', 'iframe'),
            (r'<source[^>]+src=["\']([^"\']+)["\']', 'source'),
        ]
        
        for pattern, resource_type in resource_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                line_num = content[:match.start()].count('\n')
                dependencies.append(DependencyInfo(
                    name=match.group(1).split('/')[-1],
                    import_type=resource_type,
                    source=match.group(1),
                    line_number=line_num
                ))
        
        return dependencies
    
    def _find_html_tag_end(self, content: str, match, tag_name: str, lines: List[str]) -> int:
        """Find the end line of an HTML tag."""
        start_pos = match.end()
        
        # Check if it's a self-closing tag
        if match.group(0).endswith('/>'):
            return content[:match.end()].count('\n') + 1
        
        # Check if it's a void element (self-closing by nature)
        void_elements = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
                        'link', 'meta', 'param', 'source', 'track', 'wbr'}
        if tag_name.lower() in void_elements:
            return content[:match.end()].count('\n') + 1
        
        # Look for closing tag
        closing_pattern = re.compile(f'</{tag_name}>', re.IGNORECASE)
        closing_match = closing_pattern.search(content, start_pos)
        
        if closing_match:
            return content[:closing_match.end()].count('\n') + 1
        else:
            # No closing tag found, assume single line
            return content[:match.end()].count('\n') + 1
    
    def _extract_attributes(self, attributes_str: str) -> Dict[str, str]:
        """Extract attributes from HTML tag attributes string."""
        attributes = {}
        
        if not attributes_str:
            return attributes
        
        # Pattern to match attribute="value" or attribute='value' or attribute=value
        attr_pattern = re.compile(r'([a-zA-Z-]+)=(["\'])([^"\']*)\2|([a-zA-Z-]+)=([^\s>]+)|([a-zA-Z-]+)')
        
        for match in attr_pattern.finditer(attributes_str):
            if match.group(1):  # quoted attribute
                attr_name = match.group(1)
                attr_value = match.group(3)
            elif match.group(4):  # unquoted attribute
                attr_name = match.group(4)
                attr_value = match.group(5)
            elif match.group(6):  # boolean attribute
                attr_name = match.group(6)
                attr_value = ""
            else:
                continue
            
            attributes[attr_name.lower()] = attr_value
        
        return attributes
    
    def _get_element_type(self, tag_name: str) -> ElementType:
        """Determine the element type based on HTML tag."""
        if tag_name in {'html', 'head', 'body'}:
            return ElementType.MODULE
        elif tag_name in {'div', 'section', 'article', 'header', 'footer', 'nav', 'aside', 'main'}:
            return ElementType.CLASS
        elif tag_name in {'script'}:
            return ElementType.FUNCTION
        elif tag_name in {'style'}:
            return ElementType.CLASS
        elif tag_name in {'form', 'table'}:
            return ElementType.STRUCT
        else:
            return ElementType.VARIABLE
