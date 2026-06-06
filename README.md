# Lynx Codex

[![Version](https://img.shields.io/badge/version-1.0.9-blue.svg)](https://github.com/xDarkicex/lynx)
[![License](https://img.shields.io/badge/license-GPL--3.0-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](https://python.org)

**Lynx Codex** is an intelligent codebase summarization toolkit that leverages artificial intelligence to automatically analyze, document, and summarize software projects. Built with multi-model fallback support and semantic code understanding, Lynx transforms complex codebases into comprehensive, readable documentation.

## License and Commercial Use

Lynx Codex is provided under the GNU GPL v3 license for open source and personal use. **Commercial, proprietary, or SaaS usage (including internal company use or integrations beyond personal development) requires a commercial license. [Contact us](mailto:grolofson@xdarkicex.codes) for licensing details.**

Solo developers and hobbyists are encouraged to use the open source version freely! See [LICENSE](./LICENSE) for complete terms.

## Features

### Multi-Model AI Support
- **Multiple AI Providers**: OpenAI GPT-4, Anthropic Claude, Perplexity Sonar, MiniMax (M2.7, M3), DeepSeek (V4), Kimi, Qwen, Ollama (local models)
- **Intelligent Fallback**: Automatic failover between providers for maximum reliability
- **Staged Model Selection**: Use different models for file analysis vs. aggregation (e.g., MiniMax-M2.7 for files, DeepSeek-V4-Pro for synthesis)
- **Cost Optimization**: Smart provider selection based on task complexity and cost

### Intelligent Code Analysis
- **Semantic Chunking**: Respects code structure (functions, classes, modules)
- **Language-Aware**: Optimized parsing for Python, Rust, Go, JavaScript, TypeScript, Java, C/C++
- **Context Preservation**: Maintains code relationships across large files

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

### OAuth Authentication
- **Secure Browser-Based Login**: OAuth2.0 with PKCE for secure CLI authentication
- **OS Keychain Storage**: Tokens stored securely in macOS Keychain, Windows Credential Locker, or Linux Secret Service
- **Automatic Token Refresh**: Access tokens are automatically refreshed when expired
- **Multiple Provider Support**: OpenAI OAuth out of the box, extensible for other providers

## Quick Start

### Installation

```bash
pip install lynx-codex
```

### Environment Setup

Set your AI provider API keys via environment variables **or** use OAuth authentication:

```bash
# Option 1: Environment variables
export MINIMAX_API_KEY="your-minimax-key"
export DEEPSEEK_API_KEY="your-deepseek-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export PPLX_API_KEY="your-perplexity-key"

# Option 2: OAuth (secure browser-based login)
lynx --login --client-id your-openai-client-id
lynx --status # Verify authentication

# Option 3: Ollama (local models - no API key needed)
# Install Ollama, then pull models:
# ollama pull codellama
# ollama serve  # Start the server on http://localhost:11434
```

### TOML Configuration

Lynx supports TOML config files with auto-discovery. Create `lynx.toml` or add to `pyproject.toml`:

```bash
# Auto-discovers lynx.toml or [tool.lynx] in pyproject.toml
lynx /path/to/codebase
```

See [lynx.example.toml](./lynx.example.toml) for a complete example.

### Basic Usage

```python
import lynx

# Analyze a codebase with auto-configuration
results = lynx.quick_start("/path/to/your/project")
print("Analysis complete! Check master_summary.md")
```

### CLI Usage

```bash
# Auto-discovers lynx.toml or pyproject.toml in current/codebase directory
lynx /path/to/codebase

# Or specify config explicitly
lynx /path/to/codebase my-config.toml

# Quick analysis with environment variables only (no config file)
lynx /path/to/codebase --auto-config

# Create a custom configuration
lynx --create-config my-config.toml --config-type multi-model

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

#### OAuth Authentication

```bash
# Check OAuth status
lynx --status

# Login with OAuth (opens browser for authentication)
lynx --login --client-id your-openai-client-id

# Logout (removes token from keychain)
lynx --logout
```

**First time setup:**
1. Register an OAuth application at [platform.openai.com/apps](https://platform.openai.com/apps)
2. Copy your Client ID
3. Run `lynx --login --client-id your-client-id`
4. Complete authentication in the browser
5. Token is stored securely in your OS keychain

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

### TOML Configuration (Recommended)

Create `lynx.toml` or use `[tool.lynx]` in `pyproject.toml`:

```toml
[tool.lynx]
codebase_path = "./src"

# OAuth authentication (alternative to API keys)
[tool.lynx.oauth]
enabled = true
client_id = "your-openai-client-id"
providers = ["openai"]

# Staged model selection - use different models for different tasks
file_summarizer_model = "fast"      # Individual file analysis
aggregation_model = "powerful"       # Final synthesis

[[tool.lynx.models]]
name = "fast"
provider = "minimax"
model = "MiniMax-M2.7"
temperature = 0.0
max_tokens = 16000

[[tool.lynx.models]]
name = "powerful"
provider = "deepseek"
model = "deepseek-reasoner"
temperature = 0.0
max_tokens = 32000

chunk_size = 2000
max_workers = 8
output_dest = "SUMMARY.md"
```

### Supported Providers

| Provider | Base URL | API Key Env Var |
|----------|----------|-----------------|
| `minimax` | `https://api.minimax.io/anthropic` | `MINIMAX_API_KEY` |
| `deepseek` | `https://api.deepseek.com/anthropic` | `DEEPSEEK_API_KEY` |
| `anthropic` | Default Anthropic | `ANTHROPIC_API_KEY` |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `perplexity` | `https://api.perplexity.ai` | `PPLX_API_KEY` |
| `kimi` | OpenAI-compatible | `KIMI_API_KEY` |
| `qwen` | OpenAI-compatible | `QWEN_API_KEY` |
| `ollama` | `http://localhost:11434/v1` | N/A (local) |

### JSON Configuration (Legacy)

```json
{
  "codebase_path": "./src",
  "oauth": {
    "enabled": true,
    "client_id": "your-openai-client-id",
    "providers": ["openai"]
  },
  "models": [
    {
      "name": "fast",
      "provider": "minimax",
      "model": "MiniMax-M2.7",
      "temperature": 0.0,
      "max_tokens": 16000
    }
  ],
  "file_summarizer_model": "fast",
  "aggregation_model": "powerful"
}
```

API keys are resolved from environment variables automatically based on provider. Alternatively, use OAuth for secure token-based authentication.

### Plugin System

Lynx has a powerful plugin system that hooks into the analysis pipeline at defined points. Plugins can inspect, transform, and enrich the analysis process, enabling multi-step agentic workflows.

#### Hook Points

Plugins can hook into these pipeline stages:

| Hook | When it fires |
|------|---------------|
| `BEFORE_SCAN` | Before directory scanning |
| `AFTER_SCAN` | After directory scan completes |
| `BEFORE_CHUNK` | Before file chunking |
| `AFTER_CHUNK` | After chunking completes |
| `BEFORE_AI_REQUEST` | Before sending to AI |
| `AFTER_AI_RESPONSE` | After AI responds |
| `ON_CHUNK_COMPLETE` | After each chunk finishes |
| `ON_FILE_COMPLETE` | After entire file processed |
| `BEFORE_AGGREGATE` | Before aggregation |
| `DURING_AGGREGATE` | After aggregation completes |
| `BEFORE_OUTPUT` | Before saving output |
| `AFTER_OUTPUT` | After saving output |
| `ON_ERROR` | On any error |

#### Plugin Context

Plugins receive a `PluginContext` with shared state:

```python
ctx.config        # CodexConfig
ctx.file_info     # Current file metadata
ctx.content       # File content
ctx.chunks        # Code chunks
ctx.request       # AI request sent
ctx.response     # AI response received
ctx.file_summaries # All file summaries (during aggregation)
ctx.master_summary # Final summary (after aggregation)
ctx.state        # Shared dict for plugin-to-plugin communication
```

#### Agentic Pipeline Example

Plugins can build rich multi-step workflows:

```python
class SecurityPlugin:
    """Step 1: Scan for CVEs on each file."""
    def on_hook(self, hook, ctx):
        if hook == HookPoint.ON_FILE_COMPLETE:
            # Re-scan for security issues, store in shared state
            cves = scan_for_cves(ctx.file_info, ctx.response.summary)
            ctx.state.setdefault('cve_findings', []).extend(cves)

class DAGPlugin:
    """Step 2: Build dependency graph."""
    def on_hook(self, hook, ctx):
        if hook == HookPoint.DURING_AGGREGATE:
            # Build import graph from all summaries
            ctx.state['dependency_graph'] = build_import_graph(ctx.file_summaries)

class DiagramPlugin:
    """Step 3: Generate non-technical diagrams."""
    def on_hook(self, hook, ctx):
        if hook == HookPoint.DURING_AGGREGATE:
            # Create flowcharts for non-technical users
            diagrams = generate_simplified_diagrams(ctx.master_summary)
            ctx.state['diagrams'] = diagrams
```

#### Custom Plugins

```python
from lynx.plugins.core.base import Plugin, PluginContext, HookPoint

class MyPlugin(Plugin):
    name = "my-plugin"
    version = "1.0.0"
    order = 50  # Lower runs earlier

    def supports(self, hook):
        return hook in [HookPoint.ON_FILE_COMPLETE, HookPoint.DURING_AGGREGATE]

    def on_hook(self, hook, ctx):
        if hook == HookPoint.ON_FILE_COMPLETE:
            # Process each file as it completes
            pass
        elif hook == HookPoint.DURING_AGGREGATE:
            # Process after aggregation
            pass
```

See [src/lynx/plugins/core/base.py](src/lynx/plugins/core/base.py) for the full Plugin protocol.

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

### Open Source License
Lynx Codex is licensed under GNU GPL v3.0 for open source projects, personal use, and educational purposes. Individual developers and hobbyists are welcome to use, modify, and contribute to the project under these terms.

### Commercial Licensing Required
**If you, your company, or your clients are running Lynx Codex in production environments, as a service (SaaS/API), or as part of proprietary projects, you must secure a commercial license before deployment.** This includes:

- Internal enterprise usage within organizations
- SaaS or API service offerings
- Integration into proprietary software products
- Commercial consulting or service delivery
- Any usage that generates revenue or supports business operations

### Enterprise Support and Services
For commercial licensing, enterprise support, and custom integrations:

- **Commercial Licensing**: GPL-free licensing for proprietary use
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
black lynx/
isort lynx/
```

### Roadmap

- Additional language support (R, Zig, ObjectC, NoSQL, Perl, scss, Dart, Scala, D#, Odin)
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

This project is licensed under the GNU General Public License v3.0 for open source and personal use. See the [LICENSE](LICENSE) file for complete terms.

### Commercial Usage Notice
**Commercial, proprietary, or SaaS deployments require a separate commercial license.** The GPL v3.0 license does not permit proprietary use, internal company deployment, or commercial service offerings without source code disclosure requirements.

### GPL v3.0 Summary (Open Source Use Only)
- **Open Source Use**: Full rights for open source projects with source disclosure
- **Personal Use**: Free for individual developers and hobbyists
- **Modification**: Allowed with source code disclosure requirements
- **Distribution**: Allowed with source code disclosure requirements
- **Commercial Restriction**: Proprietary use requires separate commercial licensing

For commercial licensing without GPL restrictions and source code disclosure requirements, please contact our team.

## Acknowledgments

We gratefully acknowledge the following:

- **AI Providers**: OpenAI, Anthropic, Perplexity, MiniMax, and DeepSeek for enabling intelligent code analysis
- **LangChain**: For providing excellent AI integration framework and tools
- **Dynamiq**: For workflow automation capabilities and enterprise integration
- **Contributors**: All community members who help improve Lynx through code, documentation, and feedback

---

**Lynx Codex** - Transform your codebase into comprehensive documentation with the power of artificial intelligence.

If you find this project useful, please consider starring the repository and sharing it with your development team to improve code documentation practices across your organization.