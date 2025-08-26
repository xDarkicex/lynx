"""Intelligent chunking for different file types and languages."""

import re
import ast
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from ..utils import FileInfo, count_tokens
from ..exceptions import ChunkingError

@dataclass
class Chunk:
    """Represents a semantic chunk of code."""
    content: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'module', 'block'
    language: str
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

class SemanticChunker:
    """Intelligent chunker that respects code structure."""
    
    def __init__(self, chunk_size: int = 2000, overlap: int = 400, model: str = "gpt-4"):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.model = model
        
        # Language-specific patterns for function/class detection
        self.patterns = {
            'python': {
                'function': re.compile(r'^(async\s+)?def\s+\w+.*?:', re.MULTILINE),
                'class': re.compile(r'^class\s+\w+.*?:', re.MULTILINE),
                'import': re.compile(r'^(from\s+\S+\s+)?import\s+.*', re.MULTILINE)
            },
            'rust': {
                'function': re.compile(r'^(pub\s+)?(async\s+)?fn\s+\w+.*?\{', re.MULTILINE),
                'struct': re.compile(r'^(pub\s+)?struct\s+\w+.*?\{', re.MULTILINE),
                'impl': re.compile(r'^impl.*?\{', re.MULTILINE),
                'mod': re.compile(r'^(pub\s+)?mod\s+\w+', re.MULTILINE)
            },
            'golang': {
                'function': re.compile(r'^func\s+(\w+\s+)?\w+.*?\{', re.MULTILINE),
                'type': re.compile(r'^type\s+\w+.*', re.MULTILINE),
                'var': re.compile(r'^var\s+.*', re.MULTILINE)
            },
            'javascript': {
                'function': re.compile(r'^(async\s+)?function\s+\w+.*?\{', re.MULTILINE),
                'class': re.compile(r'^class\s+\w+.*?\{', re.MULTILINE),
                'const': re.compile(r'^(export\s+)?const\s+\w+\s*=', re.MULTILINE)
            }
        }
    
    def chunk_file(self, file_info: FileInfo, content: str) -> List[Chunk]:
        """
        Intelligently chunk a file based on its language and structure.
        
        Args:
            file_info: File metadata
            content: File content
            
        Returns:
            List of semantic chunks
        """
        try:
            if file_info.language == 'python':
                return self._chunk_python(content)
            elif file_info.language == 'rust':
                return self._chunk_rust(content)
            elif file_info.language in ['javascript', 'typescript']:
                return self._chunk_javascript(content)
            else:
                return self._chunk_generic(content, file_info.language)
        except Exception as e:
            raise ChunkingError(f"Failed to chunk file {file_info.relative_path}: {e}")
    
    def _chunk_python(self, content: str) -> List[Chunk]:
        """Python-specific semantic chunking using AST."""
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 10
                    chunk_content = '\n'.join(lines[start_line:end_line])
                    
                    chunks.append(Chunk(
                        content=chunk_content,
                        start_line=start_line,
                        end_line=end_line,
                        chunk_type='function',
                        language='python',
                        metadata={'name': node.name, 'type': 'function'}
                    ))
                    
                elif isinstance(node, ast.ClassDef):
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 20
                    chunk_content = '\n'.join(lines[start_line:end_line])
                    
                    chunks.append(Chunk(
                        content=chunk_content,
                        start_line=start_line,
                        end_line=end_line,
                        chunk_type='class',
                        language='python',
                        metadata={'name': node.name, 'type': 'class'}
                    ))
            
            # If no AST chunks found, fall back to generic chunking
            if not chunks:
                return self._chunk_generic(content, 'python')
                
        except SyntaxError:
            # If AST parsing fails, use pattern-based chunking
            return self._chunk_by_patterns(content, 'python')
        
        # Merge small chunks and split large ones
        return self._optimize_chunks(chunks, content)
    
    def _chunk_rust(self, content: str) -> List[Chunk]:
        """Rust-specific chunking based on language patterns."""
        return self._chunk_by_patterns(content, 'rust')
    
    def _chunk_javascript(self, content: str) -> List[Chunk]:
        """JavaScript/TypeScript chunking based on patterns."""
        return self._chunk_by_patterns(content, 'javascript')
    
    def _chunk_by_patterns(self, content: str, language: str) -> List[Chunk]:
        """Pattern-based chunking for languages without AST support."""
        chunks = []
        lines = content.split('\n')
        patterns = self.patterns.get(language, {})
        
        current_chunk_start = 0
        
        for pattern_type, pattern in patterns.items():
            for match in pattern.finditer(content):
                # Find line number of match
                line_num = content[:match.start()].count('\n')
                
                # Extract function/class block (rough estimation)
                block_end = self._find_block_end(lines, line_num, language)
                
                chunk_content = '\n'.join(lines[line_num:block_end])
                
                if count_tokens(chunk_content, self.model) > 50:  # Skip tiny chunks
                    chunks.append(Chunk(
                        content=chunk_content,
                        start_line=line_num,
                        end_line=block_end,
                        chunk_type=pattern_type,
                        language=language,
                        metadata={'pattern_type': pattern_type}
                    ))
        
        # Fill gaps with generic chunks
        if not chunks:
            return self._chunk_generic(content, language)
            
        return self._optimize_chunks(chunks, content)
    
    def _find_block_end(self, lines: List[str], start_line: int, language: str) -> int:
        """Find the end of a code block based on indentation/braces."""
        if start_line >= len(lines):
            return start_line
            
        if language == 'python':
            # Python: find end by indentation
            base_indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            
            for i in range(start_line + 1, len(lines)):
                line = lines[i]
                if line.strip() == '':
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= base_indent and line.strip():
                    return i
            return len(lines)
            
        else:
            # Brace-based languages: count braces
            brace_count = 0
            for i in range(start_line, len(lines)):
                line = lines[i]
                brace_count += line.count('{') - line.count('}')
                if i > start_line and brace_count <= 0:
                    return i + 1
            return len(lines)
    
    def _chunk_generic(self, content: str, language: str) -> List[Chunk]:
        """Generic chunking by token size with smart line breaks."""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_tokens = 0
        
        for i, line in enumerate(lines):
            line_tokens = count_tokens(line, self.model)
            
            if current_tokens + line_tokens > self.chunk_size and current_chunk:
                # Create chunk
                chunk_content = '\n'.join(current_chunk)
                chunks.append(Chunk(
                    content=chunk_content,
                    start_line=i - len(current_chunk),
                    end_line=i,
                    chunk_type='block',
                    language=language
                ))
                
                # Start new chunk with overlap
                overlap_lines = int(len(current_chunk) * self.overlap / self.chunk_size)
                current_chunk = current_chunk[-overlap_lines:] if overlap_lines > 0 else []
                current_tokens = sum(count_tokens(l, self.model) for l in current_chunk)
            
            current_chunk.append(line)
            current_tokens += line_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n'.join(current_chunk)
            chunks.append(Chunk(
                content=chunk_content,
                start_line=len(lines) - len(current_chunk),
                end_line=len(lines),
                chunk_type='block',
                language=language
            ))
        
        return chunks
    
    def _optimize_chunks(self, chunks: List[Chunk], original_content: str) -> List[Chunk]:
        """Optimize chunks by merging small ones and splitting large ones."""
        optimized = []
        
        for chunk in chunks:
            tokens = count_tokens(chunk.content, self.model)
            
            if tokens > self.chunk_size * 1.5:
                # Split large chunks
                sub_chunks = self._chunk_generic(chunk.content, chunk.language)
                optimized.extend(sub_chunks)
            else:
                optimized.append(chunk)
        
        return optimized
