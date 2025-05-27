import os
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class CatalystSynthesisProcessor:
    """Enhanced processor for catalyst synthesis Q&A generation."""

    def __init__(self, synthesis_folder: str, papers_folder: str, output_file: str = "catalyst_synthesis_qa.json"):
        self.synthesis_folder = Path(synthesis_folder)
        self.papers_folder = Path(papers_folder)
        self.output_file = output_file
        self.qa_pairs = []

        # Enhanced patterns for better extraction
        self.catalyst_indicators = [
            'catalyst', 'atom', 'particle', 'cluster', 'species', 'material',
            'pt', 'au', 'pd', 'rh', 'ir', 'ru', 'ni', 'co', 'fe', 'cu', 'ag', 'zn', 'mn',
            'single', 'nano', 'oxo', 'supported', 'dispersed', 'isolated', 'atomic',
            'bimetallic', 'trimetallic', 'alloy', 'oxide', 'carbide', 'nitride'
        ]

        self.stop_words = [
            'prepared', 'synthesized', 'synthesised', 'made', 'fabricated', 'developed',
            'catalyse', 'catalyze', 'catalysed', 'catalyzed', 'catalysing', 'catalyzing',
            'for', 'in', 'on', 'with', 'by', 'via', 'through', 'using', 'under',
            'demonstrate', 'show', 'exhibit', 'display', 'enable', 'facilitate',
            'applied', 'used', 'employed', 'utilized', 'tested', 'evaluated',
            'towards', 'toward', 'during', 'upon', 'after', 'before',
            'promote', 'enhance', 'improve', 'boost', 'increase', 'study', 'studies'
        ]

    def extract_title_from_paper(self, paper_content: str) -> str:
        """Extract the title from the full paper content with enhanced patterns."""
        lines = paper_content.split('\n')

        # Enhanced title extraction patterns
        title_patterns = [
            # Direct title patterns
            r'(?:Title:|title:)\s*(.+)',
            r'(?:Article.*?)(\b[A-Z][^.!?]*?catalyst[^.!?]*)',
            r'(?:Published.*?)(\b[A-Z][^.!?]*?synthesis[^.!?]*)',
            # Pattern for Nature Chemistry format
            r'Single-atom.*?reactions',
            r'Atomically dispersed.*?(?=\||\n|Abstract)',
        ]

        # Try pattern matching first
        for pattern in title_patterns:
            match = re.search(pattern, paper_content, re.IGNORECASE | re.MULTILINE)
            if match:
                title = match.group(1) if match.lastindex else match.group(0)
                title = re.sub(r'\s+', ' ', title).strip()
                if len(title) > 20:
                    return title

        # Line-by-line analysis
        for i, line in enumerate(lines[:50]):
            line = line.strip()

            # Skip unwanted lines
            if not line or any(skip in line.lower() for skip in [
                'abstract', 'introduction', 'article', 'nature chemistry',
                'http', 'doi:', 'skip to', 'thank you', 'download pdf',
                'published:', 'received:', 'accepted:', 'volume', 'issue'
            ]):
                continue

            # Skip very short or very long lines
            if len(line) < 20 or len(line) > 300:
                continue

            # Look for title-like content
            if self._is_likely_title(line):
                return re.sub(r'\s+', ' ', line).strip()

        # Fallback: look for catalyst/synthesis related content
        for line in lines[:100]:
            line = line.strip()
            if (len(line) > 30 and len(line) < 200 and
                    any(keyword in line.lower() for keyword in ['catalyst', 'synthesis', 'preparation'])):
                return re.sub(r'\s+', ' ', line).strip()

        return "Catalyst synthesis"

    def _is_likely_title(self, line: str) -> bool:
        """Determine if a line is likely to be a title."""
        # Should contain catalyst-related terms
        has_catalyst_terms = any(term in line.lower() for term in self.catalyst_indicators)

        # Should not end with period (most titles don't)
        no_period_end = not line.endswith('.')

        # Should not start with common non-title words
        not_starting_badly = not any(line.lower().startswith(word) for word in [
            'published', 'received', 'the', 'this', 'these', 'we', 'here', 'in'
        ])

        # Should have reasonable capitalization
        has_capitals = sum(1 for c in line if c.isupper()) >= 2

        return has_catalyst_terms and no_period_end and not_starting_badly and has_capitals

    def extract_catalyst_from_title(self, title: str) -> str:
        """Extract catalyst name from title with enhanced logic."""
        # Split title into words
        words = title.split()

        # Find the first stop word
        stop_index = len(words)
        for i, word in enumerate(words):
            clean_word = re.sub(r'[^\w]', '', word.lower())
            if clean_word in self.stop_words:
                stop_index = i
                break

        # Extract words before the stop word
        catalyst_words = words[:stop_index]

        if not catalyst_words:
            return "the catalyst"

        catalyst_phrase = ' '.join(catalyst_words).strip()
        catalyst_phrase = re.sub(r'[,.:;!?]+$', '', catalyst_phrase)

        # Enhanced pattern matching for specific catalyst types
        if len(catalyst_phrase.split()) < 2 or not self._contains_catalyst_indicators(catalyst_phrase):
            catalyst_phrase = self._extract_with_patterns(title)

        return catalyst_phrase if catalyst_phrase else "the catalyst"

    def _contains_catalyst_indicators(self, phrase: str) -> bool:
        """Check if phrase contains catalyst-related terms."""
        return any(indicator in phrase.lower() for indicator in self.catalyst_indicators)

    def _extract_with_patterns(self, title: str) -> str:
        """Extract catalyst using specific patterns."""
        first_half = ' '.join(title.split()[:len(title.split()) // 2])

        patterns = [
            r'\b(single-atom\s+[A-Za-z]+(?:\s+[A-Za-z-]+)*)',
            r'\b([A-Za-z]+\s+oxo-clusters?)',
            r'\b([A-Za-z]+\s+nanoparticles?)',
            r'\b([A-Za-z]+/[A-Za-z0-9α-ωβ-]+)',
            r'\b(\d+%?\s*[A-Za-z]+/[A-Za-z0-9α-ωβ-]+)',
            r'\b(atomically\s+dispersed\s+[A-Za-z]+)',
            r'\b([A-Za-z]+\s+clusters?)',
            r'\b([A-Za-z]+-[A-Za-z]+\s+catalysts?)',
            r'\b(bimetallic\s+[A-Za-z]+)',
            r'\b([A-Za-z]+\s+single\s+atoms?)',
        ]

        for pattern in patterns:
            match = re.search(pattern, first_half, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return ""

    def generate_question_from_catalyst(self, catalyst_name: str) -> str:
        """Generate synthesis question from catalyst name."""
        catalyst_name = catalyst_name.strip()
        catalyst_name = re.sub(r'[.!?]+$', '', catalyst_name)

        if catalyst_name.lower() == "the catalyst":
            return "How to synthesize the catalyst"

        # Capitalize first letter if needed
        if catalyst_name and catalyst_name[0].islower():
            catalyst_name = catalyst_name[0].upper() + catalyst_name[1:]

        return f"How to synthesize {catalyst_name}"

    def extract_synthesis_methods(self, synthesis_content: str) -> str:
        """Extract synthesis methods with improved section detection."""
        # Enhanced patterns for method sections
        methods_patterns = [
            r'(?:catalyst\s+preparation|synthesis|preparation|experimental|materials\s+and\s+methods).*?(?=\n\s*(?:[A-Z][A-Z\s]*\n|characterization|activity|results|references|discussion)|\Z)',
            r'(?:^|\n)(.*?(?:preparation|synthesis).*?)(?=\n\s*[A-Z][A-Z\s]*\n|\Z)',
        ]

        synthesis_sections = []

        # Try to find specific sections
        for pattern in methods_patterns:
            matches = re.finditer(pattern, synthesis_content, re.IGNORECASE | re.DOTALL | re.MULTILINE)
            for match in matches:
                section = match.group().strip()
                if len(section) > 100:
                    synthesis_sections.append(section)

        if synthesis_sections:
            combined = '\n\n'.join(synthesis_sections)
        else:
            # If no sections found, look for synthesis-related paragraphs
            paragraphs = synthesis_content.split('\n\n')
            relevant_paragraphs = []

            for para in paragraphs:
                if (len(para) > 100 and
                        any(keyword in para.lower() for keyword in [
                            'prepare', 'synthesis', 'method', 'procedure', 'solution',
                            'temperature', 'heating', 'catalyst', 'precursor', 'support'
                        ])):
                    relevant_paragraphs.append(para)

            combined = '\n\n'.join(relevant_paragraphs) if relevant_paragraphs else synthesis_content

        # Clean up the text
        combined = self._clean_synthesis_text(combined)
        return combined

    def _clean_synthesis_text(self, text: str) -> str:
        """Clean and format synthesis text."""
        # Remove excessive line breaks
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

        # Remove separator lines
        text = re.sub(r'^\s*[-=*_]{3,}\s*$', '', text, flags=re.MULTILINE)

        # Remove page numbers and headers
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

        # Remove excessive whitespace
        text = re.sub(r'[ \t]+', ' ', text)

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

        # Support both naming patterns
        synthesis_patterns = ["*-synthesis.txt", "*_synthesis.txt"]
        synthesis_files = []

        for pattern in synthesis_patterns:
            synthesis_files.extend(list(self.synthesis_folder.glob(pattern)))

        print(f"Found {len(synthesis_files)} synthesis files")

        for synthesis_file in synthesis_files:
            # Extract DOI from filename (handle both patterns)
            if "-synthesis" in synthesis_file.stem:
                doi_filename = synthesis_file.stem.replace("-synthesis", "")
            else:
                doi_filename = synthesis_file.stem.replace("_synthesis", "")

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
                    catalyst_name = self.extract_catalyst_from_title(title)
                    question = self.generate_question_from_catalyst(catalyst_name)
                    answer = self.extract_synthesis_methods(synthesis_content)

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
                        print(f"  Title: {title[:80]}...")
                        print(f"  Catalyst: {catalyst_name}")
                        print(f"  Question: {question}")
                        print(f"  Answer length: {len(answer)} characters")
                        print("-" * 70)

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

            print(f"\n📋 Previewing first {min(num_pairs, len(data))} Q&A pairs:")
            print("=" * 80)

            for i, pair in enumerate(data[:num_pairs]):
                conversation = pair['conversation'][0]
                print(f"Q{i + 1}: {conversation['input']}")
                print(f"A{i + 1}: {conversation['output'][:300]}...")
                if len(conversation['output']) > 300:
                    print("     [... content truncated ...]")
                print("-" * 80)

        except Exception as e:
            print(f"Error previewing results: {str(e)}")

    def validate_output(self):
        """Validate the structure of the generated JSON file."""
        if not os.path.exists(self.output_file):
            print("No output file found to validate")
            return

        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"\n🔍 Validation Results:")
            print(f"✓ JSON contains {len(data)} entries")

            valid_entries = 0
            for i, entry in enumerate(data):
                if ('conversation' in entry and
                        isinstance(entry['conversation'], list) and
                        len(entry['conversation']) > 0):

                    conv = entry['conversation'][0]
                    if 'input' in conv and 'output' in conv and conv['input'] and conv['output']:
                        valid_entries += 1
                    else:
                        print(f"✗ Entry {i + 1} has invalid conversation structure")
                else:
                    print(f"✗ Entry {i + 1} missing or invalid conversation field")

            print(f"✓ {valid_entries}/{len(data)} entries have valid structure")

            if valid_entries == len(data):
                print("🎉 All entries are valid!")
            else:
                print(f"⚠️  {len(data) - valid_entries} entries have issues")

        except Exception as e:
            print(f"Error validating output: {str(e)}")

    def run(self):
        """Run the complete processing pipeline."""
        print("🔬 Starting Catalyst Synthesis Q&A Generation")
        print("=" * 50)
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

            # Show results
            self.preview_results()
            self.validate_output()

            print(f"\n🎯 Successfully created {len(qa_pairs)} question-answer pairs!")
        else:
            print("\n❌ No valid question-answer pairs were created.")


def test_catalyst_extraction():
    """Test catalyst extraction with sample titles."""
    processor = CatalystSynthesisProcessor(".", ".")  # Dummy paths for testing

    test_titles = [
        "Single-atom gold oxo-clusters prepared in alkaline solutions catalyse the heterogeneous methanol self-coupling reactions",
        "Pt/α-MoC catalysts for low-temperature hydrogen production from water and methanol",
        "Atomically dispersed Ni catalysts on nitrogen-doped carbon supports for electrochemical CO2 reduction",
        "2%Pt/β-Mo2C catalyst synthesized by stepwise precipitation method",
        "Au nanoparticles supported on TiO2 for selective oxidation reactions",
        "Isolated single-atom Rh catalysts anchored on zeolite supports enable efficient hydrogenation",
        "Bimetallic PtRu nanoparticles on carbon supports for methanol oxidation reactions",
        "Iron-nitrogen-carbon single-atom catalysts prepared via ball-milling method",
        "Pd-based catalysts synthesized using wet impregnation technique",
        "Co oxo-clusters stabilized by alkaline earth metals catalyze CO2 reduction"
    ]

    print("🧪 Testing catalyst extraction from titles:")
    print("=" * 80)

    for title in test_titles:
        catalyst_name = processor.extract_catalyst_from_title(title)
        question = processor.generate_question_from_catalyst(catalyst_name)
        print(f"Title: {title}")
        print(f"Extracted: {catalyst_name}")
        print(f"Question: {question}")
        print("-" * 80)


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
        print("    DOI-synthesis.txt (or DOI_synthesis.txt)")
        print(f"  {papers_folder}/")
        print("    DOI.txt")


if __name__ == "__main__":
    # Uncomment to test catalyst extraction
    # test_catalyst_extraction()

    main()