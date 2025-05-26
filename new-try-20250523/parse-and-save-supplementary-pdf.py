import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
import time
from urllib.parse import urljoin

# Load the CSV file
csv_path = 'D:\\pycharm-project\\parser\\single-atom-nature.csv'
df = pd.read_csv(csv_path)

# Set your column names
url_column = 'Url'  # Change if your column has a different name
doi_column = 'DOI'  # Change if your column has a different name

# Output folders
output_folder = 'articles_txt'
supplementary_folder = 'supplementary_pdfs'
os.makedirs(output_folder, exist_ok=True)
os.makedirs(supplementary_folder, exist_ok=True)


def sanitize_filename(doi):
    """Replace problematic filename characters with underscores."""
    return re.sub(r'[\\/*?:"<>|]', '_', doi)


def find_supplementary_pdf(soup, base_url):
    """Find the link to supplementary information PDF."""
    # Look for common patterns in supplementary links
    patterns = [
        'supplement', 'supplementary', 'suppl', 'extended', 'additional',
        'si.pdf', 'supp.pdf', 'suppinfo.pdf'
    ]

    # Check all links on the page
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        text = link.get_text().lower()

        # Check if link text or URL contains any of our patterns
        if any(pattern in href or pattern in text for pattern in patterns):
            # Check if it's a PDF (either in URL or likely from content type)
            if 'pdf' in href or 'pdf' in text or 'download' in text:
                return urljoin(base_url, link['href'])

    # Alternative approach: look for meta tags or specific div classes
    meta_link = soup.find('meta', {'name': 'citation_supplementary_pdf'})
    if meta_link and meta_link.get('content'):
        return urljoin(base_url, meta_link['content'])

    return None


for idx, row in df.iterrows():
    url = row[url_column]
    doi = str(row[doi_column])
    doi_clean = sanitize_filename(doi)

    try:
        # First get the main article page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        print(f"Processing: {url} ({doi})")
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        # Parse the HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # Save main text content (original functionality)
        text = soup.get_text(separator='\n', strip=True)
        file_txt = os.path.join(output_folder, f'{doi_clean}.txt')
        with open(file_txt, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Saved article text: {doi_clean}.txt")

        # Find and download supplementary PDF
        pdf_url = find_supplementary_pdf(soup, url)

        if pdf_url:
            try:
                pdf_response = requests.get(pdf_url, headers=headers, timeout=15)
                pdf_response.raise_for_status()

                if 'pdf' in pdf_response.headers.get('content-type', '').lower():
                    pdf_filename = os.path.join(supplementary_folder, f'{doi_clean}_supplementary.pdf')
                    with open(pdf_filename, 'wb') as f:
                        f.write(pdf_response.content)
                    print(f"Saved supplementary PDF: {doi_clean}_supplementary.pdf")
                else:
                    print(f"Found supplementary link but it's not a PDF: {pdf_url}")
            except Exception as e:
                print(f"Failed to download supplementary PDF from {pdf_url}: {e}")
        else:
            print("No supplementary PDF link found")

    except Exception as e:
        print(f"Failed to process {url} ({doi}): {e}")

    time.sleep(2)  # Be polite with delays between requests

print("Processing complete!")