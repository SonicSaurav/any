from .models import User, AssistantMessage, UserMessage, Simulation, Chat, Message
from . import db
from flask import Flask


def init_db(app: Flask):

    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite3"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    with app.app_context():
        db.create_all()
        if not User.query.all():
            # create 3 default users
            try:
                user1 = User(name="saurav", password="livup.ai")
                user2 = User(name="shivang", password="livup.ai")
                user3 = User(name="admin", password="strongpassword")
                user4 = User(name="subodh", password="livup.ai")
                user20 = User(name="user20", password="itagenev")
                user21 = User(name="user21", password="ulaudati")
                user22 = User(name="user22", password="nflought")
                user23 = User(name="user23", password="sphorine")
                db.session.add_all(
                    [user1, user2, user3, user4, user20, user21, user22, user23]
                )
                db.session.commit()
                print("[MODEL][INFO] Default users created.")
            except Exception as e:
                print(f"[MODEL][Error] creating default users: {e}")
        print("[MODEL][INFO] Database initialized.")
