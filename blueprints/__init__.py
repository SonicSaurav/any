from flask import Blueprint

chat_blueprint = Blueprint("chat", __name__)  # Create a blueprint for chat
simulation_blueprint = Blueprint(
    "simulation", __name__
)  # Create a blueprint for simulation
authentication_blueprint = Blueprint(
    "authentication", __name__
)  # Create a blueprint for authentication
