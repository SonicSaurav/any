import re
from openai import OpenAI
from models.models import AssistantMessage, Chat, Message, UserMessage, db
from together import Together
import json
import os
import logging
import threading

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

##############################################
# Helper Functions
##############################################

client = OpenAI()

def retrieve_or_create_chat(user, chat_id=None):
    """
    Retrieve an existing chat by ID or create a new one if no chat ID is provided.
    [... existing function code ...]
    """
    # Keep original function unchanged
    if chat_id:
        chat = Chat.query.get(chat_id)
        if not chat:
            return None, "Chat not found"
        if chat.user_id != user.id:
            return None, "Unauthorized chat access"
        return chat, None
    else:
        chat = Chat(user_id=user.id)
        db.session.add(chat)
        db.session.commit()  # Commit to generate chat.id
        return chat, None


def create_user_message(chat, user_input):
    """
    Create a new Message and a corresponding UserMessage in the database.
    [... existing function code ...]
    """
    # Keep original function unchanged
    message = Message(chat_id=chat.id)
    db.session.add(message)
    db.session.commit()  # commits to generate the message.id

    # Create the user message
    user_msg = UserMessage(message_id=message.id, content=user_input)
    db.session.add(user_msg)
    db.session.commit()

    return message


def read_prompt_template(file_path):
    """Read a prompt template from file."""
    try:
        with open(file_path, 'r', encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        error_msg = f"Error reading prompt template {file_path}: {str(e)}"
        print(f"\n{error_msg}")
        logger.error(error_msg)
        return None


def log_processed_prompt(prompt_name, processed_prompt):
    """Log the processed prompt after placeholder replacement to processed_prompts.txt."""
    import time
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    truncated_prompt = processed_prompt[:300] + "..." if len(processed_prompt) > 300 else processed_prompt
    
    with open("logs/processed_prompts.txt", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] PROCESSED {prompt_name}:\n{truncated_prompt}\n\n")


def extract_thinking(response):
    """Extract <think>...</think> tags from a response."""
    if not response or not isinstance(response, str):
        return "", response
    think_pattern = r'<think>(.*?)</think>\s*'
    match = re.search(think_pattern, response, re.DOTALL)
    if match:
        thinking_content = match.group(1)
        response_after = re.sub(think_pattern, '', response, count=1, flags=re.DOTALL).strip()
        return thinking_content, response_after
    else:
        return "", response


def extract_function_calls(response):
    """
    Extract <function> search_func(...) </function> calls.
    Returns cleaned response and a list of the function call body strings.
    """
    if not response or not isinstance(response, str):
        logger.error(f"Invalid response passed to extract_function_calls: {type(response)}")
        return "", []
    
    patterns = [
        r'<function>\s*search_func\((.*?)\)\s*</function>',
        r'<function>search_func\((.*?)\)</function>',
        r'<function>\s*search_func\s*\((.*?)\)\s*</function>'
    ]
    
    function_calls = []
    clean_response = response
    
    for pattern in patterns:
        calls = re.findall(pattern, response, flags=re.DOTALL)
        if calls:
            function_calls = calls
            clean_response = re.sub(pattern, '', response, flags=re.DOTALL)
            logger.debug(f"Extract function calls - Found pattern match: {pattern}")
            break

    logger.debug(f"Extract function calls - Found {len(function_calls)} function calls")
    clean_response = clean_response.strip()

    return clean_response, function_calls


def extract_ner_from_conversation(conversation_history):
    """
    Extract named entities (hotel preferences) from conversation using ner.md prompt.
    """
    try:
        simple_conversation = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in conversation_history
        ]
        ner_template = read_prompt_template("prompts/ner.md")
        if not ner_template:
            logger.error("Failed to read ner.md template")
            return {}
        ner_prompt = ner_template.replace("{conv}", json.dumps(simple_conversation, ensure_ascii=False, indent=2))
        
        # Log the processed prompt
        log_processed_prompt("NER_Prompt", ner_prompt)
        
        # Use the existing OpenAI client
        client = OpenAI()
        completion = client.chat.completions.create(
            model="o3-mini",
            messages=[{"role": "user", "content": ner_prompt}]
        )
        ner_response = completion.choices[0].message.content if completion.choices else None
        
        if not ner_response:
            logger.error("No NER response generated")
            return {}
            
        dict_pattern = r'```python\s*({[\s\S]*?})\s*```'
        match = re.search(dict_pattern, ner_response)
        if match:
            try:
                preferences_dict = eval(match.group(1))
                logger.debug(f"Extracted preferences: {json.dumps(preferences_dict, ensure_ascii=False)}")
                return preferences_dict
            except Exception as e:
                logger.error(f"Error parsing extracted preferences: {str(e)}")
                return {}
        else:
            # Attempt direct dictionary extraction
            try:
                dict_pattern = r'({[\s\S]*?})'
                match_direct = re.search(dict_pattern, ner_response)
                if match_direct:
                    preferences_dict = eval(match_direct.group(1))
                    logger.debug(f"Extracted preferences (direct): {json.dumps(preferences_dict, ensure_ascii=False)}")
                    return preferences_dict
                else:
                    logger.error("No valid preferences dictionary found in NER response")
                    return {}
            except Exception as e:
                logger.error(f"Error with direct parsing: {str(e)}")
                return {}
    except Exception as e:
        error_msg = f"Error in NER extraction: {str(e)}"
        logger.error(error_msg)
        return {}


