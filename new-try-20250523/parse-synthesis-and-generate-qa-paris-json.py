import os
import json
import re
from typing import List, Dict, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SynthesisQAExtractor:
    def __init__(self):
        self.synthesis_keywords = [
            'synthesis', 'preparation', 'method', 'procedure', 'catalyst preparation',
            'catalyst synthesis', 'sample preparation', 'fabrication', 'formation'
        ]
        self.qa_pairs = []

    def extract_synthesis_sections(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract synthesis-related sections from the text.
        Returns list of tuples: (title, content)
        """
        sections = []

        # Split text into potential sections based on common patterns
        # Look for section headers (capitalized text, potentially with numbers/symbols)
        section_pattern = r'^([A-Z][A-Za-z\s\-\d\(\)\/]+)$'
        lines = text.split('\n')

        current_section = ""
        current_content = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line looks like a section header
            if re.match(section_pattern, line) and len(line) < 100:
                # Save previous section if it contains synthesis keywords
                if current_section and any(
                        keyword.lower() in current_section.lower() for keyword in self.synthesis_keywords):
                    sections.append((current_section, '\n'.join(current_content)))

                current_section = line
                current_content = []
            else:
                current_content.append(line)

        # Don't forget the last section
        if current_section and any(keyword.lower() in current_section.lower() for keyword in self.synthesis_keywords):
            sections.append((current_section, '\n'.join(current_content)))

        # Also look for synthesis information in paragraphs that start with synthesis keywords
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            para = para.strip()
            if para and any(keyword.lower() in para[:100].lower() for keyword in self.synthesis_keywords):
                # Extract potential compound name from the paragraph
                compound_match = re.search(r'synthesis of ([A-Za-z0-9\-\/\(\)]+)', para.lower())
                if compound_match:
                    compound = compound_match.group(1)
                    sections.append((f"Synthesis of {compound}", para))
                else:
                    # Generic synthesis section
                    first_words = ' '.join(para.split()[:5])
                    sections.append((first_words, para))

        return sections

    def extract_compound_names(self, text: str) -> List[str]:
        """
        Extract potential compound names from synthesis descriptions.
        """
        compounds = []

        # Common patterns for compound names in synthesis contexts
        patterns = [
            r'synthesis of ([A-Za-z0-9\-\/\(\)\_\+\@]+)',
            r'preparation of ([A-Za-z0-9\-\/\(\)\_\+\@]+)',
            r'([A-Za-z0-9\-\/\(\)\_\+\@]+) was synthesized',
            r'([A-Za-z0-9\-\/\(\)\_\+\@]+) catalyst',
            r'([A-Za-z0-9\-\/\(\)\_\+\@]+) was prepared',
            r'to prepare ([A-Za-z0-9\-\/\(\)\_\+\@]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            compounds.extend(matches)

        # Clean and filter compounds
        cleaned_compounds = []
        for compound in compounds:
            # Remove common words that aren't compound names
            if compound.lower() not in ['the', 'a', 'an', 'this', 'that', 'these', 'those', 'sample', 'catalyst',
                                        'material']:
                cleaned_compounds.append(compound.strip())

        return list(set(cleaned_compounds))  # Remove duplicates

    def clean_synthesis_text(self, text: str) -> str:
        """
        Clean and format synthesis text for better readability.
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove citations (numbers in brackets)
        text = re.sub(r'\[\d+\]', '', text)

        # Remove DOI references
        text = re.sub(r'doi:\s*\S+', '', text)

        # Clean up temperature and measurement units
        text = re.sub(r'(\d+)\s*°\s*C', r'\1°C', text)
        text = re.sub(r'(\d+)\s*ml', r'\1 ml', text)
        text = re.sub(r'(\d+)\s*mg', r'\1 mg', text)
        text = re.sub(r'(\d+)\s*g', r'\1 g', text)

        return text.strip()

    def generate_question_answer_pairs(self, file_path: str, text: str) -> List[Dict]:
        """
        Generate question-answer pairs from synthesis text.
        """
        qa_pairs = []

        # Extract synthesis sections
        sections = self.extract_synthesis_sections(text)

        # Extract compound names
        compounds = self.extract_compound_names(text)

        # Generate Q&A pairs for each synthesis section
        for title, content in sections:
            if len(content.strip()) < 50:  # Skip very short sections
                continue

            cleaned_content = self.clean_synthesis_text(content)

            # Try to identify specific compound being synthesized
            section_compounds = self.extract_compound_names(title + " " + content)

            if section_compounds:
                # Use specific compound name in question
                compound = section_compounds[0]
                question = f"How to synthesize {compound}?"
            else:
                # Generic question based on section title
                if any(keyword in title.lower() for keyword in ['preparation', 'synthesis']):
                    question = f"How to synthesize {title.lower().replace('preparation of', '').replace('synthesis of', '').strip()}?"
                else:
                    question = f"How to synthesize {title}?"

            # Create the Q&A pair
            qa_pair = {
                "conversation": [
                    {
                        "input": question,
                        "output": f"In a paper with doi: {os.path.basename(file_path).replace('.txt', '')}, {cleaned_content}"
                    }
                ]
            }

            qa_pairs.append(qa_pair)

        return qa_pairs

    def process_txt_file(self, file_path: str) -> List[Dict]:
        """
        Process a single txt file and extract synthesis Q&A pairs.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()

            logger.info(f"Processing file: {file_path}")
            qa_pairs = self.generate_question_answer_pairs(file_path, text)
            logger.info(f"Generated {len(qa_pairs)} Q&A pairs from {file_path}")

            return qa_pairs

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            return []

    def process_folder(self, folder_path: str, output_file: str = "synthesis_qa_pairs.json"):
        """
        Process all txt files in a folder and save Q&A pairs to JSON.
        """
        if not os.path.exists(folder_path):
            logger.error(f"Folder not found: {folder_path}")
            return

        all_qa_pairs = []
        txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]

        if not txt_files:
            logger.warning(f"No txt files found in {folder_path}")
            return

        logger.info(f"Found {len(txt_files)} txt files to process")

        for txt_file in txt_files:
            file_path = os.path.join(folder_path, txt_file)
            qa_pairs = self.process_txt_file(file_path)
            all_qa_pairs.extend(qa_pairs)

        # Save to JSON file
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_qa_pairs, f, indent=4, ensure_ascii=False)

            logger.info(f"Successfully saved {len(all_qa_pairs)} Q&A pairs to {output_file}")

        except Exception as e:
            logger.error(f"Error saving to JSON file: {str(e)}")

    def preview_results(self, num_examples: int = 3):
        """
        Preview some of the generated Q&A pairs.
        """
        if not self.qa_pairs:
            logger.warning("No Q&A pairs to preview. Run process_folder first.")
            return

        print(f"\n--- Preview of {min(num_examples, len(self.qa_pairs))} Q&A pairs ---")

        for i, qa_pair in enumerate(self.qa_pairs[:num_examples]):
            conversation = qa_pair["conversation"][0]
            print(f"\nExample {i + 1}:")
            print(f"Q: {conversation['input']}")
            print(f"A: {conversation['output'][:200]}...")  # Show first 200 chars
            print("-" * 50)


# Usage example
def main():
    """
    Main function to demonstrate usage.
    """
    # Initialize the extractor
    extractor = SynthesisQAExtractor()

    # Specify the folder containing txt files
    folder_path = "D:\\pycharm-project\\parser\\new-try-20250523\\synthesis_outputs"  # Change this to your folder path
    output_file = "synthesis_qa_pairs.json"

    # Process all txt files in the folder
    extractor.process_folder(folder_path, output_file)

    # Optional: Preview results
    # extractor.preview_results(3)


if __name__ == "__main__":
    main()