import pandas as pd
import os
import re
from pathlib import Path
import pdfplumber
from typing import List, Optional, Tuple
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class CatalystSynthesisExtractor:
    def __init__(self, csv_file: str, supplementary_pdf_folder: str, main_text_folder: str, output_folder: str):
        """
        Initialize the extractor with folder paths

        Args:
            csv_file: Path to CSV file with DOI column
            supplementary_pdf_folder: Folder containing supplementary PDFs
            main_text_folder: Folder containing main text files
            output_folder: Output folder for synthesis files
        """
        self.csv_file = csv_file
        self.supplementary_pdf_folder = Path(supplementary_pdf_folder)
        self.main_text_folder = Path(main_text_folder)
        self.output_folder = Path(output_folder)

        # Create output folder if it doesn't exist
        self.output_folder.mkdir(exist_ok=True)

        # Keywords to identify synthesis sections
        self.synthesis_keywords = [
            'catalyst preparation', 'catalyst synthesis', 'synthesis of catalyst',
            'preparation of catalyst', 'materials synthesis', 'experimental section',
            'materials and methods', 'synthesis procedure', 'preparation procedure',
            'catalyst fabrication', 'sample preparation', 'synthesis method',
            'catalysts preparation', 'catalysts synthesis', 'experimental methods',
            'sample synthesis', 'material preparation'
        ]

        # Section headers that typically contain synthesis info
        self.section_patterns = [
            r'(?i)^\s*\d*\.?\s*(catalyst|material|sample)\s*(preparation|synthesis|fabrication)',
            r'(?i)^\s*\d*\.?\s*(synthesis|preparation)\s*(of|procedure)',
            r'(?i)^\s*\d*\.?\s*(experimental|materials)\s*(section|methods)',
            r'(?i)^\s*\d*\.?\s*methods?\s*$',
            r'(?i)^\s*\d*\.?\s*(sample|catalyst)\s*preparation\s*$'
        ]

    def clean_doi(self, doi: str) -> str:
        """Clean DOI for use in filename"""
        if pd.isna(doi):
            return ""
        # Remove common prefixes and clean for filename
        doi = str(doi).replace('doi:', '').replace('DOI:', '').replace('https://doi.org/', '')
        # Replace characters that can't be in filenames
        doi = re.sub(r'[<>:"/\\|?*]', '_', doi)
        return doi.strip()

    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF file"""
        try:
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            logger.error(f"Error extracting text from {pdf_path}: {e}")
            return ""

    def clean_text_content(self, text: str) -> str:
        """Remove figure captions, table captions, references, and table of contents"""

        # Remove table of contents / list of contents sections
        text = re.sub(r'(?i)^\s*(table\s+of\s+)?contents?\s*\.{2,}.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*list\s+of\s+(figures?|tables?)\s*\.{2,}.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*\d+\.?\s*(introduction|abstract|conclusion)\s*\.{2,}\s*\d+\s*$', '', text,
                      flags=re.MULTILINE)

        # Remove figure captions and references
        text = re.sub(r'(?i)(figure|fig\.?)\s*\d+[a-z]?[.:]\s*[^\n]*(?:\n[^\n]*){0,3}', '', text)
        text = re.sub(r'(?i)\(?(figure|fig\.?)\s*\d+[a-z]?\)?', '', text)
        text = re.sub(r'(?i)(supplementary\s+)?(figure|fig\.?)\s*s?\d+[a-z]?', '', text)

        # Remove table captions and references
        text = re.sub(r'(?i)(table)\s*\d+[a-z]?[.:]\s*[^\n]*(?:\n[^\n]*){0,3}', '', text)
        text = re.sub(r'(?i)\(?(table)\s*\d+[a-z]?\)?', '', text)
        text = re.sub(r'(?i)(supplementary\s+)?(table)\s*s?\d+[a-z]?', '', text)

        # Remove reference citations
        text = re.sub(r'\[\d+(?:[-,]\d+)*\]', '', text)
        text = re.sub(r'\(\d+(?:[-,]\d+)*\)', '', text)
        text = re.sub(r'(?i)ref\.?\s*\d+', '', text)
        text = re.sub(r'(?i)\(ref\.?\s*\d+\)', '', text)

        # Remove reference sections entirely
        # Look for "References" section and remove everything after it
        ref_patterns = [
            r'(?i)^\s*references?\s*$.*$',
            r'(?i)^\s*bibliography\s*$.*$',
            r'(?i)^\s*\d+\.?\s*references?\s*$.*$',
            r'(?i)^\s*literature\s+cited\s*$.*$'
        ]

        for pattern in ref_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.DOTALL)

        # Remove author information and affiliations typically found at the beginning
        text = re.sub(r'(?i)^\s*\*?\s*corresponding\s+author.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*e-?mail:.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*received:.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*accepted:.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(?i)^\s*published:.*$', '', text, flags=re.MULTILINE)

        # Remove page numbers and headers/footers
        text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*page\s+\d+\s*$', '', text, flags=re.MULTILINE)

        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        return text.strip()

    def is_reference_section(self, text: str) -> bool:
        """Check if a text block is likely a reference section"""
        text_lower = text.lower()
        ref_indicators = [
            'doi:', 'http://', 'https://', 'journal', 'vol.', 'pp.',
            'et al.', 'proceedings', 'conference', 'publisher'
        ]

        # If text has many reference indicators, it's likely a reference section
        indicator_count = sum(1 for indicator in ref_indicators if indicator in text_lower)
        return indicator_count >= 3

    def find_synthesis_sections(self, text: str) -> List[str]:
        """Find and extract synthesis-related sections from text"""
        synthesis_sections = []
        lines = text.split('\n')

        current_section = []
        in_synthesis_section = False
        section_title = ""

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Skip if this looks like a reference section
            if self.is_reference_section(line_stripped):
                continue

            # Check if line matches synthesis section patterns
            is_synthesis_header = False
            for pattern in self.section_patterns:
                if re.match(pattern, line_stripped):
                    is_synthesis_header = True
                    break

            # Also check for keywords in the line
            if not is_synthesis_header:
                line_lower = line_stripped.lower()
                for keyword in self.synthesis_keywords:
                    if keyword in line_lower and len(line_stripped) < 200:  # Likely a header
                        is_synthesis_header = True
                        break

            if is_synthesis_header:
                # Save previous section if it was a synthesis section
                if in_synthesis_section and current_section:
                    section_content = '\n'.join(current_section).strip()
                    if section_content and not self.is_reference_section(section_content):
                        synthesis_sections.append(f"{section_title}\n{section_content}")

                # Start new section
                current_section = []
                in_synthesis_section = True
                section_title = line_stripped

            elif in_synthesis_section:
                # Check if we've reached a new major section (likely end of synthesis)
                if (re.match(r'^\d+\.?\s+[A-Z]', line_stripped) and
                        len(line_stripped) < 100 and
                        not any(keyword in line_stripped.lower() for keyword in self.synthesis_keywords)):
                    # This looks like a new section header, end synthesis section
                    if current_section:
                        section_content = '\n'.join(current_section).strip()
                        if section_content and not self.is_reference_section(section_content):
                            synthesis_sections.append(f"{section_title}\n{section_content}")
                    in_synthesis_section = False
                    current_section = []
                else:
                    current_section.append(line)

        # Don't forget the last section
        if in_synthesis_section and current_section:
            section_content = '\n'.join(current_section).strip()
            if section_content and not self.is_reference_section(section_content):
                synthesis_sections.append(f"{section_title}\n{section_content}")

        return synthesis_sections

    def extract_synthesis_from_text(self, text: str) -> str:
        """Extract synthesis information from text"""
        # Clean text first (remove figures, tables, references, etc.)
        clean_text = self.clean_text_content(text)

        # Find synthesis sections
        synthesis_sections = self.find_synthesis_sections(clean_text)

        if synthesis_sections:
            return '\n\n'.join(synthesis_sections)

        # If no clear sections found, look for paragraphs containing synthesis keywords
        paragraphs = clean_text.split('\n\n')
        synthesis_paragraphs = []

        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            # Skip if this looks like a reference
            if self.is_reference_section(paragraph):
                continue

            if any(keyword in paragraph_lower for keyword in self.synthesis_keywords):
                if len(paragraph.strip()) > 50:  # Avoid very short matches
                    synthesis_paragraphs.append(paragraph.strip())

        return '\n\n'.join(synthesis_paragraphs)

    def process_single_doi(self, doi: str) -> bool:
        """Process a single DOI and extract synthesis information"""
        clean_doi = self.clean_doi(doi)
        if not clean_doi:
            logger.warning(f"Invalid DOI: {doi}")
            return False

        logger.info(f"Processing DOI: {doi}")

        # First, try to find supplementary PDF
        supplementary_pdf = self.supplementary_pdf_folder / f"{clean_doi}_supplementary.pdf"
        synthesis_content = ""
        source = ""

        if supplementary_pdf.exists():
            logger.info(f"Found supplementary PDF: {supplementary_pdf}")
            pdf_text = self.extract_text_from_pdf(supplementary_pdf)
            if pdf_text:
                synthesis_content = self.extract_synthesis_from_text(pdf_text)
                source = "supplementary PDF"

        # If no synthesis found in supplementary or no supplementary PDF, try main text
        if not synthesis_content:
            # Try different possible main text file extensions and naming conventions
            possible_main_files = [
                f"{clean_doi}.txt",
                f"{clean_doi}_main.txt",
                f"{clean_doi}_fulltext.txt"
            ]

            main_text_file = None
            for filename in possible_main_files:
                potential_file = self.main_text_folder / filename
                if potential_file.exists():
                    main_text_file = potential_file
                    break

            if main_text_file and main_text_file.exists():
                logger.info(f"Found main text file: {main_text_file}")
                try:
                    with open(main_text_file, 'r', encoding='utf-8', errors='ignore') as f:
                        main_text = f.read()
                    synthesis_content = self.extract_synthesis_from_text(main_text)
                    source = "main text file"
                except Exception as e:
                    logger.error(f"Error reading main text file {main_text_file}: {e}")

        # Save synthesis content if found
        if synthesis_content.strip():
            output_file = self.output_folder / f"{clean_doi}_synthesis.txt"
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"DOI: {doi}\n")
                    f.write(f"Source: {source}\n")
                    f.write("-" * 50 + "\n\n")
                    f.write(synthesis_content)
                logger.info(f"Saved synthesis content to: {output_file}")
                return True
            except Exception as e:
                logger.error(f"Error saving synthesis file {output_file}: {e}")
                return False
        else:
            logger.warning(f"No synthesis content found for DOI: {doi}")
            return False

    def process_csv(self):
        """Process all DOIs from the CSV file"""
        try:
            # Read CSV file
            df = pd.read_csv(self.csv_file)

            if 'DOI' not in df.columns:
                logger.error("CSV file must contain a 'DOI' column")
                return

            dois = df['DOI'].dropna().unique()
            logger.info(f"Found {len(dois)} unique DOIs to process")

            successful = 0
            failed = 0

            for doi in dois:
                try:
                    if self.process_single_doi(doi):
                        successful += 1
                    else:
                        failed += 1
                except Exception as e:
                    logger.error(f"Error processing DOI {doi}: {e}")
                    failed += 1

            logger.info(f"Processing complete. Successful: {successful}, Failed: {failed}")

        except Exception as e:
            logger.error(f"Error reading CSV file: {e}")


def main():
    # Configuration - UPDATE THESE PATHS
    csv_file = "D:\\pycharm-project\\parser\\single-atom-nature.csv"  # Your CSV file with DOI column
    supplementary_pdf_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\supplementary_pdfs"  # Folder with supplementary PDFs
    main_text_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\articles_txt"  # Folder with main paper text files
    output_folder = "D:\\pycharm-project\\parser\\new-try-20250523\\synthesis_outputs_after"  # Output folder for synthesis sections

    # Create extractor and process
    extractor = CatalystSynthesisExtractor(
        csv_file=csv_file,
        supplementary_pdf_folder=supplementary_pdf_folder,
        main_text_folder=main_text_folder,
        output_folder=output_folder
    )

    extractor.process_csv()


if __name__ == "__main__":
    main()