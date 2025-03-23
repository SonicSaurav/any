import os
import time
from openai import OpenAI
from .helper import (
    read_api_key,
    read_prompt_template,
    get_conversation_history_json,
    replace_conv_in_prompt,
    get_completion,
    extract_function_calls,
    process_search_simulation,
    parse_response,
    log_prompt,
    log_error,
    write_to_file,
    clear_conversation_history,
    save_final_conversation_history,
)
from .events import (
    stop_event,
    user_typing,
    assistant_typing,
    creating_persona,
    resume_event,
    clear_all_events,
)


# Ensure the logs directory exists before any logging is done.
os.makedirs("logs", exist_ok=True)
os.makedirs("history", exist_ok=True)


conv = []  # Global conversation history list
# TODO: Replace the conv with proper database model


def simulation():
    """
    Simulates a conversation between a user and an assistant agent using an AI model.
    This function performs the following steps:
    1. Initializes the simulation by:
        - Reading the API key and creating an API client instance.
        - Clearing previous conversation history.
        - Loading prompt templates for the user simulator, agent simulator, persona, and requirements.
        - Logging the loaded prompts for debugging and record-keeping.
    2. Generates the persona and requirements:
        - Triggers the 'creating_persona' event.
        - Retrieves or defaults the persona prompt response.
        - Constructs and logs the requirements prompt, then retrieves the corresponding response.
        - Clears the 'creating_persona' event after processing.
    3. Enters the main simulation loop:
        - Periodically pauses the simulation when the conversation length is a multiple of three,
          checking for resume or stop events during the pause.
        - Continues the loop only if no stop event is triggered and resume conditions are met.
    4. In each loop iteration:
        - Constructs a user prompt by integrating the conversation history, requirements, and persona.
        - Logs and sends the user prompt to the AI model and handles the AI-generated response.
        - Parses the user response, logs it, and appends it to the conversation history.
        - Constructs and logs an agent prompt based on the updated conversation.
        - Sends the agent prompt to the AI model, processes any function calls (e.g., for search)
          included in the response, and appends the final parsed assistant response to the conversation.
    5. Error and state management:
        - Exceptions during the loop are logged, and the simulation is gracefully terminated.
        - Final conversation history is saved and cleared upon exit.
    Note:
    - The function relies on several helper functions and global threading events (e.g., stop_event, resume_event,
      user_typing, assistant_typing) that are assumed to be defined elsewhere.
    - Several TODO comments in the code indicate planned improvements such as integrating a proper database model
      for conversation history management and refining the simulation pause conditions.
    """

    global conv
    print("[DEBUG] Simulator started")  # Debugging
    api_key = read_api_key()
    client = OpenAI(api_key=api_key)

    clear_conversation_history()  # TODO: Replace this with proper database model

    user_simulator_template = read_prompt_template("prompts/user_simulator.md")
    agent_simulator_template = read_prompt_template("prompts/agent_simulator.md")

    model_log_path = "logs/model_prompts.txt"
    persona_template = read_prompt_template("prompts/persona.md")
    log_prompt(model_log_path, f"Persona Prompt:\n{persona_template}")

    # udpate creating_persona event
    creating_persona.set()
    persona_output = get_completion(client, persona_template)
    persona = persona_output if persona_output else persona_template

    requirements_template = read_prompt_template("prompts/requirement.md")
    requirements_prompt = requirements_template.replace("{persona}", persona)
    log_prompt(model_log_path, f"Requirements Prompt:\n{requirements_prompt}")

    requirements_output = get_completion(client, requirements_prompt)
    requirements = requirements_output if requirements_output else requirements_prompt
    creating_persona.clear()

    user_log_path = "logs/user_prompts.txt"
    agent_log_path = "logs/agent_prompts.txt"
    error_log_path = "logs/error_logs.txt"

    try:
        while True:
            print("[DEBUG] Running simulation loop...")  # Debugging

            # 🛑 Pause when len(conv) is a multiple of 3
            if len(conv) % 3 == 0 and len(conv) > 0:
                # TODO: Replace this condition with something like
                # if lenght of current simulation messages is a multiple of 3/6
                # this will need a simulation id

                print("[DEBUG] Pausing simulation...")  # Debugging
                resume_event.clear()  # Clear the resume event to pause the simulation
                for i in range(60):  # Check every second for 60 seconds
                    if i % 10 == 0:
                        print(
                            f"[DEBUG] Will stop the simulation in {60 - i} seconds..."
                        )
                    if stop_event.is_set():
                        print("[DEBUG] Stop signal received during pause. Exiting...")
                        break  # Exit pause and stop immediately
                    if resume_event.is_set():
                        print(
                            "[DEBUG] Resume signal received. Continuing simulation..."
                        )
                        break  # Resume simulation
                    time.sleep(1)  # Small wait before checking again
            if stop_event.is_set():
                print("[DEBUG] Stop signal received. Exiting simulation...")
                # clear all events
                clear_all_events()
                return
            if not resume_event.is_set():
                print("[DEBUG] Waited for 1 minute. Stopping simulation...")
                # clear all events
                clear_all_events()
                return

            try:
                conversation_history_json = get_conversation_history_json(conv)
                # TODO: Replace this with proper database model

                user_prompt = replace_conv_in_prompt(
                    user_simulator_template,
                    conversation_history_json,
                    requirements,
                    persona,
                )
                log_prompt(user_log_path, user_prompt)
                log_prompt(model_log_path, f"User Simulator Prompt:\n{user_prompt}")

                # update user_typing event
                user_typing.set()
                user_response = get_completion(client, user_prompt)

                if user_response:
                    user_message = parse_response(user_response, "user")
                    conv.append(user_message)
                    print(f"[DEBUG] User Response Added: {user_message}")  # Debugging
                    write_to_file(conv)
                    # TODO: Add the current simulation messages to the database as User Message
                    user_typing.clear()

                    conversation_history_json = get_conversation_history_json(conv)
                    # TODO: get the conversation history from the database

                    agent_prompt = replace_conv_in_prompt(
                        agent_simulator_template, conversation_history_json
                    )
                    log_prompt(agent_log_path, agent_prompt)
                    log_prompt(
                        model_log_path, f"Agent Simulator Prompt:\n{agent_prompt}"
                    )
                    # update assistant_typing event
                    assistant_typing.set()
                    agent_response = get_completion(client, agent_prompt)
                    # clear assistant_typing event
                    # assistant_typing.clear()
                    if agent_response:
                        clean_response, function_calls = extract_function_calls(
                            agent_response
                        )
                        final_response = clean_response

                        for func_call in function_calls:
                            search_result = process_search_simulation(client, func_call)
                            if search_result:
                                final_response += (
                                    f"\n\nSearch Results:\n{search_result}"
                                )

                        assistant_message = parse_response(final_response, "assistant")
                        assistant_typing.clear()
                        conv.append(assistant_message)
                        # TODO: Add the current simulation messages to the database as Assistant Message
                        print(
                            f"[DEBUG] Assistant Response Added: {assistant_message}"
                        )  # Debugging
                        write_to_file(conv)
                        # TODO: Write the conversation history to the database

                time.sleep(1)
            except Exception as e:
                log_error(error_log_path, str(e))
                print(f"[ERROR] Exception in loop: {e}")  # Debugging
                break

        print("[DEBUG] Stopping simulation loop...")
        # save the final conversation history
        save_final_conversation_history()  # FIXME: We won't need this after replacing the conv with proper database model
        clear_conversation_history()  # FIXME: We won't need this after replacing the conv with proper database model
        return

    except Exception as e:
        print(f"[ERROR] Exception in main: {e}")
        log_error(error_log_path, str(e))
        save_final_conversation_history()  # FIXME: We won't need this after replacing the conv with proper database model
        clear_conversation_history()  # FIXME: We won't need this after replacing the conv with proper database model
        return
