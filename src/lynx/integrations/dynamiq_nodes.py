"""Dynamiq integration nodes for Lynx codebase summarization."""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from dynamiq.components import Component
from dynamiq.components.types import ComponentInput, ComponentOutput
from dynamiq.workflows import Workflow
from dynamiq.utils import get_logger

from .. import Codex, init_config, quick_start, validate_setup
from ..utils import (
    create_default_config_template, 
    get_recommended_config_for_codebase,
    scan_directory, 
    FileInfo
)
from ..exceptions import LynxError, ConfigError

logger = get_logger(__name__)

@dataclass
class CodebaseInput(ComponentInput):
    """Input specification for codebase analysis."""
    codebase_path: str
    config: Optional[Dict[str, Any]] = None
    config_type: str = "multi-model"
    analyze_codebase: bool = True
    include_patterns: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None
    chunk_size: Optional[int] = None
    max_workers: Optional[int] = None
    output_format: str = "markdown"

@dataclass
class CodebaseOutput(ComponentOutput):
    """Output specification for codebase analysis."""
    summary: str
    file_summaries: Dict[str, str]
    stats: Dict[str, Any]
    config_used: Dict[str, Any]
    output_path: Optional[str] = None

class LynxCodebaseAnalyzer(Component):
    """Dynamiq component for analyzing codebases with Lynx."""
    
    def __init__(
        self,
        name: str = "lynx_analyzer",
        auto_config: bool = True,
        fallback_enabled: bool = True,
        **kwargs
    ):
        """
        Initialize Lynx analyzer component.
        
        Args:
            name: Component name
            auto_config: Whether to use environment-based auto-configuration
            fallback_enabled: Whether to enable AI provider fallbacks
        """
        super().__init__(name=name, **kwargs)
        self.auto_config = auto_config
        self.fallback_enabled = fallback_enabled
        
        # Validate setup on initialization
        setup_status = validate_setup()
        if not setup_status["ready"]:
            logger.warning(
                f"Lynx setup incomplete. Missing: {setup_status['missing_dependencies']} "
                f"API keys found: {len(setup_status['api_keys_found'])}"
            )

    def execute(self, input_data: CodebaseInput) -> CodebaseOutput:
        """
        Execute codebase analysis.
        
        Args:
            input_data: Codebase analysis input
            
        Returns:
            Analysis results
        """
        try:
            # Validate input
            if not Path(input_data.codebase_path).exists():
                raise LynxError(f"Codebase path not found: {input_data.codebase_path}")
            
            # Prepare configuration
            config = self._prepare_config(input_data)
            
            # Run analysis
            logger.info(f"Starting Lynx analysis of: {input_data.codebase_path}")
            codex = Codex.New(config)
            results = codex.summarize()
            
            # Process results
            return CodebaseOutput(
                summary=results["summary"],
                file_summaries=results["file_summaries"],
                stats=results["stats"],
                config_used=config,
                output_path=results.get("output_path")
            )
            
        except Exception as e:
            logger.error(f"Lynx analysis failed: {e}")
            raise LynxError(f"Codebase analysis failed: {e}")
    
    def _prepare_config(self, input_data: CodebaseInput) -> Dict[str, Any]:
        """Prepare configuration for analysis."""
        if input_data.config:
            # Use provided configuration
            config = input_data.config.copy()
            config["codebase_path"] = input_data.codebase_path
        elif self.auto_config:
            # Use auto-configuration
            try:
                config = init_config(
                    config_type="auto",
                    codebase_path=input_data.codebase_path,
                    analyze_codebase=input_data.analyze_codebase
                )
            except ValueError:
                # Fallback to recommended config
                config = get_recommended_config_for_codebase(input_data.codebase_path)
        else:
            # Use default template
            config = create_default_config_template(input_data.config_type)
            config["codebase_path"] = input_data.codebase_path
        
        # Apply input overrides
        overrides = {}
        if input_data.include_patterns:
            overrides["include_patterns"] = input_data.include_patterns
        if input_data.exclude_patterns:
            overrides["exclude_patterns"] = input_data.exclude_patterns
        if input_data.chunk_size:
            overrides["chunk_size"] = input_data.chunk_size
        if input_data.max_workers:
            overrides["max_workers"] = input_data.max_workers
        if input_data.output_format:
            overrides["output_format"] = input_data.output_format
        
        overrides["fallback_enabled"] = self.fallback_enabled
        
        if overrides:
            from ..utils import merge_configs
            config = merge_configs(config, overrides)
        
        return config

