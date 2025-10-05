"""Configuration loading helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

from core.models import TopicQuery, TopicTask

ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass(slots=True)
class OpenAIConfig:
    api_key: str
    model: str
    temperature: float
    base_url: str


@dataclass(slots=True)
class FetchConfig:
    days_back: int
    max_papers_per_topic: int
    request_interval: float


@dataclass(slots=True)
class RelevanceDimension:
    name: str
    weight: float


@dataclass(slots=True)
class RelevanceConfig:
    dimensions: List[RelevanceDimension] = field(default_factory=list)
    pass_threshold: float = 60.0
    max_retries: int = 2


@dataclass(slots=True)
class SummarizationConfig:
    task_list_size: int
    max_sections: int
    max_question_retries: int


@dataclass(slots=True)
class SiteConfig:
    output_dir: Path
    base_url: str
    locale: str


@dataclass(slots=True)
class EmailConfig:
    enabled: bool
    sender: str
    sender_password: str
    smtp_host: str
    smtp_port: int
    use_tls: bool
    recipients: List[str]
    subject_template: str


@dataclass(slots=True)
class RuntimeConfig:
    max_concurrency: int
    cache_enabled: bool
    cache_dir: Path
    console_level: str


@dataclass(slots=True)
class PipelineConfig:
    openai: OpenAIConfig
    fetch: FetchConfig
    relevance: RelevanceConfig
    summarization: SummarizationConfig
    site: SiteConfig
    email: EmailConfig
    runtime: RuntimeConfig
    topics: List[TopicTask]
    raw: Dict[str, Any]


def _expand_env_values(obj: Any) -> Any:
    """Recursively replace ``${VAR}`` substrings with environment values."""

    if isinstance(obj, dict):
        return {key: _expand_env_values(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_expand_env_values(item) for item in obj]
    if isinstance(obj, str):
        return ENV_PATTERN.sub(lambda m: os.getenv(m.group(1), ""), obj)
    return obj


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _load_topics(config: Dict[str, Any]) -> List[TopicTask]:
    topics_cfg = config.get("topics", []) or []
    tasks: List[TopicTask] = []

    for entry in topics_cfg:
        name = entry.get("name")
        if not name:
            raise ValueError("Each topic requires a unique 'name' field")

        label = entry.get("label", name)
        query_cfg = entry.get("query", {}) or {}
        query = TopicQuery(
            categories=_as_list(query_cfg.get("categories")),
            include_keywords=_as_list(query_cfg.get("include_keywords")),
            exclude_keywords=_as_list(query_cfg.get("exclude_keywords")),
        )

        interest_prompt = entry.get("interest_prompt", "").strip()

        tasks.append(TopicTask(name=name, label=label, query=query, interest_prompt=interest_prompt))

    return tasks


def _load_relevance(config: Dict[str, Any]) -> RelevanceConfig:
    dims_cfg = config.get("scoring_dimensions", []) or []
    dimensions = [
        RelevanceDimension(name=str(item.get("name", f"dim{i}")), weight=float(item.get("weight", 0.0)))
        for i, item in enumerate(dims_cfg)
    ]

    return RelevanceConfig(
        dimensions=dimensions,
        pass_threshold=float(config.get("pass_threshold", 60)),
        max_retries=int(config.get("max_retries", 2)),
    )


def load_pipeline_config(path: Path | str = Path("config/pipeline.yaml")) -> PipelineConfig:
    """Load, normalize, and validate the pipeline configuration."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Pipeline configuration not found: {path}")

    with path.open("r", encoding="utf-8") as fh:
        raw_cfg = yaml.safe_load(fh) or {}

    expanded = _expand_env_values(raw_cfg)

    openai_cfg = expanded.get("openai", {})
    fetch_cfg = expanded.get("fetch", {})
    relevance_cfg = expanded.get("relevance", {})
    summarization_cfg = expanded.get("summarization", {})
    site_cfg = expanded.get("site", {})
    email_cfg = expanded.get("email", {})
    runtime_cfg = expanded.get("runtime", {})

    config = PipelineConfig(
        openai=OpenAIConfig(
            api_key=openai_cfg.get("api_key", ""),
            model=openai_cfg.get("model", "gpt-4o-mini"),
            temperature=float(openai_cfg.get("temperature", 0.2)),
            base_url=openai_cfg.get("base_url", "https://api.openai.com/v1"),
        ),
        fetch=FetchConfig(
            days_back=int(fetch_cfg.get("days_back", 7)),
            max_papers_per_topic=int(fetch_cfg.get("max_papers_per_topic", 40)),
            request_interval=float(fetch_cfg.get("request_interval", 1.0)),
        ),
        relevance=_load_relevance(relevance_cfg),
        summarization=SummarizationConfig(
            task_list_size=int(summarization_cfg.get("task_list_size", 5)),
            max_sections=int(summarization_cfg.get("max_sections", 4)),
            max_question_retries=int(summarization_cfg.get("max_question_retries", 2)),
        ),
        site=SiteConfig(
            output_dir=Path(site_cfg.get("output_dir", "site")),
            base_url=site_cfg.get("base_url", ""),
            locale=site_cfg.get("locale", "zh-CN"),
        ),
        email=EmailConfig(
            enabled=bool(email_cfg.get("enabled", False)),
            sender=email_cfg.get("sender", ""),
            sender_password=email_cfg.get("sender_password", ""),
            smtp_host=email_cfg.get("smtp_host", "smtp.gmail.com"),
            smtp_port=int(email_cfg.get("smtp_port", 587)),
            use_tls=bool(email_cfg.get("use_tls", True)),
            recipients=_as_list(email_cfg.get("recipients")),
            subject_template=email_cfg.get("subject_template", "LLM4Reading digest - {run_date}"),
        ),
        runtime=RuntimeConfig(
            max_concurrency=int(runtime_cfg.get("max_concurrency", 4)),
            cache_enabled=bool(runtime_cfg.get("cache_enabled", True)),
            cache_dir=Path(runtime_cfg.get("cache_dir", "cache")),
            console_level=str(runtime_cfg.get("console_level", "info")),
        ),
        topics=_load_topics(expanded),
        raw=expanded,
    )

    if not config.topics:
        raise ValueError("At least one topic must be defined in config/pipeline.yaml")

    return config
