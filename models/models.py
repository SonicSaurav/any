from . import db
import threading
from flask import current_app
from simulation.critic import get_score
import uuid


# ==============================================================================================#
#                                           ⛔NOTE⛔                                            #
# In this file almost every class has two methods:                                              #
# 1. dump() - This method returns a dictionary represen tation of the object.                   #
# 2. jsonify() - This method returns only what is necessary for at some particular time         #
# ==============================================================================================#


def generate_short_uuid():
    """
    Generate a shortened hexadecimal UUID.
    This function creates a new UUID using uuid4, converts its integer value to a 16-byte big-endian representation,
    and then encodes it into a hexadecimal string. The function returns the first 16 characters of this hexadecimal string,
    providing a shortened version of the standard UUID.
    Returns:
        str: A 16-character hexadecimal string.
    """

    return uuid.uuid4().int.to_bytes(16, "big").hex()[:16]


def run_update_critic_score(
    app, assistant_msg_id, conversation_history, search_history
):
    """
    Update the critic score for an assistant message.
    This function computes a new critic score using the provided conversation
    and search history, retrieves the specified assistant message from the database,
    and updates its critic score. The function operates within the Flask
    application context to ensure proper access to the application’s resources.
    Parameters:
        app (Flask): The Flask application instance containing the application context
                     and the database session.
        assistant_msg_id (int): Unique identifier for the AssistantMessage to be updated.
        conversation_history (Any): Data representing the conversation history, used in scoring.
        search_history (Any): Data representing the search history, also used in scoring.
    Raises:
        Exception: If the database commit fails, the exception is caught, the transaction is
                   rolled back, and an error message is printed.
    Returns:
        None: This function performs an in-place update of the AssistantMessage record.
    """

    print(f"[MODEL] Updating critic score for AssistantMessage {assistant_msg_id}")
    with app.app_context():
        score = get_score(conversation_history, search_history)
        assistant_msg = db.session.get(AssistantMessage, assistant_msg_id)
        if assistant_msg:
            assistant_msg.critic_score = score
            assistant_msg.is_updating = False
            try:
                db.session.commit()  # Commit safely
            except Exception as e:
                db.session.rollback()
                print(f"[MODEL][ERROR] Failed to update critic score: {e}")


class User(db.Model):
    """
    User model representing the application users.
    Attributes:
        id (str): A unique identifier for the user. It is a short UUID generated automatically.
        name (str): The name of the user. Must not be null and is limited to 100 characters.
        password (str): The user's password (typically stored in a hashed format). Must not be null and supports up to 128 characters.
        chats (list): A list of Chat objects associated with the user.
        simulations (list): A list of Simulation objects associated with the user.
    Methods:
        get_simulations():
            Returns the list of Simulation objects related to the user.
        get_chats():
            Returns the list of Chat objects related to the user.
        __repr__():
            Returns a string representation of the User instance, primarily for debugging purposes.
    """

    __tablename__ = "users"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    name = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(128), nullable=False)

    chats = db.relationship("Chat", backref="user", lazy=True)
    simulations = db.relationship("Simulation", backref="user", lazy=True)

    def get_simulations(self):
        return self.simulations

    def get_chats(self):
        return self.chats

    def __repr__(self):
        return f"<User {self.name}>"


class Simulation(db.Model):
    """
    Represents a simulation record in the database.
    Attributes:
        id (str): A unique identifier for the simulation. It is automatically generated using a short UUID.
        name (str): The name of the simulation.
        user_id (str): The identifier for the user associated with the simulation.
        messages (list[Message]): A list of Message objects related to the simulation.
    Methods:
        get_messages():
            Returns all Message objects associated with this simulation.
        __repr__():
            Returns a string representation of the simulation instance.
    """

    __tablename__ = "simulations"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.String(16), db.ForeignKey("users.id"), nullable=False)

    messages = db.relationship("Message", backref="simulation", lazy=True)

    def get_messages(self):
        return self.messages

    def __repr__(self):
        return f"<Simulation {self.name}>"


