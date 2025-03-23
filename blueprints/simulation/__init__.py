import json
import threading
from flask import (
    render_template,
    jsonify,
    session,
    url_for,
    redirect,
)
from simulation.simulator import simulator, stop_event, resume_event, user_typing, assistant_typing, creating_persona
from simulation.simulator import get_score
from simulation.simulator import clear_all_events
from .. import simulation_blueprint

# Global simulator thread
simulator_thread = None
simulator_lock = threading.Lock()

@simulation_blueprint.route("/simulation")
def simulation():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("simulation.html")


@simulation_blueprint.route("/start")
def start():
    global simulator_thread
    if "username" not in session:
        return redirect(url_for("login"))

    with simulator_lock:
        if simulator_thread and simulator_thread.is_alive():
            print("Simulation is already running")
            return jsonify({"info": "Simulation is already running"}), 200

        print("Starting a new simulation...")
        clear_all_events()
        stop_event.clear()
        simulator_thread = threading.Thread(target=simulator, daemon=True)
        simulator_thread.start()
        return jsonify({"success": "Simulation started"}), 200


@simulation_blueprint.route("/stop")
def stop():
    global simulator_thread
    if "username" not in session:
        return redirect(url_for("login"))
    with simulator_lock:
        stop_event.set()
        if simulator_thread:
            simulator_thread.join()
            simulator_thread = None
        clear_all_events()
    return jsonify({"success": "Simulation stopped"}), 200


@simulation_blueprint.route("/simulation/status/running")
def simulation_status():
    if "username" not in session:
        return redirect(url_for("login"))

    if not simulator_thread or not simulator_thread.is_alive():
        return jsonify({"status": "stopped"}), 200
    elif not resume_event.is_set():
        return jsonify({"status": "paused"}), 200
    return jsonify({"status": "running"}), 200


@simulation_blueprint.route("/simulation/messages")
def simulation_data():
    if "username" not in session:
        return redirect(url_for("login"))
    try:
        with open("conversation_history.json", "r") as file:
            messages = json.load(file)
        return jsonify({"messages": messages}), 200
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"error": "No conversation history found"}), 404
    except Exception as e:
        print(e)


@simulation_blueprint.route("/simulation/status/typing")
def typing_status():
    if "username" not in session:
        return redirect(url_for("login"))
    return jsonify(
        {
            "user_typing": user_typing.is_set(),
            "assistant_typing": assistant_typing.is_set(),
            "creating_persona": creating_persona.is_set(),
        }
    )


@simulation_blueprint.route("/continue")
def continue_simulation():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    if not simulator_thread or not simulator_thread.is_alive():
        return jsonify({"error": "Simulation is not running"}), 400

    if resume_event.is_set():  # If already running, do nothing
        return jsonify({"message": "Simulation is already running"}), 200
    try:
        resume_event.set()  # Resume the paused simulation
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"message": "Simulation resumed successfully"}), 200


@simulation_blueprint.route("/critic")
def critique_text():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    score = get_score()
    return jsonify({"score": score})
# TODO: remove critic route and use the get_score function in the simulation/simulator.py file
