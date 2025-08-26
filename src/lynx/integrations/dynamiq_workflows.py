"""Pre-built Dynamiq workflows for common Lynx use cases."""

from typing import Dict, Any, List, Optional
from dynamiq.workflows import Workflow
from dynamiq.connections import ConnectionType

from .dynamiq_nodes import (
    LynxCodebaseAnalyzer, 
    LynxFileAnalyzer, 
    LynxBatchAnalyzer,
    CodebaseInput,
    FileAnalysisInput,
    BatchAnalysisInput
)

class LynxWorkflows:
    """Pre-built workflows for common Lynx analysis patterns."""
    
    @staticmethod
    def simple_analysis_workflow() -> Workflow:
        """Simple codebase analysis workflow."""
        workflow = Workflow(name="lynx_simple_analysis")
        
        # Add analyzer component
        analyzer = LynxCodebaseAnalyzer(name="analyzer")
        workflow.add_component(analyzer)
        
        return workflow
    
    @staticmethod
    def comprehensive_analysis_workflow() -> Workflow:
        """Comprehensive analysis with multiple outputs."""
        workflow = Workflow(name="lynx_comprehensive_analysis")
        
        # Main analyzer
        analyzer = LynxCodebaseAnalyzer(
            name="main_analyzer",
            auto_config=True,
            fallback_enabled=True
        )
        workflow.add_component(analyzer)
        
        # You could add post-processing components here
        # For example, a component that formats the output differently
        # or sends results to different destinations
        
        return workflow
    
    @staticmethod
    def batch_processing_workflow() -> Workflow:
        """Workflow for processing multiple codebases."""
        workflow = Workflow(name="lynx_batch_processing")
        
        # Batch analyzer
        batch_analyzer = LynxBatchAnalyzer(name="batch_analyzer")
        workflow.add_component(batch_analyzer)
        
        return workflow
    
    @staticmethod
    def file_by_file_workflow() -> Workflow:
        """Workflow for detailed file-by-file analysis."""
        workflow = Workflow(name="lynx_file_by_file")
        
        # File analyzer for individual files
        file_analyzer = LynxFileAnalyzer(name="file_analyzer")
        workflow.add_component(file_analyzer)
        
        return workflow

class LynxWorkflowBuilder:
    """Builder for custom Lynx workflows."""
    
    def __init__(self):
        self.workflow = Workflow(name="custom_lynx_workflow")
        self.components = {}
    
    def add_codebase_analyzer(
        self, 
        name: str = "analyzer",
        auto_config: bool = True,
        fallback_enabled: bool = True
    ) -> 'LynxWorkflowBuilder':
        """Add a codebase analyzer to the workflow."""
        analyzer = LynxCodebaseAnalyzer(
            name=name,
            auto_config=auto_config,
            fallback_enabled=fallback_enabled
        )
        self.workflow.add_component(analyzer)
        self.components[name] = analyzer
        return self
    
    def add_file_analyzer(self, name: str = "file_analyzer") -> 'LynxWorkflowBuilder':
        """Add a file analyzer to the workflow."""
        analyzer = LynxFileAnalyzer(name=name)
        self.workflow.add_component(analyzer)
        self.components[name] = analyzer
        return self
    
    def add_batch_analyzer(self, name: str = "batch_analyzer") -> 'LynxWorkflowBuilder':
        """Add a batch analyzer to the workflow."""
        analyzer = LynxBatchAnalyzer(name=name)
        self.workflow.add_component(analyzer)
        self.components[name] = analyzer
        return self
    
    def connect_components(self, from_component: str, to_component: str) -> 'LynxWorkflowBuilder':
        """Connect two components in the workflow."""
        if from_component in self.components and to_component in self.components:
            # Add connection logic here based on Dynamiq's connection system
            pass
        return self
    
    def build(self) -> Workflow:
        """Build and return the workflow."""
        return self.workflow
