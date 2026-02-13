"""Fetcher for downloading files from taxsim.nber.org."""

import requests
import re
from pathlib import Path
from typing import Dict, List, Optional
from bs4 import BeautifulSoup


class TaxsimNberOrgFetcher:
    """Fetches issue data and files from taxsim.nber.org/out2psl/."""

    def __init__(self, issue_number: int):
        self.issue_number = issue_number
        self.base_url = f"https://taxsim.nber.org/out2psl/{issue_number}/"

    def list_available_files(self) -> List[str]:
        """List all files available for this issue."""
        response = requests.get(self.base_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        files = []
        for link in soup.find_all('a'):
            href = link.get('href')
            if href and href not in ['../', '/out2psl/']:
                # Decode URL-encoded filenames
                import urllib.parse
                filename = urllib.parse.unquote(href)
                files.append(filename)

        return files

    def download_file(self, filename: str, output_dir: Path) -> Optional[Path]:
        """Download a specific file from the issue directory."""
        try:
            import urllib.parse
            encoded_filename = urllib.parse.quote(filename)
            url = f"{self.base_url}{encoded_filename}"

            response = requests.get(url, stream=True)
            response.raise_for_status()

            output_path = output_dir / filename
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return output_path

        except Exception as e:
            print(f"Warning: Failed to download {filename}: {e}")
            return None

    def download_all(self, output_dir: Path) -> Dict[str, Path]:
        """Download all files for this issue."""
        output_dir.mkdir(parents=True, exist_ok=True)

        files = self.list_available_files()
        downloaded = {}

        for filename in files:
            filepath = self.download_file(filename, output_dir)
            if filepath:
                downloaded[filename] = filepath

        return downloaded

    def categorize_files(self, files: Dict[str, Path]) -> Dict[str, List[Path]]:
        """Categorize downloaded files by type."""
        categorized = {
            'pdfs': [],
            'csv': [],
            'yaml': [],
            'txt': [],
            'other': []
        }

        for filename, filepath in files.items():
            if filename.endswith('.pdf'):
                categorized['pdfs'].append(filepath)
            elif filename.endswith('.csv'):
                categorized['csv'].append(filepath)
            elif filename.endswith('.yaml'):
                categorized['yaml'].append(filepath)
            elif filename.endswith('.txt'):
                categorized['txt'].append(filepath)
            else:
                categorized['other'].append(filepath)

        return categorized


def extract_taxsim_url_from_issue(issue_body: str) -> Optional[str]:
    """Extract taxsim.nber.org URL from GitHub issue body."""
    # Pattern: http://taxsim.nber.org/out2psl/NNN
    pattern = r'https?://taxsim\.nber\.org/out2psl/(\d+)'
    match = re.search(pattern, issue_body)

    if match:
        return match.group(0)

    return None


def extract_issue_number_from_url(url: str) -> Optional[int]:
    """Extract issue number from taxsim.nber.org URL."""
    pattern = r'/out2psl/(\d+)'
    match = re.search(pattern, url)

    if match:
        return int(match.group(1))

    return None
