"""Multi-provider AI service interface with fallback support."""

import time
import logging
import os
from copy import copy
from typing import Dict, List, Optional, Any, Type
from dataclasses import dataclass
from abc import ABC, abstractmethod

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models.base import BaseLanguageModel

# Import providers
try:
    from langchain_perplexity import ChatPerplexity
except ImportError:
    ChatPerplexity = None

try:
    from langchain_openai import ChatOpenAI
except ImportError:
    ChatOpenAI = None

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None

from ..exceptions import AIInterfaceError
from ..utils import count_tokens, truncate_text, get_model_context_limit
from .config import CodexConfig, ModelConfig
from ..oauth import OAuthManager, OpenAIOAuthProvider

logger = logging.getLogger(__name__)

@dataclass
class SummaryRequest:
    """Request for AI summarization."""
    content: str
    file_path: str
    language: str
    chunk_type: str = 'unknown'
    metadata: Dict = None

@dataclass
class SummaryResponse:
    """Response from AI summarization."""
    summary: str
    tokens_used: int
    processing_time: float
    model_used: str
    provider_used: str
    error: Optional[str] = None
    fallback_used: bool = False

class AIProvider(ABC):
    """Abstract base class for AI providers."""
    
    def __init__(self, model_config: ModelConfig):
        self.model_config = model_config
        self.llm = self._initialize_llm()
    
    @abstractmethod
    def _initialize_llm(self) -> BaseLanguageModel:
        """Initialize the LLM client for this provider."""
        pass
    
    def invoke(self, prompt: str) -> Any:
        """Make a request to the AI provider."""
        return self.llm.invoke(prompt)
    
    def get_model_name(self) -> str:
        """Get the model name."""
        return self.model_config.model
    
    def get_provider_name(self) -> str:
        """Get the provider name."""
        return self.model_config.provider

class PerplexityProvider(AIProvider):
    """Perplexity AI provider implementation."""
    
    def _initialize_llm(self) -> BaseLanguageModel:
        if ChatPerplexity is None:
            raise AIInterfaceError("langchain-perplexity not installed")
        
        return ChatPerplexity(
            model=self.model_config.model,
            temperature=self.model_config.temperature,
            pplx_api_key=self.model_config.api_key,
            max_tokens=min(self.model_config.max_tokens, 4096)  # Perplexity limit
        )

class OpenAIProvider(AIProvider):
    """OpenAI provider implementation (supports custom endpoints like MiniMax, DeepSeek)."""

    def _initialize_llm(self) -> BaseLanguageModel:
        if ChatOpenAI is None:
            raise AIInterfaceError("langchain-openai not installed")

        kwargs = {
            'model': self.model_config.model,
            'temperature': self.model_config.temperature,
            'openai_api_key': self.model_config.get_api_key(),
            'max_tokens': self.model_config.max_tokens
        }

        # Get base_url from model config (via provider registry or override)
        base_url = self.model_config.get_base_url()
        if base_url:
            kwargs['base_url'] = base_url

        return ChatOpenAI(**kwargs)

class AnthropicProvider(AIProvider):
    """Anthropic provider implementation (supports custom endpoints like MiniMax, DeepSeek)."""

    def _initialize_llm(self) -> BaseLanguageModel:
        if ChatAnthropic is None:
            raise AIInterfaceError("langchain-anthropic not installed")

        kwargs = {
            'model': self.model_config.model,
            'temperature': self.model_config.temperature,
            'anthropic_api_key': self.model_config.get_api_key(),
            'max_tokens': self.model_config.max_tokens
        }

        # Get base_url from model config (via provider registry or override)
        base_url = self.model_config.get_base_url()
        if base_url:
            kwargs['base_url'] = base_url

        return ChatAnthropic(**kwargs)

