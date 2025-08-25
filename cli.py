"""Command-line interface for Lynx Codex with comprehensive configuration support."""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import lynx
from lynx.codex.config import CodexConfig
from lynx.exceptions import LynxError

def setup_logging(level: str = 'INFO') -> None:
    """Configure logging for CLI usage."""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {level}')
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def create_sample_config(output_path: str, config_type: str = "multi-model") -> None:
    """Create a sample configuration file using the enhanced template system."""
    try:
        config = lynx.create_default_config_template(
            config_type=config_type,
            include_all_providers=(config_type == "multi-model"),
            save_to_file=output_path
        )
        
        print(f"✅ Sample {config_type} configuration saved to: {output_path}")
        print("\n📝 Next steps:")
        print("   1. Edit the config file and replace placeholder API keys")
        print("   2. Remove any providers you don't want to use") 
        print("   3. Run: lynx /path/to/codebase your-config.json")
        
        if 'models' in config:
            print(f"\n💡 Configuration includes {len(config['models'])} AI provider(s):")
            for model in config['models']:
                print(f"   - {model['provider']}: {model['model']}")
        
        print("\n🔑 You can also set API keys via environment variables:")
        print("   export PPLX_API_KEY='your-perplexity-key'")
        print("   export OPENAI_API_KEY='your-openai-key'")  
        print("   export ANTHROPIC_API_KEY='your-anthropic-key'")
        
    except Exception as e:
        print(f"❌ Failed to create config: {e}")
        sys.exit(1)

def analyze_codebase(codebase_path: str) -> None:
    """Analyze a codebase and provide configuration recommendations."""
    try:
        config = lynx.get_recommended_config_for_codebase(codebase_path)
        analysis = config.get('_analysis', {})
        
        print(f"📊 Codebase Analysis for: {codebase_path}")
        print("=" * 50)
        print(f"Files found: {analysis.get('total_files', 0)}")
        print(f"Total size: {analysis.get('total_size_mb', 0)} MB")
        print(f"Languages: {', '.join(analysis.get('detected_languages', []))}")
        
        if analysis.get('recommendations'):
            print(f"\n💡 Recommendations:")
            for rec in analysis['recommendations']:
                print(f"   • {rec}")
        
        # Show recommended settings
        print(f"\n⚙️  Recommended Settings:")
        print(f"   Chunk size: {config.get('chunk_size', 2000)}")
        print(f"   Max workers: {config.get('max_workers', 8)}")
        print(f"   File patterns: {config.get('include_patterns', [])}")
        
        save_choice = input(f"\n💾 Save recommended config to file? [y/N]: ").lower().strip()
        if save_choice in ['y', 'yes']:
            filename = f"lynx-config-{Path(codebase_path).name}.json"
            lynx.create_default_config_template("multi-model", save_to_file=filename)
            print(f"✅ Config saved to: {filename}")
            
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        sys.exit(1)

def validate_environment() -> None:
    """Validate the environment setup and show status."""
    status = lynx.validate_setup()
    
    print("🔍 Lynx Environment Status")
    print("=" * 30)
    
    if status["api_keys_found"]:
        print("✅ API Keys Found:")
        for key_info in status["api_keys_found"]:
            print(f"   • {key_info['provider']}: {key_info['env_var']}")
    else:
        print("❌ No API keys found in environment variables")
        print("   Set one of: PPLX_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY")
    
    if status["missing_dependencies"]:
        print(f"\n⚠️  Missing Dependencies:")
        for dep in status["missing_dependencies"]:
            print(f"   • {dep}")
    else:
        print(f"\n✅ All dependencies installed")
    
    if status["ready"]:
        print(f"\n🎉 Lynx is ready to use!")
    else:
        print(f"\n❌ Setup incomplete - please install dependencies and set API keys")
    
    print(f"\nFor help getting started, run: lynx --help")

def handle_auto_config(codebase_path: str, save_config: Optional[str] = None) -> CodexConfig:
    """Handle automatic configuration from environment variables."""
    try:
        config_dict = lynx.init_config("auto", codebase_path=codebase_path)
        if save_config:
            lynx.create_default_config_template("auto", save_to_file=save_config)
        
        print("✅ Auto-configured from environment variables")
        if 'models' in config_dict:
            providers = [m['provider'] for m in config_dict['models']]
            print(f"🔗 Using providers: {', '.join(providers)}")
        
        return CodexConfig.from_dict(config_dict)
        
    except ValueError as e:
        print(f"❌ Auto-configuration failed: {e}")
        print("💡 Try setting API keys in environment variables or use --create-config")
        sys.exit(1)

