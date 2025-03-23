from .. import authentication_blueprint
from flask import render_template, request, session, url_for, redirect
from models.models import User

# ==================================================================================================#
#                                          ⛔NOTE⛔                                                 #
# This blueprint is registered with /auth      prefix in app.py.                                    #
# So every route in this blueprint will be prefixed with /auth                                      #
# "/login" route would be "/auth/login" in the browser.                                             #
# "/logout" route would be "/auth/logout" in the browser.                                           #
# ==================================================================================================#


@authentication_blueprint.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = User.query.filter_by(name=username, password=password).first()
        if user:
            session["username"] = username
            return redirect(url_for("index"))
        else:
            return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")


@authentication_blueprint.route("/logout")
def logout():
    session.pop("username", None)
    return redirect(url_for("authentication.login"))