class AIInterface:
    """Multi-provider AI interface with fallback support."""

    def __init__(self, config: CodexConfig):
        self.config = config
        self.oauth_manager = self._initialize_oauth()
        self.providers = self._initialize_providers()
        self.total_tokens_used = 0
        self.total_requests = 0
        self.provider_stats = {}

        # Prompts for different summarization tasks
        self.prompts = self._initialize_prompts()

        # Staged model support - use different models for file summarization vs aggregation
        self._file_summarizer_providers = None
        self._aggregation_providers = None

    def _initialize_oauth(self) -> Optional[OAuthManager]:
        """Initialize OAuth manager if OAuth is configured."""
        if not self.config.oauth or not self.config.oauth.enabled:
            return None

        manager = OAuthManager()
        for provider_name in self.config.oauth.providers:
            if provider_name == "openai" and self.config.oauth.client_id:
                provider = OpenAIOAuthProvider(client_id=self.config.oauth.client_id)
                manager.register(provider)
        return manager

    def _get_staged_providers(self, stage: str) -> List[AIProvider]:
        """Get providers for a specific stage (file_summarizer or aggregation).

        Returns filtered subset of self.providers matching the stage's model,
        or falls back to self.providers if no match found.
        """
        if stage == 'file_summarizer':
            model_name = self.config.file_summarizer_model
        elif stage == 'aggregation':
            model_name = self.config.aggregation_model
        else:
            return self.providers

        if not model_name:
            return self.providers

        staged_providers = []
        for provider in self.providers:
            # Check if this provider's model matches the stage's model
            model_config = provider.model_config
            if model_config.name == model_name or model_config.model == model_name:
                staged_providers.append(provider)

        if not staged_providers:
            logger.warning(f"No providers found for stage {stage} with model {model_name}, using defaults")
            return self.providers

        return staged_providers


    def _get_api_key(self, provider_name: str) -> str:
        """Get API key for a provider, using OAuth if enabled."""
        if self.oauth_manager:
            oauth_token = self.oauth_manager.get_token(provider_name)
            if oauth_token:
                return oauth_token

        # Fall back to environment variable
        from .config import get_provider_info
        provider_info = get_provider_info(provider_name)
        return os.getenv(provider_info["api_env_var"], "")

    def _initialize_providers(self) -> List[AIProvider]:
        """Initialize all configured AI providers."""
        providers = []
        # Map all providers to their LangChain classes
        # Note: minimax/deepseek use Anthropic/OpenAI with their respective endpoints
        provider_classes = {
            'perplexity': PerplexityProvider,
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
            'minimax': AnthropicProvider,  # MiniMax uses Anthropic-compatible endpoint
            'deepseek': AnthropicProvider,  # DeepSeek uses Anthropic-compatible endpoint
            'kimi': OpenAIProvider,  # Kimi uses OpenAI-compatible endpoint
            'qwen': OpenAIProvider,  # Qwen uses OpenAI-compatible endpoint
            'ollama': OpenAIProvider,  # Ollama uses OpenAI-compatible API
        }

        for model_config in self.config.models:
            provider_class = provider_classes.get(model_config.provider)
            if provider_class is None:
                logger.warning(f"Unknown provider: {model_config.provider}")
                continue

            try:
                # Get API key (OAuth or env var)
                api_key = self._get_api_key(model_config.provider)
                # Create a copy of model_config with the resolved API key
                config_with_key = copy(model_config)
                config_with_key.api_key = api_key
                provider = provider_class(config_with_key)
                providers.append(provider)
                logger.info(f"Initialized {model_config.provider} provider with model {model_config.model}")
            except Exception as e:
                logger.warning(f"Failed to initialize {model_config.provider} provider: {e}")
                continue

        if not providers:
            raise AIInterfaceError("No AI providers could be initialized")

        return providers
    
    def _initialize_prompts(self) -> Dict[str, ChatPromptTemplate]:
        """Initialize prompt templates for different tasks."""
        return {
            'file_summary': ChatPromptTemplate.from_messages([
                ('system', (
                    "You are a senior software engineer analyzing code. "
                    "Provide a comprehensive, technical summary of the given code file. "
                    "For EVERY function/method you MUST include:\n"
                    "1. EXACT verbatim function signature with full type annotations\n"
                    "2. Big O time and space complexity (e.g., O(n log n), O(1), etc.)\n"
                    "3. Cyclomatic complexity estimate (Low/Medium/High/Very High)\n"
                    "4. Parameter types and return types verbatim\n"
                    "5. Any interfaces, unions, or enums used\n\n"
                    "Also provide:\n"
                    "• Primary purpose and functionality\n"
                    "• Key data structures and their types\n"
                    "• Important algorithms or business logic\n"
                    "• Dependencies and integrations\n"
                    "• Notable patterns or architectural decisions\n\n"
                    "Be precise and use technical terminology. "
                    "Be comprehensive - do not truncate details. Maximum 800 tokens."
                )),
                ('human', (
                    "File: {file_path}\n"
                    "Language: {language}\n"
                    "Content:\n{content}"
                ))
            ]),

            'chunk_summary': ChatPromptTemplate.from_messages([
                ('system', (
                    "You are analyzing a code chunk. Provide a detailed summary with:\n"
                    "1. EXACT verbatim function signatures with full type annotations\n"
                    "2. Big O time and space complexity for each function/method\n"
                    "3. Cyclomatic complexity estimate (Low/Medium/High/Very High)\n"
                    "4. Parameter types and return types verbatim\n"
                    "5. Any interfaces, unions, or enums used\n\n"
                    "Also include:\n"
                    "• What this code does\n"
                    "• Key functions/methods and their purpose\n"
                    "• Important data structures\n"
                    "• Any notable patterns or algorithms\n\n"
                    "Be comprehensive - do not truncate. Maximum 500 tokens."
                )),
                ('human', (
                    "Chunk type: {chunk_type}\n"
                    "Language: {language}\n"
                    "Content:\n{content}"
                ))
            ]),
            
            'aggregate_summary': ChatPromptTemplate.from_messages([
                ('system', (
                    "You are a senior software engineer creating technical documentation. "
                    "Combine and synthesize the following detailed file summaries into a cohesive "
                    "project overview. Your output MUST include these EXACT sections:\n\n"
                    "## 1. Project Overview (1-2 sentences)\n"
                    "A single paragraph explaining what this codebase does and how it works. "
                    "Answer: What problem does it solve? How does it solve it? What is the main approach?\n\n"
                    "## 2. Project Structure & Architecture\n"
                    "Directory tree and architectural patterns used (layered, microservices, plugin-based, etc.)\n\n"
                    "## 3. Key Modules & Components\n"
                    "For each major module: its responsibility, key functions with EXACT signatures and types, Big O complexity, cyclomatic complexity estimates.\n\n"
                    "## 4. Technology Stack\n"
                    "Languages, frameworks, libraries, tools used.\n\n"
                    "## 5. Notable Design Decisions\n"
                    "Architectural choices, patterns, conventions, non-obvious implementation details.\n\n"
                    "## 6. Potential Bugs & Issues\n"
                    "Analysis of:\n"
                    "- Edge cases that may not be handled\n"
                    "- Error handling gaps or missing validation\n"
                    "- Race conditions, concurrency issues, or thread safety concerns\n"
                    "- Memory leaks, resource cleanup issues\n"
                    "- Security vulnerabilities (injection, auth issues, etc.)\n"
                    "- API/design issues that could cause problems at scale\n"
                    "- Known limitations or todos that hint at incomplete implementation\n\n"
                    "Be honest and thorough - this section helps developers understand real risks.\n\n"
                    "## 7. Complexity Analysis\n"
                    "Highlight the most complex functions/modules with their Big O and cyclomatic complexity.\n\n"
                    "Create professional technical documentation."
                )),
                ('human', "Detailed file summaries:\n{summaries}")
            ])
        }
    
    def _get_providers_for_summarize_file(self) -> List[AIProvider]:
        """Get providers for individual file summarization."""
        if self.config.file_summarizer_model:
            return self._get_staged_providers('file_summarizer')
        return self.providers

    def summarize_file(self, request: SummaryRequest) -> SummaryResponse:
        """
        Summarize a single file or chunk with fallback support.

        Args:
            request: Summary request with content and metadata

        Returns:
            Summary response with results and metrics
        """
        start_time = time.time()
        providers = self._get_providers_for_summarize_file()

        # Try each provider in order until one succeeds
        for i, provider in enumerate(providers):
            try:
                return self._attempt_summarization(request, provider, start_time, i > 0)
            except Exception as e:
                logger.warning(f"Provider {provider.get_provider_name()} failed: {e}")
                if i == len(providers) - 1:  # Last provider failed
                    logger.error(f"All providers failed for {request.file_path}")
                    return SummaryResponse(
                        summary=f"Error: All AI providers failed. Last error: {str(e)}",
                        tokens_used=0,
                        processing_time=time.time() - start_time,
                        model_used="none",
                        provider_used="none",
                        error=str(e),
                        fallback_used=i > 0
                    )
                elif self.config.fallback_enabled:
                    logger.info(f"Falling back to next provider...")
                    continue
                else:
                    # Fallback disabled, return error
                    return SummaryResponse(
                        summary=f"Error: {provider.get_provider_name()} failed and fallback disabled",
                        tokens_used=0,
                        processing_time=time.time() - start_time,
                        model_used=provider.get_model_name(),
                        provider_used=provider.get_provider_name(),
                        error=str(e),
                        fallback_used=False
                    )
    
    def _attempt_summarization(self, request: SummaryRequest, provider: AIProvider, 
                              start_time: float, is_fallback: bool) -> SummaryResponse:
        """Attempt summarization with a specific provider."""
        model_name = provider.get_model_name()
        provider_name = provider.get_provider_name()
        
        # Choose appropriate prompt based on content size
        if count_tokens(request.content, model_name) > self.config.chunk_size:
            prompt_key = 'file_summary'
        else:
            prompt_key = 'chunk_summary'
        
        prompt = self.prompts[prompt_key]
        
        # Get model context limit and adjust accordingly
        context_limit = get_model_context_limit(model_name)
        max_content_tokens = min(
            context_limit - 1000,  # Reserve tokens for prompt and response
            provider.model_config.max_tokens
        )
        
        # Truncate content to fit within model limits
        content_truncated = truncate_text(
            request.content, 
            max_content_tokens,
            model_name
        )
        
        # Format the prompt
        formatted_prompt = prompt.format(
            file_path=request.file_path,
            language=request.language,
            content=content_truncated,
            chunk_type=request.chunk_type
        )
        
        # Make AI request with retries for this provider
        response = self._make_request_with_retry(provider, formatted_prompt)

        processing_time = time.time() - start_time

        # Extract text content from response (handles MiniMax thinking blocks)
        response_text = self._extract_response_text(response)
        input_tokens = count_tokens(content_truncated, model_name)
        output_tokens = count_tokens(response_text, model_name)
        tokens_used = input_tokens + output_tokens
        
        self.total_tokens_used += tokens_used
        self.total_requests += 1
        
        # Update provider stats
        if provider_name not in self.provider_stats:
            self.provider_stats[provider_name] = {'requests': 0, 'tokens': 0, 'errors': 0}
        self.provider_stats[provider_name]['requests'] += 1
        self.provider_stats[provider_name]['tokens'] += tokens_used
        
        logger.debug(f"Summarized {request.file_path} using {provider_name} in {processing_time:.2f}s, tokens: {tokens_used}")

        return SummaryResponse(
            summary=response_text.strip(),
            tokens_used=tokens_used,
            processing_time=processing_time,
            model_used=model_name,
            provider_used=provider_name,
            fallback_used=is_fallback
        )

    def _extract_response_text(self, response: Any) -> str:
        """Extract text content from AI response, handling MiniMax thinking blocks."""
        if hasattr(response, 'content') and isinstance(response.content, list):
            # Handle content blocks (MiniMax, Anthropic style)
            text_parts = []
            for block in response.content:
                if isinstance(block, dict):
                    if block.get('type') == 'text':
                        text_parts.append(block.get('text', ''))
                elif hasattr(block, 'type'):
                    if block.type == 'text':
                        text_parts.append(block.text if hasattr(block, 'text') else str(block))
            if text_parts:
                return '\n'.join(text_parts)
        elif hasattr(response, 'content') and isinstance(response.content, str):
            return response.content
        return str(response)

    def _get_providers_for_aggregation(self) -> List[AIProvider]:
        """Get providers for aggregation stage."""
        if self.config.aggregation_model:
            return self._get_staged_providers('aggregation')
        return self.providers

    def aggregate_summaries(self, summaries: List[str]) -> SummaryResponse:
        """
        Combine multiple file summaries into a project overview with fallback support.

        Args:
            summaries: List of individual file summaries

        Returns:
            Aggregated summary response
        """
        start_time = time.time()
        providers = self._get_providers_for_aggregation()

        # Try each provider in order until one succeeds
        for i, provider in enumerate(providers):
            try:
                return self._attempt_aggregation(summaries, provider, start_time, i > 0)
            except Exception as e:
                logger.warning(f"Provider {provider.get_provider_name()} failed during aggregation: {e}")
                if i == len(self.providers) - 1:  # Last provider failed
                    logger.error("All providers failed for summary aggregation")
                    return SummaryResponse(
                        summary=f"Error: All AI providers failed during aggregation. Last error: {str(e)}",
                        tokens_used=0,
                        processing_time=time.time() - start_time,
                        model_used="none",
                        provider_used="none",
                        error=str(e),
                        fallback_used=i > 0
                    )
                elif self.config.fallback_enabled:
                    logger.info(f"Falling back to next provider for aggregation...")
                    continue
                else:
                    return SummaryResponse(
                        summary=f"Error: {provider.get_provider_name()} failed and fallback disabled",
                        tokens_used=0,
                        processing_time=time.time() - start_time,
                        model_used=provider.get_model_name(),
                        provider_used=provider.get_provider_name(),
                        error=str(e),
                        fallback_used=False
                    )
    
    def _attempt_aggregation(self, summaries: List[str], provider: AIProvider,
                           start_time: float, is_fallback: bool) -> SummaryResponse:
        """Attempt aggregation with a specific provider."""
        model_name = provider.get_model_name()
        provider_name = provider.get_provider_name()
        
        # Combine summaries with size limits
        combined_text = "\n\n".join(summaries)
        
        # Check if too large for single request
        context_limit = get_model_context_limit(model_name)
        max_tokens = min(context_limit - 1000, provider.model_config.max_tokens)
        
        combined_tokens = count_tokens(combined_text, model_name)
        if combined_tokens > max_tokens:
            return self._hierarchical_aggregation(summaries, provider, start_time, is_fallback)
        
        prompt = self.prompts['aggregate_summary']
        formatted_prompt = prompt.format(summaries=combined_text)
        
        response = self._make_request_with_retry(provider, formatted_prompt)

        processing_time = time.time() - start_time

        # Extract text content from response (handles MiniMax thinking blocks)
        response_text = self._extract_response_text(response)
        input_tokens = count_tokens(combined_text, model_name)
        output_tokens = count_tokens(response_text, model_name)
        tokens_used = input_tokens + output_tokens

        self.total_tokens_used += tokens_used
        self.total_requests += 1

        # Update provider stats
        if provider_name not in self.provider_stats:
            self.provider_stats[provider_name] = {'requests': 0, 'tokens': 0, 'errors': 0}
        self.provider_stats[provider_name]['requests'] += 1
        self.provider_stats[provider_name]['tokens'] += tokens_used

        return SummaryResponse(
            summary=response_text.strip(),
            tokens_used=tokens_used,
            processing_time=processing_time,
            model_used=model_name,
            provider_used=provider_name,
            fallback_used=is_fallback
        )
    
    def _hierarchical_aggregation(self, summaries: List[str], provider: AIProvider,
                                start_time: float, is_fallback: bool) -> SummaryResponse:
        """Handle large summary sets with hierarchical reduction using a specific provider."""
        chunk_size = 10  # Process 10 summaries at a time
        model_name = provider.get_model_name()
        context_limit = get_model_context_limit(model_name)
        max_tokens = min(context_limit - 1000, provider.model_config.max_tokens)
        
        while len(summaries) > 1:
            next_level = []
            
            for i in range(0, len(summaries), chunk_size):
                chunk = summaries[i:i + chunk_size]
                combined = "\n\n".join(chunk)
                
                # Ensure chunk fits within token limits
                combined_truncated = truncate_text(combined, max_tokens, model_name)
                
                prompt = self.prompts['aggregate_summary']
                formatted_prompt = prompt.format(summaries=combined_truncated)
                
                response = self._make_request_with_retry(provider, formatted_prompt)
                response_text = self._extract_response_text(response)
                next_level.append(response_text.strip())

                # Track tokens for hierarchical processing
                tokens_used = count_tokens(combined, model_name) + count_tokens(response_text, model_name)
                self.total_tokens_used += tokens_used
                self.total_requests += 1
                
                # Update provider stats
                if provider.get_provider_name() not in self.provider_stats:
                    self.provider_stats[provider.get_provider_name()] = {'requests': 0, 'tokens': 0, 'errors': 0}
                self.provider_stats[provider.get_provider_name()]['requests'] += 1
                self.provider_stats[provider.get_provider_name()]['tokens'] += tokens_used
            
            summaries = next_level
        
        processing_time = time.time() - start_time
        final_summary = summaries[0] if summaries else "No content to summarize"
        
        return SummaryResponse(
            summary=final_summary,
            tokens_used=self.total_tokens_used,
            processing_time=processing_time,
            model_used=model_name,
            provider_used=provider.get_provider_name(),
            fallback_used=is_fallback
        )
    
    def _make_request_with_retry(self, provider: AIProvider, prompt: str) -> Any:
        """Make LLM request with exponential backoff retry for a specific provider."""
        last_error = None
        provider_name = provider.get_provider_name()
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = provider.invoke(prompt)
                return response
                
            except Exception as e:
                last_error = e
                wait_time = (2 ** attempt) * 1  # Exponential backoff
                
                logger.warning(
                    f"{provider_name} request failed (attempt {attempt + 1}/{self.config.retry_attempts}): {e}. "
                    f"Retrying in {wait_time}s..."
                )
                
                # Update error stats
                if provider_name not in self.provider_stats:
                    self.provider_stats[provider_name] = {'requests': 0, 'tokens': 0, 'errors': 0}
                self.provider_stats[provider_name]['errors'] += 1
                
                if attempt < self.config.retry_attempts - 1:
                    time.sleep(wait_time)
        
        raise AIInterfaceError(f"All retry attempts failed for {provider_name}. Last error: {last_error}")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics including per-provider breakdown."""
        return {
            'total_requests': self.total_requests,
            'total_tokens_used': self.total_tokens_used,
            'estimated_cost': self.total_tokens_used * 0.00002,  # Rough estimate
            'primary_model': self.providers[0].get_model_name() if self.providers else "none",
            'primary_provider': self.providers[0].get_provider_name() if self.providers else "none",
            'providers_configured': len(self.providers),
            'fallback_enabled': self.config.fallback_enabled,
            'provider_stats': self.provider_stats.copy()
        }
