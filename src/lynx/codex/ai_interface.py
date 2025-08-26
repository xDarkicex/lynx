"""Multi-provider AI service interface with fallback support."""

import time
import logging
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
    """OpenAI provider implementation."""
    
    def _initialize_llm(self) -> BaseLanguageModel:
        if ChatOpenAI is None:
            raise AIInterfaceError("langchain-openai not installed")
        
        return ChatOpenAI(
            model=self.model_config.model,
            temperature=self.model_config.temperature,
            openai_api_key=self.model_config.api_key,
            max_tokens=self.model_config.max_tokens
        )

class AnthropicProvider(AIProvider):
    """Anthropic provider implementation."""
    
    def _initialize_llm(self) -> BaseLanguageModel:
        if ChatAnthropic is None:
            raise AIInterfaceError("langchain-anthropic not installed")
        
        return ChatAnthropic(
            model=self.model_config.model,
            temperature=self.model_config.temperature,
            anthropic_api_key=self.model_config.api_key,
            max_tokens=self.model_config.max_tokens
        )

class AIInterface:
    """Multi-provider AI interface with fallback support."""
    
    def __init__(self, config: CodexConfig):
        self.config = config
        self.providers = self._initialize_providers()
        self.total_tokens_used = 0
        self.total_requests = 0
        self.provider_stats = {}
        
        # Prompts for different summarization tasks
        self.prompts = self._initialize_prompts()
    
    def _initialize_providers(self) -> List[AIProvider]:
        """Initialize all configured AI providers."""
        providers = []
        provider_classes = {
            'perplexity': PerplexityProvider,
            'openai': OpenAIProvider,
            'anthropic': AnthropicProvider,
        }
        
        for model_config in self.config.models:
            provider_class = provider_classes.get(model_config.provider)
            if provider_class is None:
                logger.warning(f"Unknown provider: {model_config.provider}")
                continue
            
            try:
                provider = provider_class(model_config)
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
                SystemMessage(content=(
                    "You are a senior software engineer analyzing code. "
                    "Provide a concise, technical summary of the given code file. "
                    "Focus on:\n"
                    "• Primary purpose and functionality\n"
                    "• Key data structures and their roles\n" 
                    "• Public API/interface (functions, methods, exports)\n"
                    "• Important algorithms or business logic\n"
                    "• Dependencies and integrations\n"
                    "• Notable patterns or architectural decisions\n\n"
                    "Be precise and use technical terminology. "
                    "Limit response to 300 tokens maximum."
                )),
                HumanMessage(content=(
                    "File: {file_path}\n"
                    "Language: {language}\n"
                    "Content:\n{content}"
                ))
            ]),
            
            'chunk_summary': ChatPromptTemplate.from_messages([
                SystemMessage(content=(
                    "You are analyzing a code chunk. Provide a brief summary focusing on:\n"
                    "• What this code does\n"
                    "• Key functions/methods and their purpose\n"
                    "• Important data structures\n"
                    "• Any notable patterns or algorithms\n\n"
                    "Keep it concise (under 150 tokens)."
                )),
                HumanMessage(content=(
                    "Chunk type: {chunk_type}\n"
                    "Language: {language}\n"
                    "Content:\n{content}"
                ))
            ]),
            
            'aggregate_summary': ChatPromptTemplate.from_messages([
                SystemMessage(content=(
                    "Combine and synthesize the following file summaries into a cohesive "
                    "project overview. Organize by:\n"
                    "• Project structure and architecture\n"
                    "• Key modules and their responsibilities\n"
                    "• Main functionality and features\n"
                    "• Technology stack and dependencies\n"
                    "• Notable patterns and design decisions\n\n"
                    "Create a professional summary suitable for technical documentation."
                )),
                HumanMessage(content="File summaries:\n{summaries}")
            ])
        }
    
    def summarize_file(self, request: SummaryRequest) -> SummaryResponse:
        """
        Summarize a single file or chunk with fallback support.
        
        Args:
            request: Summary request with content and metadata
            
        Returns:
            Summary response with results and metrics
        """
        start_time = time.time()
        
        # Try each provider in order until one succeeds
        for i, provider in enumerate(self.providers):
            try:
                return self._attempt_summarization(request, provider, start_time, i > 0)
            except Exception as e:
                logger.warning(f"Provider {provider.get_provider_name()} failed: {e}")
                if i == len(self.providers) - 1:  # Last provider failed
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
        
        # Calculate accurate token usage
        input_tokens = count_tokens(content_truncated, model_name)
        output_tokens = count_tokens(response.content, model_name)
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
            summary=response.content.strip(),
            tokens_used=tokens_used,
            processing_time=processing_time,
            model_used=model_name,
            provider_used=provider_name,
            fallback_used=is_fallback
        )
    
    def aggregate_summaries(self, summaries: List[str]) -> SummaryResponse:
        """
        Combine multiple file summaries into a project overview with fallback support.
        
        Args:
            summaries: List of individual file summaries
            
        Returns:
            Aggregated summary response
        """
        start_time = time.time()
        
        # Try each provider in order until one succeeds
        for i, provider in enumerate(self.providers):
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
        
        # Calculate accurate token usage
        input_tokens = count_tokens(combined_text, model_name)
        output_tokens = count_tokens(response.content, model_name)
        tokens_used = input_tokens + output_tokens
        
        self.total_tokens_used += tokens_used
        self.total_requests += 1
        
        # Update provider stats
        if provider_name not in self.provider_stats:
            self.provider_stats[provider_name] = {'requests': 0, 'tokens': 0, 'errors': 0}
        self.provider_stats[provider_name]['requests'] += 1
        self.provider_stats[provider_name]['tokens'] += tokens_used
        
        return SummaryResponse(
            summary=response.content.strip(),
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
                next_level.append(response.content.strip())
                
                # Track tokens for hierarchical processing
                tokens_used = count_tokens(combined, model_name) + count_tokens(response.content, model_name)
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
