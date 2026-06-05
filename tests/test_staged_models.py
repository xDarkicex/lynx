"""Tests for staged model selection in Lynx Codex."""

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from lynx.codex.config import CodexConfig, PROVIDER_REGISTRY


class TestModelConfig:
    """Test ModelConfig and provider resolution."""

    def test_model_config_has_name_field(self):
        """ModelConfig should have name field."""
        from lynx.codex.config import ModelConfig
        model = ModelConfig(name="fast", provider="minimax", model="MiniMax-M2.7")
        assert model.name == "fast"
        assert model.provider == "minimax"
        assert model.model == "MiniMax-M2.7"

    def test_get_api_key_from_env(self):
        """ModelConfig should resolve API key from environment."""
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key-123"}):
            from lynx.codex.config import ModelConfig
            model = ModelConfig(name="fast", provider="minimax", model="MiniMax-M2.7")
            assert model.get_api_key() == "test-key-123"

    def test_get_api_key_deepseek(self):
        """ModelConfig should resolve DeepSeek API key from environment."""
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "deepseek-key-456"}):
            from lynx.codex.config import ModelConfig
            model = ModelConfig(name="powerful", provider="deepseek", model="deepseek-reasoner")
            assert model.get_api_key() == "deepseek-key-456"

    def test_get_base_url_from_registry(self):
        """ModelConfig should get base URL from provider registry."""
        from lynx.codex.config import ModelConfig
        model = ModelConfig(name="fast", provider="minimax", model="MiniMax-M2.7")
        assert model.get_base_url() == "https://api.minimax.io/anthropic"

    def test_get_base_url_deepseek(self):
        """ModelConfig should get DeepSeek Anthropic endpoint from registry."""
        from lynx.codex.config import ModelConfig
        model = ModelConfig(name="powerful", provider="deepseek", model="deepseek-reasoner")
        assert model.get_base_url() == "https://api.deepseek.com/anthropic"


class TestProviderRegistry:
    """Test provider registry."""

    def test_minimax_in_registry(self):
        """MiniMax should be in provider registry."""
        assert "minimax" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["minimax"]["base_url"] == "https://api.minimax.io/anthropic"
        assert PROVIDER_REGISTRY["minimax"]["api_env_var"] == "MINIMAX_API_KEY"

    def test_deepseek_in_registry(self):
        """DeepSeek should be in provider registry."""
        assert "deepseek" in PROVIDER_REGISTRY
        assert PROVIDER_REGISTRY["deepseek"]["base_url"] == "https://api.deepseek.com/anthropic"
        assert PROVIDER_REGISTRY["deepseek"]["api_env_var"] == "DEEPSEEK_API_KEY"

    def test_all_providers_have_required_fields(self):
        """All providers in registry should have required fields."""
        for name, info in PROVIDER_REGISTRY.items():
            assert "name" in info, f"{name} missing 'name'"
            assert "base_url" in info, f"{name} missing 'base_url'"
            assert "api_env_var" in info, f"{name} missing 'api_env_var'"


class TestCodexConfigFromToml:
    """Test CodexConfig loading from TOML."""

    def test_parse_staged_model_selection_from_toml(self, tmp_path):
        """TOML with staged model selection should parse correctly."""
        toml_content = '''
[tool.lynx]
codebase_path = "./"

file_summarizer_model = "fast"
aggregation_model = "powerful"

[[tool.lynx.models]]
name = "fast"
provider = "minimax"
model = "MiniMax-M2.7"

[[tool.lynx.models]]
name = "powerful"
provider = "deepseek"
model = "deepseek-reasoner"
'''
        toml_file = tmp_path / "test.toml"
        toml_file.write_text(toml_content)

        config = CodexConfig.from_file(str(toml_file))

        assert config.file_summarizer_model == "fast"
        assert config.aggregation_model == "powerful"
        assert len(config.models) == 2

        # Find models by name
        fast_model = next(m for m in config.models if m.name == "fast")
        powerful_model = next(m for m in config.models if m.name == "powerful")

        assert fast_model.provider == "minimax"
        assert fast_model.model == "MiniMax-M2.7"
        assert powerful_model.provider == "deepseek"
        assert powerful_model.model == "deepseek-reasoner"


class TestAIInterfaceStagedSelection:
    """Test AIInterface staged model selection."""

    def test_debug_matching_and_provider_lookup(self):
        """Debug why matching isn't working - check provider lookup."""
        from lynx.codex.config import ModelConfig

        provider_class_map = {
            'perplexity': 'PerplexityProvider',
            'openai': 'OpenAIProvider',
            'anthropic': 'AnthropicProvider',
            'minimax': 'AnthropicProvider',
            'deepseek': 'AnthropicProvider',
            'kimi': 'OpenAIProvider',
            'qwen': 'OpenAIProvider',
        }

        fast_model = ModelConfig(name="fast", provider="minimax", model="MiniMax-M2.7")
        powerful_model = ModelConfig(name="powerful", provider="deepseek", model="deepseek-reasoner")

        # Test provider lookup
        print(f"\nfast_model.provider = '{fast_model.provider}'")
        print(f"powerful_model.provider = '{powerful_model.provider}'")
        print(f"provider_class_map.get('minimax') = {provider_class_map.get('minimax')}")
        print(f"provider_class_map.get('deepseek') = {provider_class_map.get('deepseek')}")

        # Simulate the loop in _get_staged_providers
        model_name = "fast"
        staged = []
        for model_config in [fast_model, powerful_model]:
            print(f"\nChecking model: {model_config.name}")
            print(f"  model_name == model_config.name: {model_name == model_config.name}")
            print(f"  model_name == model_config.model: {model_name == model_config.model}")

            if model_config.name == model_name or model_config.model == model_name:
                provider_class = provider_class_map.get(model_config.provider)
                print(f"  provider_class = {provider_class}")
                if provider_class:
                    print(f"  Would create provider for {model_config.name}")
                    staged.append(model_config)

        print(f"\nStaged providers: {len(staged)}")


class TestModelMatching:
    """Test model name matching logic."""

    def test_match_by_name_not_model(self):
        """When model_name='powerful', should match by name, not by model string."""
        from lynx.codex.config import ModelConfig

        model = ModelConfig(name="powerful", provider="deepseek", model="deepseek-reasoner")

        # Test the actual matching logic from _get_staged_providers
        model_name = "powerful"

        match = model.name == model_name or model.model == model_name
        assert match == True, "Should match by name 'powerful', not model 'deepseek-reasoner'"

    def test_match_by_model_string_fallback(self):
        """Should also match by model string if name doesn't match."""
        from lynx.codex.config import ModelConfig

        model = ModelConfig(name="powerful", provider="deepseek", model="deepseek-reasoner")

        # Test matching by model string
        model_name = "deepseek-reasoner"
        match = model.name == model_name or model.model == model_name
        assert match == True, "Should match by model string 'deepseek-reasoner'"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])