# Lynx Codex

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/xDarkicex/lynx)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)

**Lynx Codex** is an intelligent codebase summarization toolkit that leverages artificial intelligence to automatically analyze, document, and summarize software projects. Built with multi-model fallback support, semantic code understanding, and an extensible plugin system, Lynx transforms complex codebases into comprehensive, readable documentation.

## Features

### Multi-Model AI Support
- **Multiple AI Providers**: OpenAI GPT-4, Anthropic Claude, Perplexity Sonar
- **Intelligent Fallback**: Automatic failover between providers for maximum reliability
- **Cost Optimization**: Smart provider selection based on task complexity and cost

### Intelligent Code Analysis
- **Semantic Chunking**: Respects code structure (functions, classes, modules)
- **Language-Aware**: Optimized parsing for Bash, C, C++, C#, CSS, Dart (Flutter), Go, HTML, Java, JavaScript, Kotlin, Next.js, PHP, Python, React, Ruby, Rust, SQL, Swift, TypeScript, and generic fallback
- **Context Preservation**: Maintains code relationships across large files
- **Plugin System**: Extensible architecture with built-in plugins for enhanced parsing and analysis

### Flexible Integration
- **CLI Tool**: Full-featured command-line interface
- **Python API**: Programmatic access with simple and advanced interfaces
- **Dynamiq Integration**: Pre-built workflows for enterprise automation
- **Multiple Output Formats**: Markdown, JSON, and plain text

### Production Ready
- **Parallel Processing**: Multi-threaded analysis for large codebases
- **Error Handling**: Robust error recovery and detailed logging
- **Configuration Management**: Flexible config system with smart defaults
- **Comprehensive Metrics**: Detailed processing statistics and cost tracking

## Plugin System

Lynx features a modular plugin system that allows for easy extension of its core functionality. Plugins can enhance code parsing, add custom analysis steps, or integrate with external tools.

### Built-in Plugins
- **Language Bridge**: Provides advanced, language-specific parsing for semantic understanding and element extraction across supported languages.

### Enabling Plugins
Plugins are enabled by default. Use CLI flags or configuration to manage them:
- `--enable-plugins`: Explicitly enable the plugin system
- `--disable-plugins`: Disable all plugins
- `--list-plugins`: List available plugins and exit

### Custom Plugins
Develop custom plugins by extending the base plugin class. Register them via the plugin registry for seamless integration.

## Quick Start

### Installation

```bash
pip install lynx-codex
```

### Environment Setup

Set your AI provider API keys:

```bash
export PPLX_API_KEY="your-perplexity-key"
export OPENAI_API_KEY="your-openai-key"  
export ANTHROPIC_API_KEY="your-anthropic-key"
```

### Basic Usage

```python
import lynx

# Analyze a codebase with auto-configuration
results = lynx.quick_start("/path/to/your/project")
print("Analysis complete! Check master_summary.md")
```

### CLI Usage

```bash
# Quick analysis with auto-configuration
lynx /path/to/codebase --auto-config

# Create a custom configuration
lynx --create-config my-config.json --config-type multi-model

# Run with custom config
lynx /path/to/codebase my-config.json
```

## Documentation

### Configuration

#### Auto-Configuration
Lynx can automatically configure itself using environment variables:

```python
import lynx

# Auto-detect from environment
config = lynx.init_config("auto")
summary = lynx.summarize("/path/to/codebase", config)
```

#### Custom Configuration
Create detailed configurations for specific needs:

```python
config = lynx.init_config(
    config_type="multi-model",
    codebase_path="/path/to/project",
    chunk_size=3000,
    max_workers=12,
    save_to_file="project-config.json"
)
```

#### Configuration Types
- **`multi-model`**: Multiple AI providers with fallback (recommended)
- **`single-model`**: Single provider setup (legacy mode)
- **`minimal`**: Lightweight setup for small projects
- **`auto`**: Automatic detection from environment

### Advanced Usage

#### Programmatic API

```python
from lynx import Codex
from lynx.codex.config import CodexConfig

# Create custom configuration
config = CodexConfig(
    codebase_path="/path/to/project",
    chunk_size=2000,
    max_workers=8,
    include_patterns={"*.py", "*.rs", "*.go"},
    exclude_patterns={"*test*", "*/target/*"},
    output_format="markdown"
)

# Initialize and run analysis
codex = Codex.New(config)
results = codex.summarize()

print(f"Processed {results['stats']['files_processed']} files")
print(f"Generated summary: {results['output_path']}")
```

