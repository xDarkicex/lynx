"""Comprehensive SQL language parser."""

import re
from typing import List, Dict, Any, Optional
from .base import BaseLanguageParser, ParsedElement, DependencyInfo, ElementType, Visibility

class SqlParser(BaseLanguageParser):
    """Advanced SQL language parser."""
    
    language_name = "sql"
    supported_extensions = [".sql"]
    
    def __init__(self):
        self.patterns = {
            'table': re.compile(
                r'CREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
                r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
                re.IGNORECASE | re.MULTILINE
            ),
            'view': re.compile(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'function': re.compile(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?FUNCTION\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'procedure': re.compile(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?PROCEDURE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'trigger': re.compile(
                r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'index': re.compile(
                r'CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?'
                r'([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'schema': re.compile(
                r'CREATE\s+SCHEMA\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'sequence': re.compile(
                r'CREATE\s+SEQUENCE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
            'type': re.compile(
                r'CREATE\s+TYPE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
                re.IGNORECASE | re.MULTILINE
            ),
        }
    
    def parse_elements(self, content: str, file_path: str = "") -> List[ParsedElement]:
        """Parse SQL code elements."""
        elements = []
        lines = content.split('\n')
        
        for pattern_name, pattern in self.patterns.items():
            for match in pattern.finditer(content):
                try:
                    element = self._create_sql_element(match, pattern_name, lines, content)
                    if element:
                        elements.append(element)
                except Exception:
                    continue
        
        return sorted(elements, key=lambda x: x.start_line)
    
    def _create_sql_element(self, match, pattern_name: str, 
                           lines: List[str], content: str) -> ParsedElement:
        """Create ParsedElement from SQL match."""
        start_line = content[:match.start()].count('\n')
        name = match.group(1) if match.groups() else f"unnamed_{pattern_name}"
        
        # Map SQL objects to element types
        element_type_map = {
            'table': ElementType.CLASS,
            'view': ElementType.CLASS,
            'function': ElementType.FUNCTION,
            'procedure': ElementType.FUNCTION,
            'trigger': ElementType.FUNCTION,
            'index': ElementType.VARIABLE,
            'schema': ElementType.NAMESPACE,
            'sequence': ElementType.VARIABLE,
            'type': ElementType.STRUCT,
        }
        
        element_type = element_type_map.get(pattern_name, ElementType.CLASS)
        
        # Find statement end (semicolon or empty line)
        end_line = self._find_sql_statement_end(lines, start_line)
        
        content_lines = '\n'.join(lines[start_line:end_line])
        
        # Rich metadata
        metadata = {
            'sql_object_type': pattern_name,
            'statement': self._extract_statement_type(match.group(0)),
            'is_temp': 'TEMP' in match.group(0).upper(),
            'or_replace': 'OR REPLACE' in match.group(0).upper(),
            'if_not_exists': 'IF NOT EXISTS' in match.group(0).upper(),
        }
        
        if pattern_name == 'table':
            metadata.update({
                'columns': self._extract_table_columns(content_lines),
                'constraints': self._extract_table_constraints(content_lines)
            })
        elif pattern_name in ['function', 'procedure']:
            metadata.update({
                'parameters': self._extract_function_parameters(content_lines),
                'return_type': self._extract_return_type(content_lines)
            })
        elif pattern_name == 'index':
            metadata.update({
                'is_unique': 'UNIQUE' in match.group(0).upper(),
                'table': self._extract_index_table(content_lines)
            })
        
        return ParsedElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
            visibility=Visibility.PUBLIC,  # SQL objects are generally public
            language=self.language_name,
            content=content_lines,
            metadata=metadata
        )
    
    def extract_dependencies(self, content: str) -> List[DependencyInfo]:
        """Extract SQL dependencies (referenced tables, schemas, etc.)."""
        dependencies = []
        
        # Extract table references from various SQL statements
        table_refs = []
        
        # FROM clauses
        from_matches = re.finditer(r'FROM\s+([a-zA-Z_][a-zA-Z0-9_.]*)', content, re.IGNORECASE)
        for match in from_matches:
            table_refs.append(('table_ref', match.group(1), match.start()))
        
        # JOIN clauses
        join_matches = re.finditer(r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_.]*)', content, re.IGNORECASE)
        for match in join_matches:
            table_refs.append(('table_ref', match.group(1), match.start()))
        
        # INTO clauses
        into_matches = re.finditer(r'INTO\s+([a-zA-Z_][a-zA-Z0-9_.]*)', content, re.IGNORECASE)
        for match in into_matches:
            table_refs.append(('table_ref', match.group(1), match.start()))
        
        # UPDATE statements
        update_matches = re.finditer(r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_.]*)', content, re.IGNORECASE)
        for match in update_matches:
            table_refs.append(('table_ref', match.group(1), match.start()))
        
        # Convert to dependencies
        for ref_type, table_name, position in table_refs:
            line_num = content[:position].count('\n')
            dependencies.append(DependencyInfo(
                name=table_name.split('.')[-1],
                import_type=ref_type,
                source=table_name,
                line_number=line_num
            ))
        
        return dependencies
    
    def _find_sql_statement_end(self, lines: List[str], start_line: int) -> int:
        """Find the end of a SQL statement."""
        for i in range(start_line, len(lines)):
            line = lines[i].strip()
            if line.endswith(';'):
                return i + 1
            # Also check for CREATE statements followed by another CREATE
            if i > start_line and line.upper().startswith('CREATE'):
                return i
        return len(lines)
    
    def _extract_statement_type(self, statement: str) -> str:
        """Extract the type of SQL statement."""
        statement_upper = statement.upper()
        if 'CREATE' in statement_upper:
            return 'CREATE'
        elif 'ALTER' in statement_upper:
            return 'ALTER'
        elif 'DROP' in statement_upper:
            return 'DROP'
        else:
            return 'OTHER'
    
    def _extract_table_columns(self, table_def: str) -> List[str]:
        """Extract column definitions from CREATE TABLE statement."""
        columns = []
        
        # Find content between first parentheses
        paren_match = re.search(r'\((.+)\)', table_def, re.DOTALL)
        if not paren_match:
            return columns
        
        content = paren_match.group(1)
        
        # Split by comma, but be careful with nested parentheses
        current_column = ""
        paren_level = 0
        
        for char in content:
            if char == '(':
                paren_level += 1
            elif char == ')':
                paren_level -= 1
            elif char == ',' and paren_level == 0:
                column_def = current_column.strip()
                if column_def and not column_def.upper().startswith(('CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK')):
                    # Extract column name (first word)
                    column_name = column_def.split()[0]
                    columns.append(column_name)
                current_column = ""
                continue
            
            current_column += char
        
        # Don't forget the last column
        if current_column.strip():
            column_def = current_column.strip()
            if not column_def.upper().startswith(('CONSTRAINT', 'PRIMARY', 'FOREIGN', 'UNIQUE', 'CHECK')):
                column_name = column_def.split()[0]
                columns.append(column_name)
        
        return columns
    
    def _extract_table_constraints(self, table_def: str) -> List[str]:
        """Extract constraint definitions from CREATE TABLE statement."""
        constraints = []
        constraint_patterns = [
            r'PRIMARY\s+KEY',
            r'FOREIGN\s+KEY',
            r'UNIQUE',
            r'CHECK',
            r'CONSTRAINT\s+[a-zA-Z_][a-zA-Z0-9_]*'
        ]
        
        for pattern in constraint_patterns:
            matches = re.finditer(pattern, table_def, re.IGNORECASE)
            for match in matches:
                constraints.append(match.group(0))
        
        return constraints
    
    def _extract_function_parameters(self, func_def: str) -> List[str]:
        """Extract parameters from function/procedure definition."""
        # Look for parameters in parentheses after function name
        paren_match = re.search(r'\(([^)]*)\)', func_def)
        if not paren_match:
            return []
        
        params_str = paren_match.group(1).strip()
        if not params_str:
            return []
        
        params = []
        for param in params_str.split(','):
            param = param.strip()
            if param:
                # Extract parameter name (first word)
                param_name = param.split()[0]
                params.append(param_name)
        
        return params
    
    def _extract_return_type(self, func_def: str) -> str:
        """Extract return type from function definition."""
        # Look for RETURNS clause
        returns_match = re.search(r'RETURNS\s+([a-zA-Z_][a-zA-Z0-9_\(\)]*)', func_def, re.IGNORECASE)
        if returns_match:
            return returns_match.group(1)
        return 'void'
    
    def _extract_index_table(self, index_def: str) -> str:
        """Extract table name from CREATE INDEX statement."""
        on_match = re.search(r'ON\s+([a-zA-Z_][a-zA-Z0-9_.]*)', index_def, re.IGNORECASE)
        if on_match:
            return on_match.group(1)
        return 'unknown'
