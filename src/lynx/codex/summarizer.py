"""Core summarization engine with multi-model fallback support."""

import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime

from ..utils import scan_directory, FileInfo, count_tokens
from ..exceptions import ProcessingError
from .config import CodexConfig
from .chunker import SemanticChunker, Chunk
from .ai_interface import AIInterface, SummaryRequest
from ..plugins.core.manager import PluginManager
from ..plugins.core.base import PluginContext, HookPoint

logger = logging.getLogger(__name__)

class CodexSummarizer:
    """Main summarization engine that orchestrates the entire process."""
    
    def __init__(self, config: CodexConfig):
        self.config = config
        self.chunker = SemanticChunker(
            chunk_size=config.chunk_size,
            overlap=config.chunk_overlap,
            model=config.get_primary_model().model
        )
        self.ai_interface = AIInterface(config)
        
        # Initialize plugin system
        if config.plugin_system.enabled:
            enabled_plugins = config.get_enabled_plugins()
            plugin_options = {name: config.plugin_system.plugins[name].options 
                            for name in enabled_plugins 
                            if name in config.plugin_system.plugins}
            self.plugin_manager = PluginManager.from_config(enabled_plugins, plugin_options)
        else:
            self.plugin_manager = None
            
        self.stats = {
            'files_processed': 0,
            'chunks_created': 0,
            'errors': [],
            'fallbacks_used': 0,
            'start_time': None,
            'end_time': None,
            'plugin_errors': []
        }
    
    def summarize_codebase(self) -> Dict[str, Any]:
        """Main entry point for codebase summarization with plugin hooks."""
        self.stats['start_time'] = datetime.now()
        
        try:
            # Create plugin context
            ctx = PluginContext(config=self.config)
            
            # Step 1: Scan directory for files
            logger.info(f"Scanning codebase: {self.config.codebase_path}")
            
            # BEFORE_SCAN hook
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_SCAN, ctx)
            
            files = scan_directory(
                self.config.codebase_path,
                include_patterns=self.config.include_patterns,
                exclude_patterns=self.config.exclude_patterns,
                max_file_size=self.config.max_file_size
            )
            
            if not files:
                raise ProcessingError("No suitable files found in codebase")
            
            # Update context with files and emit AFTER_SCAN
            ctx.state['files'] = files
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_SCAN, ctx)
            
            logger.info(f"Found {len(files)} files to process")
            logger.info(f"AI providers configured: {len(self.config.models)} (fallback {'enabled' if self.config.fallback_enabled else 'disabled'})")
            
            # Step 2: Process files in parallel
            file_summaries = self._process_files_parallel(files, ctx)
            
            # Step 3: Aggregate into master summary
            logger.info("Aggregating summaries...")
            
            # BEFORE_AGGREGATE hook
            ctx.file_summaries = file_summaries
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_AGGREGATE, ctx)
            
            master_summary = self._create_master_summary(file_summaries, files)
            
            # AFTER_AGGREGATE hook  
            ctx.master_summary = master_summary
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_AGGREGATE, ctx)
            
            # Step 4: Generate output
            output_content = self._format_output(master_summary, file_summaries)
            
            # BEFORE_OUTPUT hook
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_OUTPUT, ctx)
            
            # Step 5: Save results
            self._save_output(output_content)
            
            # AFTER_OUTPUT hook
            ctx.output_path = self.config.output_dest
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_OUTPUT, ctx)
            
            self.stats['end_time'] = datetime.now()
            
            return {
                'summary': master_summary,
                'file_summaries': file_summaries,
                'stats': self._get_final_stats(),
                'output_path': self.config.output_dest,
                'plugin_data': ctx.state.get('plugin_results', {})
            }
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            self.stats['errors'].append(str(e))
            
            # ON_ERROR hook
            if self.plugin_manager:
                error_ctx = PluginContext(config=self.config)
                error_ctx.state['error'] = str(e)
                self.plugin_manager.emit(HookPoint.ON_ERROR, error_ctx)
            
            self.stats['end_time'] = datetime.now()
            raise ProcessingError(f"Codebase summarization failed: {e}")
    
    def _process_files_parallel(self, files: List[FileInfo], ctx: PluginContext) -> Dict[str, str]:
        """Process multiple files in parallel using thread pool with plugin context."""
        file_summaries = {}
        
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all file processing tasks
            future_to_file = {
                executor.submit(self._process_single_file, file_info, ctx): file_info
                for file_info in files
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                
                try:
                    summary = future.result(timeout=self.config.timeout_seconds)
                    file_summaries[file_info.relative_path] = summary
                    self.stats['files_processed'] += 1
                    
                    logger.debug(f"Processed: {file_info.relative_path}")
                    
                except Exception as e:
                    error_msg = f"Failed to process {file_info.relative_path}: {e}"
                    logger.error(error_msg)
                    self.stats['errors'].append(error_msg)
                    file_summaries[file_info.relative_path] = f"Error: {error_msg}"
        
        return file_summaries
    
    def _process_single_file(self, file_info: FileInfo, ctx: PluginContext) -> str:
        """Process a single file with plugin hooks."""
        try:
            # Read file content
            with open(file_info.path, 'r', encoding=file_info.encoding) as f:
                content = f.read()
            
            # Skip empty files
            if not content.strip():
                return "Empty file"
            
            # Update context for this file
            ctx.file_info = file_info
            ctx.content = content
            
            # Check if file needs chunking
            primary_model = self.config.get_primary_model().model
            file_tokens = count_tokens(content, primary_model)
            if file_tokens > self.config.chunk_size * 4:
                return self._process_large_file(file_info, content, ctx)
            else:
                return self._process_regular_file(file_info, content, ctx)
                
        except Exception as e:
            raise ProcessingError(f"Failed to process file {file_info.relative_path}: {e}")
    
    def _process_regular_file(self, file_info: FileInfo, content: str, ctx: PluginContext) -> str:
        """Process a regular-sized file with plugin hooks."""
        # BEFORE_AI_REQUEST hook
        if self.plugin_manager:
            self.plugin_manager.emit(HookPoint.BEFORE_AI_REQUEST, ctx)
        
        request = SummaryRequest(
            content=content,
            file_path=file_info.relative_path,
            language=file_info.language,
            chunk_type='file',
            metadata={'size': file_info.size, 'extension': file_info.extension}
        )
        
        ctx.request = request
        response = self.ai_interface.summarize_file(request)
        ctx.response = response
        
        # AFTER_AI_RESPONSE hook
        if self.plugin_manager:
            self.plugin_manager.emit(HookPoint.AFTER_AI_RESPONSE, ctx)
        
        # Track fallback usage
        if response.fallback_used:
            self.stats['fallbacks_used'] += 1
            logger.info(f"Used fallback provider {response.provider_used} for {file_info.relative_path}")
        
        if response.error:
            raise ProcessingError(f"AI summarization failed: {response.error}")
        
        return response.summary
    
    def _process_large_file(self, file_info: FileInfo, content: str, ctx: PluginContext) -> str:
        """Process a large file by chunking it first with plugin hooks."""
        # BEFORE_CHUNK hook
        if self.plugin_manager:
            self.plugin_manager.emit(HookPoint.BEFORE_CHUNK, ctx)
        
        # Create semantic chunks
        chunks = self.chunker.chunk_file(file_info, content)
        self.stats['chunks_created'] += len(chunks)
        
        # AFTER_CHUNK hook
        ctx.chunks = chunks
        if self.plugin_manager:
            self.plugin_manager.emit(HookPoint.AFTER_CHUNK, ctx)
        
        # Process chunks with enhanced context from plugins
        chunk_summaries = []
        for chunk in chunks:
            # Update context for this chunk
            chunk_ctx = PluginContext(config=self.config)
            chunk_ctx.file_info = file_info
            chunk_ctx.content = chunk.content
            chunk_ctx.chunks = [chunk]
            
            # Use any plugin-enhanced context
            if 'chunk_hints' in ctx.state and file_info.relative_path in ctx.state['chunk_hints']:
                chunk.metadata.update(ctx.state['chunk_hints'][file_info.relative_path])
            
            request = SummaryRequest(
                content=chunk.content,
                file_path=f"{file_info.relative_path}:{chunk.start_line}-{chunk.end_line}",
                language=chunk.language,
                chunk_type=chunk.chunk_type,
                metadata=chunk.metadata
            )
            
            # BEFORE_AI_REQUEST hook for chunk
            chunk_ctx.request = request
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_AI_REQUEST, chunk_ctx)
            
            response = self.ai_interface.summarize_file(request)
            chunk_ctx.response = response
            
            # AFTER_AI_RESPONSE hook for chunk
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_AI_RESPONSE, chunk_ctx)
            
            # Track fallback usage
            if response.fallback_used:
                self.stats['fallbacks_used'] += 1
            
            if not response.error:
                chunk_summaries.append(response.summary)
            else:
                logger.warning(f"Failed to summarize chunk: {response.error}")
        
        # Combine chunk summaries for the file
        if chunk_summaries:
            combined_summary = f"File summary (chunked):\n" + "\n\n".join(chunk_summaries)
            return combined_summary
        else:
            return f"Could not summarize file {file_info.relative_path} (all chunks failed)"
    
    def _create_master_summary(self, file_summaries: Dict[str, str], files: List[FileInfo]) -> str:
        """Create the master summary from individual file summaries."""
        # Filter out error summaries
        valid_summaries = [
            summary for summary in file_summaries.values()
            if not summary.startswith("Error:")
        ]
        
        if not valid_summaries:
            return "No valid summaries could be generated."
        
        # Use AI to aggregate summaries
        response = self.ai_interface.aggregate_summaries(valid_summaries)
        
        # Track fallback usage
        if response.fallback_used:
            self.stats['fallbacks_used'] += 1
            logger.info(f"Used fallback provider {response.provider_used} for aggregation")
        
        if response.error:
            logger.warning(f"AI aggregation failed: {response.error}")
            # Fallback to simple concatenation
            return self._create_fallback_summary(file_summaries, files)
        
        return response.summary
    
    def _create_fallback_summary(self, file_summaries: Dict[str, str], files: List[FileInfo]) -> str:
        """Create a fallback summary when AI aggregation fails."""
        summary_parts = ["# Codebase Summary", ""]
        
        # Group by language
        by_language = {}
        for file_info in files:
            if file_info.language not in by_language:
                by_language[file_info.language] = []
            by_language[file_info.language].append(file_info)
        
        for language, lang_files in by_language.items():
            summary_parts.append(f"## {language.title()} Files")
            
            for file_info in lang_files[:10]:  # Limit to avoid too long output
                if file_info.relative_path in file_summaries:
                    summary = file_summaries[file_info.relative_path]
                    if not summary.startswith("Error:"):
                        summary_parts.append(f"**{file_info.relative_path}**: {summary[:200]}...")
            
            summary_parts.append("")
        
        return "\n".join(summary_parts)
    
    def _format_output(self, master_summary: str, file_summaries: Dict[str, str]) -> str:
        """Format the final output based on configuration."""
        if self.config.output_format == 'json':
            import json
            return json.dumps({
                'master_summary': master_summary,
                'file_summaries': file_summaries,
                'stats': self._get_final_stats()
            }, indent=2)
        
        elif self.config.output_format == 'markdown':
            return self._format_markdown_output(master_summary, file_summaries)
        
        else:  # text format
            return f"MASTER SUMMARY\n{'='*50}\n\n{master_summary}\n\n"
    
    def _format_markdown_output(self, master_summary: str, file_summaries: Dict[str, str]) -> str:
        """Format output as markdown."""
        lines = [
            "# Codebase Analysis Summary",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Codebase:** {self.config.codebase_path}",
            f"**Files Processed:** {self.stats['files_processed']}",
            "",
            "## Overview",
            "",
            master_summary,
            "",
        ]
        
        if self.config.include_metrics:
            usage_stats = self.ai_interface.get_usage_stats()
            lines.extend([
                "## Processing Statistics",
                "",
                f"- **Files processed:** {self.stats['files_processed']}",
                f"- **Chunks created:** {self.stats['chunks_created']}",
                f"- **AI requests:** {usage_stats['total_requests']}",
                f"- **Tokens used:** {usage_stats['total_tokens_used']}",
                f"- **Estimated cost:** ${usage_stats['estimated_cost']:.4f}",
                f"- **Processing time:** {self._get_processing_time()}",
                f"- **Primary provider:** {usage_stats['primary_provider']} ({usage_stats['primary_model']})",
                f"- **Providers configured:** {usage_stats['providers_configured']}",
                f"- **Fallbacks used:** {self.stats['fallbacks_used']}",
                ""
            ])
            
            # Add per-provider breakdown if multiple providers
            if len(usage_stats['provider_stats']) > 1:
                lines.extend([
                    "### Provider Breakdown",
                    ""
                ])
                for provider, stats in usage_stats['provider_stats'].items():
                    lines.append(f"- **{provider}:** {stats['requests']} requests, {stats['tokens']} tokens, {stats['errors']} errors")
                lines.append("")

        if self.stats['errors']:
            lines.extend([
                "## Errors",
                "",
                *[f"- {error}" for error in self.stats['errors']],
                ""
            ])
        
        return "\n".join(lines)
    
    def _save_output(self, content: str) -> None:
        """Save the output to the specified destination."""
        output_path = Path(self.config.output_dest)
        
        try:
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Output saved to: {output_path}")
            
        except Exception as e:
            raise ProcessingError(f"Failed to save output: {e}")
    
    def _get_processing_time(self) -> str:
        """Get formatted processing time."""
        if self.stats['start_time'] and self.stats['end_time']:
            delta = self.stats['end_time'] - self.stats['start_time']
            return f"{delta.total_seconds():.2f} seconds"
        return "Unknown"
    
    def _get_final_stats(self) -> Dict[str, Any]:
        """Get final processing statistics including plugin info."""
        usage_stats = self.ai_interface.get_usage_stats()
        
        stats = {
            **self.stats,
            'processing_time': self._get_processing_time(),
            'ai_usage': usage_stats
        }
        
        if self.plugin_manager:
            stats['plugins_enabled'] = True
            stats['plugin_errors'] = self.stats.get('plugin_errors', [])
        else:
            stats['plugins_enabled'] = False
            
        return stats