from .. import chat_blueprint
from flask import jsonify, request, session, redirect, url_for, render_template , current_app
from models import db
from models.models import User, Chat, Message
from .helpers import (
    retrieve_or_create_chat,
    create_user_message,
    generate_and_store_assistant_message,
    maybe_generate_second_assistant_message,
)
from models.models import User, Chat, Message, AssistantMessage, UserMessage, db
import threading

# ==================================================================================================#
#                                          ⛔NOTE⛔                                                 #
# This blueprint is registered with /assistant prefix in app.py.                                    #
# So every route in this blueprint will be prefixed with /assistant.                                #
# "/" route would be "/assistant/" in the browser.                                                  #
# "/chat" route would be "/assistant/chat" in the browser.                                          #
# ==================================================================================================#


@chat_blueprint.route("/")
def assistant():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("assistant.html")


@chat_blueprint.route("/chat/start", methods=["POST"])
def start_chat():
    """
    Starts a new chat session or reuses the last empty chat for an authenticated user.
    This function checks if a user is authenticated by verifying the presence of a "username"
    in the session. If not present, it returns a JSON response with an "Unauthorized" error
    and a 401 status code. It then queries the database for the user by username. If the user
    is not found, it returns a JSON response indicating the error with a 404 status code.
    The function next attempts to retrieve the user's most recent chat session. If the last chat
    exists and is empty (determined by the is_empty() method), it reuses that chat. Otherwise, it
    creates a new chat record, adds it to the database session, and commits the transaction.
    Returns:
        A Flask JSON response with a success flag and the chat_id in a JSON payload if the operation
        is successful (status code 200), or an error message with the appropriate error code (401 or 404)
        if the user is unauthorized or not found.
    """

    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    # if last chat is empty, return the last chat, else create a new chat
    last_chat = (
        Chat.query.filter_by(user_id=user.id).order_by(Chat.timestamp.desc()).first()
    )
    if last_chat and last_chat.is_empty():
        chat = last_chat
    else:
        chat = Chat(user_id=user.id)
        db.session.add(chat)
        db.session.commit()

    # clear logs/critic_prompt.md file
    with open("logs/critic_prompt.md", "w") as file:
        file.write("")
        print("[DEBUG] Cleared critic_prompt.md file")

    return jsonify({"success": True, "chat_id": chat.id}), 200


@chat_blueprint.route("/sessions")
def get_sessions():
    """
    Retrieve and render chat sessions for the authenticated user.
    This function performs the following operations:
    1. Verifies that a user is logged in by checking for "username" in the session.
        - If "username" is missing, returns a JSON error response with status code 401 (Unauthorized).
    2. Attempts to retrieve the User object from the database using the username from the session.
        - If the user is not found, returns a JSON error response with status code 404 (User not found).
    3. Retrieves all chat sessions from the database (ignoring session ownership) for demonstration purposes.
    4. Reverses the order of the chat sessions.
    5. Renders and returns the "chat-sessions.html" template, injecting the list of chat sessions.
    Returns:
         Flask response:
         - A JSON response with a 401 or 404 error if authentication fails or user is not found.
         - A rendered template ("chat-sessions.html") with the chat sessions data upon success.
    """

    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # For demonstration, we are ignoring ownership of sessions.
    # If you'd like to only show the user's sessions, do:
    # chat_sessions = user.get_chats()

    chat_sessions = Chat.query.all()
    chat_sessions = chat_sessions[::-1]  # Reverse the order
    return render_template("chat-sessions.html", sessions=chat_sessions)


