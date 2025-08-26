"""Comprehensive Flutter/Dart language parser with Flutter-specific patterns."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class FlutterParser(BaseLanguageParser):
    """Advanced Flutter/Dart parser with Flutter framework awareness."""
    
    language_name = "flutter"
    supported_extensions = [".dart"]
    
    def __init__(self):
        self.patterns = {
            # Classes
            'class': re.compile(
                r'^(\s*)(abstract\s+|sealed\s+)?(class)\s+([A-Z][a-zA-Z0-9_]*)'
                r'(?:\s+extends\s+[A-Z][a-zA-Z0-9_]*)?(?:\s+with\s+[^{]+)?'
                r'(?:\s+implements\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            
            # Flutter Widgets
            'widget': re.compile(
                r'^(\s*)(class)\s+([A-Z][a-zA-Z0-9_]*)\s+extends\s+'
                r'(StatelessWidget|StatefulWidget|Widget|InheritedWidget)\s*\{',
                re.MULTILINE
            ),
            
            # Functions and Methods
            'function': re.compile(
                r'^(\s*)((?:static\s+|async\s+|Future\s*<[^>]+>\s+|Stream\s*<[^>]+>\s+)*)'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^{]*\)\s*(?:async\s+)?\{',
                re.MULTILINE
            ),
            
            # Build methods (important for Flutter)
            'build_method': re.compile(
                r'^(\s*)(@override\s+)?Widget\s+build\s*\([^)]*\)\s*\{',
                re.MULTILINE
            ),
            
            # State classes
            'state_class': re.compile(
                r'^(\s*)(class)\s+(_[A-Z][a-zA-Z0-9_]*State)\s+extends\s+State\s*<[^>]+>\s*\{',
                re.MULTILINE
            ),
            
            # Enums
            'enum': re.compile(
                r'^(\s*)(enum)\s+([A-Z][a-zA-Z0-9_]*)\s*\{',
                re.MULTILINE
            ),
            
            # Mixins
            'mixin': re.compile(
                r'^(\s*)(mixin)\s+([A-Z][a-zA-Z0-9_]*)\s*(?:on\s+[^{]+)?\s*\{',
                re.MULTILINE
            ),
            
            # Extensions
            'extension': re.compile(
                r'^(\s*)(extension)\s+([A-Z][a-zA-Z0-9_]*)\s+on\s+([^{]+)\s*\{',
                re.MULTILINE
            ),
            
            # Variables and Fields
            'field': re.compile(
                r'^(\s*)(final|const|static\s+final|static\s+const|var|late)\s+'
                r'(?:[A-Z][a-zA-Z0-9_<>,\s]*\s+)?([a-zA-Z_][a-zA-Z0-9_]*)',
                re.MULTILINE
            ),
            
            # Constructors
            'constructor': re.compile(
                r'^(\s*)([A-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)?)\s*\([^{]*\)(?:\s*:\s*[^{]+)?\s*\{',
                re.MULTILINE
            ),
            
            # Imports
            'import': re.compile(
                r"^(\s*)import\s+['\"]([^'\"]+)['\"](?:\s+as\s+([a-zA-Z_][a-zA-Z0-9_]*))?\s*;",
                re.MULTILINE
            ),
            
            # Exports
            'export': re.compile(
                r"^(\s*)export\s+['\"]([^'\"]+)['\"](?:\s+show\s+[^;]+)?\s*;",
                re.MULTILINE
            ),
        }
        
        # Flutter-specific widget patterns
        self.flutter_widgets = re.compile(
            r'\b(MaterialApp|Scaffold|AppBar|Container|Column|Row|Stack|Positioned|'
            r'Text|TextField|RaisedButton|FlatButton|ElevatedButton|TextButton|'
            r'ListView|GridView|Card|FloatingActionButton|Drawer|BottomNavigationBar|'
            r'StatelessWidget|StatefulWidget|InheritedWidget|Provider|Consumer|'
            r'FutureBuilder|StreamBuilder|AnimatedContainer|Hero|GestureDetector|'
            r'InkWell|Padding|Margin|Expanded|Flexible|Wrap|Flow|CustomScrollView|'
            r'SliverList|SliverGrid|TabBar|TabBarView|PageView|IndexedStack|'
            r'BottomSheet|AlertDialog|SimpleDialog|SnackBar|Theme|MediaQuery)\b'
        )
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse Flutter/Dart code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            if pattern_name in ['import', 'export']:  # Handle separately
                continue
                
            for match in pattern.finditer(content):
                try:
                    element = self._create_flutter_element(match, pattern_name, lines, content, file_path)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_flutter_element(self, match, pattern_name: str, lines: List[str],
                               content: str, file_path: str) -> ParsedElement:
        """Create ParsedElement from Flutter/Dart match."""
        groups = match.groups()
        indent = groups[0] if len(groups) > 0 else ""
        
        # Extract name and type based on pattern
        if pattern_name in ['class', 'widget', 'state_class']:
            modifiers = groups[1] if len(groups) > 1 and groups[1] else ""
            name = groups[2] if len(groups) > 2 else (groups[1] if len(groups) > 1 else "unnamed")
            if pattern_name == 'widget':
                name = groups[2] if len(groups) > 2 else "unnamed"
                widget_type = groups[3] if len(groups) > 3 else "Widget"
            element_type = ElementType.CLASS
        elif pattern_name == 'function':
            modifiers = groups[1] if len(groups) > 1 else ""
            name = groups[2] if len(groups) > 2 else "unnamed"
            element_type = ElementType.FUNCTION
        elif pattern_name == 'build_method':
            name = "build"
            element_type = ElementType.METHOD
        elif pattern_name in ['enum', 'mixin']:
            name = groups[2] if len(groups) > 2 else "unnamed"
            element_type = ElementType.ENUM if pattern_name == 'enum' else ElementType.CLASS
        elif pattern_name == 'extension':
            name = groups[2] if len(groups) > 2 else "unnamed"
            target_type = groups[3] if len(groups) > 3 else "unknown"
            element_type = ElementType.CLASS
        elif pattern_name == 'field':
            modifiers = groups[1] if len(groups) > 1 else ""
            name = groups[2] if len(groups) > 2 else "unnamed"
            element_type = ElementType.VARIABLE
        elif pattern_name == 'constructor':
            name = groups[1] if len(groups) > 1 else "constructor"
            element_type = ElementType.METHOD
        else:
            return None
        
        start_line = content[:match.start()].count('\n')
        
        # Determine visibility (Dart uses underscore prefix for private)
        if name.startswith('_'):
            visibility = Visibility.PRIVATE
        else:
            visibility = Visibility.PUBLIC
        
        # Find block end
        if pattern_name in ['class', 'widget', 'state_class', 'enum', 'mixin', 'extension']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        elif pattern_name in ['function', 'build_method', 'constructor']:
            end_line = self._find_block_end(lines, start_line, 'brace')
        else:
            end_line = start_line + 1
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Flutter/Dart specific metadata
        metadata = {
            'pattern_type': pattern_name,
            'indent_level': len(indent),
            'is_private': name.startswith('_'),
            'is_flutter_related': self._is_flutter_related(content_lines),
            'flutter_widgets_used': self._extract_flutter_widgets(content_lines),
        }
        
        if pattern_name in ['class', 'widget', 'state_class']:
            metadata.update({
                'is_abstract': 'abstract' in (modifiers if 'modifiers' in locals() else ""),
                'is_sealed': 'sealed' in (modifiers if 'modifiers' in locals() else ""),
                'extends': self._extract_extends(match.group(0)),
                'implements': self._extract_implements(match.group(0)),
                'mixins': self._extract_mixins(match.group(0)),
            })
            
            if pattern_name == 'widget':
                widget_type = groups[3] if len(groups) > 3 else "Widget"
                metadata.update({
                    'widget_type': widget_type,
                    'is_stateless': widget_type == 'StatelessWidget',
                    'is_stateful': widget_type == 'StatefulWidget',
                    'has_build_method': 'Widget build(' in content_lines,
                    'state_class': self._find_associated_state_class(content, name) if widget_type == 'StatefulWidget' else None
                })
        elif pattern_name == 'function':
            metadata.update({
                'is_async': 'async' in (modifiers if 'modifiers' in locals() else ""),
                'is_static': 'static' in (modifiers if 'modifiers' in locals() else ""),
                'return_type': self._extract_return_type(modifiers if 'modifiers' in locals() else "", name),
                'parameters': self._extract_dart_parameters(match.group(0)),
                'is_future': 'Future' in (modifiers if 'modifiers' in locals() else ""),
                'is_stream': 'Stream' in (modifiers if 'modifiers' in locals() else ""),
            })
        elif pattern_name == 'build_method':
            metadata.update({
                'is_build_method': True,
                'is_override': '@override' in match.group(0),
                'returns_widget': True,
                'build_context_param': 'BuildContext' in match.group(0)
            })
        elif pattern_name == 'field':
            metadata.update({
                'is_final': 'final' in modifiers,
                'is_const': 'const' in modifiers,
                'is_static': 'static' in modifiers,
                'is_late': 'late' in modifiers,
                'field_type': self._extract_field_type(match.group(0))
            })
        elif pattern_name == 'extension':
            metadata.update({
                'extends_type': target_type if 'target_type' in locals() else "unknown",
                'is_extension': True
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
        """Extract Dart/Flutter dependencies."""
        dependencies = []
        
        # Import statements
        for match in self.patterns['import'].finditer(content):
            line_num = content[:match.start()].count('\n')
            import_path = match.group(2)
            alias = match.group(3) if len(match.groups()) > 2 and match.group(3) else None
            
            # Categorize import types
            if import_path.startswith('package:flutter/'):
                import_type = 'flutter_core'
            elif import_path.startswith('package:'):
                import_type = 'package'
            elif import_path.startswith('dart:'):
                import_type = 'dart_core'
            else:
                import_type = 'relative'
            
            dependencies.append(DependencyInfo(
                name=import_path.split('/')[-1].replace('.dart', ''),
                import_type=import_type,
                source=import_path,
                alias=alias,
                line_number=line_num
            ))
        
        # Export statements
        for match in self.patterns['export'].finditer(content):
            line_num = content[:match.start()].count('\n')
            export_path = match.group(2)
            
            dependencies.append(DependencyInfo(
                name=export_path.split('/')[-1].replace('.dart', ''),
                import_type='export',
                source=export_path,
                line_number=line_num
            ))
        
        return dependencies
    
    def _is_flutter_related(self, content: str) -> bool:
        """Check if content is Flutter-related."""
        flutter_indicators = [
            'Widget', 'StatelessWidget', 'StatefulWidget', 'BuildContext',
            'MaterialApp', 'Scaffold', 'flutter', 'material.dart',
            'cupertino.dart', 'widgets.dart', '@override'
        ]
        
        return any(indicator in content for indicator in flutter_indicators)
    
    def _extract_flutter_widgets(self, content: str) -> List[str]:
        """Extract Flutter widgets used in the content."""
        widgets = set()
        
        for match in self.flutter_widgets.finditer(content):
            widget_name = match.group(1)
            widgets.add(widget_name)
        
        return list(widgets)
    
    def _extract_extends(self, class_def: str) -> Optional[str]:
        """Extract the class that this class extends."""
        extends_match = re.search(r'extends\s+([A-Z][a-zA-Z0-9_<>,\s]*)', class_def)
        return extends_match.group(1).strip() if extends_match else None
    
    def _extract_implements(self, class_def: str) -> List[str]:
        """Extract interfaces that this class implements."""
        implements_match = re.search(r'implements\s+([^{]+)', class_def)
        if implements_match:
            interfaces = implements_match.group(1).strip()
            return [i.strip() for i in interfaces.split(',')]
        return []
    
    def _extract_mixins(self, class_def: str) -> List[str]:
        """Extract mixins used by this class."""
        with_match = re.search(r'with\s+([^{]+?)(?:\s+implements|$)', class_def)
        if with_match:
            mixins = with_match.group(1).strip()
            return [m.strip() for m in mixins.split(',')]
        return []
    
    def _extract_return_type(self, modifiers: str, function_name: str) -> str:
        """Extract return type from function modifiers."""
        # Look for explicit return types
        type_patterns = [
            r'(Future\s*<[^>]+>)',
            r'(Stream\s*<[^>]+>)',
            r'([A-Z][a-zA-Z0-9_<>,\s]*)\s+' + re.escape(function_name)
        ]
        
        for pattern in type_patterns:
            match = re.search(pattern, modifiers)
            if match:
                return match.group(1).strip()
        
        return 'dynamic'  # Dart's default return type
    
    def _extract_dart_parameters(self, signature: str) -> List[Dict[str, str]]:
        """Extract parameters from Dart function signature."""
        paren_match = re.search(r'\(([^)]*)\)', signature)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        params = []
        # Dart parameters can be complex: type name, {named params}, [optional params]
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Simple parsing - could be enhanced for complex Dart syntax
                parts = param.split()
                if len(parts) >= 2:
                    param_type = parts[0]
                    param_name = parts[1]
                    
                    # Check for optional/named parameters
                    is_optional = '[' in param or ']' in param
                    is_named = '{' in param or '}' in param
                    has_default = '=' in param
                    
                    params.append({
                        'name': param_name,
                        'type': param_type,
                        'optional': is_optional,
                        'named': is_named,
                        'has_default': has_default
                    })
                else:
                    params.append({
                        'name': param,
                        'type': 'dynamic',
                        'optional': False,
                        'named': False,
                        'has_default': False
                    })
        
        return params
    
    def _extract_field_type(self, field_def: str) -> str:
        """Extract field type from field definition."""
        # Match pattern: modifiers type name
        type_match = re.search(r'(?:final|const|var|late)\s+([A-Z][a-zA-Z0-9_<>,\s]*)\s+[a-zA-Z_]', field_def)
        if type_match:
            return type_match.group(1).strip()
        return 'dynamic'
    
    def _find_associated_state_class(self, content: str, widget_name: str) -> Optional[str]:
        """Find the associated State class for a StatefulWidget."""
        state_class_pattern = rf'class\s+(_?{widget_name}State)\s+extends\s+State\s*<{widget_name}>'
        match = re.search(state_class_pattern, content)
        return match.group(1) if match else None
