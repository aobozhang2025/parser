import pandas as pd
import requests
from bs4 import BeautifulSoup
import os
import re
import time

# Load the CSV file
csv_path = 'D:\\pycharm-project\\parser\\test\\single-atom-nature.csv'
df = pd.read_csv(csv_path)

# Set your column names
url_column = 'Url'   # Change if your column has a different name
doi_column = 'DOI'   # Change if your column has a different name

# Output folder
output_folder = 'articles_txt'
os.makedirs(output_folder, exist_ok=True)

def sanitize_filename(doi):
    """Replace problematic filename characters with underscores."""
    # Remove slashes, colons, spaces, and anything else not file-friendly
    return re.sub(r'[\\/*?:"<>|]', '_', doi)

for idx, row in df.iterrows():
    url = row[url_column]
    doi = str(row[doi_column])
    doi_clean = sanitize_filename(doi)
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        # Parse and save only the main text content
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text(separator='\n', strip=True)
        file_txt = os.path.join(output_folder, f'{doi_clean}.txt')
        with open(file_txt, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"Saved article: {doi_clean}.txt from {url}")
    except Exception as e:
        print(f"Failed to fetch {url} ({doi}): {e}")

    time.sleep(2)

print("Done!")
