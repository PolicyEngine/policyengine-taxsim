"""GitHub issue fetcher for downloading issue data and attachments."""

import os
import re
import requests
from pathlib import Path
from typing import Dict, List, Optional
import json


class GitHubIssueFetcher:
    """Fetches issue data and attachments from GitHub."""

    def __init__(self, repo_owner: str = "PolicyEngine", repo_name: str = "policyengine-taxsim"):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.api_base = "https://api.github.com"

        # Try to get GitHub token from environment
        self.token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')

        self.headers = {}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'

    def fetch_issue(self, issue_number: int) -> Dict:
        """Fetch issue details from GitHub API."""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def fetch_issue_comments(self, issue_number: int) -> List[Dict]:
        """Fetch all comments for an issue."""
        url = f"{self.api_base}/repos/{self.repo_owner}/{self.repo_name}/issues/{issue_number}/comments"

        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def extract_attachment_urls(self, text: str) -> List[str]:
        """Extract attachment URLs from markdown text."""
        if not text:
            return []

        urls = []

        # Pattern 1: ![filename](url) - images
        urls.extend(re.findall(r'!\[.*?\]\((https://[^\)]+)\)', text))

        # Pattern 2: [filename](url) - general links to GitHub user-content
        urls.extend(re.findall(r'\[.*?\]\((https://github\.com/.*?/files/[^\)]+)\)', text))
        urls.extend(re.findall(r'\[.*?\]\((https://user-images\.githubusercontent\.com/[^\)]+)\)', text))

        # Pattern 3: Raw URLs that look like attachments
        urls.extend(re.findall(r'(https://github\.com/.*?/files/\S+)', text))
        urls.extend(re.findall(r'(https://user-images\.githubusercontent\.com/\S+)', text))

        # Remove duplicates while preserving order
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def download_attachment(self, url: str, output_dir: Path) -> Optional[Path]:
        """Download a single attachment from a URL."""
        try:
            # Get the filename from URL or generate one
            url_parts = url.split('/')

            # Try to extract original filename if available
            filename = url_parts[-1]

            # Clean up filename
            filename = re.sub(r'[^\w\-_\. ]', '_', filename)

            output_path = output_dir / filename

            # Download the file
            response = requests.get(url, headers=self.headers, stream=True)
            response.raise_for_status()

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            return output_path

        except Exception as e:
            print(f"Warning: Failed to download {url}: {e}")
            return None

    def download_issue_attachments(self, issue_number: int, output_dir: Path) -> Dict:
        """Download all attachments from an issue and its comments."""
        output_dir.mkdir(parents=True, exist_ok=True)

        # Fetch issue data
        issue = self.fetch_issue(issue_number)
        comments = self.fetch_issue_comments(issue_number)

        # Save issue metadata
        metadata = {
            'number': issue['number'],
            'title': issue['title'],
            'author': issue['user']['login'],
            'created_at': issue['created_at'],
            'body': issue['body'],
            'comments': []
        }

        # Extract URLs from issue body
        urls = self.extract_attachment_urls(issue['body'])

        # Extract URLs from comments
        for comment in comments:
            metadata['comments'].append({
                'author': comment['user']['login'],
                'created_at': comment['created_at'],
                'body': comment['body']
            })
            urls.extend(self.extract_attachment_urls(comment['body']))

        # Save metadata
        metadata_path = output_dir / 'issue_metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        # Download all attachments
        downloaded_files = []
        for url in urls:
            filepath = self.download_attachment(url, output_dir)
            if filepath:
                downloaded_files.append(filepath)

        return {
            'metadata': metadata,
            'metadata_path': metadata_path,
            'attachments': downloaded_files,
            'output_dir': output_dir
        }