@dataclass
class FileAnalysisInput(ComponentInput):
    """Input for single file analysis."""
    file_path: str
    language: Optional[str] = None
    chunk_type: str = "file"
    config: Optional[Dict[str, Any]] = None

@dataclass  
class FileAnalysisOutput(ComponentOutput):
    """Output for single file analysis."""
    summary: str
    file_info: Dict[str, Any]
    tokens_used: int
    processing_time: float

class LynxFileAnalyzer(Component):
    """Dynamiq component for analyzing single files with Lynx."""
    
    def __init__(self, name: str = "lynx_file_analyzer", **kwargs):
        super().__init__(name=name, **kwargs)
    
    def execute(self, input_data: FileAnalysisInput) -> FileAnalysisOutput:
        """Execute single file analysis."""
        try:
            file_path = Path(input_data.file_path)
            if not file_path.exists():
                raise LynxError(f"File not found: {input_data.file_path}")
            
            # Use quick_start for single file analysis
            config = input_data.config or create_default_config_template("minimal")
            
            # Create temporary directory structure for single file
            temp_dir = file_path.parent
            config["codebase_path"] = str(temp_dir)
            config["include_patterns"] = [file_path.name]
            
            codex = Codex.New(config)
            results = codex.summarize()
            
            # Extract single file results
            file_summary = results["file_summaries"].get(file_path.name, "No summary available")
            
            return FileAnalysisOutput(
                summary=file_summary,
                file_info={
                    "path": str(file_path),
                    "size": file_path.stat().st_size,
                    "language": input_data.language or "unknown"
                },
                tokens_used=results["stats"]["ai_usage"]["total_tokens_used"],
                processing_time=float(results["stats"]["processing_time"].split()[0])
            )
            
        except Exception as e:
            logger.error(f"File analysis failed: {e}")
            raise LynxError(f"File analysis failed: {e}")

@dataclass
class BatchAnalysisInput(ComponentInput):
    """Input for batch analysis of multiple codebases."""
    codebases: List[str]
    config_template: Optional[Dict[str, Any]] = None
    parallel: bool = True
    output_dir: Optional[str] = None

@dataclass
class BatchAnalysisOutput(ComponentOutput):
    """Output for batch analysis."""
    results: List[Dict[str, Any]]
    summary_stats: Dict[str, Any]
    failed_analyses: List[Dict[str, str]]

class LynxBatchAnalyzer(Component):
    """Dynamiq component for batch analysis of multiple codebases."""
    
    def __init__(self, name: str = "lynx_batch_analyzer", **kwargs):
        super().__init__(name=name, **kwargs)
    
    def execute(self, input_data: BatchAnalysisInput) -> BatchAnalysisOutput:
        """Execute batch analysis of multiple codebases."""
        results = []
        failed_analyses = []
        
        for i, codebase_path in enumerate(input_data.codebases):
            try:
                logger.info(f"Analyzing codebase {i+1}/{len(input_data.codebases)}: {codebase_path}")
                
                # Prepare individual analysis
                analysis_input = CodebaseInput(
                    codebase_path=codebase_path,
                    config=input_data.config_template,
                    analyze_codebase=True
                )
                
                # Run analysis
                analyzer = LynxCodebaseAnalyzer()
                result = analyzer.execute(analysis_input)
                
                results.append({
                    "codebase_path": codebase_path,
                    "summary": result.summary,
                    "stats": result.stats,
                    "success": True
                })
                
            except Exception as e:
                logger.error(f"Failed to analyze {codebase_path}: {e}")
                failed_analyses.append({
                    "codebase_path": codebase_path,
                    "error": str(e)
                })
        
        # Calculate summary stats
        summary_stats = {
            "total_codebases": len(input_data.codebases),
            "successful_analyses": len(results),
            "failed_analyses": len(failed_analyses),
            "success_rate": len(results) / len(input_data.codebases) if input_data.codebases else 0
        }
        
        return BatchAnalysisOutput(
            results=results,
            summary_stats=summary_stats,
            failed_analyses=failed_analyses
        )
