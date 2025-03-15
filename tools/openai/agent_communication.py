"""OpenAI Tool for agent-to-agent communication via Authed protocol.

This module provides a simple tool that enables OpenAI Agents to communicate with other
agents using the Authed WebSocket protocol. It handles all the complexity of channel
management, authentication, and message exchange while providing a clean interface.

Required environment variables:
    AGENT_ID: Your agent's ID
    AGENT_SECRET: Your agent's secret
    PRIVATE_KEY: Your agent's private key (PEM format)
    PUBLIC_KEY: Your agent's public key (PEM format)
    REGISTRY_URL: Optional registry URL (defaults to https://api.getauthed.dev)

Setup Instructions:
1. Create a .env file in your project root
2. Add the above environment variables with your agent's credentials
3. Load the environment variables using python-dotenv:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```
4. Initialize the tool with your target agent's ID:
   ```python
   from tools.openai import AgentCommunicationTool
   
   tool = AgentCommunicationTool(target_agent_id="TARGET_AGENT_ID")
   ```

Note: Make sure to keep your .env file secure and never commit it to version control.
"""

import os
import json
import asyncio
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from agents import function_tool

from client.sdk.channel import Channel, MessageType

# Enhanced logging setup
logger = logging.getLogger(__name__)
# Set up more detailed logging for WebSocket connections
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'DEBUG'),  # Change default to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Enable detailed logging for websockets library
websocket_logger = logging.getLogger('websockets')
websocket_logger.setLevel(logging.DEBUG)
# Enable detailed logging for client.sdk.channel
channel_logger = logging.getLogger('client.sdk.channel')
channel_logger.setLevel(logging.DEBUG)

class AgentCommunicationError(Exception):
    """Base exception for agent communication errors."""
    pass

class ConfigurationError(AgentCommunicationError):
    """Raised when there are issues with agent configuration."""
    pass

class CommunicationTimeoutError(AgentCommunicationError):
    """Raised when communication times out."""
    pass

class MessageSchema(BaseModel):
    """Schema for messages sent through the tool."""
    message: str = Field(
        description="The message to send to the target agent"
    )
    target_agent_id: str = Field(
        description="ID of the agent to communicate with"
    )
    timeout_seconds: Optional[float] = Field(
        default=10.0,
        description="Maximum time to wait for a response (default: 10 seconds)"
    )

@function_tool
def communicate_with_agent(message: str, target_agent_id: str) -> str:
    """Send a message to another agent and get their response.
    
    Args:
        message: The message to send to the target agent
        target_agent_id: ID of the target agent to communicate with (must be provided)
    Returns:
        The response from the target agent
    """
    # Map common agent names to their UUIDs
    agent_id_map = {
        "A": "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa",  # Travel Agent
        "B": "cc7262a5-405d-4101-8030-1e3904a7124e",  # Weather Agent
        "Agent A": "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa",
        "Agent B": "cc7262a5-405d-4101-8030-1e3904a7124e",
        "Agent_A": "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa",
        "Agent_B": "cc7262a5-405d-4101-8030-1e3904a7124e",
        "Weather Agent": "cc7262a5-405d-4101-8030-1e3904a7124e",
        "Travel Agent": "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa"
    }
    
    # Map the agent name to UUID if needed
    if target_agent_id in agent_id_map:
        logger.debug(f"Mapping agent name '{target_agent_id}' to UUID '{agent_id_map[target_agent_id]}'")
        target_agent_id = agent_id_map[target_agent_id]
    
    # Important: Use the caller's agent ID, not the target's
    # This ensures we don't try to communicate with ourselves
    agent_id = os.getenv("AGENT_ID")
    
    # Log which agent is calling which
    logger.debug(f"Agent {agent_id} is communicating with agent {target_agent_id}")
    
    tool = AgentCommunicationTool(
        target_agent_id=target_agent_id,  # The ID of the agent we want to talk to
        agent_id=agent_id,   # Our own ID from env
        agent_secret=os.getenv("AGENT_SECRET")  # Our own secret from env
    )
    return tool._run(message)

