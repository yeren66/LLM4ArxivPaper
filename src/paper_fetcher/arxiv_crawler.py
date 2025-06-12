"""
arXiv Paper Crawler - 直接从 arXiv API 获取最新论文
"""

import arxiv
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import time
import re
from urllib.parse import quote_plus

from loguru import logger


class ArxivCrawler:
    """arXiv 论文爬取器，支持关键词搜索和分类过滤"""
    
    def __init__(self, config: Dict):
        """
        初始化 arXiv 爬取器

        Args:
            config: arXiv 配置字典
        """
        self.config = config
        self.api_base_url = config.get('api_base_url', 'http://export.arxiv.org/api/query')
        self.ar5iv_base_url = config.get('ar5iv_base_url', 'https://ar5iv.labs.arxiv.org/html')
        self.max_papers = config.get('max_papers', 20)
        self.request_delay = config.get('request_delay', 1)
        self.days_back = config.get('days_back', 1)
        self.sort_by = config.get('sort_by', 'submittedDate')
        self.sort_order = config.get('sort_order', 'descending')

        # 解析关键词组和分类
        self.keyword_groups = self._parse_keyword_groups(config.get('keyword_groups', {}))
        self.categories = self._parse_categories(config.get('categories', ''))

        # 搜索策略配置
        search_strategy = config.get('search_strategy', {})
        self.separate_keyword_searches = search_strategy.get('separate_keyword_searches', True)
        self.use_phrase_search = search_strategy.get('use_phrase_search', True)
        self.max_results_per_group = search_strategy.get('max_results_per_group', 20)

        # 向后兼容：如果没有keyword_groups，尝试解析旧的keywords配置
        if not self.keyword_groups and config.get('keywords'):
            legacy_keywords = self._parse_keywords(config.get('keywords', ''))
            self.keyword_groups = {'general': legacy_keywords}

        # 初始化 arxiv 客户端
        self.client = arxiv.Client()

        total_keywords = sum(len(keywords) for keywords in self.keyword_groups.values())
        logger.info(f"ArxivCrawler initialized with {len(self.keyword_groups)} keyword groups "
                   f"({total_keywords} total keywords) and {len(self.categories)} categories")
    
    def _parse_keywords(self, keywords_str: str) -> List[str]:
        """解析关键词字符串"""
        if not keywords_str:
            return []
        return [kw.strip().lower() for kw in keywords_str.split(',') if kw.strip()]

    def _parse_keyword_groups(self, keyword_groups: Dict) -> Dict[str, List[str]]:
        """解析关键词组配置"""
        if not keyword_groups:
            return {}

        parsed_groups = {}
        for group_name, keywords in keyword_groups.items():
            if isinstance(keywords, list):
                parsed_groups[group_name] = [kw.strip().lower() for kw in keywords if kw.strip()]
            elif isinstance(keywords, str):
                parsed_groups[group_name] = [kw.strip().lower() for kw in keywords.split(',') if kw.strip()]

        return parsed_groups

    def _parse_categories(self, categories_str: str) -> List[str]:
        """解析分类字符串"""
        if not categories_str:
            return []
        return [cat.strip() for cat in categories_str.split(',') if cat.strip()]
    
    def build_search_query(self, keywords: Optional[List[str]] = None, categories: Optional[List[str]] = None) -> str:
        """
        构建 arXiv 搜索查询

        Args:
            keywords: 关键词列表
            categories: 分类列表

        Returns:
            arXiv API 查询字符串
        """
        query_parts = []

        # 使用传入的参数或默认配置
        search_categories = categories or self.categories

        # 如果传入了关键词，使用传入的关键词
        if keywords:
            search_keywords = keywords
        else:
            # 否则使用所有关键词组的关键词
            search_keywords = []
            for group_keywords in self.keyword_groups.values():
                search_keywords.extend(group_keywords)

        # 添加关键词搜索（在标题、摘要中搜索）
        if search_keywords:
            keyword_queries = []
            for keyword in search_keywords:
                # 根据配置决定是否使用短语搜索
                if self.use_phrase_search and ' ' in keyword:
                    # 对于短语，直接使用引号包围，不进行URL编码
                    keyword_queries.append(f'(ti:"{keyword}" OR abs:"{keyword}")')
                else:
                    keyword_queries.append(f'(ti:{keyword} OR abs:{keyword})')

            if len(keyword_queries) > 1:
                query_parts.append(f"({' OR '.join(keyword_queries)})")
            else:
                query_parts.append(keyword_queries[0])

        # 添加分类过滤
        if search_categories:
            cat_queries = [f'cat:{cat}' for cat in search_categories]
            if len(cat_queries) > 1:
                query_parts.append(f"({' OR '.join(cat_queries)})")
            else:
                query_parts.append(cat_queries[0])

        # 组合查询
        if len(query_parts) > 1:
            query = ' AND '.join(query_parts)
        elif query_parts:
            query = query_parts[0]
        else:
            # 如果没有指定条件，搜索所有相关分类
            query = 'cat:cs.AI OR cat:cs.SE OR cat:cs.CL OR cat:cs.LG OR cat:cs.PL'

        logger.info(f"Built search query: {query}")
        return query

    def build_search_query_for_group(self, group_name: str, keywords: List[str]) -> str:
        """
        为特定关键词组构建优化的搜索查询

        Args:
            group_name: 关键词组名称
            keywords: 关键词列表

        Returns:
            优化的 arXiv API 查询字符串
        """
        keyword_queries = []

        for keyword in keywords:
            if self.use_phrase_search and ' ' in keyword:
                # 对于短语，直接使用引号包围，不进行URL编码
                keyword_queries.append(f'ti:"{keyword}" OR abs:"{keyword}"')
            else:
                keyword_queries.append(f'ti:{keyword} OR abs:{keyword}')

        # 构建关键词部分
        keyword_part = f"({' OR '.join(keyword_queries)})"

        # 构建分类部分
        cat_queries = [f'cat:{cat}' for cat in self.categories]
        category_part = f"({' OR '.join(cat_queries)})"

        # 组合查询
        query = f"{keyword_part} AND {category_part}"

        logger.info(f"Built search query for group '{group_name}': {query}")
        return query
    
    def get_recent_papers(self, custom_query: Optional[str] = None, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> List[Dict]:
        """
        获取最近的论文 - 支持按关键词组分别搜索

        Args:
            custom_query: 自定义查询字符串
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            论文信息列表
        """
        try:
            # 计算日期范围
            if start_date and end_date:
                search_start = start_date
                search_end = end_date
            else:
                search_end = datetime.now()
                search_start = search_end - timedelta(days=self.days_back)

            logger.info(f"Searching arXiv papers from {search_start.date()} to {search_end.date()}")

            all_papers = []
            processed_ids = set()

            if custom_query:
                # 使用自定义查询
                papers = self._search_with_query(custom_query, search_start, search_end, processed_ids)
                all_papers.extend(papers)
            elif self.separate_keyword_searches:
                # 为每个关键词组分别搜索
                for group_name, keywords in self.keyword_groups.items():
                    logger.info(f"Searching for keyword group: {group_name}")
                    query = self.build_search_query_for_group(group_name, keywords)
                    papers = self._search_with_query(query, search_start, search_end, processed_ids, self.max_results_per_group)
                    all_papers.extend(papers)
                    logger.info(f"Found {len(papers)} papers for group '{group_name}'")
            else:
                # 使用传统的组合搜索
                query = self.build_search_query()
                papers = self._search_with_query(query, search_start, search_end, processed_ids)
                all_papers.extend(papers)

            # 按相关性和日期排序
            all_papers.sort(key=lambda x: (x.get('relevance_score', 0), x.get('published_date', '')), reverse=True)

            # 限制总数量
            if len(all_papers) > self.max_papers:
                all_papers = all_papers[:self.max_papers]

            logger.info(f"Found {len(all_papers)} total recent papers")
            return all_papers

        except Exception as e:
            logger.error(f"Failed to get recent papers: {e}")
            return []

    def _search_with_query(self, query: str, start_date: datetime, end_date: datetime,
                          processed_ids: Set[str], max_results: Optional[int] = None) -> List[Dict]:
        """
        使用指定查询搜索论文

        Args:
            query: 搜索查询字符串
            start_date: 开始日期
            end_date: 结束日期
            processed_ids: 已处理的论文ID集合
            max_results: 最大结果数量

        Returns:
            论文信息列表
        """
        papers = []
        max_results = max_results or self.max_papers

        try:
            # 创建搜索对象
            search = arxiv.Search(
                query=query,
                max_results=max_results * 2,  # 获取更多结果以便过滤
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            # 获取论文
            for result in self.client.results(search):
                # 检查是否在日期范围内
                if not self._is_paper_in_date_range(result, start_date, end_date):
                    continue

                # 避免重复
                if result.entry_id in processed_ids:
                    continue
                processed_ids.add(result.entry_id)

                # 转换为标准格式
                paper_info = self._convert_arxiv_result(result)
                if paper_info:
                    # 计算相关性分数
                    paper_info['relevance_score'] = self._calculate_relevance_score(paper_info)
                    papers.append(paper_info)

                # 达到最大数量限制
                if len(papers) >= max_results:
                    break

                # 请求延迟
                time.sleep(self.request_delay)

            return papers

        except Exception as e:
            logger.error(f"Failed to search with query '{query}': {e}")
            return []
    
    def _is_paper_in_date_range(self, result, start_date: datetime, end_date: datetime) -> bool:
        """检查论文是否在指定日期范围内"""
        try:
            # 使用提交日期或更新日期
            paper_date = result.published or result.updated
            if paper_date:
                # 移除时区信息进行比较
                paper_date = paper_date.replace(tzinfo=None)
                return start_date <= paper_date <= end_date
            return False
        except Exception as e:
            logger.debug(f"Failed to check date range: {e}")
            return False
    
    def _convert_arxiv_result(self, result) -> Optional[Dict]:
        """将 arXiv 结果转换为标准格式"""
        try:
            # 提取 arXiv ID
            arxiv_id = result.entry_id.split('/')[-1]
            if 'v' in arxiv_id:
                arxiv_id = arxiv_id.split('v')[0]  # 移除版本号
            
            # 构建论文信息
            paper_info = {
                'arxiv_id': arxiv_id,
                'title': result.title.strip(),
                'authors': [author.name for author in result.authors],
                'authors_str': ', '.join([author.name for author in result.authors]),
                'abstract': result.summary.strip(),
                'categories': [cat for cat in result.categories],
                'primary_category': result.primary_category,
                'published_date': result.published.isoformat() if result.published else None,
                'updated_date': result.updated.isoformat() if result.updated else None,
                'arxiv_url': f"https://arxiv.org/abs/{arxiv_id}",
                'arxiv_pdf_url': f"https://arxiv.org/pdf/{arxiv_id}.pdf",
                'ar5iv_url': f"{self.ar5iv_base_url}/{arxiv_id}",
                'comment': result.comment,
                'journal_ref': result.journal_ref,
                'doi': result.doi,
                'links': [link.href for link in result.links]
            }
            
            return paper_info
            
        except Exception as e:
            logger.error(f"Failed to convert arXiv result: {e}")
            return None
    
    def search_by_keywords(self, keywords: List[str], max_results: Optional[int] = None) -> List[Dict]:
        """
        根据关键词搜索论文

        Args:
            keywords: 关键词列表
            max_results: 最大结果数量

        Returns:
            论文信息列表
        """
        max_results = max_results or self.max_papers
        query = self.build_search_query(keywords=keywords)

        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
                sort_order=arxiv.SortOrder.Descending
            )

            papers = []
            for result in self.client.results(search):
                paper_info = self._convert_arxiv_result(result)
                if paper_info:
                    papers.append(paper_info)
                time.sleep(self.request_delay)

            logger.info(f"Found {len(papers)} papers for keywords: {keywords}")
            return papers

        except Exception as e:
            logger.error(f"Failed to search by keywords: {e}")
            return []

    def search_by_categories(self, categories: List[str], max_results: Optional[int] = None) -> List[Dict]:
        """
        根据分类搜索论文

        Args:
            categories: 分类列表
            max_results: 最大结果数量

        Returns:
            论文信息列表
        """
        max_results = max_results or self.max_papers
        query = self.build_search_query(categories=categories)

        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            papers = []
            for result in self.client.results(search):
                paper_info = self._convert_arxiv_result(result)
                if paper_info:
                    papers.append(paper_info)
                time.sleep(self.request_delay)

            logger.info(f"Found {len(papers)} papers for categories: {categories}")
            return papers

        except Exception as e:
            logger.error(f"Failed to search by categories: {e}")
            return []

    def search_by_keyword_group(self, group_name: str) -> List[Dict]:
        """
        根据关键词组搜索论文

        Args:
            group_name: 关键词组名称

        Returns:
            论文信息列表
        """
        if group_name not in self.keyword_groups:
            logger.warning(f"Keyword group '{group_name}' not found")
            return []

        keywords = self.keyword_groups[group_name]
        query = self.build_search_query_for_group(group_name, keywords)

        try:
            search = arxiv.Search(
                query=query,
                max_results=self.max_results_per_group,
                sort_by=arxiv.SortCriterion.SubmittedDate,
                sort_order=arxiv.SortOrder.Descending
            )

            papers = []
            for result in self.client.results(search):
                paper_info = self._convert_arxiv_result(result)
                if paper_info:
                    paper_info['keyword_group'] = group_name
                    paper_info['relevance_score'] = self._calculate_relevance_score_for_group(paper_info, keywords)
                    papers.append(paper_info)
                time.sleep(self.request_delay)

            logger.info(f"Found {len(papers)} papers for keyword group '{group_name}'")
            return papers

        except Exception as e:
            logger.error(f"Failed to search by keyword group '{group_name}': {e}")
            return []
    
    def get_paper_by_id(self, arxiv_id: str) -> Optional[Dict]:
        """
        根据 arXiv ID 获取单篇论文
        
        Args:
            arxiv_id: arXiv ID
            
        Returns:
            论文信息字典
        """
        try:
            search = arxiv.Search(id_list=[arxiv_id])
            result = next(self.client.results(search))
            return self._convert_arxiv_result(result)
            
        except Exception as e:
            logger.error(f"Failed to get paper by ID {arxiv_id}: {e}")
            return None
    
    def filter_papers_by_relevance(self, papers: List[Dict], min_score: float = 0.5) -> List[Dict]:
        """
        根据相关性过滤论文

        Args:
            papers: 论文列表
            min_score: 最小相关性分数

        Returns:
            过滤后的论文列表
        """
        filtered_papers = []

        for paper in papers:
            # 如果论文已经有相关性分数（来自关键词组搜索），使用现有分数
            if 'relevance_score' in paper:
                score = paper['relevance_score']
            else:
                # 否则计算新的相关性分数
                score = self._calculate_relevance_score(paper)
                paper['relevance_score'] = score

            if score >= min_score:
                filtered_papers.append(paper)
            else:
                logger.debug(f"Paper filtered out: '{paper.get('title', 'Unknown')}' (score: {score:.3f} < {min_score})")

        # 按相关性分数排序
        filtered_papers.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        logger.info(f"Filtered {len(filtered_papers)} papers from {len(papers)} based on relevance (min_score: {min_score})")
        return filtered_papers
    
    def _calculate_relevance_score(self, paper: Dict) -> float:
        """计算论文相关性分数（基于所有关键词组）"""
        score = 0.0
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()

        # 收集所有关键词
        all_keywords = []
        for keywords in self.keyword_groups.values():
            all_keywords.extend(keywords)

        # 关键词匹配分数
        for keyword in all_keywords:
            if keyword in title:
                score += 2.0  # 标题匹配权重更高
            elif keyword in abstract:
                score += 1.0

        # 分类匹配分数
        paper_categories = paper.get('categories', [])
        for category in self.categories:
            if category in paper_categories:
                score += 1.5

        # 标准化分数
        max_possible_score = len(all_keywords) * 2 + len(self.categories) * 1.5
        if max_possible_score > 0:
            score = score / max_possible_score

        return min(score, 1.0)  # 限制在 0-1 范围内

    def _calculate_relevance_score_for_group(self, paper: Dict, keywords: List[str]) -> float:
        """计算论文对特定关键词组的相关性分数"""
        score = 0.0
        title = paper.get('title', '').lower()
        abstract = paper.get('abstract', '').lower()

        # 关键词匹配分数
        for keyword in keywords:
            if keyword in title:
                score += 2.0  # 标题匹配权重更高
            elif keyword in abstract:
                score += 1.0

        # 分类匹配分数
        paper_categories = paper.get('categories', [])
        for category in self.categories:
            if category in paper_categories:
                score += 1.5

        # 标准化分数
        max_possible_score = len(keywords) * 2 + len(self.categories) * 1.5
        if max_possible_score > 0:
            score = score / max_possible_score

        return min(score, 1.0)  # 限制在 0-1 范围内

    def get_papers_by_all_groups(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict[str, List[Dict]]:
        """
        为所有关键词组分别获取论文

        Args:
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            按关键词组分类的论文字典
        """
        results = {}
        processed_ids = set()

        # 计算日期范围
        if start_date and end_date:
            search_start = start_date
            search_end = end_date
        else:
            search_end = datetime.now()
            search_start = search_end - timedelta(days=self.days_back)

        logger.info(f"Searching papers by groups from {search_start.date()} to {search_end.date()}")

        for group_name, keywords in self.keyword_groups.items():
            logger.info(f"Searching for keyword group: {group_name}")

            try:
                query = self.build_search_query_for_group(group_name, keywords)
                papers = self._search_with_query(query, search_start, search_end, processed_ids, self.max_results_per_group)

                # 为每篇论文添加组信息
                for paper in papers:
                    paper['keyword_group'] = group_name
                    paper['relevance_score'] = self._calculate_relevance_score_for_group(paper, keywords)

                results[group_name] = papers
                logger.info(f"Found {len(papers)} papers for group '{group_name}'")

            except Exception as e:
                logger.error(f"Failed to search for group '{group_name}': {e}")
                results[group_name] = []

        return results

    def get_all_keywords(self) -> List[str]:
        """获取所有关键词的列表"""
        all_keywords = []
        for keywords in self.keyword_groups.values():
            all_keywords.extend(keywords)
        return list(set(all_keywords))  # 去重

    def get_keyword_groups_info(self) -> Dict[str, Dict]:
        """获取关键词组信息"""
        info = {}
        for group_name, keywords in self.keyword_groups.items():
            info[group_name] = {
                'keywords': keywords,
                'count': len(keywords),
                'max_results': self.max_results_per_group
            }
        return info
