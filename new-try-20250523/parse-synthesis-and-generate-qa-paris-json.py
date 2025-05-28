import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class CatalystSynthesisProcessor:
    """Processor for catalyst synthesis Q&A generation with full title preservation."""

    def __init__(self, synthesis_folder: str, papers_folder: str, output_file: str = "catalyst_synthesis_qa.json"):
        self.synthesis_folder = Path(synthesis_folder)
        self.papers_folder = Path(papers_folder)
        self.output_file = output_file
        self.qa_pairs = []

        # Patterns for title identification
        self.catalyst_indicators = [
            'catalyst', 'atom', 'particle', 'cluster', 'species', 'material',
            'pt', 'au', 'pd', 'rh', 'ir', 'ru', 'ni', 'co', 'fe', 'cu', 'ag', 'zn', 'mn',
            'single', 'nano', 'oxo', 'supported', 'dispersed', 'isolated', 'atomic',
            'bimetallic', 'trimetallic', 'alloy', 'oxide', 'carbide', 'nitride'
        ]

    def extract_title_from_paper(self, paper_content: str) -> str:
        """Extract the title from the full paper content with enhanced patterns."""
        lines = paper_content.split('\n')

        # Enhanced title extraction patterns
        title_patterns = [
            # Direct match for the specific format in uploaded file
            r'Single-atom gold oxo-clusters prepared in alkaline solutions catalyse the heterogeneous methanol self-coupling reactions',
            # General patterns
            r'(?:Article.*?Published.*?)([A-Z][^|]*(?:catalyst|synthesis|preparation|catalyse|catalyze)[^|]*?)(?:\s*\||\s*Download|\s*$)',
            r'^([A-Z][^.!?]*?(?:catalyst|synthesis|preparation|catalyse|catalyze)[^.!?]*?)(?:\s*\||\s*Download|\s*$)',
            r'(?:Title:|title:)\s*(.+)',
        ]

        # Try pattern matching first
        for pattern in title_patterns:
            match = re.search(pattern, paper_content, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1) if match.lastindex else match.group(0)
                title = re.sub(r'\s+', ' ', title).strip()
                if len(title) > 20 and any(indicator in title.lower() for indicator in self.catalyst_indicators):
                    return title

        # Line-by-line analysis for titles
        potential_titles = []
        for i, line in enumerate(lines[:100]):  # Check first 100 lines
            line = line.strip()

            # Skip unwanted lines
            if not line or any(skip in line.lower() for skip in [
                'abstract', 'introduction', 'skip to', 'thank you', 'download pdf',
                'published:', 'received:', 'accepted:', 'volume', 'issue', 'http', 'doi:'
            ]):
                continue

            # Skip very short or very long lines
            if len(line) < 30 or len(line) > 300:
                continue

            # Look for catalyst-related titles
            if any(indicator in line.lower() for indicator in self.catalyst_indicators):
                # Check if it looks like a title (has capitals, no period at end, etc.)
                if (not line.endswith('.') and
                        sum(1 for c in line if c.isupper()) >= 3 and
                        not any(line.lower().startswith(word) for word in ['the', 'this', 'we', 'here', 'in'])):
                    potential_titles.append(line)

        # Return the longest potential title (likely the main title)
        if potential_titles:
            return max(potential_titles, key=len)

        return "Catalyst synthesis"

    def generate_question_from_title(self, title: str) -> str:
        """Generate synthesis question keeping ALL information from the title."""
        title = title.strip()

        # Clean up title artifacts but preserve all content
        title = re.sub(r'\s*\|\s*Nature Chemistry.*$', '', title, re.IGNORECASE)
        title = re.sub(r'\s*\|\s*.*Journal.*$', '', title, re.IGNORECASE)
        title = re.sub(r'\s*Download PDF.*$', '', title, re.IGNORECASE)

        # Remove trailing punctuation
        title = re.sub(r'[.!?]+$', '', title).strip()

        # Ensure proper capitalization
        if title and title[0].islower():
            title = title[0].upper() + title[1:]

        # Handle edge cases
        if not title or len(title) < 10:
            return "How to synthesize the catalyst"

        return f"How to synthesize {title}"

    def format_doi(self, doi_string: str) -> str:
        """Format DOI string for better readability."""
        # Convert underscores to dots for standard DOI format
        formatted_doi = doi_string.replace('_', '/')

        # Handle common DOI prefixes
        if not formatted_doi.startswith('10.'):
            # Try to detect DOI pattern
            if re.match(r'\d+\.\d+', formatted_doi):
                pass  # Already looks like a DOI
            else:
                # Might need manual formatting - keep as is
                pass

        return formatted_doi

    def extract_synthesis_methods(self, synthesis_content: str, doi: str) -> str:
        """Extract comprehensive synthesis methods and prepend DOI information."""

        # Format DOI for the answer
        formatted_doi = self.format_doi(doi)
        doi_prefix = f"In a paper with DOI {formatted_doi}, "

        # Look for catalyst preparation sections
        methods_patterns = [
            r'(?:Catalysts?\s+Preparation|Catalyst\s+preparation).*?(?=\n\s*[A-Z][A-Z\s]*\n|\n\n[A-Z]|\Z)',
            r'(?:Materials\s+and\s+Methods).*?(?=\n\s*[A-Z][A-Z\s]*\n|\n\n[A-Z]|\Z)',
            r'(?:Synthesis|synthesis).*?(?=\n\s*[A-Z][A-Z\s]*\n|\n\n[A-Z]|\Z)',
            r'(?:Preparation|preparation).*?(?=\n\s*[A-Z][A-Z\s]*\n|\n\n[A-Z]|\Z)',
            r'(?:Methods|methods).*?(?=\n\s*[A-Z][A-Z\s]*\n|\n\n[A-Z]|\Z)',
        ]

        synthesis_sections = []

        # Extract relevant sections
        for pattern in methods_patterns:
            matches = re.finditer(pattern, synthesis_content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            for match in matches:
                section = match.group().strip()
                if len(section) > 200:  # Only substantial sections
                    synthesis_sections.append(section)

        # If specific sections found, use them
        if synthesis_sections:
            combined = '\n\n'.join(synthesis_sections)
        else:
            # Look for paragraphs with synthesis keywords
            paragraphs = synthesis_content.split('\n\n')
            relevant_paragraphs = []

            synthesis_keywords = [
                'prepare', 'prepared', 'preparation', 'synthesis', 'synthesize', 'synthesized',
                'method', 'procedure', 'solution', 'temperature', 'heating', 'catalyst',
                'precursor', 'support', 'mixture', 'reflux', 'calcined', 'dried',
                'stirring', 'added', 'suspended', 'dissolved', 'impregnation'
            ]

            for para in paragraphs:
                if (len(para) > 100 and
                        sum(keyword in para.lower() for keyword in synthesis_keywords) >= 2):
                    relevant_paragraphs.append(para)

            combined = '\n\n'.join(relevant_paragraphs) if relevant_paragraphs else synthesis_content

        # Clean up the text
        combined = self._clean_synthesis_text(combined)

        # Prepend DOI information
        if combined:
            # Make the first sentence flow naturally with the DOI prefix
            first_sentence = combined.split('.')[0] if '.' in combined else combined.split('\n')[0]
            rest_of_content = combined[len(first_sentence):] if len(combined) > len(first_sentence) else ""

            # Create a natural flow
            if first_sentence.strip():
                # If first sentence mentions preparation/synthesis, integrate DOI naturally
                if any(word in first_sentence.lower() for word in ['prepare', 'synthesis', 'method']):
                    result = f"{doi_prefix}the authors describe that {first_sentence.lower()}{rest_of_content}"
                else:
                    result = f"{doi_prefix}{first_sentence}{rest_of_content}"
            else:
                result = f"{doi_prefix}the synthesis procedure is described as follows:\n\n{combined}"
        else:
            result = f"{doi_prefix}the synthesis procedure is detailed in the supplementary materials."

        return result

    def _clean_synthesis_text(self, text: str) -> str:
        """Clean and format synthesis text."""
        # Remove excessive line breaks
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)

        # Remove separator lines
        text = re.sub(r'^\s*[-=*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # Remove page numbers and headers
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*Page\s+\d+.*$', '', text, flags=re.MULTILINE)

        # Remove excessive whitespace
        text = re.sub(r'[ \t]+', ' ', text)

        # Remove DOI and source information from beginning
        text = re.sub(r'^DOI:.*?\n', '', text)
        text = re.sub(r'^Source:.*?\n', '', text)
        text = re.sub(r'^-{10,}.*?\n', '', text)

        return text.strip()

    def read_file_safe(self, file_path: Path) -> Optional[str]:
        """Safely read file with multiple encoding attempts."""
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                return None

        print(f"Could not read {file_path} with any encoding")
        return None

    def process_file_pairs(self) -> List[Dict]:
        """Process matching DOI files and create question-answer pairs."""
        qa_pairs = []

        # Support both naming patterns: DOI_synthesis.txt and DOI-synthesis.txt
        synthesis_patterns = ["*_synthesis.txt", "*-synthesis.txt"]
        synthesis_files = []

        for pattern in synthesis_patterns:
            synthesis_files.extend(list(self.synthesis_folder.glob(pattern)))

        print(f"Found {len(synthesis_files)} synthesis files")

        for synthesis_file in synthesis_files:
            # Extract DOI from filename (handle both patterns)
            if "_synthesis" in synthesis_file.stem:
                doi_filename = synthesis_file.stem.replace("_synthesis", "")
            else:
                doi_filename = synthesis_file.stem.replace("-synthesis", "")

            # Look for corresponding paper file
            paper_file = self.papers_folder / f"{doi_filename}.txt"

            if paper_file.exists():
                try:
                    # Read files
                    synthesis_content = self.read_file_safe(synthesis_file)
                    paper_content = self.read_file_safe(paper_file)

                    if not synthesis_content or not paper_content:
                        print(f"Could not read files for {doi_filename}")
                        continue

                    # Extract information
                    title = self.extract_title_from_paper(paper_content)
                    question = self.generate_question_from_title(title)
                    answer = self.extract_synthesis_methods(synthesis_content, doi_filename)  # Pass DOI

                    # Create QA pair in the conversation format
                    if answer.strip():
                        qa_pair = {
                            "conversation": [
                                {
                                    "input": question,
                                    "output": answer
                                }
                            ]
                        }
                        qa_pairs.append(qa_pair)

                        print(f"✓ Processed: {doi_filename}")
                        print(f"  Title: {title}")
                        print(f"  Question: {question}")
                        print(f"  Answer starts with DOI: {answer[:100]}...")
                        print("-" * 80)

                except Exception as e:
                    print(f"✗ Error processing {doi_filename}: {str(e)}")
            else:
                print(f"✗ No matching paper file found for {synthesis_file.name}")

        return qa_pairs

    def save_to_json(self, qa_pairs: List[Dict]):
        """Save question-answer pairs to JSON file."""
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, indent=4, ensure_ascii=False)

        print(f"\n✓ Saved {len(qa_pairs)} question-answer pairs to {self.output_file}")

    def preview_results(self, num_pairs: int = 3):
        """Preview the generated Q&A pairs."""
        if not os.path.exists(self.output_file):
            print("No output file found to preview")
            return

        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"\n📋 Preview of Q&A pairs:")
            print("=" * 100)

            for i, pair in enumerate(data[:num_pairs]):
                conversation = pair['conversation'][0]
                print(f"\nQ{i + 1}: {conversation['input']}")
                print(f"A{i + 1}: {conversation['output'][:400]}...")
                if len(conversation['output']) > 400:
                    print("     [... content continues ...]")
                print("-" * 100)

        except Exception as e:
            print(f"Error previewing results: {str(e)}")

    def run(self):
        """Run the complete processing pipeline."""
        print("🔬 Starting Catalyst Synthesis Q&A Generation")
        print("=" * 60)
        print(f"📁 Synthesis folder: {self.synthesis_folder}")
        print(f"📁 Papers folder: {self.papers_folder}")
        print(f"📄 Output file: {self.output_file}")

        # Check folders exist
        if not self.synthesis_folder.exists():
            raise FileNotFoundError(f"Synthesis folder not found: {self.synthesis_folder}")
        if not self.papers_folder.exists():
            raise FileNotFoundError(f"Papers folder not found: {self.papers_folder}")

        # Process files
        qa_pairs = self.process_file_pairs()

        if qa_pairs:
            # Save results
            self.save_to_json(qa_pairs)

            # Show preview
            self.preview_results()

            print(f"\n🎯 Successfully created {len(qa_pairs)} question-answer pairs!")
            print(f"📁 Output saved to: {self.output_file}")
        else:
            print("\n❌ No valid question-answer pairs were created.")


