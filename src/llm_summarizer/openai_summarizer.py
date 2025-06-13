"""
OpenAI-based paper summarizer.
Uses OpenAI GPT models to generate Chinese summaries of academic papers.
"""

import os
import json
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

from openai import OpenAI
from loguru import logger


class OpenAISummarizer:
    """OpenAI-based paper summarizer."""

    def __init__(self, config: Dict):
        """
        Initialize OpenAI summarizer.

        Args:
            config: LLM configuration dictionary
        """
        self.config = config
        self.model = config.get('model', 'gpt-4')
        self.max_tokens = config.get('max_tokens', 2000)
        self.temperature = config.get('temperature', 0.3)
        self.language = config.get('language', 'chinese')
        self.summary_format = config.get('summary_format', 'markdown')
        self.include_sections = config.get('include_sections', [])
        self.max_input_tokens = config.get('max_input_tokens', 8000)

        # Initialize OpenAI client
        self.client = self._setup_openai_client(config)

        logger.info(f"OpenAISummarizer initialized with model: {self.model}")

    def get_system_prompt(self) -> str:
        """Get the system prompt for debugging purposes."""
        return self._build_system_prompt()

    def _setup_openai_client(self, config: Dict) -> OpenAI:
        """Setup LLM client with API key and base URL (supports OpenAI, DeepSeek, etc.)."""
        provider = config.get('provider', 'openai')

        # Get API key based on provider
        if provider == 'deepseek':
            api_key = os.getenv('DEEPSEEK_API_KEY') or os.getenv('LLM_API_KEY')
            default_base_url = 'https://api.deepseek.com'
            base_url = os.getenv('DEEPSEEK_BASE_URL') or os.getenv('LLM_BASE_URL') or config.get('base_url', default_base_url)
        elif provider == 'openai':
            api_key = os.getenv('OPENAI_API_KEY') or os.getenv('LLM_API_KEY')
            default_base_url = 'https://api.openai.com/v1'
            base_url = os.getenv('OPENAI_BASE_URL') or os.getenv('LLM_BASE_URL') or config.get('base_url', default_base_url)
        else:
            # Custom provider
            api_key = os.getenv('LLM_API_KEY')
            base_url = os.getenv('LLM_BASE_URL') or config.get('base_url')

        if not api_key:
            raise ValueError(f"API key is required for provider '{provider}'. Please set the appropriate environment variable.")

        try:
            # Initialize OpenAI client with minimal parameters to avoid proxy issues
            # Only pass the essential parameters that are guaranteed to be supported
            if base_url and base_url.strip():
                # For custom providers like DeepSeek
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                )
            else:
                # For default OpenAI
                client = OpenAI(
                    api_key=api_key
                )

            logger.info(f"Using {provider} API with base URL: {base_url or 'default'}")
            logger.info(f"LLM client configured successfully for provider: {provider}")

            return client

        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            logger.error(f"Provider: {provider}, API Key present: {bool(api_key)}, Base URL: {base_url}")

            # Try alternative initialization without base_url if it fails
            if base_url:
                logger.warning("Retrying OpenAI client initialization without base_url...")
                try:
                    client = OpenAI(api_key=api_key)
                    logger.info("OpenAI client initialized successfully without base_url")
                    return client
                except Exception as e2:
                    logger.error(f"Alternative initialization also failed: {e2}")

            raise
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for paper summarization."""
        if self.language == 'chinese':
            return """你是一名善于撰写学术简报的中文 AI 助手，擅长用详细且严谨的语言解读论文。请将接收到的论文正文（按章节顺序给出）整合成一篇 **完整、连贯** 的阅读报告，讲清楚：
1）论文要解决的核心问题
2）作者提出的关键方法 / 思路
3）实验或案例验证的主要效果与意义

禁止堆砌原文长句，禁止机械分点；报告需像讲故事一样自然流畅，但保持学术严谨。

**写作要求**

* 输出语言：简体中文
* 形式：Markdown
* 结构：
  - **一句话概要**
  - **主体**：用 3～4 段完整、连贯的文字依次阐述 "问题 → 解决方案 → 效果"
  - **最后一句**：指出该工作对未来研究或应用的启示
* 不要使用列表、编号、表格
* 避免出现"本文""该论文"等口语化提示词，可用"作者""研究"指代
* 若引用图表、公式，请用简洁描述嵌入（勿贴原图）

完成后仅输出 Markdown 正文，不要附加任何解释。"""
        else:
            return """You are a professional academic paper analyst. Please carefully read the provided academic paper content and generate a high-quality summary.

Summary requirements:
1. Use clear and professional language
2. Maintain academic rigor and accuracy
3. Structure information for easy understanding
4. Highlight innovations and main contributions
5. Output in Markdown format

Please organize the summary with the following structure:

# Paper Title

## 📋 Basic Information
- **Authors**: [Author list]
- **Publication Date**: [Date]
- **arXiv ID**: [Paper ID]
- **Main Field**: [Research field]

## 🎯 Background & Motivation
[Brief description of background, problems, and motivation]

## 💡 Main Contributions
[List main contributions and innovations]

## 🔬 Methodology
[Describe proposed methods, technical approach, or theoretical framework]

## 📊 Experimental Results
[Summarize main experimental results and performance]

## 🔍 Key Insights
[Extract key insights and important findings]

## 📝 Summary & Evaluation
[Overall evaluation including strengths, limitations, and potential impact]

