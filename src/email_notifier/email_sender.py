"""
邮件通知发送器
用于发送论文总结的每日报告邮件
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Optional
from loguru import logger


class EmailSender:
    """
    邮件发送器类
    
    支持通过SMTP发送HTML格式的论文总结报告邮件
    """
    
    def __init__(self, config: Dict, rtd_config: Optional[Dict] = None):
        """
        初始化邮件发送器

        Args:
            config: 邮件配置字典
            rtd_config: RTD配置字典
        """
        self.config = config
        self.rtd_config = rtd_config or {}

        # SMTP服务器配置
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.use_tls = config.get('use_tls', True)

        # 邮箱地址从config.yaml读取
        self.sender_email = config.get('sender_email')
        self.recipient_email = config.get('recipient_email')

        # 密码从环境变量读取
        self.sender_password = os.getenv('EMAIL_PASSWORD')

        if not all([self.sender_email, self.sender_password, self.recipient_email]):
            logger.warning("Email credentials not fully configured. Email notifications will be disabled.")
            logger.warning(f"Missing: sender_email={bool(self.sender_email)}, password={bool(self.sender_password)}, recipient_email={bool(self.recipient_email)}")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"EmailSender initialized for {self.recipient_email}")
    
    def send_daily_report(self, summaries: List[Dict], date_str: Optional[str] = None) -> bool:
        """
        发送每日论文总结报告
        
        Args:
            summaries: 论文总结列表
            date_str: 日期字符串，默认为今天
            
        Returns:
            发送是否成功
        """
        if not self.enabled:
            logger.warning("Email notifications disabled - missing credentials")
            return False
        
        if not summaries:
            logger.info("No summaries to send in daily report")
            return True
        
        try:
            # 生成报告内容
            if not date_str:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            subject = f"📚 LLM4Reading 每日论文报告 - {date_str}"
            html_content = self._generate_report_html(summaries, date_str)
            
            # 发送邮件
            success = self._send_email(subject, html_content)
            
            if success:
                logger.info(f"Daily report sent successfully to {self.recipient_email}")
            else:
                logger.error("Failed to send daily report")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending daily report: {e}")
            return False
    
    def _generate_report_html(self, summaries: List[Dict], date_str: str) -> str:
        """
        生成HTML格式的报告内容
        
        Args:
            summaries: 论文总结列表
            date_str: 日期字符串
            
        Returns:
            HTML格式的报告内容
        """
        # 按主题分组
        topics = {}
        for summary in summaries:
            topic = summary.get('topic', 'general')
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(summary)
        
        # 生成HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background-color: #4CAF50; color: white; padding: 20px; text-align: center; }}
                .summary {{ background-color: #f9f9f9; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
                .topic-section {{ margin: 20px 0; }}
                .topic-title {{ background-color: #e7f3ff; padding: 10px; font-weight: bold; color: #2196F3; }}
                .paper-item {{ margin: 15px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
                .paper-title {{ font-weight: bold; color: #1976D2; margin-bottom: 5px; }}
                .paper-meta {{ color: #666; font-size: 0.9em; margin-bottom: 10px; }}
                .paper-summary {{ margin-top: 10px; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 0.9em; }}
                a {{ color: #1976D2; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📚 LLM4Reading 每日论文报告</h1>
                <p>日期: {date_str} | 共发现 {len(summaries)} 篇论文</p>
            </div>
            
            <div class="summary">
                <h2>📊 今日概览</h2>
                <ul>
                    <li><strong>论文总数:</strong> {len(summaries)} 篇</li>
                    <li><strong>涵盖主题:</strong> {len(topics)} 个</li>
                    <li><strong>主要领域:</strong> {', '.join(list(topics.keys())[:3])}</li>
                </ul>
            </div>
        """
        
        # 按主题添加论文
        for topic, papers in topics.items():
            topic_display = self._get_topic_display_name(topic)
            html += f"""
            <div class="topic-section">
                <div class="topic-title">
                    📂 {topic_display} ({len(papers)} 篇)
                </div>
            """
            
            for paper in papers:
                title = paper.get('title', 'Unknown Title')
                arxiv_id = paper.get('arxiv_id', 'unknown')
                authors = paper.get('authors', [])
                arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
                github_url = paper.get('github_url', '#')

                # 生成RTD文档链接
                rtd_url = self._generate_rtd_url(paper, topic)

                # 提取总结的第一段作为预览
                summary_text = paper.get('summary', '')
                preview = self._extract_summary_preview(summary_text)
                
                html += f"""
                <div class="paper-item">
                    <div class="paper-title">
                        <a href="{arxiv_url}" target="_blank">{title}</a>
                    </div>
                    <div class="paper-meta">
                        <strong>arXiv ID:</strong> {arxiv_id} |
                        <strong>作者:</strong> {', '.join(authors[:3])}{'...' if len(authors) > 3 else ''} |
                        <a href="{github_url}" target="_blank">GitHub</a> |
                        <a href="{rtd_url}" target="_blank">📖 在线阅读</a>
                    </div>
                    <div class="paper-summary">
                        {preview}
                    </div>
                </div>
                """
            
            html += "</div>"
        
        # 添加页脚
        html += f"""
            <div class="footer">
                <p>本报告由 <strong>LLM4Reading</strong> 自动生成</p>
                <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>如需取消订阅，请联系管理员</p>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_rtd_url(self, paper: Dict, topic: str) -> str:
        """
        生成RTD文档链接

        Args:
            paper: 论文信息字典
            topic: 论文主题

        Returns:
            RTD文档链接
        """
        if not self.rtd_config:
            return '#'

        base_url = self.rtd_config.get('base_url', '')
        paper_note_path = self.rtd_config.get('paper_note_path', 'paper_note')
        file_extension = self.rtd_config.get('file_extension', '.html')

        if not base_url:
            return '#'

        # 生成文件名（与topic_organizer中的逻辑保持一致）
        arxiv_id = paper.get('arxiv_id', 'unknown')

        # Clean arXiv ID (remove 'arXiv:' prefix if present)
        if arxiv_id.startswith('arXiv:'):
            arxiv_id = arxiv_id[6:]

        # 获取日期（使用4位年份格式，与topic_organizer保持一致）
        from datetime import datetime
        date_str = datetime.now().strftime("%Y%m%d")

        # 构造文件名
        filename = f"{date_str}_{arxiv_id.replace('/', '_')}"

        # Sanitize topic name (与topic_organizer保持一致)
        sanitized_topic = self._sanitize_topic_name(topic)

        # 构造完整URL
        rtd_url = f"{base_url}/{paper_note_path}/{sanitized_topic}/{filename}{file_extension}"

        return rtd_url

    def _sanitize_topic_name(self, topic: str) -> str:
        """
        Sanitize topic name to be filesystem and URL safe.
        与topic_organizer中的逻辑保持一致

        Args:
            topic: Raw topic name

        Returns:
            Sanitized topic name
        """
        import re
        # Convert to lowercase and replace spaces/special chars with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', topic.lower())
        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)
        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        return sanitized or 'general'

    def _get_topic_display_name(self, topic: str) -> str:
        """获取主题的显示名称"""
        topic_names = {
            'test_generation': '测试生成',
            'software_testing': '软件测试',
            'code_generation': '代码生成',
            'knowledge_graph': '知识图谱',
            'machine_learning': '机器学习',
            'computer_vision': '计算机视觉',
            'natural_language_processing': '自然语言处理',
            'software_engineering': '软件工程',
            'security': '安全',
            'robotics': '机器人学',
            'human_computer_interaction': '人机交互',
            'general': '综合'
        }
        return topic_names.get(topic, topic.replace('_', ' ').title())
    
    def _extract_summary_preview(self, summary_text: str) -> str:
        """提取总结预览（第一段或前200字符）"""
        if not summary_text:
            return "暂无总结"
        
        # 尝试提取"一句话概要"
        lines = summary_text.split('\n')
        for line in lines:
            if '一句话概要' in line or '概要' in line:
                # 找到下一行作为概要
                idx = lines.index(line)
                if idx + 1 < len(lines):
                    preview = lines[idx + 1].strip()
                    if preview and not preview.startswith('#'):
                        return preview[:200] + ('...' if len(preview) > 200 else '')
        
        # 如果没有找到概要，返回前200字符
        clean_text = summary_text.replace('#', '').replace('*', '').strip()
        return clean_text[:200] + ('...' if len(clean_text) > 200 else '')
    
    def _send_email(self, subject: str, html_content: str) -> bool:
        """
        发送HTML邮件
        
        Args:
            subject: 邮件主题
            html_content: HTML内容
            
        Returns:
            发送是否成功
        """
        try:
            # 创建邮件
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = self.recipient_email
            
            # 添加HTML内容
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(html_part)
            
            # 发送邮件
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        测试邮件连接
        
        Returns:
            连接是否成功
        """
        if not self.enabled:
            return False
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
            
            logger.info("Email connection test successful")
            return True
            
        except Exception as e:
            logger.error(f"Email connection test failed: {e}")
            return False