def process_search_call(extracted_preferences):
    """
    Determine if a search should be triggered from search_call.md prompt.
    Returns the function call snippet or empty string.
    """
    try:
        search_call_template = read_prompt_template("prompts/search_call.md")
        if not search_call_template:
            logger.error("Failed to read search_call.md template")
            return ""
        search_call_prompt = search_call_template.replace(
            "{preferences}",
            json.dumps(extracted_preferences, ensure_ascii=False, indent=2)
        )
        
        # Log the processed prompt
        log_processed_prompt("Search_Call_Prompt", search_call_prompt)
        
        # Use the existing OpenAI client
        client = OpenAI()
        completion = client.chat.completions.create(
            model="o3-mini",
            messages=[{"role": "user", "content": search_call_prompt}]
        )
        search_call_response = completion.choices[0].message.content if completion.choices else None
        
        if not search_call_response:
            logger.error("No search call response generated")
            return ""
            
        search_call_response = search_call_response.strip()
        if "<function>" in search_call_response:
            return search_call_response
        return ""
    except Exception as e:
        error_msg = f"Error in search call processing: {str(e)}"
        logger.error(error_msg)
        return ""


def process_search_simulation(function_call_content, conversation_history):
    """Process search_func call with search_simulator.md."""
    if not function_call_content or function_call_content.strip() == "":
        logger.error("Empty function call content passed to search processing")
        return None
    
    logger.debug(f"Processing search with function call of length: {len(function_call_content)}")
    try:
        logger.debug(f"Processing search query: {function_call_content}")
        search_template = read_prompt_template("prompts/search_simulator.md")
        if not search_template:
            logger.error("Failed to read search_simulator.md template")
            return None
            
        search_prompt = search_template.replace("{search_query}", function_call_content.strip())
        
        # Log the processed prompt
        log_processed_prompt("Search_Simulator_Prompt", search_prompt)
        
        # Use the existing OpenAI client
        client = OpenAI()
        completion = client.chat.completions.create(
            model="o3-mini-2025-01-31",
            messages=[{"role": "user", "content": search_prompt}]
        )
        search_response = completion.choices[0].message.content if completion.choices else None
        
        if not search_response:
            logger.error("No search result received for query")
            return None
            
        logger.debug(f"Search result received of length: {len(search_response)}")
        
        # Extract number of matches
        num_matches = None
        patterns = [
            r'"Number of matches":\s*(\d+)',
            r'Number of matches:\s*(\d+)',
            r'Found (\d+) matches',
            r'(\d+) results found',
            r'(\d+) hotels match'
        ]
        for pattern in patterns:
            mm = re.search(pattern, search_response, re.IGNORECASE)
            if mm:
                try:
                    num_matches = int(mm.group(1))
                    logger.debug(f"Found {num_matches} matches in search results using pattern: {pattern}")
                    break
                except ValueError:
                    continue
                    
        if num_matches is None:
            no_matches_patterns = [r'no matches', r'no results', r'0 matches', r'0 results']
            for p in no_matches_patterns:
                if re.search(p, search_response, re.IGNORECASE):
                    logger.debug("Search explicitly mentions no matches")
                    num_matches = 0
                    break
                    
        if num_matches is None:
            # fallback count
            hotel_name_count = len(re.findall(r'Hotel name:', search_response, re.IGNORECASE))
            if hotel_name_count > 0:
                num_matches = hotel_name_count
                logger.debug(f"Fallback: Estimated {num_matches} matches by counting 'Hotel name:' occurrences")
            else:
                num_matches = 100  # Default to high number to be safe
                logger.debug(f"Could not determine number of matches, defaulting to {num_matches}")
                
        # Create search record
        timestamp = ""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        search_record = {
            "timestamp": timestamp,
            "parameters": function_call_content,
            "results": search_response,
            "num_matches": num_matches
        }
        
        return search_record
    except Exception as e:
        error_msg = f"Unexpected error in search processing: {str(e)}"
        logger.error(error_msg)
        return None


