"""
Topic organizer for managing paper classification and RTD documentation structure.
"""

import os
import re
from typing import Dict, List, Optional, Set, Tuple
from pathlib import Path
from datetime import datetime

from loguru import logger


class TopicOrganizer:
    """Organizes papers by topics and manages RTD documentation structure."""
    
    def __init__(self, config: Dict):
        """
        Initialize topic organizer.
        
        Args:
            config: Topic organization configuration
        """
        self.config = config
        self.base_dir = config.get('base_dir', 'source/paper_note')
        self.topic_mapping = config.get('topic_mapping', {})
        self.default_topic = config.get('default_topic', 'general')
        self.auto_create_topics = config.get('auto_create_topics', True)
        
        # Topic keywords mapping for automatic classification - 扩展和优化
        self.topic_keywords = {
            'test_generation': [
                'test generation', 'unit test generation', 'test case generation',
                'automated test generation', 'test synthesis', 'test case synthesis',
                'unit test', 'test case', 'test oracle', 'mutation testing',
                'property-based testing', 'fuzz testing', 'fuzzing',
                'test coverage', 'code coverage', 'test suite', 'test framework'
            ],
            'software_testing': [
                'software testing', 'automated testing', 'test automation',
                'testing framework', 'regression testing', 'integration testing',
                'system testing', 'acceptance testing', 'performance testing',
                'load testing', 'stress testing', 'security testing',
                'usability testing', 'compatibility testing', 'test management',
                'test strategy', 'test planning', 'test execution', 'test evaluation'
            ],
            'code_generation': [
                'code generation', 'program synthesis', 'automated programming',
                'code completion', 'source code generation', 'code synthesis',
                'automatic programming', 'program generation', 'code assistant',
                'programming assistant', 'code suggestion', 'code recommendation'
            ],
            'knowledge_graph': [
                'knowledge graph', 'code knowledge graph', 'program knowledge graph',
                'software knowledge graph', 'code representation', 'program understanding',
                'code analysis', 'program analysis', 'semantic analysis',
                'knowledge extraction', 'graph neural network', 'graph embedding'
            ],
            'machine_learning': [
                'machine learning', 'deep learning', 'neural network', 'transformer',
                'attention', 'llm', 'large language model', 'ai', 'artificial intelligence',
                'gradient descent', 'backpropagation', 'optimization', 'feature learning',
                'representation learning', 'transfer learning', 'meta learning', 'few-shot learning',
                'ensemble learning', 'online learning', 'federated learning', 'continual learning',
                'supervised learning', 'unsupervised learning', 'reinforcement learning'
            ],
            'software_engineering': [
                'software engineering', 'code analysis', 'static analysis', 'refactoring',
                'code quality', 'software architecture', 'design pattern',
                'program synthesis', 'code generation', 'software development',
                'software maintenance', 'debugging', 'code review', 'technical debt',
                'continuous integration', 'devops', 'agile development', 'software metrics'
            ],
            'natural_language_processing': [
                'natural language processing', 'nlp', 'text processing', 'language model',
                'text generation', 'sentiment analysis', 'named entity recognition',
                'machine translation', 'text classification', 'question answering',
                'text summarization', 'dialogue system', 'chatbot', 'bert', 'gpt',
                'information extraction', 'text mining', 'semantic analysis', 'parsing'
            ],
            'computer_vision': [
                'computer vision', 'image processing', 'object detection', 'image classification',
                'cnn', 'convolutional neural network', 'image recognition',
                'image segmentation', 'face recognition', 'object tracking', 'pose estimation',
                'scene understanding', 'visual perception', 'image generation', 'style transfer',
                'super resolution', 'depth estimation', 'optical flow', 'stereo vision'
            ],
            'security': [
                'security', 'vulnerability', 'malware', 'cryptography', 'privacy',
                'attack', 'defense', 'cybersecurity', 'penetration testing',
                'intrusion detection', 'authentication', 'access control', 'encryption',
                'blockchain', 'secure coding', 'threat modeling', 'incident response'
            ],
            'robotics': [
                'robotics', 'robot', 'autonomous', 'navigation', 'path planning',
                'motion planning', 'control systems', 'sensor fusion', 'localization',
                'mapping', 'slam', 'manipulation', 'grasping', 'human-robot interaction',
                'swarm robotics', 'mobile robot', 'robotic arm', 'drone', 'uav'
            ],
            'human_computer_interaction': [
                'human computer interaction', 'hci', 'user interface', 'ui', 'ux',
                'user experience', 'usability', 'accessibility', 'interaction design',
                'user study', 'human factors', 'ergonomics', 'interface design',
                'mobile interface', 'web interface', 'gesture recognition', 'eye tracking'
            ]
        }
        
        logger.info(f"TopicOrganizer initialized with base_dir: {self.base_dir}")
    
    def classify_paper_topic(self, paper_data: Dict) -> str:
        """
        Classify paper into a topic based on title, abstract, keywords, and arXiv keyword group.

        Args:
            paper_data: Paper metadata including title, abstract, etc.

        Returns:
            Topic name (directory-safe)
        """
        title = paper_data.get('title', '').lower()
        abstract = paper_data.get('abstract', '').lower()
        keywords = paper_data.get('keywords', [])

        # 优先使用arXiv搜索时的关键词组信息
        arxiv_keyword_group = paper_data.get('keyword_group')
        if arxiv_keyword_group:
            # 映射arXiv关键词组到主题分类
            group_to_topic_mapping = {
                'test_generation': 'test_generation',
                'software_testing': 'software_testing',      # 软件测试单独分类
                'code_generation': 'code_generation',        # 代码生成单独分类
                'code_knowledge_graph': 'knowledge_graph'    # 知识图谱单独分类
            }

            mapped_topic = group_to_topic_mapping.get(arxiv_keyword_group)
            if mapped_topic:
                logger.info(f"Classified paper '{paper_data.get('title', 'Unknown')}' as topic: {mapped_topic} (from arXiv group: {arxiv_keyword_group})")
                return mapped_topic

        # Combine all text for analysis
        text_content = f"{title} {abstract} {' '.join(keywords)}".lower()

        # Score each topic based on keyword matches
        topic_scores = {}

        for topic, topic_keywords in self.topic_keywords.items():
            score = 0
            for keyword in topic_keywords:
                # Count occurrences of each keyword
                count = text_content.count(keyword.lower())
                score += count

                # Give extra weight to title matches
                if keyword.lower() in title:
                    score += 2

            topic_scores[topic] = score

        # 特殊规则：如果标题包含特定关键词，优先分类
        if 'test generation' in title or 'unit test generation' in title:
            logger.info(f"Classified paper '{paper_data.get('title', 'Unknown')}' as topic: test_generation (special rule)")
            return 'test_generation'
        elif 'test automation' in title or 'automated testing' in title:
            logger.info(f"Classified paper '{paper_data.get('title', 'Unknown')}' as topic: software_engineering (special rule)")
            return 'software_engineering'

        # Find the topic with highest score
        if topic_scores:
            best_topic = max(topic_scores.keys(), key=lambda k: topic_scores[k])
            if topic_scores[best_topic] > 0:
                logger.info(f"Classified paper '{paper_data.get('title', 'Unknown')}' as topic: {best_topic} (score: {topic_scores[best_topic]})")
                return best_topic

        # Fallback to default topic
        logger.info(f"Using default topic '{self.default_topic}' for paper '{paper_data.get('title', 'Unknown')}'")
        return self.default_topic
    
    def sanitize_topic_name(self, topic: str) -> str:
        """
        Sanitize topic name to be filesystem and URL safe.
        
        Args:
            topic: Raw topic name
            
        Returns:
            Sanitized topic name
        """
        # Convert to lowercase and replace spaces/special chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', topic.lower())
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')
        
        return sanitized or 'general'
    
    def get_topic_display_name(self, topic: str) -> str:
        """
        Get display name for a topic.
        
        Args:
            topic: Topic directory name
            
        Returns:
            Human-readable topic name
        """
        # Convert underscores to spaces and title case
        display_name = topic.replace('_', ' ').title()
        
        # Special cases for better display
        display_mapping = {
            'Test Generation': 'Test Generation',
            'Software Testing': 'Software Testing',
            'Code Generation': 'Code Generation',
            'Knowledge Graph': 'Knowledge Graph',
            'Machine Learning': 'Machine Learning',
            'Software Engineering': 'Software Engineering',
            'Natural Language Processing': 'Natural Language Processing',
            'Computer Vision': 'Computer Vision',
            'Security': 'Security',
            'General': 'General'
        }
        
        return display_mapping.get(display_name, display_name)
    
    def create_topic_directory(self, topic: str) -> Tuple[str, bool]:
        """
        Create topic directory and index.rst if they don't exist.
        
        Args:
            topic: Topic name
            
        Returns:
            Tuple of (topic_path, was_created)
        """
        sanitized_topic = self.sanitize_topic_name(topic)
        topic_path = os.path.join(self.base_dir, sanitized_topic)
        
        was_created = False
        
        # Create directory if it doesn't exist
        if not os.path.exists(topic_path):
            os.makedirs(topic_path, exist_ok=True)
            was_created = True
            logger.info(f"Created topic directory: {topic_path}")
        
        # Create index.rst if it doesn't exist
        index_path = os.path.join(topic_path, 'index.rst')
        if not os.path.exists(index_path):
            self._create_topic_index(topic_path, sanitized_topic)
            was_created = True
        
        return topic_path, was_created
    
    def _create_topic_index(self, topic_path: str, topic: str) -> None:
        """
        Create index.rst file for a topic directory.

        Args:
            topic_path: Path to topic directory
            topic: Topic name
        """
        display_name = self.get_topic_display_name(topic)

        # Create RST index that can include Markdown files
        index_content = f"""{display_name}
{'=' * len(display_name)}

导航
----------------

.. toctree::
    :titlesonly:
    :glob:

    *
"""

        index_path = os.path.join(topic_path, 'index.rst')
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)

        logger.info(f"Created topic index: {index_path}")
    
    def update_main_index(self, existing_topics: Set[str]) -> None:
        """
        Update the main paper_note/index.rst file with all topics.
        
        Args:
            existing_topics: Set of existing topic directory names
        """
        main_index_path = os.path.join(self.base_dir, 'index.rst')
        
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Generate toctree entries
        toctree_entries = []
        for topic in sorted(existing_topics):
            toctree_entries.append(f"   {topic}/index")
        
        index_content = f"""论文笔记
============

按主题分类的论文总结和笔记。

最后更新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

主题导航
----------------

.. toctree::
   :titlesonly:

{chr(10).join(toctree_entries)}
"""
        
        with open(main_index_path, 'w', encoding='utf-8') as f:
            f.write(index_content)
        
        logger.info(f"Updated main index with {len(existing_topics)} topics")
    
    def get_paper_file_path(self, paper_data: Dict, topic: str) -> str:
        """
        Generate file path for a paper within its topic directory.

        Args:
            paper_data: Paper metadata
            topic: Topic name

        Returns:
            Relative file path for the paper
        """
        sanitized_topic = self.sanitize_topic_name(topic)
        arxiv_id = paper_data.get('arxiv_id', 'unknown')

        # Clean arXiv ID (remove 'arXiv:' prefix if present)
        if arxiv_id.startswith('arXiv:'):
            arxiv_id = arxiv_id[6:]

        # Use 4-digit year format: YYYYMMDD
        date_str = datetime.now().strftime("%Y%m%d")

        # Create filename: YYYYMMDD_arXivID.md
        filename = f"{date_str}_{arxiv_id.replace('/', '_')}.md"

        # Return path relative to base_dir
        return os.path.join(sanitized_topic, filename)
    
    def add_paper_metadata(self, markdown_content: str, paper_data: Dict) -> str:
        """
        Add paper metadata to the beginning of markdown content.

        Args:
            markdown_content: Original Markdown content
            paper_data: Paper metadata

        Returns:
            Markdown content with metadata header and title
        """
        # Extract metadata from paper data
        title = paper_data.get('title', 'Unknown Paper')
        arxiv_id = paper_data.get('arxiv_id', 'unknown')
        authors = paper_data.get('authors', [])
        published_date = paper_data.get('published_date', 'Unknown')

        # Clean title (remove 'Title:' prefix if present)
        clean_title = title
        if clean_title.startswith('Title:'):
            clean_title = clean_title[6:].strip()

        # Clean arXiv ID
        clean_arxiv_id = arxiv_id
        if clean_arxiv_id.startswith('arXiv:'):
            clean_arxiv_id = clean_arxiv_id[6:]

        # Generate date prefix for title (YYMMDD format)
        date_prefix = datetime.now().strftime("%y%m%d")

        # Generate arXiv URL
        arxiv_url = f"https://arxiv.org/abs/{clean_arxiv_id}" if clean_arxiv_id != 'unknown' else 'N/A'

        # Create main title with date prefix
        main_title = f"# {date_prefix}_{clean_title}"

        # Create metadata header
        metadata_header = f"""---
**论文信息**

- **标题**: {clean_title}
- **arXiv ID**: {clean_arxiv_id}
- **作者**: {', '.join(authors) if authors else 'Unknown'}
- **发表日期**: {published_date}
- **论文链接**: [{clean_arxiv_id}]({arxiv_url})
- **总结生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

"""

        # Combine title, metadata, and original content
        return f"{main_title}\n\n{metadata_header}{markdown_content}"
    
    def organize_paper(self, paper_data: Dict, summary_content: str) -> Dict:
        """
        Organize a paper into appropriate topic directory.
        
        Args:
            paper_data: Paper metadata
            summary_content: Paper summary content
            
        Returns:
            Organization result with paths and status
        """
        # Classify paper topic
        topic = self.classify_paper_topic(paper_data)
        
        # Create topic directory if needed
        topic_path, was_created = self.create_topic_directory(topic)
        
        # Get file path for this paper
        relative_file_path = self.get_paper_file_path(paper_data, topic)
        full_file_path = os.path.join(self.base_dir, relative_file_path)
        
        # Add metadata to markdown content
        markdown_with_metadata = self.add_paper_metadata(summary_content, paper_data)

        # Write the file
        os.makedirs(os.path.dirname(full_file_path), exist_ok=True)
        with open(full_file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_with_metadata)
        
        # Get all existing topics for index update
        existing_topics = set()
        if os.path.exists(self.base_dir):
            for item in os.listdir(self.base_dir):
                item_path = os.path.join(self.base_dir, item)
                if os.path.isdir(item_path) and item != '__pycache__':
                    existing_topics.add(item)
        
        # Update main index
        self.update_main_index(existing_topics)
        
        result = {
            'topic': topic,
            'sanitized_topic': self.sanitize_topic_name(topic),
            'topic_display_name': self.get_topic_display_name(topic),
            'topic_path': topic_path,
            'file_path': full_file_path,
            'relative_file_path': relative_file_path,
            'topic_created': was_created,
            'existing_topics': list(existing_topics)
        }
        
        logger.info(f"Organized paper '{paper_data.get('title', 'Unknown')}' into topic '{topic}'")
        return result