class Chat(db.Model):
    """
    Chat model representing a conversation session.

    Attributes:
        id (str): Unique identifier for the chat, generated using a short UUID.
        user_id (str): Identifier for the user associated with this chat (foreign key to users.id).
        messages (List[Message]): Relationship of Message objects associated with this chat.
        allow_second_assistant (bool): Flag indicating if the chat permits a second assistant output.
        timestamp (datetime): Timestamp indicating when the chat was created.

    Methods:
        get_messages():
            Returns the messages associated with the chat sorted by their timestamp.

        get_critic_scores():
            Iterates through the chat's messages, collecting and returning all critic scores.

        get_conversation_history():
            Constructs and returns a list representing the conversation history.
            Includes user messages and their corresponding preferred assistant messages.

        update_missing_critic_scores():
            Identifies assistant messages lacking a critic score and not already in an updating state.
            Initiates an asynchronous update for each missing critic score, using the current conversation
            history and search history for context.

        jsonify():
            Serializes the chat object into a JSON-friendly dictionary format,
            including the chat's id, user_id, second assistant flag, and serialized messages.

        dump():
            Provides a detailed dictionary representation of the chat,
            including messages ordered by their timestamp.

        is_empty():
            Checks whether the chat contains any messages.

        get_search_history():
            Retrieves up to the last 10 messages that have a corresponding search output in their preferred assistant message,
            returning a dictionary mapping message IDs to their search outputs.

        __repr__():
            Returns a string representation of the chat object.


    """

    __tablename__ = "chats"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    user_id = db.Column(db.String(16), db.ForeignKey("users.id"), nullable=False)
    messages = db.relationship("Message", backref="chat", lazy=True)

    # New flag: if True, messages in this chat are allowed to have a second assistant output.
    allow_second_assistant = db.Column(db.Boolean, default=False, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.now())

    def get_messages(self):
        return sorted(self.messages, key=lambda x: x.timestamp)

    def get_critic_scores(self):
        critic_scores = []
        for msg in self.get_messages():
            critic_scores.extend(msg.get_critic_score())
        return critic_scores

    def get_conversation_history(self):
        """
        Retrieve the conversation history for the current object.
        This method gathers a list of JSON-formatted messages from the conversation history.
        It iterates through all messages returned by self.get_messages(). For each message:
          - If a user message is present, its JSON representation (using jsonify()) is added.
          - If an assistant message (determined by get_preferred_assistant_message()) is available, its JSON representation is also added.
        Returns:
            list: A list of JSON-formatted messages representing the conversation history.
        """

        conversation_history = []
        for msg in self.get_messages():
            if msg.user_message:
                conversation_history.append(msg.user_message.jsonify())
            preferred = msg.get_preferred_assistant_message()
            if preferred:
                conversation_history.append(preferred.jsonify())
        return conversation_history

    def update_missing_critic_scores(self):
        """
        Update missing critic scores for assistant messages in the current chat.
        This method queries the database for assistant messages associated with the current chat
        (i.e., messages with Message.chat_id equal to self.id) that have:
            - A missing critic_score (i.e., is None)
            - Not currently being updated (i.e., is_updating is False)
        If any such messages are found, the method retrieves the full conversation history and search history,
        marks each selected assistant message as updating, and launches a new thread to compute the critic
        score via the function run_update_critic_score. This asynchronous handling ensures that
        the potentially long-running update process does not block the main thread.
        Returns:
                None
        """

        # Query the assistant_messages table joined with Message.
        missing_scores = (
            db.session.query(AssistantMessage)
            .join(Message)
            .filter(
                Message.chat_id == self.id,
                # Message.preferred_assistant == AssistantMessage.output_number,
                AssistantMessage.critic_score.is_(None),
                AssistantMessage.is_updating.is_(False),
            )
            .all()
        )

        if not missing_scores:
            return
        conversation_history = self.get_conversation_history()

        for assistant_msg in missing_scores:
            assistant_msg.mark_as_updating()
            history_copy = conversation_history.copy()
            search_history = self.get_search_history()
            threading.Thread(
                target=run_update_critic_score,
                args=(
                    current_app._get_current_object(),
                    assistant_msg.id,
                    history_copy,
                    search_history,
                ),
            ).start()

    def jsonify(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "allow_second_assistant": self.allow_second_assistant,
            "messages": [msg.jsonify() for msg in self.messages],
        }

    def dump(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "allow_second_assistant": self.allow_second_assistant,
            "messages": [msg.dump() for msg in self.get_messages()],
        }

    def is_empty(self):
        return len(self.messages) == 0

    def get_search_history(self):
        """
        Retrieves the search history from the most recent 10 messages.
        This method iterates over the last 10 messages obtained from self.get_messages(),
        checks each for a preferred assistant message via get_preferred_assistant_message(), and if
        the preferred message exists and contains a valid search_output, it records the message
        ID alongside its search output.
        Returns:
            dict: A dictionary mapping message IDs to their corresponding search outputs.
        """

        search_history = {}
        for msg in self.get_messages()[-10:]:
            preferred = msg.get_preferred_assistant_message()
            if preferred and preferred.search_output:
                search_history[msg.id] = preferred.search_output
        return search_history

    def __repr__(self):
        return f"<Chat {self.id}>"

    def update_missing_critic_scores(self):
        """
        Finds assistant messages without a critic score and updates them asynchronously.
        Enhanced to support regeneration of low-scored responses.
        """
        missing_scores = (
            db.session.query(AssistantMessage)
            .join(Message)
            .filter(
                Message.chat_id == self.id,
                AssistantMessage.critic_score.is_(None),
                AssistantMessage.is_updating.is_(False),
            )
            .all()
        )

        if not missing_scores:
            return

        app_ctx = current_app._get_current_object().app_context()
        conversation_history = self.get_conversation_history()
        search_history = self.get_search_history()

        for msg in missing_scores:
            msg.mark_as_updating()
            history_copy = conversation_history.copy()
            
            # We need to modify the run_update_critic_score function to handle regeneration
            # We'll define this function below
            threading.Thread(
                target=run_update_critic_score_with_regen,
                args=(app_ctx, msg.id, history_copy, search_history),
            ).start()