Please ensure the summary is accurate, concise, and readable."""
    
    def _prepare_paper_content(self, paper_data: Dict) -> str:
        """
        Prepare paper content for LLM processing.
        
        Args:
            paper_data: Paper data dictionary from ar5iv parser
            
        Returns:
            Formatted content string for LLM
        """
        content_parts = []
        
        # Add basic information
        if paper_data.get('title'):
            content_parts.append(f"# {paper_data['title']}")
        
        if paper_data.get('authors'):
            authors_str = ', '.join(paper_data['authors']) if isinstance(paper_data['authors'], list) else paper_data['authors']
            content_parts.append(f"**Authors:** {authors_str}")
        
        if paper_data.get('arxiv_id'):
            content_parts.append(f"**arXiv ID:** {paper_data['arxiv_id']}")
        
        # Add abstract
        if paper_data.get('abstract'):
            content_parts.append(f"\n## Abstract\n{paper_data['abstract']}")
        
        # Add main content
        if paper_data.get('markdown_content'):
            content_parts.append(f"\n## Full Content\n{paper_data['markdown_content']}")
        elif paper_data.get('sections'):
            content_parts.append("\n## Paper Sections")
            for section in paper_data['sections']:
                if section.get('title') and section.get('content'):
                    content_parts.append(f"\n### {section['title']}\n{section['content']}")
        
        # Add figures and tables information if available
        if paper_data.get('figures'):
            content_parts.append(f"\n## Figures\n{len(paper_data['figures'])} figures included in the paper")
        
        if paper_data.get('tables'):
            content_parts.append(f"\n## Tables\n{len(paper_data['tables'])} tables included in the paper")
        
        full_content = '\n'.join(content_parts)

        # 不再截断内容，保留完整论文
        logger.info(f"Paper content prepared: {len(full_content)} characters")

        return full_content
    
    def summarize_paper(self, paper_data: Dict) -> Optional[Dict]:
        """
        Generate summary for a single paper.
        
        Args:
            paper_data: Paper data dictionary from ar5iv parser
            
        Returns:
            Summary result dictionary
        """
        try:
            arxiv_id = paper_data.get('arxiv_id', 'unknown')
            title = paper_data.get('title', 'Unknown Title')
            
            logger.info(f"Generating summary for paper: {title} ({arxiv_id})")
            
            # Prepare content for LLM
            paper_content = self._prepare_paper_content(paper_data)
            
            # Build messages for chat completion
            title = paper_data.get('title', '未知标题')
            arxiv_id = paper_data.get('arxiv_id', '未知ID')

            user_prompt = f"""论文标题：{title}
arXiv ID：{arxiv_id}
（以下是论文正文片段，已按章节顺序提供，含必要图片说明）

<<<START_OF_PAPER>>>
{paper_content}
<<<END_OF_PAPER>>>"""

            messages = [
                {"role": "system", "content": self._build_system_prompt()},
                {"role": "user", "content": user_prompt}
            ]
            
            # Call OpenAI API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                timeout=60
            )
            
            # Extract summary
            summary_content = response.choices[0].message.content.strip()
            
            # Build result
            result = {
                'arxiv_id': arxiv_id,
                'title': title,
                'original_title': title,
                'authors': paper_data.get('authors', []),
                'published_date': paper_data.get('published_date'),
                'summary': summary_content,
                'summary_language': self.language,
                'model_used': self.model,
                'generated_at': datetime.now().isoformat(),
                'token_usage': {
                    'prompt_tokens': response.usage.prompt_tokens,
                    'completion_tokens': response.usage.completion_tokens,
                    'total_tokens': response.usage.total_tokens
                }
            }
            
            logger.info(f"Successfully generated summary for {arxiv_id} (tokens: {response.usage.total_tokens})")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate summary for paper {paper_data.get('arxiv_id', 'unknown')}: {e}")
            return None
    
    def summarize_papers(self, papers_data: List[Dict]) -> List[Dict]:
        """
        Generate summaries for multiple papers.
        
        Args:
            papers_data: List of paper data dictionaries
            
        Returns:
            List of summary result dictionaries
        """
        summaries = []
        
        for i, paper_data in enumerate(papers_data, 1):
            logger.info(f"Processing paper {i}/{len(papers_data)}")
            
            summary = self.summarize_paper(paper_data)
            if summary:
                summaries.append(summary)
            
            # Add delay between requests to avoid rate limiting
            if i < len(papers_data):
                time.sleep(1)
        
        logger.info(f"Generated {len(summaries)} summaries out of {len(papers_data)} papers")
        return summaries
    
    def save_summary(self, summary: Dict, output_dir: str = "summaries") -> Optional[str]:
        """
        Save summary to markdown file.

        Args:
            summary: Summary dictionary
            output_dir: Output directory

        Returns:
            Path to saved file
        """
        try:
            os.makedirs(output_dir, exist_ok=True)

            # Generate filename with consistent format: YYYYMMDD_arxivid.md
            arxiv_id = summary['arxiv_id']
            date_str = datetime.now().strftime("%Y%m%d")  # 使用4位年份保持一致

            # Clean arXiv ID (remove 'arXiv:' prefix if present)
            if arxiv_id.startswith('arXiv:'):
                arxiv_id = arxiv_id[6:]

            filename = f"{date_str}_{arxiv_id.replace('/', '_')}.md"
            filepath = os.path.join(output_dir, filename)
            
            # Write summary to file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(summary['summary'])
            
            logger.info(f"Summary saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            return None
