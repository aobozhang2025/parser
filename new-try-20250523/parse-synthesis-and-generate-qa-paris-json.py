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
        Focus on catalyst names like Pt/MoC-2, Au₁–Oₓ–Na₉–(OH)ᵧ/TiO₂, etc.
        """
        compounds = []

        # Enhanced patterns for catalyst compound names
        patterns = [
            # Direct synthesis patterns
            r'synthesis of ([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+)',
            r'preparation of ([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+)',

            # Catalyst-specific patterns
            r'([A-Za-z0-9]+/[A-Za-z0-9\-\_]+)',  # e.g., Pt/MoC-2, Au/TiO2
            r'([A-Za-z0-9₀₁₂₃₄₅₆₇₈₉ₓᵧ]+–[A-Za-z0-9₀₁₂₃₄₅₆₇₈₉ₓᵧ–]+/[A-Za-z0-9₀₁₂₃₄₅₆₇₈₉]+)',
            # e.g., Au₁–Oₓ–Na₉–(OH)ᵧ/TiO₂
            r'([A-Za-z0-9]+Pc[A-Za-z0-9\-–]+)',  # e.g., NiPc–OMe, CoPc
            r'([A-Za-z0-9₀₁₂₃₄₅₆₇₈₉]+@[A-Za-z0-9\-\_]+)',  # e.g., Pt@CeO2

            # Complex catalyst formulations
            r'([A-Za-z0-9₀₁₂₃₄₅₆₇₈₉]+\([A-Za-z0-9₀₁₂₃₄₅₆₇₈₉\-\_]+\)[₀₁₂₃₄₅₆₇₈₉]*)',  # e.g., Ni(OH)2
            r'([A-Za-z0-9₀₁₂₃₄₅₆₇₈₉]+[A-Za-z0-9₀₁₂₃₄₅₆₇₈₉\-\_]+/[A-Za-z0-9₀₁₂₃₄₅₆₇₈₉\-\_]+)',
            # General supported catalysts

            # Was synthesized/prepared patterns
            r'([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+) was synthesized',
            r'([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+) was prepared',
            r'([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+) catalyst',
            r'to prepare ([A-Za-z0-9\-\/\(\)\_\+\@\{\}₀₁₂₃₄₅₆₇₈₉ₓᵧᵦαβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ°·–−]+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            compounds.extend(matches)

        # Clean and filter compounds
        cleaned_compounds = []
        stop_words = ['the', 'a', 'an', 'this', 'that', 'these', 'those', 'sample', 'material',
                      'method', 'procedure', 'process', 'step', 'stage', 'conditions', 'temperature',
                      'solution', 'mixture', 'powder', 'solid', 'liquid', 'gas', 'flow', 'rate']

        for compound in compounds:
            compound = compound.strip()
            # Filter out common words and very short strings
            if (compound.lower() not in stop_words and
                    len(compound) > 2 and
                    not compound.isdigit() and
                    # Keep compounds that look like catalysts (contain /, @, or metal symbols)
                    (any(char in compound for char in ['/', '@', '-']) or
                     any(metal in compound.upper() for metal in
                         ['PT', 'AU', 'NI', 'CO', 'FE', 'CU', 'ZN', 'MO', 'TI', 'CE', 'ZR', 'AL', 'MG', 'CA', 'RU',
                          'PD', 'IR', 'RH']))):
                cleaned_compounds.append(compound)

        return list(set(cleaned_compounds))  # Remove duplicates

    def clean_synthesis_text(self, text: str) -> str:
        """
        Clean and format synthesis text for better readability.
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove citations (numbers in brackets, but preserve chemical formulas)
        text = re.sub(r'\[(\d+)\]', '', text)
        text = re.sub(r'\(\d+\)', '', text)  # Remove numbered references in parentheses

        # Remove DOI references
        text = re.sub(r'doi:\s*\S+', '', text)

        # Clean up temperature and measurement units (preserve subscripts/superscripts)
        text = re.sub(r'(\d+)\s*°\s*C', r'\1°C', text)
        text = re.sub(r'(\d+)\s*ml(?!\w)', r'\1 ml', text)
        text = re.sub(r'(\d+)\s*mg(?!\w)', r'\1 mg', text)
        text = re.sub(r'(\d+)\s*g(?!\w)', r'\1 g', text)
        text = re.sub(r'(\d+)\s*h(?!\w)', r'\1 h', text)
        text = re.sub(r'(\d+)\s*min(?!\w)', r'\1 min', text)

        # Fix common chemical notation
        text = re.sub(r'H\s*2\s*O', 'H₂O', text)
        text = re.sub(r'CO\s*2', 'CO₂', text)
        text = re.sub(r'NH\s*3', 'NH₃', text)

        # Remove extra periods and clean punctuation
        text = re.sub(r'\.{2,}', '.', text)
        text = re.sub(r'\s+([,.;:])', r'\1', text)

        return text.strip()

    def generate_question_answer_pairs(self, file_path: str, text: str) -> List[Dict]:
        """
        Generate question-answer pairs from synthesis text.
        """
        qa_pairs = []

        # Extract DOI from filename (remove _synthesis.txt)
        filename = os.path.basename(file_path)
        doi = filename.replace('_synthesis.txt', '').replace('.txt', '')

        # Extract synthesis sections
        sections = self.extract_synthesis_sections(text)

        # Extract all compound names from the entire text
        all_compounds = self.extract_compound_names(text)

        # Generate Q&A pairs for each synthesis section
        for title, content in sections:
            if len(content.strip()) < 50:  # Skip very short sections
                continue

            cleaned_content = self.clean_synthesis_text(content)

            # Try to identify specific compound being synthesized in this section
            section_text = title + " " + content
            section_compounds = self.extract_compound_names(section_text)

            # Determine the best compound name for the question
            target_compound = None

            if section_compounds:
                # Use the first compound found in this section
                target_compound = section_compounds[0]
            elif all_compounds:
                # Fall back to any compound found in the entire document
                target_compound = all_compounds[0]

            # Generate question based on available information
            if target_compound:
                question = f"How to synthesize {target_compound}?"
            else:
                # Extract from section title if no specific compound found
                if 'synthesis of' in title.lower():
                    extracted = title.lower().replace('synthesis of', '').strip()
                    question = f"How to synthesize {extracted}?"
                elif 'preparation of' in title.lower():
                    extracted = title.lower().replace('preparation of', '').strip()
                    question = f"How to synthesize {extracted}?"
                else:
                    # Generic question
                    question = f"How to synthesize {title}?"

            # Create the Q&A pair with proper DOI formatting
            qa_pair = {
                "conversation": [
                    {
                        "input": question,
                        "output": f"In a paper with doi: {doi}, {cleaned_content}"
                    }
                ]
            }

            qa_pairs.append(qa_pair)

        # If no sections found, try to extract from the entire text
        if not qa_pairs and all_compounds:
            for compound in all_compounds[:3]:  # Limit to first 3 compounds
                # Look for synthesis information related to this compound
                compound_sections = []
                text_lower = text.lower()
                compound_lower = compound.lower()

                # Find paragraphs that mention this compound and synthesis
                paragraphs = text.split('\n\n')
                for para in paragraphs:
                    if (compound_lower in para.lower() and
                            any(keyword in para.lower() for keyword in
                                ['synthesis', 'preparation', 'method', 'procedure'])):
                        compound_sections.append(para.strip())

                if compound_sections:
                    combined_content = ' '.join(compound_sections)
                    cleaned_content = self.clean_synthesis_text(combined_content)

                    qa_pair = {
                        "conversation": [
                            {
                                "input": f"How to synthesize {compound}?",
                                "output": f"In a paper with doi: {doi}, {cleaned_content}"
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