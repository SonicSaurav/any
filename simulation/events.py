import threading

file_lock = threading.Lock()  # global lock for file writing

stop_event = threading.Event()  # Event to signal the simulator to stop

user_typing = threading.Event()  # Event to signal user typing
assistant_typing = threading.Event()  # Event to signal agent typing
creating_persona = threading.Event()  # Event to signal persona creation

resume_event = threading.Event()  # Global event for pausing & resuming
resume_event.set()  # Initially set to allow normal execution


def clear_all_events():
    """
    Clears all simulation events, resetting their states for a fresh start.
    This function resets several event objects used in the simulation:
        - Clears 'stop_event' to indicate that any ongoing stop signal is reset.
        - Clears 'user_typing' to signal that the user is no longer typing.
        - Clears 'assistant_typing' to signal that the assistant is no longer typing.
        - Clears 'creating_persona' to indicate that the persona creation process (if any) is reset.
        - Sets 'resume_event' to signal that operations can resume.
    No parameters are required and the function does not return any value.
    """

    stop_event.clear()
    user_typing.clear()
    assistant_typing.clear()
    creating_persona.clear()
    resume_event.set()
