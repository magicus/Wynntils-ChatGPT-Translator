import json
import os
import time

from openai import OpenAI
from dotenv import load_dotenv


# Localization data is a dictionary where the keys are the localization keys, the values are the localization strings
# The localization keys are unique, and they are in the format of "<category>.wynntils.<feature>.<.*>"
# Batch the localization strings by features and return them as a dictionary, where the key is the category
# and the value is a dictionary where the key is the feature, where the value is a dictionary,
# where the localization key and the value is the localization string
def batch_localization_by_keys(data: dict) -> dict:
    batched_localization = {}

    for key, value in data.items():
        # Split the key by "."
        parts = key.split(".")

        # Extract the category and the feature
        category = parts[0]
        feature = parts[2]

        # If the category is not in the batched_localization, add it
        if category not in batched_localization:
            batched_localization[category] = {}

        # If the feature is not in the batched_localization[category], add it
        if feature not in batched_localization[category]:
            batched_localization[category][feature] = {}

        # Add the localization key and the localization string to the batched_localization
        batched_localization[category][feature][key] = value

    return batched_localization


load_dotenv()

# Load the API key from the .env file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# Define the prompt
prompt = """You are an excellent translator. You always try to be as accurate as possible. 
You MUST translate all the localization lines you receive.

You are given a JSON file, which is a list of localization strings,
in american english, and your job is to translate it into the requested language.
The localization strings are related to each other, most of the time, they refer to a single feature.
You can reword the strings if needed, but you need to keep the original meaning.
The localization also has format strings (%s, %d, etc.), you need to keep them in the translated string, 
in a way that it makes sense in the requested language. 
Try to use a language that is suitable for an MMORPG game.

None of these words should be translated: "lootrun", "class", "guild", "wynntils", "hades".
Do not translate the localization keys, only the localization strings.
Do not translate strings in (escaped) quotes, only the remaining text.

The requested language code is either a single string, or an array of strings, in ISO 639-1 language code format.

You are only allowed to answer as a JSON object, where the keys are the original localization keys, 
and the values are an object with the requested language code as the key, and the translated string as the value.

Input JSON format:
```
{
   "requested": ["hu_HU", "de_DE"],
   "data":{
      "command.wynntils.bomb.description": "List previously announced bombs",
      "command.wynntils.bomb.clickHere": "Click here to confirm."
      ...
   }
}
```

Output JSON format:
```
{
    "command.wynntils.bomb.description": {
        "hu_HU": "Listázza a korábban bejelentett bombákat",
        "de_DE": "Liste zuvor angekündigter Bomben"
        ...
    },
    "command.wynntils.bomb.clickHere": {
        "hu_HU": "Kattintson ide a megerősítéshez.",
        "de_DE": "Klicken Sie hier, um zu bestätigen."
        ...
    },
    ...
}
```
"""

languages = ["hu_HU", "nl_NL", "pl_PL", "es_ES", "fr_FR", "de_DE", "it_IT", "pt_PT", "ru_RU", "ja_JP", "ko_KR", "zh_CN", "zh_TW"]

# Load the localization data from the en_us.json file
with open("en_us.json", "r") as file:
    localization_data = json.load(file)

# Batch the localization data by features
batched_localization = batch_localization_by_keys(localization_data)

batches = []
batch_file_folder = "batch_files" + os.sep + str(int(time.time()))

# Create a task for each category and feature
for category, features in batched_localization.items():
    # One batch line should have a maximum of 100 localization strings
    # Split the features into multiple batches if there are more than 100 localization strings
    task_lines = []

    # Collect all the category lines, sort them, and batch them by 100
    batched_task = {}
    for key, lines in features.items():
        for loc_key, value in lines.items():
            batched_task[loc_key] = value

            if len(batched_task) >= 50:
                task_lines.append(batched_task)
                batched_task = {}

    if len(batched_task) > 0:
        task_lines.append(batched_task)
        batched_task = {}

    tasks = []
    for task in task_lines:
        user_data = {"requested": languages, "data": task}
        # Write the user_message as a single line JSON string
        user_message = json.dumps(user_data, separators=(",", ":"))

        task = {
            "custom_id": f"{category}-{len(tasks)}-{int(time.time())}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-2024-08-06",
                "temperature": 0.1,
                "max_tokens": 16384,
                "response_format": {
                    "type": "json_object"
                },
                "messages": [
                    {
                        "role": "system",
                        "content": prompt
                    },
                    {
                        "role": "user",
                        "content": user_message
                    }
                ],
            }
        }

        tasks.append(task)

    # Define the file name, based on timestamp and all language codes, based on sorted order
    file_name = f"wynntils-config-translation-{category}-{'-'.join(sorted(languages))}.jsonl"

    # Create the batch_file_folder if it does not exist
    batches_path = os.path.join(batch_file_folder, "batches")
    os.makedirs(batches_path, exist_ok=True)

    # Write all the tasks to the file
    with open(os.path.join(batches_path, file_name), "w") as file:
        for task in tasks:
            # Write each task as a single line JSON string
            file.write(json.dumps(task, separators=(",", ":")) + "\n")

    batches += [os.path.join(batches_path, file_name)]

    print(f"Task save to {batches[-1]}")

for batch in batches:
    # Upload the batch file to the OpenAI API
    with open(batch, "rb") as file:
        batch_file = client.files.create(file=file, purpose="batch")

    # Submit the batch to the OpenAI API
    batch_job = client.batches.create(
        input_file_id=batch_file.id,
        endpoint="/v1/chat/completions",
        completion_window="24h"
    )

    print(f"Batch submitted: {batch_job}")

    failed = False

    # Continue checking the status of the batch until it is completed
    while batch_job.status != "completed":
        batch_job = client.batches.retrieve(batch_job.id)
        print(f"Batch status: {batch_job.status} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(10)

        if (batch_job.status == "failed" or
                batch_job.status == "expired" or
                batch_job.status == "cancelling" or
                batch_job.status == "cancelled"):
            print(f"Batch failed: {batch_job}")
            failed = True
            break

    if failed:
        continue

    print(f"Batch completed: {batch_job}")

    # Download the results of the batch
    print(f"Downloading the results of the batch: {batch_job.output_file_id}")
    results = client.files.retrieve(batch_job.output_file_id)

    result_file_id = batch_job.output_file_id
    result_content = client.files.content(result_file_id).content

    # Save the results to a file
    results_path = os.path.join(batch_file_folder, "results")
    os.makedirs(results_path, exist_ok=True)

    with open(os.path.join(results_path, f"{batch.split(os.sep)[-1].replace('.jsonl', '')}-results.jsonl"),
              "wb") as file:
        file.write(result_content)
