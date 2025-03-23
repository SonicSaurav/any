from .. import chat_blueprint
from flask import jsonify, request, session, redirect, url_for, render_template
from models import db
from models.models import User, Chat, Message
from .helpers import (
    retrieve_or_create_chat,
    create_user_message,
    generate_and_store_assistant_message,
    maybe_generate_second_assistant_message,
)


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
    Handles chat interactions by performing a series of operations:
    1. Authenticates the user by verifying that 'username' is present in the session.
    2. Retrieves the authenticated user from the database.
    3. Retrieves an existing chat or creates a new one based on the provided 'chat_id' in the JSON payload.
    4. Validates the presence of user input in the JSON payload.
    5. Creates a new message entry for the user.
    6. Generates and stores the first assistant response based on a predefined primary prompt and search prompt.
    7. Optionally generates a second assistant response if the chat configuration allows it.
    8. Dumps and augments the message data with the chat id, then triggers asynchronous updates for missing critic scores.
    Returns:
        A Flask JSON response containing:
            - The dumped message data along with the associated chat id upon success, with an HTTP status code 200.
            - An error message with an appropriate HTTP status code in case of issues (401 for unauthorized, 404 if user/chat not found or input missing, 403 for forbidden actions).
    Note:
        This function relies on several helper functions (e.g., retrieve_or_create_chat, create_user_message,
        generate_and_store_assistant_message, maybe_generate_second_assistant_message) and expects request data to be in JSON format.
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

    # 5) Generate the first assistant response
    generate_and_store_assistant_message(
        chat,
        message,
        base_prompt_path="./prompts/actor.md",
        search_prompt_path="./prompts/search_simulator.md",
    )

    # 6) If second assistant is enabled, generate a second assistant response
    if chat.allow_second_assistant:
        maybe_generate_second_assistant_message(
            chat,
            message,
            base_prompt_path="./prompts/actor.md",
            search_prompt_path="./prompts/search_simulator.md",
        )

    # 7) Dump message data
    data = message.dump()
    data["chat_id"] = chat.id

    # 8) Update chat critic scores (asynchronous triggers)
    chat.update_missing_critic_scores()

    print(data)
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
