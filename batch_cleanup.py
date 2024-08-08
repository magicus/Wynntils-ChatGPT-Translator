import json
import glob
import os


def clean_openapi_responses(input_files, output_file):
    cleaned_responses = {}

    for input_file in input_files:
        print("Loading file: ", input_file)
        with open(input_file, "r") as file:
            for line in file:
                # Parse the JSON line
                response = json.loads(line.strip())

                # Extract the desired information
                response_body = response.get("response", {}).get("body", {})
                assistant_message = response_body.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Store the cleaned information
                json_response = json.loads(assistant_message)
                cleaned_responses.update(json_response)

    # Save the cleaned responses to a new file
    with open(output_file, "w") as outfile:
        outfile.write(json.dumps(cleaned_responses, ensure_ascii=False, indent=2) + "\n")

    print(f"Processed {len(input_files)} files and saved cleaned responses to {output_file}.")

    return cleaned_responses

# Based on the input files, create separate language files for each language, with the cleaned responses,
# and make them an object where they key is the localization key and the value is the cleaned response
# {
#   "screens.wynntils.additionalContent.description": {
#     "hu_HU": "Tekintsd meg az összes további, ismételhető tartalmat a Wynncraft tartalom menüjében.",
#     "nl_NL": "Bekijk alle aanvullende, herhaalbare inhoud in het Wynncraft inhoudsmenu.",
#     "pl_PL": "Zobacz całą dodatkową, powtarzalną zawartość w menu zawartości Wynncraft."
#   },
def create_separate_lang_files(cleaned_responses, output_dir):
    for loc_key, loc_values in cleaned_responses.items():
        for lang, loc_value in loc_values.items():
            lang_file = os.path.join(output_dir, f"{lang}.json")
            if not os.path.exists(lang_file):
                with open(lang_file, "w") as file:
                    file.write("{}")

            with open(lang_file, "r") as file:
                lang_data = json.load(file)

            lang_data[loc_key] = loc_value

            # Sort language data by keys
            lang_data = dict(sorted(lang_data.items()))

            with open(lang_file, "w") as file:
                file.write(json.dumps(lang_data, ensure_ascii=False, indent=2) + "\n")

    print(f"Saved cleaned responses to separate language files in {output_dir}.")


# Visit all folders in the batch_files directory
batch_files_dir = "batch_files"

# The batch_files directory has folders with timestamps as names
# Each folder contains a results folder with output files from the OpenAI API
# We want to clean these files and save the cleaned responses to a new file in the same folder
for timestamp in os.listdir(batch_files_dir):
    results_dir = os.path.join(batch_files_dir, timestamp, "results")
    output_file = os.path.join(results_dir, "cleaned_responses.json")

    # Find all files matching the pattern
    input_files = glob.glob(os.path.join(results_dir, "wynntils-config-translation-*-results.jsonl"))

    # Process and clean the responses
    cleaned_responses = clean_openapi_responses(input_files, output_file)

    # Create separate language files for each language
    create_separate_lang_files(cleaned_responses, results_dir)