"""Ollama integration for pr-auto-reviewer.

This package provides Ollama LLM integration including:
- OllamaStreamingChatABC: Abstract base class for Ollama streaming chat
- OllamaStreamingChatClient: Concrete implementation using /api/chat endpoint
- OllamaStreamingLlmAdapter: Adapter implementing LlmReviewPort
- OllamaAgentAdapter: Agentic review adapter
- OllamaChatClient: Base chat client
- OllamaLlmAdapter: Legacy LLM adapter (maintained for backward compatibility)
"""