#### Batch Processing

```python
import lynx

# Analyze multiple projects
projects = ["/path/to/project1", "/path/to/project2", "/path/to/project3"]

for project_path in projects:
    try:
        results = lynx.quick_start(project_path, output=f"{project_path}/analysis.md")
        print(f"✓ Completed: {project_path}")
    except Exception as e:
        print(f"✗ Failed: {project_path} - {e}")
```

### CLI Reference

#### Basic Commands

```bash
# Analyze with auto-configuration
lynx /path/to/codebase --auto-config

# Use custom configuration file
lynx /path/to/codebase config.json

# Legacy single-model mode
lynx /path/to/codebase --api-key your-key --model gpt-4
```

#### Configuration Management

```bash
# Generate configuration templates
lynx --create-config config.json --config-type multi-model
lynx --create-config minimal.json --config-type minimal

# Analyze codebase and get recommendations
lynx --analyze /path/to/codebase

# Validate environment setup
lynx --validate-env
```

#### Advanced Options

```bash
# Custom output and processing
lynx /path/to/codebase \
  --output custom-summary.md \
  --format markdown \
  --workers 16 \
  --chunk-size 4000

# Feature flags
lynx /path/to/codebase \
  --no-semantic-chunking \
  --no-metrics \
  --disable-fallback

# Plugin options
lynx /path/to/codebase \
  --enable-plugins \
  --list-plugins
```

### Dynamiq Integration

