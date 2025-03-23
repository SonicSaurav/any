import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env file if present

client = OpenAI()  # Initialize the OpenAI client with the API key from .env


# ==============================================================================#
#                             ✋✋✋✋✋✋ STOP! ✋✋✋✋✋✋                  #
#  Before you proceed, make sure you have the following placeholders in the     #
#  critic_prompt.md file:                                                       #
#  - {conversation}                                                             #
#  - {original_prompt}                                                          #
#  - {search_history}                                                           #
#  - {last_response}                                                            #
# If you don't have these placeholders, the warrenty would be voided.           #
# ==============================================================================#


def get_score(conversation_history: list, search_history: list = []) -> int:
    """
    Calculate and return a rating based on the conversation and search histories.
    This function constructs a critic prompt by replacing placeholders with relevant data from the conversation history,
    the original agent prompt, the search history, and the last response. It then logs the generated prompt to a file,
    performs a chat completion API call using the "o3-mini" model, and attempts to extract a "Rating" from the JSON
    formatted response.
    Parameters:
        conversation_history (list): List containing the conversation history. The final element is considered the
                                     last response, while the remaining elements form the conversation context.
        search_history (list, optional): Optional list of search-related inputs. Defaults to an empty list.
    Returns:
        int: The extracted rating if the process is successful. In case of an error during prompt preparation,
             API call, JSON decoding, or if the expected "Rating" key is missing, the function returns -1.0.
    Notes:
        - The critic prompt is logged to "logs/critic_prompt.log".
        - Any errors encountered during processing (e.g., formatting, API invocation, parsing) are logged to
          "logs/critic_error.log" and result in a return value of -1.0.
    """

    # Open the file using the resolved absolute path
    with open("prompts/actor.md", "r") as file:
        agent_prompt = file.read()

    with open("prompts/critic.md", "r") as file:
        critic_prompt = file.read()

    with open("logs/conv_hist.json", "w") as file:
        json.dump(conversation_history, file)

    last_response = conversation_history[-1]
    conversation_history = conversation_history[:-1]
    try:
        critic_prompt = (
            critic_prompt.replace("{conversation}", str(conversation_history))
            .replace("{original_prompt}", str(agent_prompt))
            .replace("{search_history}", str(search_history))
            .replace("{last_response}", str(last_response))
        )
        # dump the critic prompt to a file
        with open("logs/critic.md", "a") as file:
            file.write(f"{critic_prompt}\n")
            file.write("-" * 50 + "\n" * 5)
    except Exception as e:
        print(f"[CRITIC] Error: {e}")
        with open("logs/critic_error.log", "a") as file:
            file.write(f"{e}\n")
        return -1.0

    # messages = [
    #     {"role": "user", "content": critic_prompt},
    # ]

    completion = client.chat.completions.create(
        model="o1-2024-12-17",
        # model="o3-mini",
        messages=[
            {
                "role": "user",
                "content": critic_prompt,
            }
        ],
    )

    response = completion.choices[0].message.content
    print(f"[CRITIC] Response: {response}")
    with open("logs/critic_response.log", "a") as file:
        file.write(f"{response}\n")
        file.write("-" * 50 + "\n" * 5)
    try:
        response = json.loads(response)
        return response["score"]
    except json.JSONDecodeError as json_error:
        print(f"[CRITIC] Error: {json_error}")
        # write the error to a log file
        with open("logs/critic_error.log", "a") as file:
            file.write(f"{json_error}\n")
        return -1.0
    except KeyError:
        print(f"[CRITIC] Error: Key Error")
        print(response)
        with open("logs/critic_error.log", "a") as file:
            file.write(f"{response}\n")
        return -1.0
    except Exception as e:
        print(f"[CRITIC] Error: {e}")
        with open("logs/critic_error.log", "a") as file:
            file.write(f"{e}\n")
        return -1.0
