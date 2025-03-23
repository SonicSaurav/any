# import json
import os
from dotenv import load_dotenv
from flask import (
    Flask,
    render_template,
    session,
    url_for,
    redirect,
)
from models.helpers import init_db
from blueprints.chat import chat_blueprint
from blueprints.auth import authentication_blueprint


load_dotenv()  # Load environment variables from .env file if present
app = Flask(__name__)
app.secret_key = os.getenv(
    "SECRET_KEY", "your_secret_key"
)  # Set a secret key for session handling

app.register_blueprint(
    chat_blueprint, url_prefix="/assistant"
)  # Register the chat blueprint with the URL prefix /assistant
app.register_blueprint(
    authentication_blueprint, url_prefix="/auth"
)  # Register the authentication blueprint with the URL prefix /auth


# Initialize the database
init_db(app)
print("[INFO] Database initialized")

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)  # Create directory if it doesn't exist


@app.route("/")
def index():
    if "username" not in session:
        return redirect(url_for("authentication.login"))

    return render_template("index.html")


if __name__ == "__main__":
    app.run(port=5591, host="0.0.0.0")  # Run the app on port 5591 and host
    # app.run(debug=True) # Run the app in debug mode
