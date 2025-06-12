"""
LLM4Reading - 自动化论文阅读系统

这是一个基于AI的自动化学术论文处理系统，主要功能包括：
1. 从arXiv自动获取最新论文
2. 使用大语言模型生成中文总结
3. 按主题自动分类和组织
4. 上传到GitHub并构建文档网站

支持的运行模式：
- --arxiv: 手动运行，获取最新论文
- --daily: 定时运行，处理前一天的论文（用于GitHub Actions）
- --email: 邮件监控模式（实验性功能）
- --daemon: 守护进程模式（预留功能）

作者: AI Assistant
版本: 1.0.0
"""

import os
import sys
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add src to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from paper_fetcher.arxiv_crawler import ArxivCrawler
from paper_fetcher.ar5iv_parser import Ar5ivParser
from llm_summarizer.openai_summarizer import OpenAISummarizer
from github_uploader.github_client import GitHubClient
from topic_manager.topic_organizer import TopicOrganizer
from email_notifier.email_sender import EmailSender


class LLM4Reading:
    """
    LLM4Reading 主应用类

    这是系统的核心控制器，负责协调各个模块的工作：
    - ArxivCrawler: 论文获取模块
    - Ar5ivParser: 论文内容解析模块
    - OpenAISummarizer: LLM总结生成模块
    - TopicOrganizer: 主题分类和文档组织模块
    - GitHubClient: GitHub上传和版本控制模块
    """

    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化应用程序

        Args:
            config_path: 配置文件路径，默认为 config/config.yaml
        """
        self.config_path = config_path
        self.config = self._load_config()
        self._setup_logging()
        self._load_environment()
        
        # Initialize components
        self.arxiv_crawler = ArxivCrawler(self.config.get('arxiv', {}))
        self.ar5iv_parser = Ar5ivParser(self.config.get('arxiv', {}))
        self.llm_summarizer = OpenAISummarizer(self.config.get('llm', {}))
        self.github_client = GitHubClient(self.config.get('github', {}))
        self.topic_organizer = TopicOrganizer(self.config.get('topic_organization', {}))
        self.email_sender = EmailSender(self.config.get('email', {}), self.config.get('rtd', {}))

        logger.info("LLM4Reading initialized successfully")
    
    def _load_config(self) -> Dict:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {self.config_path}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse configuration file: {e}")
            raise
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        log_config = self.config.get('logging', {})
        
        # Create logs directory if it doesn't exist
        log_file = log_config.get('file', 'logs/llm4reading.log')
        log_dir = os.path.dirname(log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        
        # Configure loguru
        logger.remove()  # Remove default handler
        logger.add(
            sys.stderr,
            level=log_config.get('level', 'INFO'),
            format=log_config.get('format', "{time} | {level} | {message}")
        )
        logger.add(
            log_file,
            level=log_config.get('level', 'INFO'),
            format=log_config.get('format', "{time} | {level} | {message}"),
            rotation=log_config.get('rotation', '1 day'),
            retention=log_config.get('retention', '30 days')
        )
    
    def _load_environment(self) -> None:
        """Load environment variables."""
        # Load from .env file if it exists
        env_file = "config/secrets.env"
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info("Environment variables loaded from secrets.env")
        else:
            logger.warning("secrets.env file not found, using system environment variables")
    


    def crawl_arxiv_papers(self, days_back: int = 1, start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> List[Dict]:
        """
        直接从 arXiv API 爬取指定日期范围的论文

        Args:
            days_back: 向前搜索的天数，默认1天（前一天）
            start_date: 开始日期（可选，优先级高于days_back）
            end_date: 结束日期（可选，优先级高于days_back）

        Returns:
            List of arXiv papers found
        """
        # 确定日期范围
        if start_date and end_date:
            search_start = start_date
            search_end = end_date
            logger.info(f"Starting arXiv paper crawling for custom date range...")
        else:
            search_end = datetime.now()
            search_start = search_end - timedelta(days=days_back)
            logger.info(f"Starting arXiv paper crawling for last {days_back} days...")

        try:
            logger.info(f"Searching papers from {search_start.strftime('%Y-%m-%d')} to {search_end.strftime('%Y-%m-%d')}")

            # 获取指定日期范围的论文（使用关键词搜索）
            papers = self.arxiv_crawler.get_recent_papers(start_date=search_start, end_date=search_end)

            if not papers:
                logger.info("No new papers found from arXiv in the specified date range")
                return []

            # 过滤相关性高的论文（降低阈值，因为新的搜索策略已经提高了精确度）
            filtered_papers = self.arxiv_crawler.filter_papers_by_relevance(papers, min_score=0.05)

            logger.info(f"Found {len(papers)} papers, {len(filtered_papers)} after relevance filtering")

            # 为每篇论文获取详细内容
            enriched_papers = []
            for paper in filtered_papers[:20]:  # 增加处理数量用于日常运行
                try:
                    logger.info(f"Fetching detailed content for: {paper['title']}")

                    # 获取 ar5iv 内容
                    detailed_content = self.ar5iv_parser.get_paper_content(paper['arxiv_id'])

                    if detailed_content:
                        # 合并基本信息和详细内容
                        enriched_paper = {**paper, **detailed_content}
                        enriched_papers.append(enriched_paper)
                        logger.info(f"Successfully enriched paper: {paper['arxiv_id']}")
                    else:
                        # 如果无法获取详细内容，仍然保留基本信息
                        enriched_papers.append(paper)
                        logger.warning(f"Failed to get detailed content for {paper['arxiv_id']}, using basic info")

                except Exception as e:
                    logger.error(f"Failed to process paper {paper['arxiv_id']}: {e}")
                    # 出错时仍然保留基本信息
                    enriched_papers.append(paper)

            logger.info(f"Successfully processed {len(enriched_papers)} papers with detailed content")
            return enriched_papers

        except Exception as e:
            logger.error(f"arXiv crawling failed: {e}")
            return []

    def generate_summaries(self, papers: List[Dict]) -> List[Dict]:
        """
        Generate LLM summaries for papers.

        Args:
            papers: List of paper dictionaries with content

        Returns:
            List of summary dictionaries
        """
        try:
            logger.info(f"Generating summaries for {len(papers)} papers...")

            summaries = self.llm_summarizer.summarize_papers(papers)

            logger.info(f"Successfully generated {len(summaries)} summaries")
            return summaries

        except Exception as e:
            logger.error(f"Failed to generate summaries: {e}")
            return []

    def organize_papers_by_topics(self, summaries: List[Dict]) -> List[Dict]:
        """
        Organize papers by topics and create RTD structure.

        Args:
            summaries: List of summary dictionaries

        Returns:
            List of organization results
        """
        organized_results = []

        try:
            for summary in summaries:
                # Organize paper into topic directory
                result = self.topic_organizer.organize_paper(
                    summary,
                    summary.get('summary', '')
                )
                organized_results.append(result)

                logger.info(f"Organized paper '{summary.get('title', 'Unknown')}' into topic '{result['topic']}'")

            return organized_results

        except Exception as e:
            logger.error(f"Failed to organize papers by topics: {e}")
            return []

    def save_summaries(self, summaries: List[Dict]) -> List[str]:
        """
        Save summaries to local files.

        Args:
            summaries: List of summary dictionaries

        Returns:
            List of saved file paths
        """
        saved_files = []

        try:
            output_dir = "summaries"
            os.makedirs(output_dir, exist_ok=True)

            for summary in summaries:
                filepath = self.llm_summarizer.save_summary(summary, output_dir)
                if filepath:
                    logger.info(f"Saved summary: {filepath}")
                    saved_files.append(filepath)

            return saved_files

        except Exception as e:
            logger.error(f"Failed to save summaries: {e}")
            return saved_files

    def upload_summaries_to_github(self, summaries: List[Dict], local_files: List[str],
                                  organized_results: Optional[List[Dict]] = None) -> None:
        """
        Upload summaries to GitHub repository.

        Args:
            summaries: List of summary dictionaries
            local_files: List of local file paths
            organized_results: List of topic organization results (optional)
        """
        try:
            if not summaries or not local_files:
                logger.warning("No summaries to upload")
                return

            # Upload summaries in batch
            results = self.github_client.upload_summaries_batch(summaries, local_files)

            # Upload organized topic files if available
            if organized_results:
                self.upload_topic_files(organized_results)

            # Count successful uploads
            successful_uploads = [r for r in results if 'error' not in r]
            failed_uploads = [r for r in results if 'error' in r]

            logger.info(f"GitHub upload completed: {len(successful_uploads)}/{len(results)} successful")

            if failed_uploads:
                logger.warning(f"Failed uploads: {len(failed_uploads)}")
                for failed in failed_uploads:
                    logger.error(f"Failed to upload {failed.get('local_file_path', 'unknown')}: {failed.get('error', 'unknown error')}")

            # Create and upload index file
            if successful_uploads:
                try:
                    index_file = self.github_client.create_index_file(summaries)
                    self.github_client.upload_file(
                        index_file,
                        "README.md",
                        f"Update paper summaries index - {len(summaries)} papers"
                    )
                    logger.info("Updated repository index file")

                    # Clean up local index file
                    os.remove(index_file)

                except Exception as e:
                    logger.error(f"Failed to update index file: {e}")

            # Trigger RTD build if configured
            if successful_uploads:
                self.github_client.trigger_rtd_build()

        except Exception as e:
            logger.error(f"Failed to upload summaries to GitHub: {e}")

    def upload_topic_files(self, organized_results: List[Dict]) -> None:
        """
        Upload topic-organized files to GitHub.

        Args:
            organized_results: List of topic organization results
        """
        try:
            uploaded_files = set()

            for result in organized_results:
                file_path = result.get('file_path')
                relative_path = result.get('relative_file_path')

                if file_path and relative_path and os.path.exists(file_path):
                    # Upload the paper file
                    repo_path = f"source/paper_note/{relative_path}"
                    commit_msg = f"Add paper to {result['topic']}: {os.path.basename(file_path)}"

                    try:
                        self.github_client.upload_file(file_path, repo_path, commit_msg)
                        uploaded_files.add(file_path)
                        logger.info(f"Uploaded topic file: {repo_path}")
                    except Exception as e:
                        logger.error(f"Failed to upload {file_path}: {e}")

            # Upload topic index files
            topic_dirs = set()
            for result in organized_results:
                topic_path = result.get('topic_path')
                if topic_path and os.path.exists(topic_path):
                    topic_dirs.add(topic_path)

            for topic_dir in topic_dirs:
                index_file = os.path.join(topic_dir, 'index.rst')
                if os.path.exists(index_file):
                    # Calculate relative path for GitHub
                    rel_path = os.path.relpath(index_file, '.')
                    commit_msg = f"Update topic index: {os.path.basename(topic_dir)}"

                    try:
                        self.github_client.upload_file(index_file, rel_path, commit_msg)
                        logger.info(f"Uploaded topic index: {rel_path}")
                    except Exception as e:
                        logger.error(f"Failed to upload topic index {index_file}: {e}")

            # Upload main paper_note index
            main_index = os.path.join(self.topic_organizer.base_dir, 'index.rst')
            if os.path.exists(main_index):
                rel_path = os.path.relpath(main_index, '.')
                commit_msg = "Update main paper note index"

                try:
                    self.github_client.upload_file(main_index, rel_path, commit_msg)
                    logger.info(f"Uploaded main index: {rel_path}")
                except Exception as e:
                    logger.error(f"Failed to upload main index: {e}")

            logger.info(f"Topic file upload completed: {len(uploaded_files)} files uploaded")

        except Exception as e:
            logger.error(f"Failed to upload topic files: {e}")
    
    def run_once(self, use_arxiv_crawler: bool = True) -> None:
        """
        Run the application once (for testing or manual execution).

        Args:
            use_arxiv_crawler: If True, use arXiv crawler; if False, use email monitoring
        """
        logger.info("Starting LLM4Reading single run...")

        try:
            if use_arxiv_crawler:
                # Step 1: Crawl arXiv directly for latest papers
                logger.info("Using arXiv crawler to get latest papers...")
                papers = self.crawl_arxiv_papers()
            else:
                # Email monitoring is not currently supported
                logger.warning("Email monitoring is not currently supported, using arXiv crawler instead")
                papers = self.crawl_arxiv_papers()

            if not papers:
                logger.info("No papers to process")
                return

            # Log found papers
            logger.info(f"Processing {len(papers)} papers:")
            for i, paper in enumerate(papers, 1):
                logger.info(f"{i}. {paper['title']} (arXiv:{paper['arxiv_id']})")

            # Step 2: Generate LLM summaries
            logger.info("Generating LLM summaries...")
            summaries = self.generate_summaries(papers)

            if not summaries:
                logger.warning("No summaries generated")
                return

            # Step 3: Organize papers by topics
            logger.info("Organizing papers by topics...")
            organized_results = self.organize_papers_by_topics(summaries)

            # Step 4: Save summaries locally (both original and organized)
            logger.info("Saving summaries...")
            saved_files = self.save_summaries(summaries)

            # Step 5: Upload to GitHub
            logger.info("Uploading summaries to GitHub...")
            self.upload_summaries_to_github(summaries, saved_files, organized_results)

            logger.info(f"Single run completed successfully - processed {len(summaries)} papers")

        except Exception as e:
            logger.error(f"Application run failed: {e}")
            raise

    def run_daily(self, days_back: int = 1) -> None:
        """
        Run daily paper processing (for GitHub Actions).

        Args:
            days_back: Number of days back to search for papers
        """
        logger.info(f"Starting LLM4Reading daily run - processing last {days_back} days...")

        try:
            # Step 1: Crawl arXiv for papers from specified date range
            logger.info(f"Crawling arXiv papers from last {days_back} days...")
            papers = self.crawl_arxiv_papers(days_back)

            self._process_papers_batch(papers, f"daily run ({days_back} days)")

        except Exception as e:
            logger.error(f"Daily run failed: {e}")
            raise

    def run_date_range(self, start_date: str, end_date: str) -> None:
        """
        Run paper processing for a specific date range.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        """
        try:
            # Parse dates
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')

            logger.info(f"Starting LLM4Reading date range run - {start_date} to {end_date}")

            # Step 1: Crawl arXiv for papers in date range
            papers = self.crawl_arxiv_papers(start_date=start_dt, end_date=end_dt)

            self._process_papers_batch(papers, f"date range ({start_date} to {end_date})")

        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            raise
        except Exception as e:
            logger.error(f"Date range run failed: {e}")
            raise

    def _process_papers_batch(self, papers: List[Dict], run_description: str) -> None:
        """
        Process a batch of papers (common logic for daily and date range runs).

        Args:
            papers: List of paper dictionaries
            run_description: Description of the run for logging
        """
        if not papers:
            logger.info(f"No papers found for {run_description}")
            return

        # Log found papers
        logger.info(f"Found {len(papers)} papers to process for {run_description}:")
        for i, paper in enumerate(papers, 1):
            logger.info(f"{i}. {paper['title']} (arXiv:{paper['arxiv_id']})")

        # Step 2: Generate LLM summaries for all papers
        logger.info("Generating LLM summaries...")
        summaries = self.generate_summaries(papers)

        if not summaries:
            logger.warning("No summaries generated")
            return

        # Step 3: Organize papers by topics
        logger.info("Organizing papers by topics...")
        organized_results = self.organize_papers_by_topics(summaries)

        # Step 4: Save summaries locally
        logger.info("Saving summaries...")
        saved_files = self.save_summaries(summaries)

        # Step 5: Upload all files to GitHub in a single batch
        logger.info("Uploading all summaries to GitHub...")
        self.upload_daily_batch_to_github(summaries, saved_files, organized_results)

        logger.info(f"{run_description.capitalize()} completed successfully - processed {len(summaries)} papers")

        # Send email notification if enabled
        if self.email_sender.enabled and self.config.get('email', {}).get('send_daily_report', True):
            logger.info("Sending daily email report...")
            # Add topic and GitHub URLs to summaries for email
            for i, summary in enumerate(summaries):
                # Add topic information from organized_results
                if i < len(organized_results):
                    summary['topic'] = organized_results[i].get('topic', 'general')
                    summary['sanitized_topic'] = organized_results[i].get('sanitized_topic', 'general')
                else:
                    summary['topic'] = 'general'
                    summary['sanitized_topic'] = 'general'

                # Add GitHub URL for RTD documentation
                repository = self.config.get('github', {}).get('repository', 'unknown/unknown')
                repo_url = f"https://github.com/{repository}"
                summary['github_url'] = f"{repo_url}/blob/main/summaries/{summary.get('arxiv_id', 'unknown')}.md"

            self.email_sender.send_daily_report(summaries)
        else:
            logger.info("Email notifications disabled or not configured")

    def upload_daily_batch_to_github(self, summaries: List[Dict], local_files: List[str],
                                   organized_results: List[Dict]) -> None:
        """
        Upload daily batch of summaries to GitHub with a single commit.

        Args:
            summaries: List of summary dictionaries
            local_files: List of local file paths
            organized_results: List of topic organization results
        """
        try:
            if not summaries:
                logger.warning("No summaries to upload")
                return

            # Collect all files to upload
            files_to_upload = []

            # 不再上传到summaries目录，只上传到RTD文档结构
            # 注释掉原始summary文件上传，避免重复
            # for summary, local_file in zip(summaries, local_files):
            #     if os.path.exists(local_file):
            #         result = self.github_client.upload_summary(summary, local_file)
            #         files_to_upload.append(result)

            # Add topic-organized files
            for result in organized_results:
                file_path = result.get('file_path')
                relative_path = result.get('relative_file_path')

                if file_path and relative_path and os.path.exists(file_path):
                    repo_path = f"source/paper_note/{relative_path}"
                    commit_msg = f"Add paper to {result['topic']}: {os.path.basename(file_path)}"

                    upload_result = self.github_client.upload_file(file_path, repo_path, commit_msg)
                    files_to_upload.append(upload_result)

            # Upload topic index files
            topic_dirs = set()
            for result in organized_results:
                topic_path = result.get('topic_path')
                if topic_path and os.path.exists(topic_path):
                    topic_dirs.add(topic_path)

            for topic_dir in topic_dirs:
                index_file = os.path.join(topic_dir, 'index.rst')
                if os.path.exists(index_file):
                    rel_path = os.path.relpath(index_file, '.')
                    commit_msg = f"Update topic index: {os.path.basename(topic_dir)}"

                    self.github_client.upload_file(index_file, rel_path, commit_msg)

            # Upload main paper_note index
            main_index = os.path.join(self.topic_organizer.base_dir, 'index.rst')
            if os.path.exists(main_index):
                rel_path = os.path.relpath(main_index, '.')
                commit_msg = f"Daily update: {len(summaries)} new papers - {datetime.now().strftime('%Y-%m-%d')}"

                self.github_client.upload_file(main_index, rel_path, commit_msg)

            # Create and upload daily index
            daily_index = self.github_client.create_index_file(summaries)
            self.github_client.upload_file(
                daily_index,
                "README.md",
                f"Daily update: {len(summaries)} new papers - {datetime.now().strftime('%Y-%m-%d')}"
            )

            # Clean up local index file
            os.remove(daily_index)

            # Trigger RTD build
            self.github_client.trigger_rtd_build()

            logger.info(f"Daily batch upload completed: {len(summaries)} papers uploaded")

        except Exception as e:
            logger.error(f"Failed to upload daily batch to GitHub: {e}")

    def send_email_report(self, date_str: Optional[str] = None) -> None:
        """
        发送邮件报告（基于已有的GitHub仓库内容）

        Args:
            date_str: 报告日期，格式YYYY-MM-DD，默认为昨天
        """
        try:
            if not date_str:
                # 默认发送昨天的报告
                yesterday = datetime.now() - timedelta(days=1)
                date_str = yesterday.strftime('%Y-%m-%d')

            logger.info(f"Generating email report for {date_str}")

            # 从GitHub仓库获取指定日期的论文总结
            summaries = self._get_summaries_from_github(date_str)

            if not summaries:
                logger.info(f"No summaries found for {date_str}")
                return

            # 发送邮件报告
            success = self.email_sender.send_daily_report(summaries, date_str)

            if success:
                logger.info(f"Email report sent successfully for {date_str}")
            else:
                logger.error(f"Failed to send email report for {date_str}")

        except Exception as e:
            logger.error(f"Error sending email report: {e}")

    def _get_summaries_from_github(self, date_str: str) -> List[Dict]:
        """
        从GitHub仓库获取指定日期的论文总结

        Args:
            date_str: 日期字符串 YYYY-MM-DD

        Returns:
            论文总结列表
        """
        try:
            # 这里可以通过GitHub API获取文件列表
            # 为了简化，我们假设有一个本地的summaries目录
            summaries = []

            # 构造日期前缀（YYMMDD格式）
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_prefix = date_obj.strftime('%y%m%d')

            # 扫描summaries目录
            summaries_dir = "summaries"
            if os.path.exists(summaries_dir):
                for filename in os.listdir(summaries_dir):
                    if filename.startswith(date_prefix) and filename.endswith('.md'):
                        file_path = os.path.join(summaries_dir, filename)
                        summary = self._parse_summary_file(file_path)
                        if summary:
                            summaries.append(summary)

            logger.info(f"Found {len(summaries)} summaries for {date_str}")
            return summaries

        except Exception as e:
            logger.error(f"Error getting summaries from GitHub: {e}")
            return []

    def _parse_summary_file(self, file_path: str) -> Optional[Dict]:
        """
        解析总结文件，提取元数据和内容

        Args:
            file_path: 文件路径

        Returns:
            解析后的总结字典
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 提取基本信息
            summary = {
                'title': 'Unknown Title',
                'arxiv_id': 'unknown',
                'authors': [],
                'summary': content,
                'topic': 'general'
            }

            # 解析元数据
            lines = content.split('\n')
            for line in lines:
                if '**标题**:' in line:
                    summary['title'] = line.split('**标题**:')[1].strip()
                elif '**arXiv ID**:' in line:
                    summary['arxiv_id'] = line.split('**arXiv ID**:')[1].strip()
                elif '**作者**:' in line:
                    authors_str = line.split('**作者**:')[1].strip()
                    summary['authors'] = [author.strip() for author in authors_str.split(',')]

            # 根据文件路径推断topic
            if 'test_generation' in file_path:
                summary['topic'] = 'test_generation'
            elif 'software_testing' in file_path:
                summary['topic'] = 'software_testing'
            elif 'code_generation' in file_path:
                summary['topic'] = 'code_generation'
            elif 'knowledge_graph' in file_path:
                summary['topic'] = 'knowledge_graph'
            elif 'machine_learning' in file_path:
                summary['topic'] = 'machine_learning'
            elif 'software_engineering' in file_path:
                summary['topic'] = 'software_engineering'
            elif 'computer_vision' in file_path:
                summary['topic'] = 'computer_vision'
            elif 'natural_language_processing' in file_path:
                summary['topic'] = 'natural_language_processing'
            elif 'security' in file_path:
                summary['topic'] = 'security'
            elif 'robotics' in file_path:
                summary['topic'] = 'robotics'
            elif 'human_computer_interaction' in file_path:
                summary['topic'] = 'human_computer_interaction'

            # 添加GitHub链接
            repository = self.config.get('github', {}).get('repository', 'unknown/unknown')
            repo_url = f"https://github.com/{repository}"
            filename = os.path.basename(file_path)
            summary['github_url'] = f"{repo_url}/blob/main/summaries/{filename}"

            return summary

        except Exception as e:
            logger.error(f"Error parsing summary file {file_path}: {e}")
            return None

    def run_daemon(self) -> None:
        """Run the application as a daemon (continuous monitoring)."""
        logger.info("Starting LLM4Reading daemon mode...")
        
        # TODO: Implement daemon mode with scheduling
        # For now, just run once
        self.run_once()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='LLM4Reading - Automated Paper Reading System')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon (continuous monitoring)')
    parser.add_argument('--email', action='store_true', help='Use email monitoring (legacy)')
    parser.add_argument('--arxiv', action='store_true', help='Use arXiv crawler (default)')
    parser.add_argument('--daily', action='store_true', help='Daily run for GitHub Actions')
    parser.add_argument('--date-range', action='store_true', help='Run for specific date range')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--days-back', type=int, default=1, help='Number of days back to search')
    parser.add_argument('--send-email-report', action='store_true', help='Send daily email report')
    parser.add_argument('--email-only', action='store_true', help='Send email report only (no crawling)')
    parser.add_argument('--report-date', type=str, help='Date for email report (YYYY-MM-DD)')

    args = parser.parse_args()

    try:
        app = LLM4Reading()

        if args.daemon:
            app.run_daemon()
        elif args.email:
            # Use email monitoring (legacy method)
            app.run_once(use_arxiv_crawler=False)
        elif args.daily:
            # Daily run for GitHub Actions
            days_back = int(os.getenv('DAYS_BACK', str(args.days_back)))
            app.run_daily(days_back)
        elif args.date_range:
            # Date range run
            if not args.start_date or not args.end_date:
                print("Error: --date-range requires --start-date and --end-date")
                sys.exit(1)
            app.run_date_range(args.start_date, args.end_date)
        elif args.send_email_report or args.email_only:
            # Send email report
            report_date = args.report_date or os.getenv('REPORT_DATE')
            app.send_email_report(report_date)
        elif args.arxiv:
            # Use arXiv crawler
            app.run_once(use_arxiv_crawler=True)
        else:
            # Default: use arXiv crawler
            app.run_once(use_arxiv_crawler=True)

    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
