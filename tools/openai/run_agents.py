#!/usr/bin/env python3
import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load main .env file for OpenAI API key
load_dotenv(project_root / '.env')

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Change to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable detailed logging for websockets and channel
websocket_logger = logging.getLogger('websockets')
websocket_logger.setLevel(logging.DEBUG)
channel_logger = logging.getLogger('client.sdk.channel')
channel_logger.setLevel(logging.DEBUG)

# Default ports
WEATHER_AGENT_PORT = 8000
TRAVEL_AGENT_PORT = 8001

async def wait_for_agent(url: str, max_retries: int = 10, retry_delay: float = 1.0) -> bool:
    """Wait for an agent to be ready."""
    for i in range(max_retries):
        try:
            # Simple check if process is running
            logger.info(f"Checking if agent at port {url.split(':')[-1]} is running (attempt {i+1}/{max_retries})...")
            await asyncio.sleep(retry_delay)
            return True
        except Exception as e:
            logger.debug(f"Agent at {url} not ready yet: {str(e)}")
    
    logger.error(f"Agent at {url} failed to start after {max_retries} attempts")
    return False

async def run_agents():
    try:
        # Set up Python path for subprocesses
        python_path = str(project_root)
        
        # Start Weather Agent
        logger.info("Starting Weather Agent...")
        weather_env = os.environ.copy()
        weather_env.update({
            "PORT": str(WEATHER_AGENT_PORT),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "PYTHONPATH": python_path
        })
        
        weather_process = subprocess.Popen(
            [sys.executable, "weather_agent/weather_agent.py"],
            env=weather_env,
            cwd=Path(__file__).parent
        )
        
        # Start Travel Agent
        logger.info("Starting Travel Agent...")
        travel_env = os.environ.copy()
        travel_env.update({
            "PORT": str(TRAVEL_AGENT_PORT),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
            "PYTHONPATH": python_path
        })
        
        travel_process = subprocess.Popen(
            [sys.executable, "travel_agent/travel_agent.py"],
            env=travel_env,
            cwd=Path(__file__).parent
        )
        
        # Wait for both agents to be ready
        await wait_for_agent(f"http://localhost:{WEATHER_AGENT_PORT}")
        await wait_for_agent(f"http://localhost:{TRAVEL_AGENT_PORT}")
        
        logger.info(f"Both agents are running!")
        logger.info(f"Weather Agent is available at port {WEATHER_AGENT_PORT}")
        logger.info(f"Travel Agent is available at port {TRAVEL_AGENT_PORT}")
        
        # Keep the script running
        while True:
            await asyncio.sleep(1)
            
            # Check if processes are still running
            if weather_process.poll() is not None:
                logger.error("Weather Agent process has terminated!")
                break
            if travel_process.poll() is not None:
                logger.error("Travel Agent process has terminated!")
                break
                
    except KeyboardInterrupt:
        logger.info("Shutting down agents...")
    except Exception as e:
        logger.error(f"Error running agents: {str(e)}")
    finally:
        # Terminate the agent processes
        logger.info("Terminating agent processes...")
        try:
            weather_process.terminate()
            travel_process.terminate()
            
            # Wait for processes to terminate
            weather_process.wait(timeout=5)
            travel_process.wait(timeout=5)
        except Exception as e:
            logger.error(f"Error terminating agent processes: {str(e)}")
            # Force kill if terminate fails
            try:
                weather_process.kill()
                travel_process.kill()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(run_agents()) 