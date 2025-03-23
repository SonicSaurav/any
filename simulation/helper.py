from .logger import log_function_call
import json
import re
import os
import time
from .events import file_lock

# ==================================================================================================#
# ------------------------------- Code written by Saurav -------------------------------------------#
# I have not changed anything in this code. I have just copied this code from the file              #
# langchain_workflow.py and pasted it here to be imported in simulator.py file.                     #
# 🚩🚩🚩🚩 Code written by me is in the next block seperated by a similar comment                   #
# ==================================================================================================#


@log_function_call
def read_api_key(key_path="./openai.key"):
    with open(key_path, "r") as f:
        return f.read().strip()


@log_function_call
def read_prompt_template(file_path):
    with open(file_path, "r") as f:
        return f.read()


def get_conversation_history_json(conv):
    """
    Returns the conversation history as a JSON string.
    """
    return json.dumps(conv, ensure_ascii=False, indent=2)


@log_function_call
def replace_conv_in_prompt(
    template, conversation_history_json, requirements=None, persona=None
):
    """
    Replace placeholders in template with actual values.
    """
    result = template.replace("{conv}", conversation_history_json)
    if requirements:
        result = result.replace("{requirements}", requirements)
    if persona:
        result = result.replace("{persona}", persona)
    return result


@log_function_call
def get_completion(client, prompt):
    try:
        response = client.chat.completions.create(
            model="o3-mini-2025-01-31",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error in API call: {e}")
        return None


def extract_function_calls(response):
    """
    Extracts all search_hotel function calls from the assistant's response.

    It returns a tuple containing:
      - the response text with all <function>search_hotel ... </function> blocks removed,
      - a list of the extracted function call parameters.

    The regex pattern looks for a block like:

      <function>
        search_hotel(...)
      </function>

    and captures everything between 'search_hotel' and the closing </function> tag.
    """
    # Use DOTALL to allow newline characters in the match
    pattern = r"<function>\s*search_hotel(.*?)</function>"
    function_calls = re.findall(pattern, response, flags=re.DOTALL)
    # Remove the entire function call block from the response
    clean_response = re.sub(
        r"<function>\s*search_hotel.*?</function>", "", response, flags=re.DOTALL
    )
    return clean_response.strip(), function_calls


@log_function_call
def process_search_simulation(client, function_call):
    """
    Process a search_hotel function call by replacing user preferences in the search simulator template.
    """
    try:
        # Read search simulator template
        search_template = read_prompt_template("./search_simulator.txt")
        # Replace the placeholder with the extracted function call (user preferences)
        search_prompt = search_template.replace("{pref}", function_call.strip())

        # Log the search prompt to the model prompts log.
        log_prompt("logs/model_prompts.txt", f"Search Prompt:\n{search_prompt}")

        # Get completion from API
        search_result = get_completion(client, search_prompt)
        return search_result
    except Exception as e:
        print(f"Error in search simulation: {e}")
        return None


def parse_response(response, role):
    if not response:
        return {"role": role, "content": "No response received"}

    try:
        parsed = json.loads(response)
        if isinstance(parsed, dict):
            parsed["role"] = role
            return parsed
        else:
            return {"role": role, "content": response.strip()}
    except json.JSONDecodeError:
        return {"role": role, "content": response.strip()}


def print_debug_info(prompt_type, template, conversation_history_json, final_prompt):
    print("\n" + "=" * 50)
    print(f"\n{prompt_type} Template:")
    print("-" * 20)
    print(template)

    print("\nCurrent Conversation History (JSON):")
    print("-" * 20)
    print(conversation_history_json if conversation_history_json else "[Empty]")

    print(f"\nFinal {prompt_type} Prompt:")
    print("-" * 20)
    print(final_prompt)
    print("=" * 50 + "\n")


def log_prompt(file_path, prompt):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}]\n{prompt}\n\n")


def log_error(file_path, error_message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] ERROR: {error_message}\n\n")


# ==================================================================================================#
# ------------------------------- Code written by me - Shivang ------------------------------------#
# I have written this code to add some extra functionalities to the existing code or               #
# to avoid redundancy in the code.                                                                 #
# ==================================================================================================#


def write_to_file(data):
    # TODO: Replace this with proper database model
    """Thread-safe method to write conversation history to a file"""
    try:
        with file_lock:
            with open("conversation_history.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()  # Flush buffer
                os.fsync(f.fileno())  # Force OS to write immediately
            print(
                "[DEBUG] Successfully wrote to conversation_history.json"
            )  # Debugging
    except Exception as e:
        print(f"[ERROR] Failed to write to file: {e}")  # Debugging


def save_final_conversation_history():
    # TODO: Replace this with proper database model
    """Thread-safe method to write conversation history to a file inside the history directory"""
    try:
        with file_lock:
            # Generate a unique filename based on the current timestamp
            filename = f"history/{time.strftime('%Y%m%d%H%M%S')}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(conv, f, ensure_ascii=False, indent=2)
            print(f"[DEBUG] Successfully wrote to {filename}")  # Debugging
    except Exception as e:
        print(f"[ERROR] Failed to write to file: {e}")  # Debugging


def clear_conversation_history():
    # TODO: We won't need this after replacing the conv with proper database model
    """Clears the conversation history before starting the simulation"""
    global conv
    try:
        conv = []  # Clear the global conversation history list
        with open("conversation_history.json", "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        print("[DEBUG] Cleared conversation_history.json")  # Debugging log
    except Exception as e:
        print(f"[ERROR] Failed to clear conversation history: {e}")  # Debugging log
