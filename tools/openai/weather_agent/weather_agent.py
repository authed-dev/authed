from agents import Agent, Runner, RunConfig
from agents import function_tool
from pydantic import BaseModel
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
from tools.openai.agent_communication import AgentCommunicationTool, communicate_with_agent

# Load environment variables from local .env file
load_dotenv(Path(__file__).parent / '.env')

class WeatherResponse(BaseModel):
    location: str
    temperature: str
    conditions: str
    forecast: str

@function_tool
def get_weather_data(city: str) -> dict:
    """Get current weather data for a specific city"""
    # Simulating weather API
    return {
        "location": city,
        "temperature": "25°C",
        "conditions": "sunny with clear skies",
        "forecast": "Continued sunshine for the next 3 days"
    }

@function_tool
def get_historical_weather(city: str, days_ago: int) -> str:
    """Get historical weather data for a specific city"""
    return f"Historical weather for {city} {days_ago} days ago: 23°C, partly cloudy"

communication_tool = AgentCommunicationTool(
    target_agent_id="e30cbe1e-c47c-40e8-8f0f-0fe3bd3518aa"
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

async def main():
    config = RunConfig()
    output = await Runner.run(
        weather_agent,
        [{"role": "user", "content": "What's the weather like in Paris today?"}],
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
            print("\nWeather Response (from dict):")
            print(f"Location: {response.get('location')}")
            print(f"Temperature: {response.get('temperature')}")
            print(f"Conditions: {response.get('conditions')}")
            print(f"Forecast: {response.get('forecast')}")
        else:
            print("\nWeather Response (direct access):")
            print(f"Location: {response.location}")
            print(f"Temperature: {response.temperature}")
            print(f"Conditions: {response.conditions}")
            print(f"Forecast: {response.forecast}")
            
    except AttributeError as e:
        print(f"Debug - Error accessing fields: {e}")
    except Exception as e:
        print(f"Debug - Other error: {type(e)}: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 