"""Utilities for Dynamiq integration."""

import json
from typing import Dict, Any, List
from pathlib import Path

from ..utils import validate_config, create_default_config_template
from ..exceptions import ConfigError

def create_dynamiq_config_template(
    workflow_type: str = "simple",
    codebases: List[str] = None,
    output_dir: str = "./lynx_results"
) -> Dict[str, Any]:
    """Create a Dynamiq workflow configuration template."""
    
    base_config = create_default_config_template("multi-model")
    
    dynamiq_config = {
        "workflow": {
            "type": workflow_type,
            "name": f"lynx_{workflow_type}_workflow",
            "description": f"Lynx {workflow_type} analysis workflow"
        },
        "lynx_config": base_config,
        "execution": {
            "parallel": True,
            "max_concurrent": 3,
            "timeout_minutes": 30
        },
        "output": {
            "directory": output_dir,
            "format": "markdown",
            "include_stats": True
        }
    }
    
    if codebases:
        dynamiq_config["inputs"] = {
            "codebases": codebases
        }
    
    return dynamiq_config

def validate_dynamiq_config(config: Dict[str, Any]) -> List[str]:
    """Validate Dynamiq workflow configuration."""
    issues = []
    
    # Check workflow configuration
    if "workflow" not in config:
        issues.append("Missing 'workflow' configuration")
    else:
        workflow = config["workflow"]
        if "type" not in workflow:
            issues.append("Workflow type not specified")
        if "name" not in workflow:
            issues.append("Workflow name not specified")
    
    # Validate Lynx configuration
    if "lynx_config" in config:
        lynx_issues = validate_config(config["lynx_config"])
        issues.extend([f"Lynx config: {issue}" for issue in lynx_issues])
    
    # Check execution settings
    if "execution" in config:
        exec_config = config["execution"]
        if "max_concurrent" in exec_config:
            max_concurrent = exec_config["max_concurrent"]
            if not isinstance(max_concurrent, int) or max_concurrent < 1:
                issues.append("max_concurrent must be a positive integer")
    
    return issues

def save_dynamiq_config(config: Dict[str, Any], path: str) -> None:
    """Save Dynamiq configuration to file."""
    issues = validate_dynamiq_config(config)
    if issues:
        raise ConfigError(f"Invalid Dynamiq configuration:\n" + "\n".join(issues))
    
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2)

class DynamiqResultsProcessor:
    """Process and format Dynamiq workflow results."""
    
    @staticmethod
    def combine_summaries(results: List[Dict[str, Any]]) -> str:
        """Combine multiple analysis results into a master summary."""
        summaries = []
        for result in results:
            if "summary" in result:
                codebase = result.get("codebase_path", "Unknown")
                summaries.append(f"## {Path(codebase).name}\n\n{result['summary']}")
        
        master_summary = "# Combined Codebase Analysis\n\n"
        master_summary += "\n\n".join(summaries)
        
        return master_summary
    
    @staticmethod
    def generate_stats_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate comprehensive statistics from multiple results."""
        total_files = 0
        total_requests = 0
        total_tokens = 0
        total_cost = 0.0
        providers_used = set()
        
        for result in results:
            if "stats" in result:
                stats = result["stats"]
                if "files_processed" in stats:
                    total_files += stats["files_processed"]
                if "ai_usage" in stats:
                    ai_stats = stats["ai_usage"]
                    total_requests += ai_stats.get("total_requests", 0)
                    total_tokens += ai_stats.get("total_tokens_used", 0)
                    total_cost += ai_stats.get("estimated_cost", 0.0)
                    if "primary_provider" in ai_stats:
                        providers_used.add(ai_stats["primary_provider"])
        
        return {
            "total_codebases": len(results),
            "total_files_processed": total_files,
            "total_ai_requests": total_requests,
            "total_tokens_used": total_tokens,
            "total_estimated_cost": total_cost,
            "providers_used": list(providers_used),
            "average_files_per_codebase": total_files / len(results) if results else 0
        }