def process_search_results(search_record):
    """
    Decide whether to show search results to the actor or not.
    Returns (show_results_to_actor, search_text).
    """
    if not search_record:
        return False, ""
    try:
        search_response = search_record.get("results", "")
        if not search_response:
            logger.debug("Empty search results found")
            return False, ""
            
        num_matches = search_record.get("num_matches", 100)
        
        # This is where we decide whether to show search results to the actor
        # We use 10 as the threshold based on the actor.md prompt instructions
        if num_matches > 10:
            logger.debug(f"Will NOT show search results to actor ({num_matches} matches > 10)")
            return False, search_response
        else:
            logger.debug(f"Will show search results to actor ({num_matches} matches ≤ 10)")
            return True, search_response
    except Exception as e:
        error_msg = f"Error processing search results: {str(e)}"
        logger.error(error_msg)
        return False, ""


def generate_assistant_response(
    chat,
    base_prompt_path,
    search_prompt_path,
    conversation_history,
    search_history,
    assistant,
):
    """
    Generate an assistant response using the improved three-prompt workflow.
    
    This function:
    1. Extracts hotel preferences using NER
    2. Determines if a search should be triggered
    3. Processes search results if needed
    4. Generates the final assistant response
    
    Returns:
        tuple: (assistant_message_content, search_results, NER_preferences, all_processing_steps)
        where all_processing_steps is a dictionary with all the intermediate steps for UI display
    """
    processing_steps = {
        "NER": None,
        "search_call": None,
        "search_results": None,
        "final_response": None,
        "thinking": None
    }
    
    try:
        # 1) Extract hotel preferences with NER
        preferences = extract_ner_from_conversation(conversation_history)
        processing_steps["NER"] = preferences
        
        # 2) Determine if search should be triggered
        search_record = None
        show_results_to_actor = False
        search_call_result = process_search_call(preferences)
        processing_steps["search_call"] = search_call_result
        
        if search_call_result:
            # 3) Process search if a call was triggered
            search_record = process_search_simulation(search_call_result, conversation_history)
            processing_steps["search_results"] = search_record
            
            if search_record:
                # Decide if we show results to actor based on match count
                show, search_text = process_search_results(search_record)
                show_results_to_actor = show
                if show_results_to_actor:
                    search_record["show_results_to_actor"] = True
                else:
                    search_record["show_results_to_actor"] = False
        
        # 4) Read base prompt template
        with open(base_prompt_path, "r") as file:
            prompt = file.read()
        
        # 5) Build the prompt with conversation history and search results if applicable
        num_matches = search_record["num_matches"] if search_record else ""
        search_results_text = search_record["results"] if search_record and show_results_to_actor else ""
        
        updated_prompt = (
            prompt
            .replace("{conv}", str(conversation_history))
            .replace("{search}", search_results_text)
            .replace("{num_matches}", str(num_matches))
        )
        
        # Log the prompt for debugging
        with open("logs/assistant_prompt.log", "a+") as file:
            file.write(f"{updated_prompt}\n")
            file.write("-" * 50 + "\n" * 5)
        
        # 6) Generate the assistant response
        try:
            client = Together(api_key='a923ff51a697d6812f846b69aea86466853cceaf95c8ab2dfc84de07cce6ffe1')
            completion = client.chat.completions.create(
                model="deepseek-ai/DeepSeek-R1",
                messages=[
                    {
                        "role": "user",
                        "content": updated_prompt,
                    }
                ],
                seed=assistant,
                temperature=0.6,
            )
        except Exception as e:
            logger.error(f"Failed to generate a response: {e}")
            return None, None, preferences, processing_steps
        
        response_content = completion.choices[0].message.content
        
        # 7) Extract thinking if present
        thinking, response_after_thinking = extract_thinking(response_content)
        processing_steps["thinking"] = thinking
        
        # 8) Extract any function calls in the response
        clean_response, _ = extract_function_calls(response_after_thinking)
        
        # Use the clean response if available, otherwise use the full response
        assistant_message_content = clean_response if clean_response else response_after_thinking
        processing_steps["final_response"] = assistant_message_content
        
        return assistant_message_content, search_record, preferences, processing_steps
        
    except Exception as e:
        logger.error(f"Error in generate_assistant_response: {e}")
        return None, None, {}, processing_steps