class Message(db.Model):
    """
    Represents a message in the chat system.
    Attributes:
        id (str): A unique identifier for the message. It is generated using 'generate_short_uuid' and serves as the primary key.
        chat_id (str): Identifier for the associated chat (foreign key to "chats.id"). Can be None.
        timestamp (datetime): The time when the message was created. Defaults to the current time provided by the database.
        simulation_id (str): Identifier for the related simulation (foreign key to "simulations.id"). Can be None.
        preferred_assistant (int): Indicates which assistant output is preferred. A value of 1 represents the primary assistant message,
                                   while 2 represents the secondary assistant message.
    Relationships:
        assistant_message: The primary assistant message associated with this message (output_number == 1).
        assistant_message2: The secondary assistant message associated with this message (output_number == 2).
        user_message: The user message linked to this message.
    Methods:
        get_preferred_assistant_message():
            Returns the preferred assistant message based on 'preferred_assistant'. If 'preferred_assistant' is 1,
            returns 'assistant_message'; if 2, returns 'assistant_message2'; otherwise, returns None.
        process_timestamp(timestamp):
            A static method that formats the given timestamp into a string representation ("%Y-%m-%d %H:%M:%S").
        get_critic_score():
            Retrieves and returns the critic scores from the available assistant messages as a list.
        dump():
            Serializes the complete state of the message into a dictionary, including both assistant and user messages.
        jsonify():
            Serializes a minimal version of the message suitable for JSON responses.
        __repr__():
            Returns a string representation of the message instance.
    """

    __tablename__ = "messages"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    chat_id = db.Column(db.String(16), db.ForeignKey("chats.id"), nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=db.func.now())
    simulation_id = db.Column(
        db.String(16), db.ForeignKey("simulations.id"), nullable=True
    )

    assistant_message = db.relationship(
        "AssistantMessage",
        primaryjoin="and_(Message.id==AssistantMessage.message_id, AssistantMessage.output_number==1)",
        uselist=False,
        foreign_keys="[AssistantMessage.message_id]",
        overlaps="assistant_message2",
    )
    assistant_message2 = db.relationship(
        "AssistantMessage",
        primaryjoin="and_(Message.id==AssistantMessage.message_id, AssistantMessage.output_number==2)\n",
        uselist=False,
        foreign_keys="[AssistantMessage.message_id]",
        overlaps="assistant_message",
    )
    user_message = db.relationship(
        "UserMessage", back_populates="message", uselist=False
    )

    # Indicates which assistant output is preferred: 1 for primary, 2 for secondary.
    preferred_assistant = db.Column(db.Integer, nullable=False, default=1)

    def get_preferred_assistant_message(self):
        if self.preferred_assistant == 1:
            return self.assistant_message
        elif self.preferred_assistant == 2:
            return self.assistant_message2
        return None

    @staticmethod
    def process_timestamp(timestamp):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def get_critic_score(self):
        score = []
        # return the critic score of both assistant messages
        if self.assistant_message:
            score.append(self.assistant_message.get_critic_score())
        if self.assistant_message2:
            score.append(self.assistant_message2.get_critic_score())
        return score

    def dump(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "timestamp": self.process_timestamp(self.timestamp),
            "simulation_id": self.simulation_id,
            "preferred_assistant": self.preferred_assistant,
            "assistant_message": (
                self.assistant_message.dump() if self.assistant_message else None
            ),
            "assistant_message2": (
                self.assistant_message2.dump() if self.assistant_message2 else None
            ),
            "user_message": (self.user_message.dump() if self.user_message else None),
        }

    def jsonify(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "preferred_assistant": self.preferred_assistant,
            "assistant_message": (
                self.assistant_message.jsonify() if self.assistant_message else None
            ),
            "assistant_message2": (
                self.assistant_message2.jsonify() if self.assistant_message2 else None
            ),
            "user_message": (
                self.user_message.jsonify() if self.user_message else None
            ),
        }

    def __repr__(self):
        return f"<Message {self.id}>"