class AgentCommunicationTool:
    """Tool for enabling OpenAI Agents to communicate with other agents via Authed protocol.
    
    This tool provides a simple interface for agent-to-agent communication while handling
    all the complexity of channel management, authentication, and message exchange.
    
    Example:
        ```python
        from openai import Agent
        from tools.openai import AgentCommunicationTool
        
        # All credentials and keys are loaded from environment variables
        tool = AgentCommunicationTool(target_agent_id="AGENT_B_ID")
        agent = Agent(tools=[tool])
        ```
    """
    
    def __init__(
        self,
        target_agent_id: str,
        agent_id: Optional[str] = None,
        agent_secret: Optional[str] = None,
        registry_url: Optional[str] = None
    ):
        """Initialize the tool.
        
        Args:
            target_agent_id: ID of the target agent to communicate with
            agent_id: ID of this agent (defaults to AGENT_ID env var)
            agent_secret: Secret for this agent (defaults to AGENT_SECRET env var)
            registry_url: URL of the registry service (defaults to REGISTRY_URL env var)
        """
        # Get configuration from environment if not provided
        self.agent_id = agent_id or os.getenv("AGENT_ID")
        self.agent_secret = agent_secret or os.getenv("AGENT_SECRET")
        self.registry_url = registry_url or os.getenv("REGISTRY_URL", "https://api.getauthed.dev")
        
        # Get keys from environment
        self.private_key = os.getenv("PRIVATE_KEY")
        self.public_key = os.getenv("PUBLIC_KEY")
        
        # Validate required configuration
        if not self.agent_id or not self.agent_secret:
            raise ValueError(
                "agent_id and agent_secret must be provided either as arguments "
                "or via AGENT_ID and AGENT_SECRET environment variables"
            )
            
        if not self.private_key or not self.public_key:
            raise ValueError(
                "PRIVATE_KEY and PUBLIC_KEY environment variables must be set"
            )
        
        # Initialize the channel agent
        self._agent = Channel(
            agent_id=self.agent_id,
            agent_secret=self.agent_secret,
            registry_url=self.registry_url,
            private_key=self.private_key,
            public_key=self.public_key
        )
        
        # Store target agent ID
        self.target_agent_id = target_agent_id
        
        # Dictionary to store active channels
        self._channels: Dict[str, Any] = {}
        
        logger.info(
            f"Initialized AgentCommunicationTool for {self.agent_id} "
            "with encrypted communication"
        )
    
    @property
    def name(self) -> str:
        """The name of the tool."""
        return "agent_communication"
    
    @property
    def description(self) -> str:
        """Description of what the tool does."""
        return (
            "Sends messages to other agents and receives their responses. "
            "Use this when you need to communicate with external agents or services."
        )
    
    @property
    def args_schema(self) -> Dict[str, Any]:
        """The schema for the tool's arguments."""
        return MessageSchema.schema()
    
    def _run(self, message: str, target_agent_id: Optional[str] = None, 
             timeout_seconds: float = 10.0) -> str:
        """Synchronously send a message to another agent and get their response.
        
        Args:
            message: The message to send
            target_agent_id: Optional override for the target agent ID
            timeout_seconds: Maximum time to wait for response
            
        Returns:
            The response from the target agent
            
        Raises:
            ChannelError: If communication fails
        """
        # Get the current event loop or create a new one if needed
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in a running event loop, we need to use a different approach
                logger.debug("Using existing running event loop")
                
                # Create a new thread to run the async function
                import threading
                import concurrent.futures
                
                # Define a function to run in a separate thread
                def run_in_thread():
                    # Create a new event loop for this thread
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        # Run the async function in the new loop
                        return new_loop.run_until_complete(
                            self._arun(
                                message=message,
                                target_agent_id=target_agent_id,
                                timeout_seconds=timeout_seconds
                            )
                        )
                    finally:
                        new_loop.close()
                
                # Run the function in a separate thread and wait for the result
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    try:
                        return future.result(timeout=timeout_seconds)
                    except concurrent.futures.TimeoutError:
                        raise CommunicationTimeoutError(
                            f"Timeout waiting for response from target agent after {timeout_seconds} seconds"
                        )
            else:
                # Loop exists but isn't running, we can use run_until_complete
                logger.debug("Using existing non-running event loop")
                return loop.run_until_complete(
                    self._arun(
                        message=message,
                        target_agent_id=target_agent_id,
                        timeout_seconds=timeout_seconds
                    )
                )
        except RuntimeError:
            # No event loop exists in this thread, create a new one
            logger.debug("Creating new event loop")
            return asyncio.run(
                self._arun(
                    message=message,
                    target_agent_id=target_agent_id,
                    timeout_seconds=timeout_seconds
                )
            )
    
    async def _arun(self, message: str, target_agent_id: Optional[str] = None,
                    timeout_seconds: float = 10.0) -> str:
        """Asynchronously send a message to another agent and get their response."""
        target_id = target_agent_id or self.target_agent_id
        
        try:
            # Get or create channel
            channel = self._channels.get(target_id)
            if not channel or not channel.is_connected:
                logger.debug(f"Opening new channel to {target_id}")
                try:
                    # Fix: Use localhost with the appropriate port for local development
                    # This assumes Weather Agent is on port 8000 and Travel Agent is on port 8001
                    if target_id == "cc7262a5-405d-4101-8030-1e3904a7124e":  # Weather Agent
                        websocket_url = "ws://localhost:8000/ws"
                    elif target_id == "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa":  # Travel Agent
                        websocket_url = "ws://localhost:8001/ws"
                    else:
                        # For Agent_B or other formats, use the appropriate mapping
                        if target_id == "Agent_B" or target_id == "B":
                            websocket_url = "ws://localhost:8000/ws"  # Weather Agent
                        elif target_id == "Agent_A" or target_id == "A":
                            websocket_url = "ws://localhost:8001/ws"  # Travel Agent
                        else:
                            # Fallback to a default format if the ID is not recognized
                            websocket_url = f"ws://localhost:8000/ws"
                    
                    logger.debug(f"Using WebSocket URL: {websocket_url}")
                    
                    channel = await self._agent.open_channel(
                        target_agent_id=target_id,
                        websocket_url=websocket_url
                    )
                except Exception as e:
                    raise ConfigurationError(
                        f"Failed to open channel to {target_id}: {str(e)}"
                    )
                self._channels[target_id] = channel
            
            # Prepare message with timestamp
            content_data = {
                "message": message,
                "timestamp": self._agent.get_iso_timestamp(),
                "sender_id": self.agent_id
            }
            
            # Send message with retry logic
            try:
                message_id = await self._agent.send_message(
                    channel=channel,
                    content_type=MessageType.REQUEST,
                    content_data=content_data
                )
                logger.debug(f"Sent message {message_id} to {target_id}")
            except Exception as e:
                raise AgentCommunicationError(
                    f"Failed to send message to {target_id}: {str(e)}"
                )
            
            # Wait for response with timeout
            try:
                response = await asyncio.wait_for(
                    self._agent.receive_message(channel),
                    timeout=timeout_seconds
                )
                logger.debug(f"Received response from {target_id}")
                return response.get("message", "No response message received")
                
            except asyncio.TimeoutError:
                raise CommunicationTimeoutError(
                    f"Timeout waiting for response from {target_id} "
                    f"after {timeout_seconds} seconds"
                )
            
        except AgentCommunicationError:
            raise
        except Exception as e:
            raise AgentCommunicationError(f"Unexpected error: {str(e)}")
    
    async def close_channel(self, target_agent_id: Optional[str] = None):
        """Close the communication channel with a specific agent.
        
        Args:
            target_agent_id: ID of the target agent (defaults to initialized target)
        """
        target_id = target_agent_id or self.target_agent_id
        channel = self._channels.get(target_id)
        if channel:
            await self._agent.close_channel(channel)
            del self._channels[target_id]
    
    async def close_all_channels(self):
        """Close all open communication channels."""
        for target_id in list(self._channels.keys()):
            await self.close_channel(target_id) 