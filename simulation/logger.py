import time


# ==================================================================================================#
# ------------------------------- Code written by Saurav -------------------------------------------#
# I have not changed anything in this code. I have just copied this code from the file              #
# langchain_workflow.py and pasted it here to be imported in helper.py file.                        #
# ==================================================================================================#
def log_function_call(func):
    """
    Decorator that logs function calls and their results.
    This decorator wraps a function, logging the time when the function is called along with its
    name, positional arguments, and keyword arguments. After executing the function, it also logs the
    time and the returned value. The log entries are appended to the "logs/function_calls.txt" file,
    with each entry timestamped.
    Usage:
        @log_function_call
        def your_function(...):
            ...
    Parameters:
        func (callable): The function to be decorated and logged.
    Returns:
        callable: A wrapped version of the original function that logs its call details and return value.
    """

    def wrapper(*args, **kwargs):
        log_line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {func.__name__} called with args: {args}, kwargs: {kwargs}\n"
        with open("logs/function_calls.txt", "a", encoding="utf-8") as f:
            f.write(log_line)
        result = func(*args, **kwargs)
        log_line_result = f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {func.__name__} returned: {result}\n"
        with open("logs/function_calls.txt", "a", encoding="utf-8") as f:
            f.write(log_line_result)
        return result

    return wrapper