class AssistantMessage(db.Model):
    """
    Class representing an assistant's message in the chat application.
    Attributes:
        id (str): A unique identifier for the assistant message generated using generate_short_uuid.
        message_id (str): References the primary message's id from the "messages" table.
        output_number (int): Indicates the response type where 1 is the primary response and 2 (or higher) is additional content.
        content (str): The main textual content of the assistant's message.
        search_output (str, optional): Additional search-related output attached to the message.
        critic_score (float, optional): An optional evaluation score assigned to the message.
        is_updating (bool): Flag indicating if the message is currently being updated in the database.
    Methods:
        __repr__():
            Returns a string representation of the AssistantMessage instance including its id, output number, and critic score.
        set_critic_score(score):
            Sets the critic_score to the provided value, marks updating as finished by setting is_updating to False,
            and commits the change to the database.
        get_critic_score():
            Retrieves a dictionary containing the message id and its critic score.
        mark_as_updating():
            Marks the message as currently being updated by setting is_updating to True, and commits the change to the database.
        set_search_output(search_output):
            Updates the search_output field with the provided value and commits the change to the database.
        jsonify():
            Serializes the assistant message into a dictionary format with "role" set to "assistant", along with the content,
            and includes the critic_score if it is not None.
        dump():
            Serializes and returns all attributes of the AssistantMessage instance as a dictionary.
    Usage:
        The AssistantMessage class is used to encapsulate messages generated by the assistant component of the chat UI,
        managing content, evaluation metrics, update status, and database interactions.
    """

    __tablename__ = "assistant_messages"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    message_id = db.Column(db.String(16), db.ForeignKey("messages.id"), nullable=False)
    # This field distinguishes whether the row is the primary (1) or additional (2) response.
    output_number = db.Column(db.Integer, nullable=False, default=1)
    content = db.Column(db.Text, nullable=False)
    search_output = db.Column(db.Text, nullable=True)
    critic_score = db.Column(db.Float, nullable=True)
    is_updating = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self):
        return f"<AssistantMessage {self.id} (Output {self.output_number}) - Critic Score: {self.critic_score}>"

    def set_critic_score(self, score):
        self.critic_score = score
        self.is_updating = False
        db.session.commit()

    def get_critic_score(self):
        return {"id": self.id, "critic_score": self.critic_score}

    def mark_as_updating(self):
        self.is_updating = True
        db.session.commit()

    def set_search_output(self, search_output):
        self.search_output = search_output
        db.session.commit()

    def jsonify(self):
        data = {"role": "assistant", "content": self.content}
        if self.critic_score is not None:
            data["critic_score"] = self.critic_score
        return data

    def dump(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "output_number": self.output_number,
            "role": "assistant",
            "content": self.content,
            "search_output": self.search_output,
            "critic_score": self.critic_score,
            "is_updating": self.is_updating,
        }