def test_with_uploaded_files():
    """Test the processor with the specific uploaded files."""
    # Create test data based on uploaded files
    test_synthesis_content = """DOI: 10.1038/s41557-019-0345-3
Source: supplementary PDF

Catalysts Preparation
In this work, titanium dioxide in anatase form from Millennium (G5, 100 % anatase, ~270 m2/g) was used as the support for various gold/titania catalysts. Prior to each catalyst preparation, the support powder was calcined in air at 400 °C for 10 h, then stored in dark vacuum. All other chemicals, including Au(OH)3, HAuCl4, NaOH pellets, and (NH4)2CO3, were supplied by Alfar Aesar.

To prepare the Au1-Ox-Na9-(OH)y solution, the proper amount of Au(OH)3 powder was suspended in 30 mL of H2O with O2 sparging and heated up to 80 °C. NaOH powder (atomic ratio of Au:Na=1:9) was added into the slurry at the same temperature. The mixture was refluxed at 80 °C overnight to get a transparent solution (colorless at lower concentrations – light yellow at higher concentrations). The atomic ratio of the Au:Na was set at 1:9 in order to have multi-coordinated Au1–Ox-Na clusters to adequately stabilize the cationic gold atom, as determined experimentally and by DFT calculations published recently.

The Au1-Ox-Na9-(OH)y/TiO2 catalysts were prepared by IWI of the gold solution at room temperature (RT) in air. The solution was concentrated by heating followed by drying at 200 °C with N2 protection, and then the sample was further dried in vacuum overnight at 80 °C. The powder samples were stored in dark vacuum before any activity tests and characterization."""

    test_paper_content = """Single-atom gold oxo-clusters prepared in alkaline solutions catalyse the heterogeneous methanol self-coupling reactions | Nature Chemistry

Article
Published: 21 October 2019
Single-atom gold oxo-clusters prepared in alkaline solutions catalyse the heterogeneous methanol self-coupling reactions

Abstract
In an effort to obtain the maximum atom efficiency, research on heterogeneous single-atom catalysts has intensified recently. Here we report a facile one-pot synthesis of inorganometallic mononuclear gold complexes formed in alkaline solutions as robust and versatile single-atom gold catalysts."""

    # Create test folders and files
    os.makedirs("test_synthesis", exist_ok=True)
    os.makedirs("test_papers", exist_ok=True)

    with open("test_synthesis/10.1038_s41557-019-0345-3_synthesis.txt", "w", encoding="utf-8") as f:
        f.write(test_synthesis_content)

    with open("test_papers/10.1038_s41557-019-0345-3.txt", "w", encoding="utf-8") as f:
        f.write(test_paper_content)

    # Run processor
    processor = CatalystSynthesisProcessor(
        synthesis_folder="test_synthesis",
        papers_folder="test_papers",
        output_file="test_catalyst_qa.json"
    )
    processor.run()

    print("\n🧪 Test completed! Check 'test_catalyst_qa.json' for results.")


def main():
    """Main function with configurable paths."""
    # Define folder paths
    synthesis_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\synthesis_outputs"  # Folder containing DOI-synthesis.txt files
    papers_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\articles_txt"  # Folder containing DOI.txt files
    output_file = "catalyst_synthesis_qa.json"

    try:
        processor = CatalystSynthesisProcessor(
            synthesis_folder=synthesis_folder,
            papers_folder=papers_folder,
            output_file=output_file
        )
        processor.run()

    except Exception as e:
        print(f"❌ Error: {e}")
        print("\n💡 Make sure your folder structure is correct:")
        print(f"  {synthesis_folder}/")
        print("    DOI_synthesis.txt (or DOI-synthesis.txt)")
        print(f"  {papers_folder}/")
        print("    DOI.txt")


if __name__ == "__main__":
    # Uncomment the next line to test with example data
    # test_with_uploaded_files()

    main()