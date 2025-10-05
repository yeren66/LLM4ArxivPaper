import sys
sys.path.insert(0, 'src')

from core.models import FetchConfig, TopicConfig, TopicQuery
from fetchers.arxiv_client import ArxivClient

# 创建测试配置
fetch_config = FetchConfig(
    max_papers_per_topic=5,
    days_back=7,
    request_delay=1.0
)

topic = TopicConfig(
    name="test",
    label="测试主题",
    query=TopicQuery(
        categories=["cs.AI"],
        include=["llm", "large language model"],
        exclude=[]
    ),
    interest_prompt="测试"
)

print(f"[TEST] Creating ArxivClient...")
client = ArxivClient(fetch_config)

print(f"[TEST] Building query for topic: {topic.label}")
query = client._build_query(topic)
print(f"[TEST] Query string: {query}")

print(f"[TEST] Fetching papers...")
papers = client.fetch_for_topic(topic)

print(f"\n[RESULT] Found {len(papers)} papers")
for i, paper in enumerate(papers[:3], 1):
    print(f"\n{i}. {paper.title}")
    print(f"   ID: {paper.arxiv_id}")
    print(f"   Published: {paper.published}")
    print(f"   Categories: {', '.join(paper.categories)}")

if len(papers) == 0:
    print("\n[ERROR] No papers fetched! Check logs above for errors.")
    sys.exit(1)
else:
    print(f"\n[SUCCESS] Successfully fetched {len(papers)} papers")
