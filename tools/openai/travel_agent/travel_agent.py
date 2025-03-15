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

# Load main .env file first (for OpenAI API key)
load_dotenv()
# Then load agent-specific .env file (for agent credentials)
load_dotenv(Path(__file__).parent / '.env', override=True)

# Get port from environment or use default
PORT = int(os.getenv("PORT", "8001"))

# Create FastAPI app
app = FastAPI(title="Travel Agent")

# Create a Channel instance for handling WebSocket connections
channel_agent = Channel(
    agent_id=os.getenv("AGENT_ID"),
    agent_secret=os.getenv("AGENT_SECRET"),
    registry_url=os.getenv("REGISTRY_URL", "https://api.getauthed.dev"),
    private_key=os.getenv("PRIVATE_KEY"),
    public_key=os.getenv("PUBLIC_KEY")
)

class TravelRecommendation(BaseModel):
    destination: str
    recommendation: str
    activities: list[str]
    best_time_to_visit: str
    weather_info: str | None = None  # Optional field without default
    local_tips: str | None = None    # Optional field without default

@function_tool
def get_destination_info(city: str) -> dict:
    """Get travel information about a specific destination"""
    # Simulating travel database
    logger.debug(f"Getting destination info for {city}")
    destinations = {
        "tokyo": {
            "recommendation": "Tokyo is a vibrant metropolis blending traditional and modern culture",
            "activities": ["Visit Senso-ji Temple", "Explore Shibuya Crossing", "Tokyo Skytree", "Tsukiji Fish Market"],
            "best_time": "March-May for cherry blossoms or October-November for autumn colors"
        },
        "paris": {
            "recommendation": "Paris is known for its art, cuisine, and romantic atmosphere",
            "activities": ["Visit the Eiffel Tower", "Explore the Louvre", "Walk along Seine River", "Visit Montmartre"],
            "best_time": "April to June or September to October for mild weather"
        },
        "new york": {
            "recommendation": "New York offers world-class entertainment, dining, and cultural experiences",
            "activities": ["Visit Times Square", "Explore Central Park", "See a Broadway show", "Visit the MET"],
            "best_time": "April to June or September to early November"
        }
    }
    
    city_lower = city.lower()
    if city_lower in destinations:
        return {
            "destination": city,
            "recommendation": destinations[city_lower]["recommendation"],
            "activities": destinations[city_lower]["activities"],
            "best_time_to_visit": destinations[city_lower]["best_time"]
        }
    else:
        return {
            "destination": city,
            "recommendation": "A fascinating destination worth exploring",
            "activities": ["Sightseeing", "Local cuisine", "Cultural experiences", "Shopping"],
            "best_time_to_visit": "Spring or fall for moderate weather"
        }

@function_tool
def get_budget_estimate(city: str, days: int) -> str:
    """Get a budget estimate for a trip"""
    logger.debug(f"Getting budget estimate for {city} for {days} days")
    budget_estimates = {
        "tokyo": 200,
        "paris": 180,
        "new york": 250,
    }
    
    city_lower = city.lower()
    daily_cost = budget_estimates.get(city_lower, 150)
    total = daily_cost * days
    
    return f"Estimated budget for {days} days in {city}: ${total} USD (approximately ${daily_cost}/day)"

# Define a message handler for incoming requests
async def handle_message(channel, message):
    """Handle incoming messages from other agents"""
    logger.debug(f"Received message: {message}")
    
    try:
        # Extract the message content
        content = message.get("message", "")
        sender_id = message.get("sender_id", "unknown")
        
        logger.info(f"Message from {sender_id}: {content}")
        
        # Process the message to extract destination
        city = "Paris"  # Default
        for word in content.lower().split():
            if word not in ["travel", "visit", "in", "to", "the", "for", "about", "information"]:
                city = word.capitalize()
                break
        
        # Get destination info
        destination_info = get_destination_info(city)
        
        # Prepare response with local tips
        local_tips = {
            "tokyo": "Visit during weekdays to avoid crowds. Try the local ramen shops in alleyways for authentic food.",
            "paris": "Many museums are free on the first Sunday of each month. The best croissants are found in small bakeries away from tourist areas.",
            "new york": "Get a MetroCard for public transit. Visit the High Line for a unique urban park experience."
        }.get(city.lower(), "Explore local neighborhoods for authentic experiences and try to learn a few phrases in the local language.")
        
        response = (
            f"Travel tips for {destination_info['destination']}: {destination_info['recommendation']}. "
            f"Best time to visit is {destination_info['best_time_to_visit']}. "
            f"Local tip: {local_tips}"
        )
        
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
    return {"status": "healthy", "agent": "travel_agent"}

# Create communication tool for Agent B (which can handle both weather and local guide functionality)
communication_tool = AgentCommunicationTool(
    target_agent_id= "e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa" # Weather Agent's ID (Agent A)
)

# Create the travel agent (Agent A) with the correct ID
travel_agent = Agent(
    name="travel_agent",
    instructions="""You are TravelGuide, an expert travel advisor with access to a specialized agent.
    
    When providing recommendations:
    1. Use get_destination_info for basic destination information
    2. Use get_budget_estimate for cost planning
    3. Contact Agent B (using communication_tool) for both weather information and local tips
    
    Combine all this information to provide comprehensive travel advice.
    Be enthusiastic and personable in your responses.""",
    tools=[
        get_destination_info,
        get_budget_estimate,
        communicate_with_agent
    ],
    output_type=TravelRecommendation
)

async def process_query(query: str):
    """Process a single query to the travel agent"""
    logger.info(f"Processing query: {query}")
    config = RunConfig()
    
    output = await Runner.run(
        travel_agent,
        [{"role": "user", "content": query}],
        run_config=config
    )
    logger.debug(f"Raw output: {output}")
    
    # Extract and print the response
    try:
        response = output.final_output
        logger.info(f"Travel Recommendation:")
        logger.info(f"Destination: {response.destination}")
        logger.info(f"Recommendation: {response.recommendation}")
        logger.info(f"Activities: {', '.join(response.activities)}")
        logger.info(f"Best time to visit: {response.best_time_to_visit}")
        if response.weather_info:
            logger.info(f"Weather info: {response.weather_info}")
        if response.local_tips:
            logger.info(f"Local tips: {response.local_tips}")
        return response
    except Exception as e:
        logger.error(f"Error processing response: {e}")
        return None

async def main():
    """Run the travel agent continuously"""
    logger.info(f"Starting Travel Agent on port {PORT}")
    
    # Process an initial query to test the agent
    await process_query("I'm planning to visit Tokyo next month, what should I do there?")
    
    # Start the FastAPI server
    config = uvicorn.Config(app=app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main()) 