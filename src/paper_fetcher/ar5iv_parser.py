"""
ar5iv HTML Parser - 从 ar5iv 网站解析论文 HTML 内容
"""

import requests
from bs4 import BeautifulSoup
import html2text
from typing import Dict, Optional, List
import time
import re
from urllib.parse import urljoin, urlparse

from loguru import logger


class Ar5ivParser:
    """ar5iv HTML 解析器，用于获取论文的 HTML 格式内容"""
    
    def __init__(self, config: Dict):
        """
        初始化 ar5iv 解析器
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.base_url = config.get('ar5iv_base_url', 'https://ar5iv.labs.arxiv.org/html')
        self.request_delay = config.get('request_delay', 1)
        self.timeout = config.get('timeout', 30)
        
        # 设置请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 初始化 HTML 到 Markdown 转换器
        self.html_converter = html2text.HTML2Text()
        self.html_converter.ignore_links = False
        self.html_converter.ignore_images = False
        self.html_converter.body_width = 0  # 不限制行宽
        
        logger.info("Ar5ivParser initialized")
    
    def get_paper_html_url(self, arxiv_id: str) -> str:
        """
        构建论文的 ar5iv HTML URL
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            ar5iv HTML URL
        """
        return f"{self.base_url}/{arxiv_id}"
    
    def fetch_paper_html(self, arxiv_id: str) -> Optional[str]:
        """
        获取论文的 HTML 内容
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            HTML 内容字符串，失败返回 None
        """
        url = self.get_paper_html_url(arxiv_id)
        
        try:
            logger.info(f"Fetching HTML for paper {arxiv_id} from {url}")
            
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully fetched HTML for paper {arxiv_id}")
                return response.text
            else:
                logger.warning(f"Failed to fetch HTML for paper {arxiv_id}: HTTP {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for paper {arxiv_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching HTML for paper {arxiv_id}: {e}")
            return None
    
    def parse_paper_content(self, html_content: str, arxiv_id: str) -> Optional[Dict]:
        """
        解析论文 HTML 内容
        
        Args:
            html_content: HTML 内容
            arxiv_id: arXiv ID
            
        Returns:
            解析后的论文内容字典
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取论文各部分内容
            content = {
                'arxiv_id': arxiv_id,
                'title': self._extract_title(soup),
                'authors': self._extract_authors(soup),
                'abstract': self._extract_abstract(soup),
                'sections': self._extract_sections(soup),
                'references': self._extract_references(soup),
                'figures': self._extract_figures(soup),
                'tables': self._extract_tables(soup),
                'equations': self._extract_equations(soup),
                'full_text': self._extract_full_text(soup),
                'markdown_content': self._convert_to_markdown(soup)
            }
            
            logger.info(f"Successfully parsed content for paper {arxiv_id}")
            return content
            
        except Exception as e:
            logger.error(f"Failed to parse HTML content for paper {arxiv_id}: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取论文标题"""
        # 尝试多种选择器
        selectors = [
            'h1.ltx_title',
            'h1[class*="title"]',
            '.ltx_title_document',
            'h1',
            'title'
        ]
        
        for selector in selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text().strip()
                # 清理标题
                title = re.sub(r'\s+', ' ', title)
                if title and len(title) > 5:  # 确保标题有意义
                    return title
        
        return ""
    
    def _extract_authors(self, soup: BeautifulSoup) -> List[str]:
        """提取作者信息"""
        authors = []
        
        # 尝试多种选择器
        selectors = [
            '.ltx_author',
            '.author',
            '[class*="author"]',
            '.ltx_personname'
        ]
        
        for selector in selectors:
            author_elems = soup.select(selector)
            if author_elems:
                for elem in author_elems:
                    author = elem.get_text().strip()
                    if author and author not in authors:
                        authors.append(author)
                break
        
        return authors
    
    def _extract_abstract(self, soup: BeautifulSoup) -> str:
        """提取摘要"""
        selectors = [
            '.ltx_abstract',
            '.abstract',
            '[class*="abstract"]',
            '#abstract'
        ]
        
        for selector in selectors:
            abstract_elem = soup.select_one(selector)
            if abstract_elem:
                abstract = abstract_elem.get_text().strip()
                # 清理摘要文本
                abstract = re.sub(r'\s+', ' ', abstract)
                if abstract and len(abstract) > 50:  # 确保摘要有意义
                    return abstract
        
        return ""
    
    def _extract_sections(self, soup: BeautifulSoup) -> List[Dict]:
        """提取论文章节"""
        sections = []
        
        # 查找章节标题
        section_selectors = [
            'h2, h3, h4, h5, h6',
            '.ltx_section',
            '[class*="section"]'
        ]
        
        for selector in section_selectors:
            section_elems = soup.select(selector)
            if section_elems:
                for elem in section_elems:
                    title = elem.get_text().strip()
                    if title and len(title) > 2:
                        # 获取章节内容
                        content = self._get_section_content(elem)
                        sections.append({
                            'title': title,
                            'content': content,
                            'level': elem.name if elem.name.startswith('h') else 'section'
                        })
                break
        
        return sections
    
    def _get_section_content(self, section_elem) -> str:
        """获取章节内容"""
        try:
            # 查找下一个同级或更高级的标题之前的所有内容
            content_parts = []
            current = section_elem.next_sibling
            
            while current:
                if hasattr(current, 'name'):
                    # 如果遇到同级或更高级标题，停止
                    if current.name and current.name.startswith('h'):
                        break
                    # 收集文本内容
                    if current.name in ['p', 'div', 'span']:
                        text = current.get_text().strip()
                        if text:
                            content_parts.append(text)
                
                current = current.next_sibling
            
            return ' '.join(content_parts)
            
        except Exception as e:
            logger.debug(f"Failed to get section content: {e}")
            return ""
    
    def _extract_references(self, soup: BeautifulSoup) -> List[str]:
        """提取参考文献"""
        references = []
        
        # 查找参考文献部分
        ref_selectors = [
            '.ltx_bibliography',
            '.references',
            '[class*="reference"]',
            '#references'
        ]
        
        for selector in ref_selectors:
            ref_section = soup.select_one(selector)
            if ref_section:
                # 提取每个参考文献条目
                ref_items = ref_section.find_all(['li', 'div', 'p'])
                for item in ref_items:
                    ref_text = item.get_text().strip()
                    if ref_text and len(ref_text) > 20:
                        references.append(ref_text)
                break
        
        return references
    
    def _extract_figures(self, soup: BeautifulSoup) -> List[Dict]:
        """提取图片信息"""
        figures = []
        
        # 查找图片
        img_elems = soup.find_all('img')
        for img in img_elems:
            src = img.get('src', '')
            alt = img.get('alt', '')
            title = img.get('title', '')
            
            if src:
                figures.append({
                    'src': src,
                    'alt': alt,
                    'title': title,
                    'caption': self._find_figure_caption(img)
                })
        
        return figures
    
    def _find_figure_caption(self, img_elem) -> str:
        """查找图片说明"""
        try:
            # 查找相邻的说明文字
            parent = img_elem.parent
            if parent:
                caption_elem = parent.find(['figcaption', 'caption'])
                if caption_elem:
                    return caption_elem.get_text().strip()
        except:
            pass
        return ""
    
    def _extract_tables(self, soup: BeautifulSoup) -> List[Dict]:
        """提取表格信息"""
        tables = []
        
        table_elems = soup.find_all('table')
        for table in table_elems:
            table_data = {
                'headers': [],
                'rows': [],
                'caption': self._find_table_caption(table)
            }
            
            # 提取表头
            thead = table.find('thead')
            if thead:
                header_row = thead.find('tr')
                if header_row:
                    headers = header_row.find_all(['th', 'td'])
                    table_data['headers'] = [h.get_text().strip() for h in headers]
            
            # 提取表格行
            tbody = table.find('tbody') or table
            rows = tbody.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text().strip() for cell in cells]
                if row_data:
                    table_data['rows'].append(row_data)
            
            if table_data['headers'] or table_data['rows']:
                tables.append(table_data)
        
        return tables
    
    def _find_table_caption(self, table_elem) -> str:
        """查找表格说明"""
        try:
            caption_elem = table_elem.find('caption')
            if caption_elem:
                return caption_elem.get_text().strip()
        except:
            pass
        return ""
    
    def _extract_equations(self, soup: BeautifulSoup) -> List[str]:
        """提取数学公式"""
        equations = []
        
        # 查找数学公式
        math_selectors = [
            '.ltx_Math',
            '.math',
            'math',
            '[class*="equation"]'
        ]
        
        for selector in math_selectors:
            math_elems = soup.select(selector)
            for elem in math_elems:
                eq_text = elem.get_text().strip()
                if eq_text:
                    equations.append(eq_text)
        
        return equations
    
    def _extract_full_text(self, soup: BeautifulSoup) -> str:
        """提取完整文本内容"""
        try:
            # 移除不需要的元素
            for elem in soup(['script', 'style', 'nav', 'header', 'footer']):
                elem.decompose()
            
            # 获取主要内容区域
            main_content = soup.find('main') or soup.find('body') or soup
            
            # 提取文本
            text = main_content.get_text()
            
            # 清理文本
            text = re.sub(r'\s+', ' ', text)
            text = text.strip()
            
            return text
            
        except Exception as e:
            logger.error(f"Failed to extract full text: {e}")
            return ""
    
    def _convert_to_markdown(self, soup: BeautifulSoup) -> str:
        """将 HTML 转换为 Markdown"""
        try:
            # 移除不需要的元素
            for elem in soup(['script', 'style', 'nav', 'header', 'footer']):
                elem.decompose()
            
            # 获取主要内容
            main_content = soup.find('main') or soup.find('body') or soup
            
            # 转换为 Markdown
            markdown = self.html_converter.handle(str(main_content))
            
            return markdown
            
        except Exception as e:
            logger.error(f"Failed to convert to markdown: {e}")
            return ""
    
    def get_paper_content(self, arxiv_id: str) -> Optional[Dict]:
        """
        获取并解析论文内容的完整流程
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            解析后的论文内容字典
        """
        # 添加请求延迟
        time.sleep(self.request_delay)
        
        # 获取 HTML 内容
        html_content = self.fetch_paper_html(arxiv_id)
        if not html_content:
            return None
        
        # 解析内容
        return self.parse_paper_content(html_content, arxiv_id)
