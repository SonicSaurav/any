import re
from openai import OpenAI
from models.models import AssistantMessage, Chat, Message, UserMessage, db
from together import Together

##############################################
# Helper Functions
##############################################


client = OpenAI()


def retrieve_or_create_chat(user, chat_id=None):
    """
    Retrieve an existing chat by ID or create a new one if no chat ID is provided.

    This function checks if a chat ID is provided. If it is, the function fetches the chat from the database,
    verifying that the specified chat exists and is owned by the given user. If the chat does not exist or does not belong
    to the user, an appropriate error message is returned. When no chat ID is provided, a new chat instance is created for the user,
    added to the database, and committed to generate its ID.

    Parameters:
        user: The user instance who owns the chat.
        chat_id (optional): The unique identifier of the chat to retrieve. Defaults to None.

    Returns:
        tuple:
            - The chat instance if successfully retrieved or created, otherwise None.
            - An error message if an error occurred (e.g. chat not found or unauthorized access), otherwise None.

    """
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
    """
    # Create a new parent message record
    message = Message(chat_id=chat.id)
    db.session.add(message)
    db.session.commit()  # commits to generate the message.id

    # Create the user message
    user_msg = UserMessage(message_id=message.id, content=user_input)
    db.session.add(user_msg)
    db.session.commit()

    return message


def generate_assistant_response(
    chat,
    base_prompt_path,
    search_prompt_path,
    conversation_history,
    search_history,
    assistant,
):
    """
    Generate an assistant response based on the conversation and search history.

        This function reads a base prompt from a file and customizes it with the provided conversation and search history. It then requests a response from a chat completions API. If the generated response indicates that a search is needed (by containing specific tags), it extracts a search query, generates search results using a separate prompt, and finally produces a second-pass response that integrates the new search results.

        Parameters:
            chat (object): An object representing the current chat context. It should provide a method get_conversation_history() to retrieve the updated conversation history.
            base_prompt_path (str): File path to the base prompt template.
            search_prompt_path (str): File path to the search prompt template.
            conversation_history (Any): The history of the conversation to be incorporated into the prompt.
            search_history (Any): The history of previous search interactions to be incorporated into the prompt.
            assistant (Any): A seed or identifier used to influence the response generation.

        Returns:
            tuple: A tuple containing:
                - assistant_message_content (str): The final assistant response text.
                - search_results (str or None): The generated search results if a search was triggered, otherwise None.

        Notes:
            - Logs of the prompts and responses are written to files under the "logs" directory.
            - If an error occurs during any request, the function prints an error message and returns (None, None).
    """
    # 1) Read the base prompt
    with open(base_prompt_path, "r") as file:
        prompt = file.read()

    # 2) Build the prompt with conversation history and search history
    updated_prompt = prompt.replace("{conv}", str(conversation_history)).replace(
        "{search}", str(search_history)
    )

    with open("logs/assistant_prompt.log", "a+") as file:
        file.write(f"{updated_prompt}\n")
        file.write("-" * 50 + "\n" * 5)

    # 3) Attempt first generation
    try:
        client = Together(api_key='a923ff51a697d6812f846b69aea86466853cceaf95c8ab2dfc84de07cce6ffe1')
        completion = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-R1",  # Updated model
            messages=[
                {
                    "role": "user",
                    "content": updated_prompt,
                }
            ],
            seed=assistant,
            temperature=0.6 ,
        )
    except Exception as e:
        print(f"[ERROR] Failed to generate a response: {e}")
        return None, None

    think_tag_end = completion.choices[0].message.content
    # Find the position of the closing think tag
    assistant_message_content = think_tag_end.find('</think>')
    
    if assistant_message_content != -1:
        # Extract only the content after </think>
        assistant_message_content = think_tag_end[assistant_message_content + len('</think>'):].strip()
    else:
        # If no </think> tag is found, return the full content
        assistant_message_content = think_tag_end.strip()

    # 4) If the content suggests a search is needed, parse out the search query and do a second pass
    search_results = None
    if (
        "<function>" in assistant_message_content
    ):
        print("[DEBUG] Search needed")
        # Split at <function>
        splitted = re.split(r"<function>", assistant_message_content)
        if len(splitted) > 1:
            assistant_message_content = splitted[0]
            search_query = splitted[1]

            with open(search_prompt_path, "r") as file:
                search_prompt = file.read()
            search_prompt = search_prompt.replace("{search_query}", search_query)

            with open("logs/search_prompt.log", "a") as file:
                file.write(f"{search_prompt}\n")
                file.write("-" * 50 + "\n" * 5)

            # Generate the search results
            try:
                search = client.chat.completions.create(
                    model="o3-mini-2025-01-31",
                    messages=[{"role": "user", "content": search_prompt}],
                    seed=assistant,
                )
                search_results = search.choices[0].message.content
            except Exception as e:
                print(f"[ERROR] Failed to generate search results: {e}")

            # After obtaining search results, we re-generate a final assistant message
            print("[DEBUG] Prompt updated with search results.")
            # Use updated conversation history from chat plus these search results.
            second_prompt = prompt.replace(
                "{conv}", str(chat.get_conversation_history())
            ).replace("{search}", str(search_results))

            with open("logs/assistant_prompt_after_search.log", "a") as file:
                file.write(f"{second_prompt}\n")
                file.write("-" * 50 + "\n" * 5)

            try:
                completion2 = client.chat.completions.create(
                    model="o3-mini-2025-01-31",
                    # model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": second_prompt,
                        }
                    ],
                    seed=assistant,
                    # temperature=0.4 if assistant == 1 else 0.7,
                )
                assistant_message_content = completion2.choices[0].message.content
                print(
                    f"[DEBUG] Assistant message after search: {assistant_message_content}"
                )
            except Exception as e:
                print(f"[ERROR] Failed to generate second pass response: {e}")
        else:
            print("[DEBUG] <function> tag found but no query to search.")
    else:
        print("[DEBUG] Search not needed")

    return assistant_message_content, search_results


def store_assistant_message(message_id, content, search_output=None, output_number=1):
    """
    Stores an assistant message in the database.
    This function creates a new instance of AssistantMessage using the provided parameters,
    adds it to the database session, commits the transaction, and returns the stored message.
    Args:
        message_id (int or str): A unique identifier for the message.
        content (str): The textual content of the assistant's message.
        search_output (optional): Additional search output associated with the message. Defaults to None.
        output_number (int, optional): The sequence number or identifier of the output. Defaults to 1.
    Returns:
        AssistantMessage: The assistant message object that was stored in the database.
    """

    assistant_msg = AssistantMessage(
        message_id=message_id,
        content=content,
        search_output=search_output,
        output_number=output_number,
    )
    db.session.add(assistant_msg)
    db.session.commit()
    return assistant_msg


def generate_and_store_assistant_message(
    chat, message, base_prompt_path, search_prompt_path
):
    """
    Generates an assistant response based on the current conversation and search history,
    and stores the generated message along with any associated search results.
    Parameters:
        chat: An object representing the active chat session. It must support methods:
              - get_conversation_history(): Returns the list of previous chat messages.
              - get_search_history(): Returns the list of previous search queries/results.
        message: An object representing the current message context with an attribute 'id'
                 that uniquely identifies the message.
        base_prompt_path: A string representing the file path to the base prompt template used
                          for generating the assistant's response.
        search_prompt_path: A string representing the file path to the prompt template used for
                            generating search-related outputs.
    Process:
        1. Retrieves conversation and search history from the provided chat session.
        2. Calls the generate_assistant_response function to obtain the assistant's message content
           and any search results. A fallback error message is used if no valid response is generated.
        3. Stores the assistant message output by calling store_assistant_message, including any
           search output if available.
    Returns:
        None
    """

    conversation_history = chat.get_conversation_history()
    search_history = chat.get_search_history()

    assistant_message_content, search_results = generate_assistant_response(
        chat,
        base_prompt_path,
        search_prompt_path,
        conversation_history,
        search_history,
        assistant=1,
    )

    if assistant_message_content is None:
        # Return some fallback or error message if generation fails
        print("[ERROR] No assistant message content generated.")
        assistant_message_content = "[Error: assistant failed to respond.]"

    # Store the assistant message (primary output)
    store_assistant_message(
        message_id=message.id,
        content=assistant_message_content,
        search_output=search_results if search_results else None,
        output_number=1,
    )


def maybe_generate_second_assistant_message(
    chat, message, base_prompt_path, search_prompt_path
):
    """
    Generate a response for the second assistant and store the message.
    This function retrieves the conversation and search history from the provided chat object,
    generates a response using the given prompt paths via the generate_assistant_response function,
    and then stores the assistant's message along with any search results. If the response for the
    second assistant is not generated, an error message is assigned instead.
    Args:
        chat: An object representing the chat, which provides methods to get conversation and search history.
        message: The message object associated with this interaction. It must contain an attribute `id`
                 used for storing the assistant's output.
        base_prompt_path (str): File path to the base prompt used for generating the assistant's response.
        search_prompt_path (str): File path to the search prompt used for generating the assistant's response.
    Notes:
        - The generate_assistant_response function is called with assistant set to 2 to designate the
          secondary assistant.
        - If no valid response is generated (i.e., assistant_message_content is None), an error message
          is assigned.
        - The assistant's message is stored using store_assistant_message with output_number set to 2,
          and search results are included if available.
    """
    conversation_history = chat.get_conversation_history()
    search_history = chat.get_search_history()

    assistant_message_content, search_results = generate_assistant_response(
        chat,
        base_prompt_path,
        search_prompt_path,
        conversation_history,
        search_history,
        assistant=2,
    )

    if assistant_message_content is None:
        assistant_message_content = "[Error]: second assistant failed to respond."

    # Store the assistant message (secondary output)
    store_assistant_message(
        message_id=message.id,
        content=assistant_message_content,
        search_output=search_results if search_results else None,
        output_number=2,
    )
