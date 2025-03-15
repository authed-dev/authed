import asyncio
import os
import sys
import logging
from pathlib import Path
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# Enable detailed logging for websockets
websocket_logger = logging.getLogger('websockets')
websocket_logger.setLevel(logging.DEBUG)
# Enable detailed logging for channel
channel_logger = logging.getLogger('client.sdk.channel')
channel_logger.setLevel(logging.DEBUG)

from dotenv import load_dotenv
from agents import Agent, Runner, RunConfig
from agents import function_tool
from pydantic import BaseModel
from tools.openai.agent_communication import AgentCommunicationTool, communicate_with_agent
from client.sdk.channel import Channel, MessageType

# Load environment variables from local .env file
load_dotenv(Path(__file__).parent / '.env')

# Get port from environment or use default
PORT = int(os.getenv("PORT", "8000"))

# Create FastAPI app
app = FastAPI(title="Weather Agent")

# Create a Channel instance for handling WebSocket connections
channel_agent = Channel(
    agent_id=os.getenv("AGENT_ID"),
    agent_secret=os.getenv("AGENT_SECRET"),
    registry_url=os.getenv("REGISTRY_URL", "https://api.getauthed.dev"),
    private_key=os.getenv("PRIVATE_KEY"),
    public_key=os.getenv("PUBLIC_KEY")
)

class WeatherResponse(BaseModel):
    location: str
    temperature: str
    conditions: str
    forecast: str

@function_tool
def get_weather_data(city: str) -> dict:
    """Get current weather data for a specific city"""
    # Simulating weather API
    logger.debug(f"Getting weather data for {city}")
    return {
        "location": city,
        "temperature": "25°C",
        "conditions": "sunny with clear skies",
        "forecast": "Continued sunshine for the next 3 days"
    }

@function_tool
def get_historical_weather(city: str, days_ago: int) -> str:
    """Get historical weather data for a specific city"""
    logger.debug(f"Getting historical weather for {city}, {days_ago} days ago")
    return f"Historical weather for {city} {days_ago} days ago: 23°C, partly cloudy"

# Define a message handler for incoming requests
async def handle_message(channel, message):
    """Handle incoming messages from other agents"""
    logger.debug(f"Received message: {message}")
    
    try:
        # Extract the message content
        content = message.get("message", "")
        sender_id = message.get("sender_id", "unknown")
        
        logger.info(f"Message from {sender_id}: {content}")
        
        # Process the message using the weather agent
        if "weather" in content.lower():
            # Extract city from message
            city = "Paris"  # Default
            for word in content.lower().split():
                if word not in ["weather", "in", "the", "for", "current", "what's", "whats", "how's", "hows"]:
                    city = word.capitalize()
                    break
            
            # Get weather data
            weather_data = get_weather_data(city)
            
            # Prepare response
            response = f"The current weather in {weather_data['location']} is {weather_data['temperature']} and {weather_data['conditions']}. {weather_data['forecast']}"
        else:
            response = "I'm a weather agent. Please ask me about the weather in a specific city."
        
        # Send response back
        await channel_agent.send_message(
            channel=channel,
            content_type=MessageType.RESPONSE,
            content_data={"message": response}
        )
        
        # Return the response for the handler
        return {"message": response}
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        # Send error response
        error_message = f"Error processing your request: {str(e)}"
        await channel_agent.send_message(
            channel=channel,
            content_type=MessageType.RESPONSE,
            content_data={"message": error_message}
        )
        
        # Return the error message for the handler
        return {"message": error_message}

# Register the message handler using the correct method
channel_agent.register_handler(MessageType.REQUEST, handle_message)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    
    try:
        # Handle the WebSocket connection with the channel agent
        await channel_agent.handle_websocket_connection(websocket)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "weather_agent"}

# Create communication tool for Agent A (which can handle travel recommendations)
communication_tool = AgentCommunicationTool(
    target_agent_id="e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa"  # Travel Agent's ID (Agent A)
)

# Create the weather agent
weather_agent = Agent(
    name="weather_agent",
    instructions="""You are WeatherBot, an expert meteorologist with access to weather data.
    Provide accurate and helpful weather information when users ask about current or historical weather.
    Be conversational and friendly in your responses.""",
    tools=[get_weather_data, get_historical_weather, communicate_with_agent],
    output_type=WeatherResponse
)

async def process_query(query: str):
    """Process a single query to the weather agent"""
    logger.info(f"Processing query: {query}")
    config = RunConfig()
    output = await Runner.run(
        weather_agent,
        [{"role": "user", "content": query}],
        run_config=config
    )
    logger.debug(f"Raw output: {output}")
    
    # Extract and print the response
    try:
        response = output.final_output
        logger.info(f"Weather Response:")
        logger.info(f"Location: {response.location}")
        logger.info(f"Temperature: {response.temperature}")
        logger.info(f"Conditions: {response.conditions}")
        logger.info(f"Forecast: {response.forecast}")
        return response
    except Exception as e:
        logger.error(f"Error processing response: {e}")
        return None

async def main():
    """Run the weather agent continuously"""
    logger.info(f"Starting Weather Agent on port {PORT}")
    
    # Process an initial query to test the agent
    await process_query("What's the weather like in Paris today?")
    
    # Start the FastAPI server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main()) 