from . import db

import threading
from flask import current_app
from simulation.critic import get_score
import uuid


def generate_short_uuid():
    return uuid.uuid4().int.to_bytes(16, "big").hex()[:16]


def run_update_critic_score(app_context, assistant_msg_id, conversation_history):
    """
    Runs in a background thread: computes the critic score and updates the AssistantMessage.
    """
    with app_context:
        score = get_score(conversation_history)
        assistant_msg = AssistantMessage.query.get(assistant_msg_id)
        if assistant_msg:
            assistant_msg.set_critic_score(score)


class User(db.Model):
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

    def get_messages(self):
        return sorted(self.messages, key=lambda x: x.timestamp)

    def get_critic_scores(self):
        critic_scores = []
        for msg in self.get_messages():
            if msg.assistant_message:
                critic_scores.append(msg.assistant_message.get_critic_score())
        return critic_scores

    def get_conversation_history(self):
        """
        Returns the conversation history without modifying any critic scores.
        """
        conversation_history = []
        for msg in self.get_messages():
            if msg.user_message:
                conversation_history.append(msg.user_message.jsonify())
            if msg.assistant_message:
                conversation_history.append(msg.assistant_message.jsonify())
        return conversation_history

    def update_missing_critic_scores(self):
        """
        Finds assistant messages without a critic score and updates them asynchronously.
        """
        missing_scores = (
            db.session.query(AssistantMessage)
            .filter(
                AssistantMessage.critic_score.is_(None),
                AssistantMessage.is_updating.is_(False),
            )
            .join(Message)
            .filter(Message.chat_id == self.id)
            .all()
        )

        if not missing_scores:
            return

        app_ctx = current_app._get_current_object().app_context()
        conversation_history = self.get_conversation_history()

        for msg in missing_scores:
            msg.mark_as_updating()
            history_copy = conversation_history.copy()
            threading.Thread(
                target=run_update_critic_score,
                args=(app_ctx, msg.id, history_copy),
            ).start()

    def jsonify(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": [msg.jsonify() for msg in self.messages],
        }

    def dump(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "messages": [msg.dump() for msg in self.get_messages()],
        }

    def get_search_history(self):
        search_history = []
        for msg in self.get_messages()[-10:]:
            if msg.assistant_message and msg.assistant_message.search_output:
                search_history.append(msg.assistant_message.search_output)
        return search_history

    def __repr__(self):
        return f"<Chat {self.id}>"


class Message(db.Model):
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
        "AssistantMessage", back_populates="message", uselist=False
    )
    user_message = db.relationship(
        "UserMessage", back_populates="message", uselist=False
    )

    def get_assistant_message(self):
        return self.assistant_message

    def get_user_message(self):
        return self.user_message

    @staticmethod
    def process_timestamp(timestamp):
        return timestamp.strftime("%Y-%m-%d %H:%M:%S")

    def get_critic_score(self):
        if self.assistant_message:
            return self.assistant_message.get_critic_score()
        return None

    def dump(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "timestamp": self.process_timestamp(self.timestamp),
            "simulation_id": self.simulation_id,
            "assistant_message": (
                self.assistant_message.dump() if self.assistant_message else None
            ),
            "user_message": (self.user_message.dump() if self.user_message else None),
        }

    def jsonify(self):
        return {
            "id": self.id,
            "chat_id": self.chat_id,
            "assistant_message": (
                self.assistant_message.jsonify() if self.assistant_message else None
            ),
            "user_message": (
                self.user_message.jsonify() if self.user_message else None
            ),
        }

    def __repr__(self):
        return f"<Message {self.id}>"


class AssistantMessage(db.Model):
    __tablename__ = "assistant_messages"
    id = db.Column(
        db.String(16),
        primary_key=True,
        default=generate_short_uuid,
        unique=True,
        nullable=False,
    )
    message_id = db.Column(db.String(16), db.ForeignKey("messages.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    search_output = db.Column(db.Text, nullable=True)
    critic_score = db.Column(db.Float, nullable=True)
    is_updating = db.Column(db.Boolean, default=False, nullable=False)

    message = db.relationship(
        "Message", back_populates="assistant_message", uselist=False
    )

    def __repr__(self):
        return f"<AssistantMessage {self.id} - Critic Score: {self.critic_score}>"

    def set_critic_score(self, score):
        self.critic_score = score
        self.is_updating = False
        db.session.commit()

    def get_critic_score(self):
        return {
            "id": self.id,
            "critic_score": self.critic_score,
        }

    def mark_as_updating(self):
        self.is_updating = True
        db.session.commit()

    def set_search_output(self, search_output):
        self.search_output = search_output
        db.session.commit()

    def jsonify(self):
        data = {
            "role": "assistant",
            "content": self.content,
        }
        if self.critic_score is not None:
            data["critic_score"] = self.critic_score
        return data

    def dump(self):
        data = {
            "id": self.id,
            "message_id": self.message_id,
            "role": "assistant",
            "content": self.content,
            "search_output": self.search_output,
            "critic_score": self.critic_score,
            "is_updating": self.is_updating,
        }
        return data


class UserMessage(db.Model):
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
        return {
            "role": "user",
            "content": self.content,
        }

    def dump(self):
        return {
            "id": self.id,
            "message_id": self.message_id,
            "content": self.content,
            "role": "user",
        }
