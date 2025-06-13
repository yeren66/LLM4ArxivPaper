"""
GitHub client for uploading files to repositories.
Supports both single file uploads and batch operations.
"""

import os
import base64
import time
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
    
    def _make_request(self, method: str, url: str, max_retries: int = 3,
                     retry_delay: float = 2.0, **kwargs) -> requests.Response:
        """
        Make authenticated request to GitHub API with retry mechanism.

        Args:
            method: HTTP method
            url: Request URL
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            **kwargs: Additional request parameters

        Returns:
            Response object
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                response = requests.request(method, url, headers=self.headers, **kwargs)
                response.raise_for_status()
                return response

            except requests.exceptions.RequestException as e:
                last_exception = e

                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = retry_delay * (2 ** attempt)
                    logger.warning(f"GitHub API request failed (attempt {attempt + 1}/{max_retries + 1}): {e}")
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                else:
                    logger.error(f"GitHub API request failed after {max_retries + 1} attempts: {e}")

        # If we get here, all retries failed
        if last_exception:
            raise last_exception
        else:
            raise requests.exceptions.RequestException("All retry attempts failed")
    
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
        Note: This method is kept for compatibility but summaries are not uploaded to GitHub.
        Only RTD documentation structure files are uploaded.

        Args:
            summary_data: Summary metadata
            local_file_path: Path to local summary file

        Returns:
            Upload result (mock result since we don't actually upload)
        """
        # Generate repository file path (for reference only)
        arxiv_id = summary_data.get('arxiv_id', 'unknown')
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{date_str}_{arxiv_id.replace('/', '_')}.md"
        repo_file_path = f"{self.summaries_dir}/{filename}"

        # Return mock result without actually uploading
        logger.info(f"Skipping summary upload to GitHub: {local_file_path} (summaries are kept local only)")

        return {
            'summary_data': summary_data,
            'repo_file_path': repo_file_path,
            'local_file_path': local_file_path,
            'skipped': True,
            'message': 'Summary files are not uploaded to GitHub repository'
        }
    
    def upload_summaries_batch(self, summaries: List[Dict],
                              local_files: List[str]) -> List[Dict[str, Any]]:
        """
        Upload multiple summaries in batch with improved error handling.

        Args:
            summaries: List of summary metadata
            local_files: List of local file paths

        Returns:
            List of upload results
        """
        if len(summaries) != len(local_files):
            raise ValueError("Number of summaries must match number of files")

        results = []
        successful_count = 0
        failed_count = 0

        logger.info(f"Starting batch upload of {len(summaries)} files...")

        for i, (summary, local_file) in enumerate(zip(summaries, local_files), 1):
            try:
                logger.info(f"Uploading file {i}/{len(summaries)}: {local_file}")
                result = self.upload_summary(summary, local_file)
                results.append(result)
                successful_count += 1

                logger.info(f"✅ Successfully uploaded {i}/{len(summaries)}: {local_file}")

                # Add delay between uploads to avoid rate limiting
                time.sleep(1)

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                logger.error(f"❌ Failed to upload {i}/{len(summaries)}: {local_file} - {error_msg}")

                # Store detailed error information
                results.append({
                    'error': error_msg,
                    'summary_data': summary,
                    'local_file_path': local_file,
                    'upload_index': i,
                    'failed_at': datetime.now().isoformat()
                })

                # Continue with next file instead of stopping
                logger.info(f"Continuing with remaining {len(summaries) - i} files...")

        # Final summary
        logger.info(f"Batch upload completed: {successful_count}/{len(results)} successful, {failed_count} failed")

        if failed_count > 0:
            logger.warning(f"Failed uploads summary:")
            for result in results:
                if 'error' in result:
                    logger.warning(f"  - {result.get('local_file_path', 'unknown')}: {result.get('error', 'unknown error')}")

        return results

    def retry_failed_uploads(self, failed_results: List[Dict]) -> List[Dict[str, Any]]:
        """
        Retry uploading files that failed in previous batch upload.

        Args:
            failed_results: List of failed upload results from previous batch

        Returns:
            List of retry results
        """
        if not failed_results:
            logger.info("No failed uploads to retry")
            return []

        retry_results = []
        logger.info(f"Retrying {len(failed_results)} failed uploads...")

        for i, failed_result in enumerate(failed_results, 1):
            if 'error' not in failed_result:
                continue  # Skip non-failed results

            summary = failed_result.get('summary_data')
            local_file = failed_result.get('local_file_path')

            if not summary or not local_file:
                logger.error(f"Invalid failed result data for retry {i}/{len(failed_results)}")
                continue

            try:
                logger.info(f"Retrying upload {i}/{len(failed_results)}: {local_file}")
                result = self.upload_summary(summary, local_file)
                retry_results.append(result)
                logger.info(f"✅ Retry successful {i}/{len(failed_results)}: {local_file}")

                # Add delay between retries
                time.sleep(2)

            except Exception as e:
                logger.error(f"❌ Retry failed {i}/{len(failed_results)}: {local_file} - {e}")
                retry_results.append({
                    'error': str(e),
                    'summary_data': summary,
                    'local_file_path': local_file,
                    'retry_failed_at': datetime.now().isoformat(),
                    'original_error': failed_result.get('error', 'unknown')
                })

        successful_retries = [r for r in retry_results if 'error' not in r]
        failed_retries = [r for r in retry_results if 'error' in r]

        logger.info(f"Retry completed: {len(successful_retries)}/{len(retry_results)} successful")

        return retry_results

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