@chat_blueprint.route("/chat/<string:chat_id>")
def chat_session(chat_id):
    """
    Handle a chat session by retrieving the chat data for the given chat_id.
    This function first prints the debug information for the provided chat_id. It then checks if the user is authenticated by
    verifying the presence of "username" in the session. If the user is not authenticated, it logs a debug message and redirects
    the user to the login page.
    The function then attempts to retrieve the user object from the database using the username stored in the session. If the user
    is not found, it returns a JSON error response with a 404 status code. Similarly, it retrieves the chat object based on the
    provided chat_id. If the chat is not found, it returns a JSON error response with a 404 status.
    If both the user and chat are successfully retrieved, it returns the chat data in JSON format with a 200 status code.
    Args:
        chat_id (int): The unique identifier for the chat session to be retrieved.
    Returns:
        Response: A Flask response object that may either be a redirect to the login page, a JSON error message with a 404 status,
                  or a JSON representation of the chat data with a 200 status code.
    """

    print(f"[DEBUG] Chat ID: {chat_id}")
    if "username" not in session:
        print("[DEBUG] Redirecting to login")
        return redirect(url_for("login"))
    user = User.query.filter_by(name=session["username"]).first()
    print(f"[DEBUG] User: {user}")
    if not user:
        return jsonify({"error": "User not found"}), 404

    chat = db.session.get(Chat, chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(chat.dump()), 200


@chat_blueprint.route("/chat/score/<string:chat_id>", methods=["POST"])
def score_chat(chat_id):
    """
    Scores a chat by retrieving its critic scores.
    This function checks whether a user session exists and verifies the user by
    querying the database using the session username. It then retrieves a chat record
    by the provided chat_id. If the chat exists, it retrieves the chat's critic scores,
    updates any missing scores, and returns the scores as a JSON response with HTTP status 200.
    Error Handling:
        - Returns a JSON error with status 401 if the user is not authenticated (i.e., "username" not in session).
        - Returns a JSON error with status 404 if the user is not found.
        - Returns a JSON error with status 404 if the chat is not found.
    Parameters:
        chat_id: The unique identifier for the chat whose scores are to be retrieved.
    Returns:
        A Flask JSON response containing:
            - "scores": The critic scores associated with the chat (on success),
            or
            - "error": An error message indicating the failure reason.
    """

    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        print("[DEBUG] User not found")
        return jsonify({"error": "User not found"}), 404

    chat = db.session.get(Chat, chat_id)
    if not chat:
        print("[DEBUG] Chat not found")
        return jsonify({"error": "Chat not found"}), 404
    print(f"[DEBUG] Chat ID: {chat_id}")
    scores = chat.get_critic_scores()
    print(f"[DEBUG] Scores: {scores}")
    # Update the scores before exiting
    chat.update_missing_critic_scores()
    return jsonify({"scores": scores}), 200


@chat_blueprint.route(
    "/chat/enable_second_assistant/<string:chat_id>", methods=["POST"]
)
def enable_second_assistant(chat_id):
    """Enables the second assistant for a given chat.
    This function allows the owner of a chat to enable a second assistant for that chat.
    It first checks if the user is logged in and if the user exists.
    Then it checks if the chat exists and if the user is the owner of the chat.
    If all checks pass, it enables the second assistant for the chat and commits the changes to the database.
    Args:
        chat_id (int): The ID of the chat to enable the second assistant for.
    Returns:
        tuple: A tuple containing a JSON response and an HTTP status code.
            The JSON response contains either:
                - An error message if any of the checks fail.
                - A success message with the updated 'allow_second_assistant' status if the operation is successful.
            The HTTP status code indicates the success or failure of the operation.
                - 200: Success
                - 401: Unauthorized (user not logged in or invalid session)
                - 403: Forbidden (user is not the owner of the chat)
                - 404: Not Found (user or chat not found)
    """

    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    if chat.user_id != user.id:
        return jsonify({"error": "Unauthorized"}), 403

    chat.allow_second_assistant = True
    db.session.commit()
    return jsonify({"success": True, "allow_second_assistant": True}), 200


@chat_blueprint.route(
    "/chat/disable_second_assistant/<string:chat_id>", methods=["POST"]
)
def disable_second_assistant(chat_id):
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404
    if chat.user_id != user.id:
        return jsonify({"error": "Unauthorized"}), 403

    chat.allow_second_assistant = False
    db.session.commit()
    return jsonify({"success": True, "allow_second_assistant": False}), 200


@chat_blueprint.route("/chat", methods=["POST"])
def chat():
    """
    Handles chat interactions with immediate response and background processing.
    """
    print("[DEBUG] Chat route accessed")
    # 1) User authentication
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    # 2) Retrieve or create a chat
    chat_id = request.json.get("chat_id")
    chat, error = retrieve_or_create_chat(user, chat_id)
    if not chat:
        return jsonify({"error": error}), 404 if error == "Chat not found" else 403

    # 3) Get user_input
    user_input = request.json.get("user_input")
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    # 4) Create a user message
    message = create_user_message(chat, user_input)
    
    # 5) Return IMMEDIATELY with the messageId that will be used for polling
    data = {
        "chat_id": chat.id,
        "message_id": message.id,
        "user_message": message.user_message.dump() if message.user_message else None,
        "status": "processing_started"
    }
    
    # 6) Start background processing thread with application context
    app_context = current_app._get_current_object().app_context()
    thread = threading.Thread(
        target=process_message_async,
        args=(
            app_context,
            chat.id,
            message.id,
            "./prompts/actor.md",
            "./prompts/search_simulator.md",
        )
    )
    thread.daemon = True
    thread.start()

    return jsonify(data), 200

@chat_blueprint.route(
    "/chat/<string:chat_id>/message/<string:message_id>/prefer", methods=["POST"]
)
def prefer_message(chat_id, message_id):
    """
    Route handler to update the preferred assistant output for a given message within a chat.

    This endpoint processes POST requests to set the preferred assistant (either 1 or 2) for a message.
    It performs several checks:
        - Validates that a 'username' exists in the session.
        - Confirms the existence of the user and the chat.
        - Ensures the requesting user is authorized to modify the chat.
        - Retrieves the message and verifies it belongs to the specified chat.
        - Validates the 'preferred_output' from the JSON payload, ensuring it is either 1 or 2.
        - Updates the message's preferred assistant field and commits the change to the database.

    Parameters:
            chat_id (str): The unique identifier for the chat, extracted from the URL.
            message_id (str): The unique identifier for the message, extracted from the URL.

    JSON Payload (expected in the request body):
            preferred_output (int): The preferred assistant output number; must be either 1 or 2.

    Returns:
            A JSON response:
                - On success, returns a JSON with 'success', 'chat_id', 'message_id', and 'preferred_assistant' fields, accompanied by an HTTP 200 status.
                - On error, returns a JSON with an 'error' message and an appropriate HTTP error status code (e.g., 401, 403, 404, or 400).
    """
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    user = User.query.filter_by(name=session["username"]).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    chat = Chat.query.get(chat_id)
    if not chat:
        return jsonify({"error": "Chat not found"}), 404

    if chat.user_id != user.id:
        return jsonify({"error": "Unauthorized"}), 403

    # Retrieve the message
    message = Message.query.get(message_id)
    if not message:
        return jsonify({"error": "Message not found"}), 404

    # Ensure the message belongs to the specified chat
    if message.chat_id != chat_id:
        return jsonify({"error": "Message does not belong to this chat"}), 400

    # Get the preferred output number from JSON
    preferred_output = request.json.get("preferred_output")
    if preferred_output not in [1, 2]:
        return jsonify({"error": "Invalid preferred output. Must be 1 or 2."}), 400

    # Update the message's preferred assistant
    message.preferred_assistant = preferred_output
    db.session.commit()

    return (
        jsonify(
            {
                "success": True,
                "chat_id": chat_id,
                "message_id": message_id,
                "preferred_assistant": preferred_output,
            }
        ),
        200,
    )

@chat_blueprint.route("/chat/message/<string:message_id>")
def get_message(message_id):
    """
    Retrieve details for a specific message.
    """
    from models.models import AssistantMessage
    
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get the message
    assistant_msg = AssistantMessage.query.filter_by(id=message_id).first()
    if not assistant_msg:
        return jsonify({"error": "Message not found"}), 404
    
    # Return the message details
    return jsonify(assistant_msg.dump()), 200

def process_message_async(app_context, chat_id, message_id, base_prompt_path, search_prompt_path):
    """
    Process a message asynchronously with Flask application context.
    
    Executes the entire processing pipeline:
    1. Named Entity Recognition (NER)
    2. Search processing if needed
    3. Assistant response generation
    4. Updates processing status at each step
    
    Args:
        app_context: Flask application context
        chat_id: ID of the chat
        message_id: ID of the message to process
        base_prompt_path: Path to the actor prompt template
        search_prompt_path: Path to the search simulator prompt
    """
    import json
    import traceback
    from together import Together
    from models.models import Chat, Message, AssistantMessage, db
    from blueprints.chat.helpers import (
        extract_ner_from_conversation,
        process_search_call,
        process_search_simulation,
        process_search_results,
        extract_thinking,
        extract_function_calls
    )
    
    with app_context:
        try:
            # Get the chat and message objects
            chat = db.session.get(Chat, chat_id)
            message = db.session.get(Message, message_id)
            
            if not chat or not message:
                print(f"Error: Chat {chat_id} or Message {message_id} not found")
                return
            
            # Create initial assistant message
            assistant_msg = AssistantMessage(
                message_id=message.id,
                content="Processing your request...",
                output_number=1,
                is_updating=True
            )
            db.session.add(assistant_msg)
            db.session.commit()
            
            # Store processing status
            def update_status(status, data=None):
                """Update the processing status and data"""
                status_data = {"status": status}
                if data:
                    status_data.update(data)
                    
                try:
                    assistant_msg.search_output = json.dumps(status_data)
                    db.session.commit()
                except Exception as e:
                    print(f"Error updating status: {e}")
            
            # Initialize data storage
            processing_data = {}
            
            # Step 1: Named Entity Recognition
            update_status("ner_started")
            conversation_history = chat.get_conversation_history()
            search_history = chat.get_search_history()
            
            try:
                preferences = extract_ner_from_conversation(conversation_history)
                processing_data["ner_results"] = preferences
                update_status("ner_completed", processing_data)
            except Exception as e:
                print(f"Error in NER extraction: {e}")
                processing_data["ner_error"] = str(e)
                update_status("ner_error", processing_data)
            
            # Step 2: Search Processing
            search_record = None
            if processing_data.get("ner_results"):
                update_status("search_started", processing_data)
                
                try:
                    search_call_result = process_search_call(processing_data["ner_results"])
                    if search_call_result:
                        processing_data["search_call"] = search_call_result
                        update_status("search_call_completed", processing_data)
                        
                        search_record = process_search_simulation(search_call_result, conversation_history)
                        if search_record:
                            show, search_text = process_search_results(search_record)
                            search_record["show_results_to_actor"] = show
                            processing_data["search_results"] = search_record
                            
                        update_status("search_completed", processing_data)
                except Exception as e:
                    print(f"Error in search processing: {e}")
                    processing_data["search_error"] = str(e)
                    update_status("search_error", processing_data)
            
            # Step 3: Generate Assistant Response
            update_status("generating_response", processing_data)
            
            try:
                # Read the prompt template
                with open(base_prompt_path, "r") as file:
                    prompt = file.read()
                
                # Format the prompt with conversation history and search results
                num_matches = search_record.get("num_matches", "") if search_record else ""
                search_results_text = ""
                
                if search_record and search_record.get("show_results_to_actor"):
                    search_results_text = search_record.get("results", "")
                
                updated_prompt = (
                    prompt
                    .replace("{conv}", json.dumps(conversation_history, ensure_ascii=False, indent=2))
                    .replace("{search}", search_results_text)
                    .replace("{num_matches}", str(num_matches))
                )
                
                # Log the assistant prompt
                with open("logs/assistant_prompt.log", "a+") as file:
                    file.write(f"{updated_prompt}\n")
                    file.write("-" * 50 + "\n" * 5)
                
                # Generate the assistant response
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
                        seed=1,
                        temperature=0.6,
                    )
                    
                    response_content = completion.choices[0].message.content
                    
                    # Extract thinking and clean the response
                    thinking, response_after_thinking = extract_thinking(response_content)
                    clean_response, _ = extract_function_calls(response_after_thinking)
                    
                    # Use the clean response if available, otherwise use the full response
                    final_response = clean_response if clean_response.strip() else response_after_thinking
                    
                    # Add thinking to processing data
                    if thinking:
                        processing_data["thinking"] = thinking
                    
                except Exception as e:
                    print(f"Error generating assistant response: {e}")
                    processing_data["response_error"] = str(e)
                    final_response = "I'm sorry, I encountered an error while processing your request."
                
                # Save the final response
                assistant_msg.content = final_response
                processing_data["status"] = "response_generated"
                assistant_msg.search_output = json.dumps(processing_data)
                assistant_msg.is_updating = False
                db.session.commit()
                
                # Trigger asynchronous critic evaluation
                chat.update_missing_critic_scores()
                
            except Exception as e:
                print(f"Error in assistant response generation: {e}")
                processing_data["response_error"] = str(e)
                update_status("response_error", processing_data)
                
                # Set a fallback response
                assistant_msg.content = "I'm sorry, I encountered an error while processing your request."
                assistant_msg.is_updating = False
                db.session.commit()
            
        except Exception as e:
            # Global error handler
            error_msg = f"Error in process_message_async: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            
            with open("logs/process_error.log", "a") as file:
                file.write(f"{error_msg}\n")
                file.write("-" * 50 + "\n" * 5)
            
            # Try to save the error state
            try:
                # Fetch the assistant message again (it might have been detached from the session)
                assistant_msg = AssistantMessage.query.filter_by(message_id=message_id, output_number=1).first()
                if assistant_msg:
                    assistant_msg.content = "I'm sorry, an error occurred while processing your request."
                    assistant_msg.search_output = json.dumps({
                        "status": "error",
                        "error": str(e)
                    })
                    assistant_msg.is_updating = False
                    db.session.commit()
            except Exception as nested_e:
                print(f"Error saving error state: {nested_e}")

@chat_blueprint.route("/chat/status/<string:message_id>")
def message_status(message_id):
    """
    Get the current processing status of a message.
    """
    from models.models import AssistantMessage
    
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Get the message
    assistant_msg = AssistantMessage.query.filter_by(message_id=message_id).first()
    if not assistant_msg:
        return jsonify({"status": "not_found"}), 404
    
    # Get current status
    status = "completed"
    processing_data = {}
    
    if assistant_msg.is_updating:
        status = "processing"
    
    if assistant_msg.search_output:
        try:
            search_data = json.loads(assistant_msg.search_output)
            if "status" in search_data:
                status = search_data["status"]
            processing_data = search_data
        except:
            pass
    
    # Return current status and data
    return jsonify({
        "status": status,
        "message_id": assistant_msg.id,
        "content": assistant_msg.content,
        "critic_score": assistant_msg.critic_score,
        "processing_data": processing_data
    }), 200