"""Authed OpenAI Tools Package

This package provides tools for integrating Authed's agent communication capabilities
with OpenAI's agent framework.
"""

from .agent_communication import AgentCommunicationTool, AgentCommunicationError, ConfigurationError, CommunicationTimeoutError

__all__ = [
    'AgentCommunicationTool',
    'AgentCommunicationError',
    'ConfigurationError',
    'CommunicationTimeoutError'
] 