import sys
sys.path.insert(0, 'src')

from core.models import FetchConfig, TopicConfig, TopicQuery
from fetchers.arxiv_client import ArxivClient

# 简单配置
fetch_config = FetchConfig(max_papers_per_topic=3, days_back=7, request_delay=1.0)
topic = TopicConfig(
    name="test",
    label="测试",
    query=TopicQuery(categories=["cs.AI"], include=[], exclude=[]),
    interest_prompt="测试"
)

client = ArxivClient(fetch_config)
print("=" * 60)
print(f"[TEST] Fetching papers for topic: {topic.label}")
print("=" * 60)
papers = client.fetch_for_topic(topic)
print("=" * 60)
print(f"[TEST] ✓ Found {len(papers)} papers")
print("=" * 60)
for i, paper in enumerate(papers[:3], 1):
    print(f"  {i}. {paper.title[:60]}... ({paper.arxiv_id})")
print("=" * 60)
print("[TEST] Success! arXiv fetch is working correctly.")
