"""Ollama integration for pr-auto-reviewer.

This package provides Ollama LLM integration including:
- OllamaStreamingChatABC: Abstract base class for Ollama streaming chat
- OllamaStreamingChatClient: Concrete implementation using /api/chat endpoint
- OllamaStreamingLlmAdapter: Adapter implementing LlmReviewPort
- OllamaAgentAdapter: Legacy adapter (maintained for backward compatibility)
- OllamaChatClient: Base chat client
- OllamaExploratoryChatAdapter: Exploratory chat adapter
- OllamaLlmAdapter: Legacy LLM adapter (maintained for backward compatibility)
"""