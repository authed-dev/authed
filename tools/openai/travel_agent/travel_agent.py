import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from agents import Agent, Runner, RunConfig
from agents import function_tool
from pydantic import BaseModel
from tools.openai.agent_communication import AgentCommunicationTool, communicate_with_agent

# Load main .env file first (for OpenAI API key)
load_dotenv()
# Then load agent-specific .env file (for agent credentials)
load_dotenv(Path(__file__).parent / '.env', override=True)

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
    budget_estimates = {
        "tokyo": 200,
        "paris": 180,
        "new york": 250,
    }
    
    city_lower = city.lower()
    daily_cost = budget_estimates.get(city_lower, 150)
    total = daily_cost * days
    
    return f"Estimated budget for {days} days in {city}: ${total} USD (approximately ${daily_cost}/day)"

# Create communication tool for Agent B (which can handle both weather and local guide functionality)
communication_tool = AgentCommunicationTool(
    target_agent_id= "cc7262a5-405d-4101-8030-1e3904a7124e" # Agent B's ID
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

async def main():
    config = RunConfig()
    
    # Example queries showing agent interaction
    queries = [
        "I'm planning to visit Tokyo next month, what should I do there?",
        "Tell me about Paris in spring, including weather and local events.",
        "What's the best time to visit New York, considering weather and activities?"
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        output = await Runner.run(
            travel_agent,
            [{"role": "user", "content": query}],
            run_config=config
        )
        print("\nDebug - Raw output:", output)
        print("Debug - Output type:", type(output))
        print("Debug - Output dir:", dir(output))
        print("Debug - Dict representation:", vars(output) if hasattr(output, '__dict__') else "No __dict__")
        
        # Try different ways of accessing the response
        try:
            # First try to get the message
            if hasattr(output, 'messages') and output.messages:
                print("\nAccessing via output.messages:")
                message = output.messages[-1]  # Get the last message
            elif hasattr(output, 'message'):
                print("\nAccessing via output.message:")
                message = output.message
            else:
                print("\nNo message field found, using output directly:")
                message = output
                
            print(f"Message type: {type(message)}")
            print(f"Message content: {message}")
            
            # Then try to get the actual content
            if hasattr(message, 'content'):
                response = message.content
            elif hasattr(message, 'final_output'):
                response = message.final_output
            else:
                response = message
                
            print(f"\nResponse type: {type(response)}")
            print(f"Response content: {response}")
            
            if isinstance(response, dict):
                print("\nTravel Recommendation (from dict):")
                print(f"Destination: {response.get('destination')}")
                print(f"Recommendation: {response.get('recommendation')}")
                print(f"Activities: {', '.join(response.get('activities', []))}")
                print(f"Best time to visit: {response.get('best_time_to_visit')}")
                if 'weather_info' in response:
                    print(f"Weather info: {response.get('weather_info')}")
                if 'local_tips' in response:
                    print(f"Local tips: {response.get('local_tips')}")
            else:
                print("\nTravel Recommendation (direct access):")
                print(f"Destination: {response.destination}")
                print(f"Recommendation: {response.recommendation}")
                print(f"Activities: {', '.join(response.activities)}")
                print(f"Best time to visit: {response.best_time_to_visit}")
                if response.weather_info:
                    print(f"Weather info: {response.weather_info}")
                if response.local_tips:
                    print(f"Local tips: {response.local_tips}")
                
        except AttributeError as e:
            print(f"Debug - Error accessing fields: {e}")
        except Exception as e:
            print(f"Debug - Other error: {type(e)}: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 