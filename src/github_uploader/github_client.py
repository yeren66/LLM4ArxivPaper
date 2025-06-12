"""
GitHub client for uploading files to repositories.
Supports both single file uploads and batch operations.
"""

import os
import base64
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger


class GitHubClient:
    """GitHub API client for file operations."""
    
    def __init__(self, config: Dict):
        """
        Initialize GitHub client.
        
        Args:
            config: GitHub configuration dictionary
        """
        self.config = config
        self.token = self._get_github_token()
        self.username = self._get_github_username()
        self.repo_name = self._get_repo_name()
        self.branch = config.get('branch', 'main')
        self.summaries_dir = config.get('summaries_dir', 'summaries')
        self.commit_message_template = config.get('commit_message_template', 'Add paper summary: {title}')
        
        # GitHub API settings
        self.api_base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        logger.info(f"GitHubClient initialized for {self.username}/{self.repo_name}")
    
    def _get_github_token(self) -> str:
        """Get GitHub token from environment variables."""
        token = os.getenv('GH_TOKEN')
        if not token:
            raise ValueError("GH_TOKEN environment variable is required")
        return token
    
    def _get_github_username(self) -> str:
        """Get GitHub username from config."""
        repository = self.config.get('repository')
        if not repository:
            raise ValueError("GitHub repository is required in config.yaml (format: username/repo)")

        if '/' not in repository:
            raise ValueError("Repository must be in format 'username/repo'")

        return repository.split('/')[0]

    def _get_repo_name(self) -> str:
        """Get repository name from config."""
        repository = self.config.get('repository')
        if not repository:
            raise ValueError("GitHub repository is required in config.yaml (format: username/repo)")

        if '/' not in repository:
            raise ValueError("Repository must be in format 'username/repo'")

        return repository.split('/')[1]
    
    def _make_request(self, method: str, url: str, **kwargs) -> requests.Response:
        """Make authenticated request to GitHub API."""
        try:
            response = requests.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"GitHub API request failed: {e}")
            raise
    
    def get_file_sha(self, file_path: str) -> Optional[str]:
        """
        Get the SHA of an existing file in the repository.
        
        Args:
            file_path: Path to file in repository
            
        Returns:
            SHA string if file exists, None otherwise
        """
        url = f"{self.api_base_url}/repos/{self.username}/{self.repo_name}/contents/{file_path}"
        
        try:
            response = self._make_request("GET", url)
            return response.json().get('sha')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None  # File doesn't exist
            raise
    
    def upload_file(self, local_file_path: str, repo_file_path: str,
                   commit_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Upload a single file to GitHub repository.
        
        Args:
            local_file_path: Path to local file
            repo_file_path: Path where file should be stored in repo
            commit_message: Custom commit message
            
        Returns:
            GitHub API response data
        """
        # Read file content
        try:
            with open(local_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read file {local_file_path}: {e}")
            raise
        
        # Encode content to base64
        content_encoded = base64.b64encode(content.encode('utf-8')).decode('utf-8')
        
        # Check if file already exists
        existing_sha = self.get_file_sha(repo_file_path)
        
        # Prepare request data
        data = {
            "message": commit_message or f"Upload {Path(local_file_path).name}",
            "content": content_encoded,
            "branch": self.branch
        }
        
        if existing_sha:
            data["sha"] = existing_sha
            logger.info(f"Updating existing file: {repo_file_path}")
        else:
            logger.info(f"Creating new file: {repo_file_path}")
        
        # Make API request
        url = f"{self.api_base_url}/repos/{self.username}/{self.repo_name}/contents/{repo_file_path}"
        
        try:
            response = self._make_request("PUT", url, json=data)
            result = response.json()
            
            logger.info(f"Successfully uploaded {local_file_path} to {repo_file_path}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to upload {local_file_path}: {e}")
            raise
    
    def upload_summary(self, summary_data: Dict, local_file_path: str) -> Dict[str, Any]:
        """
        Upload a paper summary to the repository.
        
        Args:
            summary_data: Summary metadata
            local_file_path: Path to local summary file
            
        Returns:
            Upload result
        """
        # Generate repository file path
        arxiv_id = summary_data.get('arxiv_id', 'unknown')
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{date_str}_{arxiv_id.replace('/', '_')}.md"
        repo_file_path = f"{self.summaries_dir}/{filename}"
        
        # Generate commit message
        title = summary_data.get('title', 'Unknown Paper')
        commit_message = self.commit_message_template.format(
            title=title,
            arxiv_id=arxiv_id,
            date=date_str
        )
        
        # Upload file
        result = self.upload_file(local_file_path, repo_file_path, commit_message)
        
        # Add metadata to result
        result.update({
            'summary_data': summary_data,
            'repo_file_path': repo_file_path,
            'local_file_path': local_file_path
        })
        
        return result
    
    def upload_summaries_batch(self, summaries: List[Dict], 
                              local_files: List[str]) -> List[Dict[str, Any]]:
        """
        Upload multiple summaries in batch.
        
        Args:
            summaries: List of summary metadata
            local_files: List of local file paths
            
        Returns:
            List of upload results
        """
        if len(summaries) != len(local_files):
            raise ValueError("Number of summaries must match number of files")
        
        results = []
        
        for summary, local_file in zip(summaries, local_files):
            try:
                result = self.upload_summary(summary, local_file)
                results.append(result)
                
                # Add delay between uploads to avoid rate limiting
                import time
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Failed to upload {local_file}: {e}")
                results.append({
                    'error': str(e),
                    'summary_data': summary,
                    'local_file_path': local_file
                })
        
        logger.info(f"Batch upload completed: {len([r for r in results if 'error' not in r])}/{len(results)} successful")
        return results
    
    def create_index_file(self, summaries: List[Dict]) -> str:
        """
        Create an index file listing all summaries.
        
        Args:
            summaries: List of summary metadata
            
        Returns:
            Path to created index file
        """
        index_content = "# 论文总结索引\n\n"
        index_content += f"最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        index_content += f"总计论文数量：{len(summaries)}\n\n"
        
        # Group by date
        summaries_by_date = {}
        for summary in summaries:
            date = summary.get('generated_at', '')[:10] if summary.get('generated_at') else 'unknown'
            if date not in summaries_by_date:
                summaries_by_date[date] = []
            summaries_by_date[date].append(summary)
        
        # Generate index content
        for date in sorted(summaries_by_date.keys(), reverse=True):
            index_content += f"## {date}\n\n"
            
            for summary in summaries_by_date[date]:
                title = summary.get('title', 'Unknown Title')
                arxiv_id = summary.get('arxiv_id', 'unknown')
                filename = f"{date.replace('-', '')}_{arxiv_id.replace('/', '_')}.md"
                
                index_content += f"- [{title}]({self.summaries_dir}/{filename}) (arXiv:{arxiv_id})\n"
            
            index_content += "\n"
        
        # Save index file
        index_file_path = "paper_summaries_index.md"
        with open(index_file_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        logger.info(f"Created index file: {index_file_path}")
        return index_file_path
    
    def trigger_rtd_build(self) -> bool:
        """
        Trigger Read the Docs build (if webhook is configured).
        
        Returns:
            True if successful, False otherwise
        """
        rtd_webhook = os.getenv('RTD_WEBHOOK')
        if not rtd_webhook:
            logger.warning("RTD_WEBHOOK not configured, skipping RTD build trigger")
            return False
        
        try:
            response = requests.post(rtd_webhook)
            response.raise_for_status()
            logger.info("Successfully triggered RTD build")
            return True
        except Exception as e:
            logger.error(f"Failed to trigger RTD build: {e}")
            return False
