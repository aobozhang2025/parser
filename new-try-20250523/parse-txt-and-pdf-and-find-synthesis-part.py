import pandas as pd
import os
import re
from pathlib import Path
import PyPDF2
from typing import Optional, List, Tuple


class CatalystSynthesisParser:
    def __init__(self, csv_file: str, supplementary_pdf_folder: str, main_text_folder: str, output_folder: str):
        """
        Initialize the parser with folder paths and create output directory.

        Args:
            csv_file: Path to CSV file with DOI column
            supplementary_pdf_folder: Folder containing supplementary PDFs
            main_text_folder: Folder containing main paper text files
            output_folder: Folder to save parsed synthesis sections
        """
        self.csv_file = csv_file
        self.supplementary_pdf_folder = Path(supplementary_pdf_folder)
        self.main_text_folder = Path(main_text_folder)
        self.output_folder = Path(output_folder)

        # Create output folder if it doesn't exist
        self.output_folder.mkdir(exist_ok=True)

        # Keywords to identify figure captions and references to exclude
        self.exclude_patterns = [
            r'fig\.\s*\d+',  # Fig. 1, fig. 2, etc.
            r'figure\s*\d+',  # Figure 1, figure 2, etc.
            r'ref\.\s*\d+',  # Ref. 1, ref. 2, etc.
            r'reference\s*\d+',  # Reference 1, reference 2, etc.
            r'\[\d+\]',  # [1], [2], etc.
            r'\(\d+\)',  # (1), (2), etc. - be careful with this one
            r'see\s+fig',  # "see fig", "see figure"
            r'shown\s+in\s+fig',  # "shown in fig"
            r'depicted\s+in\s+fig'  # "depicted in fig"
        ]

    def clean_doi(self, doi: str) -> str:
        """Clean DOI string to be filesystem-safe."""
        if pd.isna(doi) or not doi:
            return ""
        # Replace problematic characters for filenames
        cleaned = str(doi).replace('/', '_').replace('\\', '_').replace(':', '_')
        cleaned = re.sub(r'[<>:"|?*]', '_', cleaned)
        return cleaned.strip()

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file using PyPDF2."""
        try:
            text = ""
            with open(pdf_path, 'rb') as pdf_file:
                pdf_reader = PyPDF2.PdfReader(pdf_file)

                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            print(f"Error reading PDF {pdf_path}: {e}")
            return ""

    def read_text_file(self, file_path: Path) -> str:
        """Read text from a text file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading text file {file_path}: {e}")
            return ""

    def extract_synthesis_section(self, content: str) -> Optional[str]:
        """Extract the synthesis/preparation section from the text content."""
        if not content:
            return None

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

    def clean_synthesis_text(self, text: str) -> str:
        """Remove figure captions and references from synthesis text."""
        if not text:
            return ""

        cleaned_text = text

        # Remove text matching exclude patterns
        for pattern in self.exclude_patterns:
            cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.IGNORECASE)

        # Remove lines that are likely figure captions (start with Fig or Figure)
        lines = cleaned_text.split('\n')
        filtered_lines = []

        for line in lines:
            line_lower = line.strip().lower()
            # Skip lines that start with figure references
            if (line_lower.startswith('fig.') or
                    line_lower.startswith('figure') or
                    line_lower.startswith('ref.') or
                    line_lower.startswith('reference')):
                continue
            filtered_lines.append(line)

        cleaned_text = '\n'.join(filtered_lines)

        # Clean up extra whitespace
        cleaned_text = re.sub(r'\n\s*\n', '\n\n', cleaned_text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

        return cleaned_text.strip()

    def save_synthesis_content(self, doi: str, content: str, source_type: str) -> bool:
        """
        Save synthesis content to a text file.

        Args:
            doi: DOI of the paper
            content: Synthesis content to save
            source_type: 'supplementary' or 'main' to determine filename format

        Returns:
            True if saved successfully, False otherwise
        """
        if not content.strip():
            return False

        cleaned_doi = self.clean_doi(doi)
        if not cleaned_doi:
            print(f"Invalid DOI: {doi}")
            return False

        # Different filename formats based on source
        if source_type == 'supplementary':
            filename = f"{cleaned_doi}-synthesis.txt"
        else:  # main text
            filename = f"{cleaned_doi}_synthesis.txt"

        output_path = self.output_folder / filename

        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"DOI: {doi}\n")
                f.write(f"Source: {source_type}\n")
                f.write("=" * 50 + "\n\n")
                f.write(content)

            print(f"Saved synthesis content for DOI {doi} to {filename}")
            return True

        except Exception as e:
            print(f"Error saving synthesis content for DOI {doi}: {e}")
            return False

    def process_single_doi(self, doi: str) -> bool:
        """
        Process a single DOI to extract synthesis information.

        Args:
            doi: DOI to process

        Returns:
            True if synthesis content was found and saved, False otherwise
        """
        if not doi or pd.isna(doi):
            return False

        cleaned_doi = self.clean_doi(doi)
        if not cleaned_doi:
            return False

        print(f"Processing DOI: {doi}")

        # Step 1: Look for supplementary PDF
        supplementary_pdf_name = f"{cleaned_doi}_supplementary.pdf"
        supplementary_pdf_path = self.supplementary_pdf_folder / supplementary_pdf_name

        synthesis_content = ""
        source_type = ""

        if supplementary_pdf_path.exists():
            print(f"  Found supplementary PDF: {supplementary_pdf_name}")
            pdf_text = self.extract_text_from_pdf(supplementary_pdf_path)

            if pdf_text:
                synthesis_section = self.extract_synthesis_section(pdf_text)
                if synthesis_section:
                    synthesis_content = synthesis_section
                    source_type = 'supplementary'
                    print(f"  Found synthesis content in supplementary PDF")

        # Step 2: If no synthesis found in supplementary PDF, look in main text files
        if not synthesis_content:
            print(f"  No synthesis content in supplementary PDF, checking main text files...")

            # Try different possible text file names
            possible_names = [
                f"{cleaned_doi}.txt",
                f"{doi.replace('/', '_')}.txt",
                f"{doi.replace('/', '-')}.txt"
            ]

            main_text_path = None
            for name in possible_names:
                potential_path = self.main_text_folder / name
                if potential_path.exists():
                    main_text_path = potential_path
                    break

            if main_text_path:
                print(f"  Found main text file: {main_text_path.name}")
                main_text = self.read_text_file(main_text_path)

                if main_text:
                    synthesis_section = self.extract_synthesis_section(main_text)
                    if synthesis_section:
                        synthesis_content = synthesis_section
                        source_type = 'main'
                        print(f"  Found synthesis content in main text file")
            else:
                print(f"  No main text file found for DOI {doi}")

        # Step 3: Clean and save synthesis content
        if synthesis_content:
            cleaned_content = self.clean_synthesis_text(synthesis_content)
            if cleaned_content:
                return self.save_synthesis_content(doi, cleaned_content, source_type)

        print(f"  No synthesis content found for DOI {doi}")
        return False

    def process_all_dois(self) -> Tuple[int, int]:
        """
        Process all DOIs from the CSV file.

        Returns:
            Tuple of (successful_count, total_count)
        """
        try:
            # Read CSV file
            df = pd.read_csv(self.csv_file)

            if 'DOI' not in df.columns:
                print("Error: 'DOI' column not found in CSV file")
                return 0, 0

            dois = df['DOI'].dropna().unique()
            total_count = len(dois)
            successful_count = 0

            print(f"Processing {total_count} unique DOIs...")

            for doi in dois:
                if self.process_single_doi(doi):
                    successful_count += 1

            print(f"\nCompleted processing:")
            print(f"  Total DOIs: {total_count}")
            print(f"  Successfully processed: {successful_count}")
            print(f"  Failed: {total_count - successful_count}")
            print(f"  Output folder: {self.output_folder}")

            return successful_count, total_count

        except Exception as e:
            print(f"Error processing CSV file: {e}")
            return 0, 0


