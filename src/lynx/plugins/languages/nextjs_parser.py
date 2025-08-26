"""Comprehensive Next.js framework parser extending React capabilities."""

import re
from typing import List, Dict, Any, Optional
from .react_parser import ReactParser
from .base import ParsedElement, DependencyInfo, ElementType, Visibility

class NextjsParser(ReactParser):
    """Advanced Next.js parser extending React parser with Next.js specific patterns."""
    
    language_name = "nextjs"
    supported_extensions = [".js", ".jsx", ".ts", ".tsx"]
    
    def __init__(self):
        super().__init__()
        
        # Extend patterns with Next.js-specific ones
        self.patterns.update({
            # API Routes
            'api_route': re.compile(
                r'^(\s*)(export\s+(?:default\s+)?(?:async\s+)?function)\s+'
                r'(handler|GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # Page Components
            'page_component': re.compile(
                r'^(\s*)(export\s+default\s+(?:function|const))\s+'
                r'([A-Z][a-zA-Z0-9_]*)\s*(?:\([^)]*\))?\s*(?:=>\s*)?\{',
                re.MULTILINE
            ),
            
            # Middleware
            'middleware': re.compile(
                r'^(\s*)(export\s+(?:async\s+)?function)\s+'
                r'(middleware)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # Next.js specific hooks and functions
            'nextjs_hook': re.compile(
                r'^(\s*)(const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*'
                r'(useRouter|usePathname|useSearchParams|useParams|getServerSideProps|getStaticProps|getStaticPaths)\s*\(',
                re.MULTILINE
            ),
            
            # Layout components
            'layout': re.compile(
                r'^(\s*)(export\s+default\s+(?:function|const))\s+'
                r'([A-Z][a-zA-Z0-9_]*Layout)\s*(?:\([^)]*\))?\s*(?:=>\s*)?\{',
                re.MULTILINE
            ),
            
            # App Router specific
            'app_route_handler': re.compile(
                r'^(\s*)(export\s+(?:async\s+)?function)\s+'
                r'(GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS)\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # Dynamic imports
            'dynamic_import': re.compile(
                r'^(\s*)(const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*'
                r'dynamic\s*\(\s*\(\)\s*=>\s*import\s*\([\'"]([^\'"]+)[\'"]\)',
                re.MULTILINE
            ),
        })
        
        # Next.js specific dependency patterns
        self.nextjs_imports = re.compile(
            r'^(\s*)import\s+([^\'\"]+)\s+from\s+[\'\"](next/[^\'"]+|@next/[^\'"]+)[\'\"]\s*;?',
            re.MULTILINE
        )
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Next.js code elements."""
        elements = []
        lines = content.split('\n')
        
        # First get React elements
        react_elements = super().parse_elements(content, file_path)
        elements.extend(react_elements)
        
        # Then add Next.js specific elements
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'require', 'dynamic_import']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_nextjs_element(match, pattern_name, lines, content, file_path)
                    if element and not self._is_duplicate_element(element, elements):
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_nextjs_element(self, match, pattern_name: str, lines: List[str],
                              content: str, file_path: str) -> ParsedElement:
        """Create Next.js specific elements."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        declaration = groups[1] if len(groups) > 1 else ""
        name = groups[2] if len(groups) > 2 else "unnamed"
        
        start_line = content[:match.start()].count('\n')
        
        # Determine element type based on Next.js patterns
        if pattern_name in ['api_route', 'app_route_handler']:
            element_type = ElementType.FUNCTION
            if pattern_name == 'api_route' and name == 'handler':
                name = f"API Handler ({file_path})"
            elif pattern_name == 'app_route_handler':
                name = f"{name} Route Handler"
        elif pattern_name in ['page_component', 'layout']:
            element_type = ElementType.CLASS  # Treat components as class-like
        elif pattern_name == 'middleware':
            element_type = ElementType.FUNCTION
        elif pattern_name == 'nextjs_hook':
            element_type = ElementType.VARIABLE
            hook_type = groups[3] if len(groups) > 3 else "unknown"
            name = f"{name} ({hook_type})"
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
        if pattern_name in ['api_route', 'page_component', 'middleware', 'layout', 'app_route_handler']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Next.js specific metadata
        metadata = {
            'framework': 'nextjs',
            'pattern_type': pattern_name,
            'is_exported': 'export' in declaration,
            'is_default_export': 'export default' in declaration,
            'is_async': 'async' in declaration,
            'file_type': self._detect_nextjs_file_type(file_path),
            'route_type': self._detect_route_type(file_path, pattern_name),
        }
        
        if pattern_name in ['api_route', 'app_route_handler']:
            metadata.update({
                'http_method': name if name in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'] else 'handler',
                'is_api_route': True,
                'route_path': self._extract_route_path(file_path)
            })
        elif pattern_name in ['page_component', 'layout']:
            metadata.update({
                'is_page': pattern_name == 'page_component',
                'is_layout': pattern_name == 'layout',
                'component_type': 'page' if pattern_name == 'page_component' else 'layout'
            })
        elif pattern_name == 'nextjs_hook':
            hook_type = groups[3] if len(groups) > 3 else "unknown"
            metadata.update({
                'hook_type': hook_type,
                'is_nextjs_hook': True,
                'is_server_side': hook_type in ['getServerSideProps', 'getStaticProps', 'getStaticPaths']
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
        """Extract Next.js dependencies extending React dependencies."""
        dependencies = super().extract_dependencies(content)
        
        # Add Next.js specific imports
        for match in self.nextjs_imports.finditer(content):
            line_num = content[:match.start()].count('\n')
            imports = match.group(2).strip()
            module = match.group(3)
            
            # Parse Next.js imports
            if imports.startswith('{') and imports.endswith('}'):
                # Named imports: { Component, ... }
                names = imports.strip('{}').split(',')
                for name in names:
                    name = name.strip()
                    if ' as ' in name:
                        orig_name, alias = name.split(' as ')
                        dependencies.append(DependencyInfo(
                            name=orig_name.strip(),
                            import_type='nextjs_import',
                            source=module,
                            alias=alias.strip(),
                            line_number=line_num
                        ))
                    else:
                        dependencies.append(DependencyInfo(
                            name=name,
                            import_type='nextjs_import',
                            source=module,
                            line_number=line_num
                        ))
            else:
                # Default import
                dependencies.append(DependencyInfo(
                    name=imports,
                    import_type='nextjs_import',
                    source=module,
                    line_number=line_num
                ))
        
        # Dynamic imports
        dynamic_pattern = self.patterns['dynamic_import']
        for match in dynamic_pattern.finditer(content):
            line_num = content[:match.start()].count('\n')
            component_name = match.group(3)
            import_path = match.group(4)
            
            dependencies.append(DependencyInfo(
                name=component_name,
                import_type='dynamic_import',
                source=import_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _detect_nextjs_file_type(self, file_path: str) -> str:
        """Detect Next.js file type based on path."""
        path_lower = file_path.lower()
        
        if '/pages/api/' in path_lower or '/app/' in path_lower and '/route.' in path_lower:
            return 'api_route'
        elif '/pages/' in path_lower:
            return 'page'
        elif '/app/' in path_lower and ('layout.' in path_lower or 'page.' in path_lower):
            return 'app_router'
        elif 'middleware.' in path_lower:
            return 'middleware'
        elif '/components/' in path_lower:
            return 'component'
        else:
            return 'unknown'
    
    def _detect_route_type(self, file_path: str, pattern_name: str) -> Optional[str]:
        """Detect the type of route (pages router vs app router)."""
        if '/pages/' in file_path:
            return 'pages_router'
        elif '/app/' in file_path:
            return 'app_router'
        return None
    
    def _extract_route_path(self, file_path: str) -> str:
        """Extract the route path from file path."""
        if '/pages/api/' in file_path:
            route = file_path.split('/pages/api/')[-1]
        elif '/pages/' in file_path:
            route = file_path.split('/pages/')[-1]
        elif '/app/' in file_path:
            route = file_path.split('/app/')[-1]
        else:
            return file_path
        
        # Remove file extension
        route = route.rsplit('.', 1)[0]
        return f"/{route}" if not route.startswith('/') else route
    
    def _is_duplicate_element(self, element: ParsedElement, existing: List[ParsedElement]) -> bool:
        """Check if element already exists to avoid duplicates."""
        for existing_element in existing:
            if (existing_element.name == element.name and 
                existing_element.start_line == element.start_line and
                existing_element.element_type == element.element_type):
                return True
        return False
