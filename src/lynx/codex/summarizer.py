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
from .ai_interface import AIInterface, SummaryRequest, SummaryResponse
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
            plugin_deps = {name: config.plugin_system.plugins[name].dependencies
                          for name in enabled_plugins
                          if name in config.plugin_system.plugins}
            self.plugin_manager = PluginManager.from_config(enabled_plugins, plugin_options, plugin_deps)
        else:
            self.plugin_manager = None
            
        self.stats = {
            'files_processed': 0,
            'chunks_created': 0,
            'errors': [],
            'fallbacks_used': 0,
            'start_time': None,
            'end_time': None,
            'plugin_errors': [],
            'tokens_used': 0,
            'file_times': [],
            'total_files': 0,
        }
    
    def summarize_codebase(self) -> Dict[str, Any]:
        """Main entry point for codebase summarization with plugin hooks."""
        self.stats['start_time'] = datetime.now()

        try:
            # Create plugin context
            ctx = PluginContext(config=self.config)

            # ===== Phase 1: Scan =====
            logger.info("")
            logger.info("=" * 60)
            logger.info("Phase 1/4: SCANNING")
            logger.info("=" * 60)
            logger.info(f"Codebase: {self.config.codebase_path}")

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

            self.stats['total_files'] = len(files)

            # Update context with files and emit AFTER_SCAN
            ctx.state['files'] = files
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_SCAN, ctx)

            model_name = self.config.get_primary_model().model
            provider_name = self.config.get_primary_model().provider
            logger.info(f"Found {len(files)} files to process")
            logger.info(f"Model: {model_name} (provider: {provider_name})")
            logger.info(f"Workers: {self.config.max_workers} | Fallback: {'enabled' if self.config.fallback_enabled else 'disabled'}")

            # ===== Phase 2: Process =====
            logger.info("")
            logger.info("=" * 60)
            logger.info("Phase 2/4: PROCESSING")
            logger.info("=" * 60)

            file_summaries = self._process_files_parallel(files, ctx)

            # ===== Phase 3: Aggregate =====
            logger.info("")
            logger.info("=" * 60)
            logger.info("Phase 3/4: AGGREGATING")
            logger.info("=" * 60)
            
            # BEFORE_AGGREGATE hook
            ctx.file_summaries = file_summaries
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_AGGREGATE, ctx)

            master_summary = self._create_master_summary(file_summaries, files)

            # AFTER_AGGREGATE hook
            ctx.master_summary = master_summary
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_AGGREGATE, ctx)

            # ===== Phase 4: Output =====
            logger.info("")
            logger.info("=" * 60)
            logger.info("Phase 4/4: SAVING OUTPUT")
            logger.info("=" * 60)

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

            # Log final summary
            self._log_final_summary()

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
        processing_start = datetime.now()

        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            # Submit all file processing tasks
            future_to_file = {
                executor.submit(self._process_single_file, file_info, ctx): file_info
                for file_info in files
            }

            # Collect results as they complete
            for future in as_completed(future_to_file):
                file_info = future_to_file[future]
                file_start = datetime.now()

                try:
                    summary, file_time, tokens = future.result(timeout=self.config.timeout_seconds)
                    file_summaries[file_info.relative_path] = summary
                    self.stats['files_processed'] += 1
                    self.stats['tokens_used'] += tokens
                    self.stats['file_times'].append(file_time)

                    # Calculate progress
                    total = len(files)
                    done = self.stats['files_processed']
                    pct = (done / total) * 100
                    elapsed = (datetime.now() - processing_start).total_seconds()
                    avg_time = elapsed / done if done > 0 else 0
                    remaining = avg_time * (total - done)
                    tokens_so_far = self.stats['tokens_used']

                    logger.info(
                        f"Completed ({done}/{total}, {pct:.1f}%): {file_info.relative_path} "
                        f"[{file_time:.1f}s | {tokens} tokens | "
                        f"~{self._format_duration(remaining)} remaining | {tokens_so_far} total tokens]"
                    )

                    # ON_FILE_COMPLETE hook - fire after each file finishes
                    if self.plugin_manager:
                        file_ctx = PluginContext(config=self.config)
                        file_ctx.file_info = file_info
                        file_ctx.file_summary = summary
                        file_ctx.file_time = file_time
                        file_ctx.file_tokens = tokens
                        file_ctx.state['file_summary'] = summary
                        file_ctx.state['file_time'] = file_time
                        file_ctx.state['file_tokens'] = tokens
                        # Accumulate token stats in state for plugins
                        file_ctx.state.setdefault('_token_stats', {'total': 0, 'files': 0, 'errors': 0})
                        file_ctx.state['_token_stats']['total'] += tokens
                        file_ctx.state['_token_stats']['files'] += 1
                        self.plugin_manager.emit(HookPoint.ON_FILE_COMPLETE, file_ctx)

                        # ON_TOKEN_USAGE hook - per-file token accounting
                        # Plugins can use this to track cumulative token usage per-file and overall
                        token_ctx = PluginContext(config=self.config)
                        token_ctx.file_info = file_info
                        token_ctx.file_tokens = tokens
                        token_ctx.file_time = file_time
                        token_ctx.state['tokens_this_file'] = tokens
                        token_ctx.state['tokens_cumulative'] = tokens_so_far
                        token_ctx.state['files_processed'] = done
                        token_ctx.state['files_total'] = total
                        token_ctx.state['avg_tokens_per_file'] = tokens_so_far / done if done > 0 else 0
                        self.plugin_manager.emit(HookPoint.ON_TOKEN_USAGE, token_ctx)

                except Exception as e:
                    error_msg = f"Failed to process {file_info.relative_path}: {e}"
                    logger.error(error_msg)
                    self.stats['errors'].append(error_msg)
                    file_summaries[file_info.relative_path] = f"Error: {error_msg}"
                    self.stats['files_processed'] += 1

        return file_summaries
    
    def _process_single_file(self, file_info: FileInfo, shared_ctx: PluginContext) -> tuple:
        """Process a single file with plugin hooks. Returns (summary, processing_time, tokens_used)."""
        file_start = datetime.now()
        try:
            logger.info(f"Processing file: {file_info.relative_path}")
            # Read file content
            with open(file_info.path, 'r', encoding=file_info.encoding) as f:
                content = f.read()

            # Skip empty files
            if not content.strip():
                elapsed = (datetime.now() - file_start).total_seconds()
                return "Empty file", elapsed, 0

            # Create a thread-safe copy of context for this file
            ctx = PluginContext(config=shared_ctx.config)
            ctx.file_info = file_info
            ctx.content = content
            ctx.state = shared_ctx.state.copy()  # Copy state to avoid race conditions

            # Check if file needs chunking
            primary_model = self.config.get_primary_model().model
            file_tokens = count_tokens(content, primary_model)
            if file_tokens > self.config.chunk_size * 4:
                summary, tokens = self._process_large_file(file_info, content, ctx)
            else:
                summary, tokens = self._process_regular_file(file_info, content, ctx)

            elapsed = (datetime.now() - file_start).total_seconds()
            return summary, elapsed, tokens

        except Exception as e:
            elapsed = (datetime.now() - file_start).total_seconds()
            raise ProcessingError(f"Failed to process file {file_info.relative_path}: {e}")
    
    def _process_regular_file(self, file_info: FileInfo, content: str, ctx: PluginContext) -> tuple:
        """Process a regular-sized file with plugin hooks. Returns (summary, tokens_used)."""
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

        return response.summary, response.tokens_used
    
    def _process_large_file(self, file_info: FileInfo, content: str, ctx: PluginContext) -> tuple:
        """Process a large file by chunking it first with plugin hooks. Returns (summary, tokens_used)."""
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
        total_tokens = 0
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks, 1):
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

            logger.info(f"  Chunk {i}/{total_chunks}: lines {chunk.start_line}-{chunk.end_line}")

            # BEFORE_AI_REQUEST hook for chunk
            chunk_ctx.request = request
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.BEFORE_AI_REQUEST, chunk_ctx)

            response = self.ai_interface.summarize_file(request)
            chunk_ctx.response = response
            total_tokens += response.tokens_used

            # AFTER_AI_RESPONSE hook for chunk
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.AFTER_AI_RESPONSE, chunk_ctx)

            # ON_CHUNK_COMPLETE hook - fires after each chunk
            if self.plugin_manager:
                self.plugin_manager.emit(HookPoint.ON_CHUNK_COMPLETE, chunk_ctx)

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
            return combined_summary, total_tokens
        else:
            return f"Could not summarize file {file_info.relative_path} (all chunks failed)", total_tokens
    
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
        
        # DURING_AGGREGATE hook - fires after aggregation completes
        if self.plugin_manager:
            agg_ctx = PluginContext(config=self.config)
            agg_ctx.master_summary = response.summary
            agg_ctx.file_summaries = file_summaries
            self.plugin_manager.emit(HookPoint.DURING_AGGREGATE, agg_ctx)
        
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

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = seconds / 60
            return f"{mins:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    def _log_final_summary(self) -> None:
        """Log comprehensive final summary of the run."""
        stats = self._get_final_stats()
        usage = stats.get('ai_usage', {})

        logger.info("")
        logger.info("=" * 60)
        logger.info("RUN COMPLETE - FINAL SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Files processed:   {stats['files_processed']} / {stats['total_files']}")
        logger.info(f"Total tokens:      {stats['tokens_used']:,}")
        logger.info(f"Processing time:   {stats['processing_time']}")
        logger.info(f"Model used:        {usage.get('primary_model', 'N/A')} ({usage.get('primary_provider', 'N/A')})")
        logger.info(f"Errors:            {len(stats['errors'])}")
        if stats['fallbacks_used'] > 0:
            logger.info(f"Fallbacks used:    {stats['fallbacks_used']}")
        if stats['file_times']:
            avg_time = sum(stats['file_times']) / len(stats['file_times'])
            max_time = max(stats['file_times'])
            min_time = min(stats['file_times'])
            logger.info(f"Avg file time:    {avg_time:.2f}s (min: {min_time:.2f}s, max: {max_time:.2f}s)")
        logger.info(f"Output saved:     {self.config.output_dest}")
        logger.info("=" * 60)