def store_assistant_message(message_id, content, search_output=None, output_number=1, processing_steps=None):
    """
    Stores an assistant message in the database.
    We'll store processing_steps in the search_output field as JSON if search_output is None.
    """
    # If there's actual search output, use that
    # Otherwise, we can store processing steps in the search_output field temporarily for debugging
    final_search_output = search_output
    if search_output is None and processing_steps is not None:
        # Only for debugging - this won't be shown to users
        final_search_output = json.dumps({"debug_processing_steps": processing_steps})

    assistant_msg = AssistantMessage(
        message_id=message_id,
        content=content,
        search_output=final_search_output,
        output_number=output_number
    )
    db.session.add(assistant_msg)
    db.session.commit()
    return assistant_msg


def generate_and_store_assistant_message(
    chat, message, base_prompt_path, search_prompt_path
):
    """
    Generates an assistant response and stores the generated message.
    Now includes all processing steps for UI display.
    """
    conversation_history = chat.get_conversation_history()
    search_history = chat.get_search_history()

    assistant_message_content, search_results, preferences, processing_steps = generate_assistant_response(
        chat,
        base_prompt_path,
        search_prompt_path,
        conversation_history,
        search_history,
        assistant=1,
    )

    if assistant_message_content is None:
        # Return some fallback or error message if generation fails
        logger.error("No assistant message content generated.")
        assistant_message_content = "[Error: assistant failed to respond.]"
        processing_steps["final_response"] = assistant_message_content

    # Store the assistant message with all processing steps
    search_output = json.dumps(search_results) if search_results else None
    store_assistant_message(
        message_id=message.id,
        content=assistant_message_content,
        search_output=search_output,
        output_number=1,
        processing_steps=processing_steps
    )


def maybe_generate_second_assistant_message(
    chat, message, base_prompt_path, search_prompt_path
):
    """
    Generate a response for the second assistant and store the message.
    Now includes processing steps for UI display.
    """
    conversation_history = chat.get_conversation_history()
    search_history = chat.get_search_history()

    assistant_message_content, search_results, preferences, processing_steps = generate_assistant_response(
        chat,
        base_prompt_path,
        search_prompt_path,
        conversation_history,
        search_history,
        assistant=2,
    )

    if assistant_message_content is None:
        assistant_message_content = "[Error]: second assistant failed to respond."
        processing_steps["final_response"] = assistant_message_content

    # Store the assistant message with all processing steps
    search_output = json.dumps(search_results) if search_results else None
    store_assistant_message(
        message_id=message.id,
        content=assistant_message_content,
        search_output=search_output,
        output_number=2,
        processing_steps=processing_steps
    )