def main():
    """
    Main function to run the catalyst synthesis parser.
    Modify the paths below according to your folder structure.
    """

    # Configuration - UPDATE THESE PATHS
    csv_file = "D:\\pycharm-project\\parser\\single-atom-nature.csv"  # Your CSV file with DOI column
    supplementary_pdf_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\supplementary_pdfs\\"  # Folder with supplementary PDFs
    main_text_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\articles_txt\\"  # Folder with main paper text files
    output_folder = "D:\\pycharm-project\parser\\new-try-20250523\\synthesis_output_claude\\"  # Output folder for synthesis sections

    # Verify input paths exist
    if not os.path.exists(csv_file):
        print(f"Error: CSV file '{csv_file}' not found")
        return

    if not os.path.exists(supplementary_pdf_folder):
        print(f"Error: Supplementary PDF folder '{supplementary_pdf_folder}' not found")
        return

    if not os.path.exists(main_text_folder):
        print(f"Error: Main text folder '{main_text_folder}' not found")
        return

    # Initialize and run parser
    parser = CatalystSynthesisParser(
        csv_file=csv_file,
        supplementary_pdf_folder=supplementary_pdf_folder,
        main_text_folder=main_text_folder,
        output_folder=output_folder
    )

    successful, total = parser.process_all_dois()

    if successful > 0:
        print(f"\nSuccess! Extracted synthesis information for {successful}/{total} papers.")
        print(f"Check the '{output_folder}' folder for the results.")
    else:
        print("\nNo synthesis information could be extracted from any papers.")


if __name__ == "__main__":
    main()