Lynx includes pre-built [Dynamiq](https://dynamiq.ai) workflows for enterprise automation:

#### Simple Workflow

```python
from lynx.integrations import LynxWorkflows, CodebaseInput

# Create workflow
workflow = LynxWorkflows.simple_analysis_workflow()

# Execute analysis
input_data = CodebaseInput(
    codebase_path="/path/to/codebase",
    config_type="multi-model",
    output_format="markdown"
)

results = workflow.run(input_data)
print(f"Analysis complete: {results.summary}")
```

#### Batch Processing Workflow

```python
from lynx.integrations import LynxWorkflows, BatchAnalysisInput

# Batch analysis workflow
workflow = LynxWorkflows.batch_processing_workflow()

# Process multiple codebases
batch_input = BatchAnalysisInput(
    codebases=["/path/to/project1", "/path/to/project2", "/path/to/project3"],
    parallel=True,
    output_dir="./batch_results"
)

results = workflow.run(batch_input)
print(f"Processed {results.summary_stats['successful_analyses']} codebases")
```

#### Custom Workflow Builder

```python
from lynx.integrations import LynxWorkflowBuilder

# Build custom workflow
workflow = (LynxWorkflowBuilder()
    .add_codebase_analyzer("main_analyzer", auto_config=True)
    .add_batch_analyzer("batch_processor")
    .build())

# Execute custom workflow
results = workflow.run(input_data)
```

## Configuration Reference

### Model Configuration

```json
{
  "models": [
    {
      "provider": "perplexity",
      "model": "sonar-large-chat",
      "api_key": "pplx-your-key",
      "temperature": 0.0,
      "max_tokens": 16000
    },
    {
      "provider": "openai",
      "model": "gpt-4o",
      "api_key": "sk-your-key",
      "temperature": 0.0,
      "max_tokens": 8000
    }
  ]
}
```

### Processing Settings

```json
{
  "chunk_size": 2000,
  "max_workers": 8,
  "semantic_chunking": true,
  "fallback_enabled": true,
  "include_patterns": ["*.py", "*.rs", "*.go", "*.js", "*.ts"],
  "exclude_patterns": ["*/__pycache__/*", "*/node_modules/*", "*/.git/*"],
  "max_file_size": 10485760,
  "timeout_seconds": 30,
  "retry_attempts": 3
}
```

### Plugin Configuration

```json
{
  "plugin_system": {
    "enabled": true,
    "auto_discover": true,
    "plugins": {
      "language_bridge": {
        "enabled": true,
        "priority": 50,
        "options": {
          "max_elements_per_file": 200,
          "analyze_dependencies": true,
          "cache_parsed_results": true,
          "enable_semantic_hints": true
        }
      }
    }
  }
}
```

### Output Configuration

```json
{
  "output_dest": "master_summary.md",
  "output_format": "markdown",
  "include_metrics": true
}
```

## Use Cases

### Software Documentation
Generate comprehensive project documentation, create API documentation from source code, and maintain up-to-date technical specifications.

### Code Review and Onboarding
Accelerate new team member onboarding, provide contextual code understanding, and generate architectural overviews for faster project comprehension.

### Technical Debt Analysis
Identify complex or problematic code sections, understand legacy system architectures, and plan refactoring initiatives with data-driven insights.

### Compliance and Auditing
Generate code documentation for compliance requirements, create audit trails for software changes, and maintain regulatory documentation automatically.

## Performance and Scaling

### Benchmarks
- **Small Projects** (~50 files): 30-60 seconds
- **Medium Projects** (~500 files): 5-10 minutes  
- **Large Projects** (~2000+ files): 15-30 minutes

### Optimization Tips
- Use `chunk_size: 3000` for large files
- Increase `max_workers` for multi-core systems
- Enable `semantic_chunking` for better context preservation
- Use Anthropic Claude for very large codebases (200K+ token context)

## Security and Privacy

- **Local Processing**: Code analysis happens locally on your infrastructure
- **API Security**: Secure communication with AI providers using encrypted connections
- **No Data Storage**: AI providers don't store your code (verify with provider policies)
- **Configurable Exclusions**: Exclude sensitive files and directories from analysis

## Commercial Use and Support

### Open Source
Lynx Codex is licensed under GNU GPL v3.0, making it free for open source projects and personal use.

### Commercial Licensing
For commercial use, enterprise support, and custom integrations:

- **Professional Support**: Priority bug fixes and feature requests
- **Custom Integrations**: Tailored solutions for enterprise workflows  
- **Training and Consulting**: Team training and implementation consulting
- **SLA Support**: Service level agreements for mission-critical applications

**Contact**: [grolofson@xdarkicex.codes](mailto:grolofson@xdarkicex.codes)  
**Website**: [https://xdarkicex.codes](https://xdarkicex.codes)

## Contributing

We welcome contributions from the community. Please see our [Contributing Guide](CONTRIBUTING.md) for detailed information about our development process, code standards, and submission guidelines.

### Development Setup

```bash
# Clone repository
git clone https://github.com/xDarkicex/lynx.git
cd lynx

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/lynx/
isort src/lynx/
```

### Roadmap

- Web interface for interactive analysis
- Integration with popular IDEs (VS Code, IntelliJ, etc.)
- Advanced visualization features
- Real-time codebase monitoring
- Custom AI model training capabilities

## Issues and Support

### Reporting Issues
- **Bug Reports**: Use GitHub Issues with detailed reproduction steps and environment information
- **Feature Requests**: Describe your use case and expected behavior clearly
- **Questions**: Check documentation first, then create a discussion thread

### Getting Help

1. **Documentation**: Review this README and inline code documentation
2. **Environment Validation**: Run `lynx --validate-env` to check your setup
3. **Verbose Logging**: Use `--log-level DEBUG` for detailed troubleshooting output
4. **Community**: GitHub Discussions for questions, tips, and best practices

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for complete details.

### GPL Summary
- **Commercial Use**: Allowed with source code disclosure requirements
- **Modification**: Allowed with source code disclosure requirements
- **Distribution**: Allowed with source code disclosure requirements
- **Private Use**: Modifications must be disclosed if distributed publicly

For commercial licensing without GPL restrictions, please contact our team.

## Acknowledgments

We gratefully acknowledge the following:

- **AI Providers**: OpenAI, Anthropic, and Perplexity for enabling intelligent code analysis
- **LangChain**: For providing excellent AI integration framework and tools
- **Dynamiq**: For workflow automation capabilities and enterprise integration
- **Contributors**: All community members who help improve Lynx through code, documentation, and feedback

---

**Lynx Codex** - Transform your codebase into comprehensive documentation with the power of artificial intelligence.

If you find this project useful, please consider starring the repository and sharing it with your development team to improve code documentation practices across your organization.