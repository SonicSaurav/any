import json
from openai import OpenAI
from together import Together
import re
import logging
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if present

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize clients
openai_client = OpenAI()
together_client = None
try:
    together_client = Together(api_key='a923ff51a697d6812f846b69aea86466853cceaf95c8ab2dfc84de07cce6ffe1')
except Exception as e:
    logger.error(f"Error initializing Together client: {str(e)}")


def read_prompt_template(file_path):
    """Read a prompt template from file."""
    try:
        with open(file_path, 'r', encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        error_msg = f"Error reading prompt template {file_path}: {str(e)}"
        logger.error(error_msg)
        return None


def get_together_completion(prompt, max_retries=2):
    """Use Together AI for critic evaluations."""
    if not together_client:
        logger.error("Together client not initialized")
        return None
        
    for attempt in range(max_retries):
        try:
            completion = together_client.chat.completions.create(
                model="deepseek-ai/DeepSeek-R1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                stream=False
            )
            return completion.choices[0].message.content if completion.choices else None
        except Exception as e:
            logger.error(f"Error in get_together_completion (attempt {attempt+1}): {str(e)}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)  # Wait before retrying
    
    return None


def parse_critic_response(response_text):
    """Parse the critic response to extract JSON structure."""
    if not response_text:
        print("Empty critic response")
        return {"error": "No critic response generated"}
        
    # Log the raw response for debugging
    with open("logs/critic_raw_response.log", "a") as file:
        file.write(f"{response_text}\n")
        file.write("-" * 50 + "\n" * 5)
    
    # Extract all JSON-like structures with a greedy approach
    try:
        # Find the most complete JSON object in the text
        found_jsons = []
        start_positions = [m.start() for m in re.finditer(r'\{', response_text)]
        
        for start in start_positions:
            # Try to find a valid JSON object starting from this position
            open_braces = 0
            for i in range(start, len(response_text)):
                if response_text[i] == '{':
                    open_braces += 1
                elif response_text[i] == '}':
                    open_braces -= 1
                    if open_braces == 0:  # Found a complete JSON-like structure
                        json_candidate = response_text[start:i+1]
                        try:
                            parsed = json.loads(json_candidate)
                            found_jsons.append(parsed)
                            break
                        except:
                            pass  # Not valid JSON, continue
        
        # Check found JSONs for critique format
        for json_obj in found_jsons:
            if 'total_score' in json_obj or 'adherence_to_search' in json_obj or 'question_format' in json_obj:
                return json_obj
        
        # If no matching critique format found but we have JSONs, return the largest one
        if found_jsons:
            return max(found_jsons, key=lambda x: len(json.dumps(x)))
    except Exception as e:
        print(f"Error in advanced JSON parsing: {str(e)}")
    
    # If all parsing fails, return a default response with the raw text
    print("All JSON parsing approaches failed")
    return {
        "error": "Failed to parse critic response",
        "raw_response": response_text[:1000],  # Truncate very long responses
        "total_score": -1.0
    }

def get_score(conversation_history, search_history={}):
    """
    Calculate and return a rating based on the conversation and search histories.
    Enhanced to return a more detailed critique and support regeneration.
    """
    # Open the file using the resolved absolute path
    with open("prompts/actor.md", "r") as file:
        agent_prompt = file.read()

    with open("prompts/critic.md", "r") as file:
        critic_prompt = file.read()

    with open("logs/conv_hist.json", "w") as file:
        json.dump(conversation_history, file)

    last_response = conversation_history[-1]
    conversation_history = conversation_history[:-1]
    
    try:
        # Replace placeholders in the critic prompt
        critic_prompt = (
            critic_prompt.replace("{conversation}", str(conversation_history))
            .replace("{original_prompt}", str(agent_prompt))
            .replace("{search_history}", str(search_history))
            .replace("{last_response}", str(last_response))
        )
        
        # Log the prepared critic prompt
        with open("logs/critic.md", "a") as file:
            file.write(f"{critic_prompt}\n")
            file.write("-" * 50 + "\n" * 5)
    except Exception as e:
        logger.error(f"Error preparing critic prompt: {e}")
        with open("logs/critic_error.log", "a") as file:
            file.write(f"{e}\n")
        return -1.0

    # Get critic evaluation from Together
    critic_response = get_together_completion(critic_prompt)
    if not critic_response:
        logger.error("Failed to get critic response")
        return -1.0
        
    # Log the raw critic response
    with open("logs/critic_response.log", "a") as file:
        file.write(f"{critic_response}\n")
        file.write("-" * 50 + "\n" * 5)
        
    # Parse the critic response
    parsed_critique = parse_critic_response(critic_response)
    
    # Log the parsed critique
    with open("logs/critic_parsed.log", "a") as file:
        file.write(f"{json.dumps(parsed_critique, indent=2)}\n")
        file.write("-" * 50 + "\n" * 5)
    
    # Extract the total score
    if "total_score" in parsed_critique:
        if parsed_critique["total_score"] is None:
            parsed_critique["total_score"] = -1.0  # Default to -1.0
        return parsed_critique
    elif "score" in parsed_critique:
        if parsed_critique["score"] is None:
            return -1.0  # Default to -1.0
        return parsed_critique["score"]
    
    logger.error("No score found in critic response")
    return -1.0  # Default to -1.0

def regenerate_response(conversation_history, last_response, critique):
    """
    Regenerate a response based on critic feedback.
    """
    with open("prompts/critic_regen.md", "r") as file:
        regen_template = file.read()
    
    # Create the conversation context
    conversation_context = []
    for msg in conversation_history:
        role = msg["role"]
        content = msg["content"]
        conversation_context.append(f"{role}: {content}")
    conversation_context = "\n\n".join(conversation_context)
    
    # Create a summary of critique feedback
    critique_reason = ""
    if isinstance(critique, dict):
        sections = []
        for key, value in critique.items():
            if key in ["total_score", "score", "error", "raw_response"]:
                continue
            if isinstance(value, dict) and "reason" in value:
                sections.append(f"## {key}\n{value['reason']}")
            elif key == "summary":
                sections.append(f"## Summary\n{value}")
        critique_reason = "\n\n".join(sections)
    
    # Create the regeneration prompt
    regen_prompt = (
        regen_template
        .replace("{conversation_context}", conversation_context)
        .replace("{last_response}", last_response)
        .replace("{critic_reason}", critique_reason)
        .replace("{search_history}", "")  # We don't have search_history here
    )
    
    # Log the regeneration prompt
    with open("logs/regen_prompt.log", "a") as file:
        file.write(f"{regen_prompt}\n")
        file.write("-" * 50 + "\n" * 5)
    
    # Get the regenerated response
    regenerated_response = get_together_completion(regen_prompt)
    if not regenerated_response:
        logger.error("Failed to regenerate response")
        return None
    
    # Log the regenerated response
    with open("logs/regen_response.log", "a") as file:
        file.write(f"{regenerated_response}\n")
        file.write("-" * 50 + "\n" * 5)
    
    return regenerated_response