def main() -> None:
    """Main CLI entry point with comprehensive functionality."""
    parser = argparse.ArgumentParser(
        description="Lynx Codex: AI-powered codebase summarization with multi-model fallback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick start with auto-configuration
  lynx /path/to/codebase --auto-config

  # Analyze codebase and get recommendations
  lynx --analyze /path/to/codebase

  # Generate different types of configs
  lynx --create-config config.json --config-type multi-model
  lynx --create-config minimal.json --config-type minimal
  
  # Use existing config file
  lynx /path/to/codebase config.json

  # Legacy single-model mode
  lynx /path/to/codebase --api-key pplx-xxx

  # Validate environment setup
  lynx --validate-env

Environment Variables:
  PPLX_API_KEY or PERPLEXITY_API_KEY - Perplexity API key
  OPENAI_API_KEY - OpenAI API key  
  ANTHROPIC_API_KEY - Anthropic API key

Configuration Types:
  multi-model  - Multiple AI providers with fallback (recommended)
  single-model - Legacy single provider mode
  minimal      - Lightweight setup for small projects
  auto         - Auto-detect from environment variables
        """
    )
    
    # Main arguments
    parser.add_argument(
        'codebase_path',
        nargs='?',
        help='Path to the codebase directory to analyze'
    )
    
    parser.add_argument(
        'config_file',
        nargs='?',
        help='Path to JSON configuration file'
    )
    
    # Configuration options
    parser.add_argument(
        '--auto-config',
        action='store_true',
        help='Auto-configure from environment variables'
    )
    
    parser.add_argument(
        '--api-key',
        help='API key (legacy single model mode, overrides config file)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file path (default: master_summary.md)'
    )
    
    parser.add_argument(
        '--model',
        default='sonar-large-chat',
        help='AI model to use (legacy single model mode, default: sonar-large-chat)'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        help='Number of worker threads for parallel processing'
    )
    
    parser.add_argument(
        '--chunk-size',
        type=int,
        help='Token size for chunking large files'
    )
    
    parser.add_argument(
        '--format',
        choices=['markdown', 'json', 'text'],
        help='Output format'
    )
    
    # Feature flags
    parser.add_argument(
        '--no-semantic-chunking',
        action='store_true',
        help='Disable semantic code chunking'
    )
    
    parser.add_argument(
        '--no-metrics',
        action='store_true',
        help='Exclude processing metrics from output'
    )
    
    parser.add_argument(
        '--disable-fallback',
        action='store_true',
        help='Disable fallback to other AI providers'
    )
    
    # Utility options
    parser.add_argument(
        '--create-config',
        metavar='PATH',
        help='Create a sample configuration file and exit'
    )
    
    parser.add_argument(
        '--config-type',
        choices=['multi-model', 'single-model', 'minimal', 'auto'],
        default='multi-model',
        help='Type of config to create (default: multi-model)'
    )
    
    parser.add_argument(
        '--analyze',
        metavar='PATH',
        help='Analyze codebase and show configuration recommendations'
    )
    
    parser.add_argument(
        '--validate-env',
        action='store_true',
        help='Validate environment setup and show status'
    )
    
    parser.add_argument(
        '--save-config',
        metavar='PATH',
        help='Save auto-generated config to file'
    )
    
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Set logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'Lynx Codex v{lynx.__version__}'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    try:
        # Handle utility commands first
        if args.validate_env:
            validate_environment()
            return
            
        if args.create_config:
            create_sample_config(args.create_config, args.config_type)
            return
            
        if args.analyze:
            analyze_codebase(args.analyze)
            return
        
        # Validate required arguments for main analysis
        if not args.codebase_path:
            parser.error("codebase_path is required (unless using utility commands)")
        
        if not Path(args.codebase_path).exists():
            parser.error(f"Codebase path does not exist: {args.codebase_path}")
        
        # Load or create configuration
        config = None
        
        if args.auto_config:
            config = handle_auto_config(args.codebase_path, args.save_config)
        elif args.config_file and Path(args.config_file).exists():
            logger.info(f"Loading configuration from: {args.config_file}")
            try:
                config_dict = lynx.load_config_file(args.config_file)
                config = CodexConfig.from_dict(config_dict)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")
                sys.exit(1)
        else:
            logger.info("Using default configuration")
            config = CodexConfig()
        
        # Update config with CLI arguments
        config.codebase_path = args.codebase_path
        
        # Legacy single model support
        if args.api_key:
            config.api_key = args.api_key
        
        if args.output:
            config.output_dest = args.output
        
        if args.model and args.api_key:  # Only update model if API key provided
            config.model = args.model
        
        if args.workers:
            config.max_workers = args.workers
        
        if args.chunk_size:
            config.chunk_size = args.chunk_size
        
        if args.format:
            config.output_format = args.format
        
        if args.no_semantic_chunking:
            config.semantic_chunking = False
        
        if args.no_metrics:
            config.include_metrics = False
        
        if args.disable_fallback and hasattr(config, 'fallback_enabled'):
            config.fallback_enabled = False
        
        # Validate configuration
        config.validate()
        
        # Create and run Codex
        logger.info("Initializing Lynx Codex...")
        codex = lynx.Codex.New(config)
        
        logger.info("Starting codebase analysis...")
        results = codex.summarize()
        
        # Print success message
        print(f"\n✅ Analysis complete!")
        print(f"📄 Summary saved to: {config.output_dest}")
        print(f"📊 Files processed: {results['stats']['files_processed']}")
        
        if results['stats']['errors']:
            print(f"⚠️  Errors encountered: {len(results['stats']['errors'])}")
        
        usage_stats = results['stats']['ai_usage']
        print(f"🤖 AI requests: {usage_stats['total_requests']}")
        print(f"💰 Estimated cost: ${usage_stats['estimated_cost']:.4f}")
        
        # Show fallback info if available
        if 'fallbacks_used' in results['stats']:
            print(f"🔄 Fallbacks used: {results['stats']['fallbacks_used']}")
        
        if usage_stats.get('providers_configured', 1) > 1:
            print(f"🏷️  Primary provider: {usage_stats['primary_provider']}")
        
    except LynxError as e:
        logger.error(f"Lynx error: {e}")
        print(f"\n❌ {e}")
        print("💡 Try running 'lynx --validate-env' to check your setup")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print(f"\n⏹️  Operation cancelled")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\n💥 Unexpected error: {e}")
        print("🐛 Please report this issue at: https://github.com/xDarkicex/lynx/issues")
        sys.exit(2)

if __name__ == '__main__':
    main()
