import os
import re
from pathlib import Path


def extract_synthesis_section(content):
    """Extract the synthesis/preparation section from the text content."""
    # Define patterns that might indicate the start of the synthesis section
    synthesis_patterns = [
        r'Methods\s*Preparation of catalysts',
        r'Methods\s*Synthesis',
        r'Preparation of catalysts',
        r'Catalyst preparation',
        r'Experimental section\s*Synthesis',
        r'Synthesis of',
        r'Preparation of',
        r'Synthesis\s*Methods',
        r'Materials and methods\s*Synthesis'
    ]

    # Try to find the start of the synthesis section using different patterns
    start_index = -1
    for pattern in synthesis_patterns:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            start_index = match.start()
            break

    if start_index == -1:
        return None

    # Look for the end of the section (typically before "Results" or "Characterization")
    end_patterns = [
        r'Evaluation of catalytic performance',
        r'Characterization',
        r'Results and discussion',
        r'Catalytic tests',
        r'Experimental results',
        r'\nReferences\n',
        r'\nAcknowledgements\n',
        r'\nAuthor information\n',
        r'\nAdditional information\n'
    ]

    end_index = len(content)
    for pattern in end_patterns:
        match = re.search(pattern, content[start_index:], re.IGNORECASE)
        if match:
            end_index = start_index + match.start()
            break

    # Extract the synthesis section
    synthesis_section = content[start_index:end_index].strip()

    return synthesis_section


def process_files(input_folder, output_folder):
    """Process all txt files in input_folder and save extracted sections to output_folder."""
    # Create output folder if it doesn't exist
    Path(output_folder).mkdir(parents=True, exist_ok=True)

    processed_files = 0
    skipped_files = 0

    for filename in os.listdir(input_folder):
        if filename.endswith('.txt'):
            input_path = os.path.join(input_folder, filename)

            try:
                with open(input_path, 'r', encoding='utf-8') as file:
                    content = file.read()

                synthesis_text = extract_synthesis_section(content)

                if synthesis_text:
                    # Create output filename
                    base_name = os.path.splitext(filename)[0]
                    output_filename = f"{base_name}-synthesis.txt"
                    output_path = os.path.join(output_folder, output_filename)

                    # Save the synthesis text
                    with open(output_path, 'w', encoding='utf-8') as file:
                        file.write(synthesis_text)

                    processed_files += 1
                else:
                    print(f"No synthesis section found in: {filename}")
                    skipped_files += 1

            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")
                skipped_files += 1

    print(f"\nProcessing complete!")
    print(f"Files processed successfully: {processed_files}")
    print(f"Files skipped: {skipped_files}")


def main():
    # Get folder paths from user
    input_folder = input("Enter the path to the folder containing text files: ").strip()
    output_folder = input("Enter the path for the output folder (will be created if it doesn't exist): ").strip()

    # Validate input folder exists
    if not os.path.isdir(input_folder):
        print(f"Error: Input folder '{input_folder}' does not exist.")
        return

    # Process all files
    process_files(input_folder, output_folder)


if __name__ == "__main__":
    main()