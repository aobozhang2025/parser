import os
import json
import re
from typing import List, Dict


def extract_catalyst_info(content: str) -> str:
    """
    Analyze the text content to identify the catalyst being synthesized.
    Returns a concise description of the catalyst.
    """
    # Look for common catalyst patterns in the text
    patterns = [
        r"(\d+%Pt/\w+-?\w+)",  # e.g., 2%Pt/α-MoC
        r"(Pt/\w+-?\w+)",  # e.g., Pt/α-MoC
        r"(\w+-?\w+ support)",  # e.g., α-MoC support
        r"(Mo\w+)"  # e.g., Mo2C, MoC
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1).replace(" support", "")

    # Fallback to first line if no pattern matches
    return content.split('\n')[0].strip()


def generate_input_question(catalyst: str) -> str:
    """
    Generate a concise question about synthesizing the catalyst.
    """
    catalyst = catalyst.replace("_", "/")  # Clean formatting
    return f"How to synthesize {catalyst}?"


def read_txt_files(folder_path: str) -> List[Dict]:
    """
    Process all .txt files in a folder and generate structured summaries.
    """
    summaries = []
    for filename in os.listdir(folder_path):
        if filename.endswith(".txt"):
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                catalyst = extract_catalyst_info(content)
                input_question = generate_input_question(catalyst)
                doi = filename.replace("-synthesis.txt", "").replace(".txt", "")

                summaries.append({
                    "conversation": [{
                        "input": input_question,
                        "output": f"In a paper with doi: {doi}, {content}"
                    }]
                })
    return summaries


def save_to_json(data: List[Dict], output_path: str) -> None:
    """Save the structured data to a JSON file."""
    with open(output_path, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)


def main():
    input_folder = "D:\\pycharm-project\\parser\\test\\articles_txt_synthesis"  # Replace with your folder path
    output_json = "summarized_catalysts.json"

    summaries = read_txt_files(input_folder)
    save_to_json(summaries, output_json)
    print(f"Generated summaries saved to {output_json}")


if __name__ == "__main__":
    main()