class UserMessage(db.Model):
    """
    Represents a user message stored in the database.
    Attributes:
        id (str): A unique identifier for the user message. Generated using the custom
            "generate_short_uuid" function. This column serves as the primary key in the table.
        message_id (str): Foreign key linking to the associated Message object in the "messages" table.
        content (str): The actual text content of the user message.
        message (Message): SQLAlchemy relationship linking this user message to its corresponding
            Message object. This is a one-to-one relationship (uselist=False).
    Methods:
        __repr__():
            Returns a string representation of the user message instance for debugging purposes.
        jsonify():
            Serializes the user message into a dictionary containing:
                - "role": Set to "user" indicating the message is from the user.
                - "content": The text content of the message.
        dump():
            Returns a detailed dictionary representation of the user message with keys:
                - "id": Unique identifier of the message.
                - "message_id": Associated Message's identifier.
                - "content": The message content.
                - "role": A static string "user" indicating the role of the message.
    """

    __tablename__ = "user_messages"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    message_id = db.Column(db.String(16), db.ForeignKey("messages.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    message = db.relationship("Message", back_populates="user_message", uselist=False)

    def __repr__(self):
        return f"<UserMessage {self.id}>"

    def jsonify(self):
        return {"role": "user", "content": self.content}

    def dump(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "content": self.content,
            "role": "user",
        }

def run_update_critic_score_with_regen(app_context, assistant_msg_id, conversation_history, search_history):
    """
    Runs in a background thread: computes the critic score and updates the AssistantMessage.
    Also handles regeneration if the score is low.
    """
    import json
    import logging
    logger = logging.getLogger(__name__)
    
    from simulation.critic import get_score, regenerate_response
    
    with app_context:
        try:
            # Get the original message
            assistant_msg = db.session.get(AssistantMessage, assistant_msg_id)
            if not assistant_msg:
                logger.error(f"AssistantMessage {assistant_msg_id} not found")
                return
                
            # Get the critic score
            critique = get_score(conversation_history, search_history)
            
            # Check if we got a score or a full critique object
            if isinstance(critique, dict):
                score = critique.get("total_score")
                # Store the score in the critic_score field
                assistant_msg.critic_score = score
                
                # Store the full critique in the search_output field if it's empty
                if not assistant_msg.search_output:
                    assistant_msg.search_output = json.dumps({"critique": critique})
                elif assistant_msg.search_output:
                    # Update existing search_output to include critique
                    try:
                        search_data = json.loads(assistant_msg.search_output)
                        search_data["critique"] = critique
                        assistant_msg.search_output = json.dumps(search_data)
                    except:
                        # If we can't parse the JSON, just overwrite it
                        assistant_msg.search_output = json.dumps({"critique": critique})
                
                # Regenerate if score is low (≤ 8.5)
                if score is not None and score <= 8.5:
                    logger.info(f"Low score ({score}) for message {assistant_msg_id}, regenerating...")
                    
                    # Get the last message from conversation_history
                    last_response = assistant_msg.content
                    
                    # Regenerate the response
                    regenerated_content = regenerate_response(
                        conversation_history, last_response, critique
                    )
                    
                    if regenerated_content:
                        # Store regenerated content in search_output
                        try:
                            search_data = json.loads(assistant_msg.search_output)
                            search_data["regenerated_content"] = regenerated_content
                            assistant_msg.search_output = json.dumps(search_data)
                        except:
                            # If we can't parse the JSON, create a new one
                            assistant_msg.search_output = json.dumps({
                                "critique": critique,
                                "regenerated_content": regenerated_content
                            })
                        
                        # Get critique for regenerated content
                        regen_conversation = conversation_history.copy()
                        regen_conversation.append({"role": "assistant", "content": regenerated_content})
                        regen_critique = get_score(regen_conversation, search_history)
                        
                        if isinstance(regen_critique, dict):
                            # Store regenerated critique
                            try:
                                search_data = json.loads(assistant_msg.search_output)
                                search_data["regenerated_critique"] = regen_critique
                                assistant_msg.search_output = json.dumps(search_data)
                            except:
                                # If we can't parse the JSON, create a new one
                                assistant_msg.search_output = json.dumps({
                                    "critique": critique,
                                    "regenerated_content": regenerated_content,
                                    "regenerated_critique": regen_critique
                                })
            else:
                # Simple numeric score
                assistant_msg.critic_score = critique
            
            assistant_msg.is_updating = False
            db.session.commit()
            
        except Exception as e:
            import traceback
            error_msg = f"Error in run_update_critic_score_with_regen: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            
            with open("logs/critic_error.log", "a") as f:
                f.write(f"{error_msg}\n\n")
                
            db.session.rollback()
            
            # Mark the message as not updating
            try:
                assistant_msg = db.session.get(AssistantMessage, assistant_msg_id)
                if assistant_msg:
                    assistant_msg.is_updating = False
                    db.session.commit()
            except:
                pass