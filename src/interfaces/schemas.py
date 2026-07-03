"""Pydantic 数据验证层 — Entity / Article / Relationship / Report 模型及 API 请求/响应类型。

提供:
  - 核心数据模型 (Entity, Article, Relationship, Report)
  - API 请求模型 (Create/Update/Delete payloads)
  - API 响应模型 (分页包装、导出格式)
  - 验证工具函数

所有模型严格匹配 SQLite schema，确保 API ↔ DB 数据一致性。
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator
import re


# ═══════════════════════════════════════════════════════
# 核心数据模型
# ═══════════════════════════════════════════════════════

VALID_TYPES = frozenset({
    "methodology", "company", "model", "tech",
    "concept", "product", "person", "event",
})

VALID_REL_TYPES = frozenset({
    "develops", "uses", "depends_on", "competes_with",
    "part_of", "related_to", "founded_by", "creates",
    "implements", "extends", "inspired_by", "supports",
})


class TimelineEvent(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}(-\d{2}(-\d{2})?)?$",
                      description="YYYY / YYYY-MM / YYYY-MM-DD")
    event: str = Field(..., min_length=1, max_length=500)


class EntityBase(BaseModel):
    """知识卡片核心字段。"""
    id: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(default="concept")
    importance: int = Field(default=3, ge=1, le=5)
    summary: str = Field(default="", max_length=5000)
    significance: str = Field(default="", max_length=8000)
    release_date: str = Field(default="")
    company: str = Field(default="", max_length=200)
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    color: str = Field(default="#999", pattern=r"^#[0-9a-fA-F]{3,6}$")

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Invalid type '{v}'. Must be one of: {sorted(VALID_TYPES)}")
        return v


class Entity(EntityBase):
    """完整实体 (含时间戳)。"""
    created_at: str = ""
    updated_at: str = ""


class EntityCreate(BaseModel):
    """POST /api/entities 请求体。"""
    id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    type: str = "concept"
    importance: int = Field(default=3, ge=1, le=5)
    summary: str = ""
    significance: str = ""
    release_date: str = ""
    company: str = ""
    tags: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    color: str = "#999"

    @field_validator("type")
    @classmethod
    def check_type(cls, v: str) -> str:
        if v not in VALID_TYPES:
            raise ValueError(f"Invalid type '{v}'")
        return v

    @field_validator("id")
    @classmethod
    def check_id(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$", v):
            raise ValueError(f"Invalid id '{v}': must be kebab-case")
        return v


class EntityUpdate(BaseModel):
    """PUT /api/entities/{id} 请求体 — 所有字段可选。"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    type: Optional[str] = None
    importance: Optional[int] = Field(default=None, ge=1, le=5)
    summary: Optional[str] = None
    significance: Optional[str] = None
    release_date: Optional[str] = None
    company: Optional[str] = None
    tags: Optional[list[str]] = None
    aliases: Optional[list[str]] = None
    timeline: Optional[list[dict]] = None
    color: Optional[str] = None

    @field_validator("type")
    @classmethod
    def check_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_TYPES:
            raise ValueError(f"Invalid type '{v}'")
        return v


class RelationshipCreate(BaseModel):
    """POST /api/relationships 请求体。"""
    source_id: str = Field(..., min_length=1, max_length=100)
    target_id: str = Field(..., min_length=1, max_length=100)
    rel_type: str = Field(..., min_length=1, max_length=50)
    label: str = ""


class ArticleBase(BaseModel):
    """文章核心字段。"""
    id: str = Field(..., min_length=1, max_length=200)
    title: str = Field(..., min_length=1, max_length=500)
    url: str = Field(..., min_length=1, max_length=2000)
    source: str = ""
    published: str = ""
    content_raw: str = ""
    categories: list[str] = Field(default_factory=list)
    title_cn: str = ""
    one_liner: str = ""
    summary_points: list[str] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=5)
    score_reason: str = ""
    cluster_id: str = ""


# ═══════════════════════════════════════════════════════
# 分页响应模型
# ═══════════════════════════════════════════════════════

class PaginatedResponse(BaseModel):
    """标准分页响应包装。"""
    data: list[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    has_next: bool = False


# ═══════════════════════════════════════════════════════
# Pipeline 触发模型
# ═══════════════════════════════════════════════════════

class PipelineRunRequest(BaseModel):
    """POST /api/pipeline/run 请求体。"""
    mode: str = Field(default="daily")
    agent: bool = False
    concept_agent: bool = False
    trend_agent: bool = False

    @field_validator("mode")
    @classmethod
    def check_mode(cls, v: str) -> str:
        if v not in ("daily", "weekly", "monthly"):
            raise ValueError("mode must be daily, weekly, or monthly")
        return v


class PipelineRunResponse(BaseModel):
    status: str
    mode: str
    concept_agent: bool
    trend_agent: bool


# ═══════════════════════════════════════════════════════
# 导出模型
# ═══════════════════════════════════════════════════════

class ExportResponse(BaseModel):
    exported_at: str
    version: str
    entities: list[dict]
    articles: list[dict]
    relationships: list[dict]


# ═══════════════════════════════════════════════════════
# Research 请求模型
# ═══════════════════════════════════════════════════════

class ResearchRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500)
    depth: str = Field(default="standard")
    lang: str = Field(default="zh")
    agent: bool = False

    @field_validator("depth")
    @classmethod
    def check_depth(cls, v: str) -> str:
        if v not in ("standard", "deep"):
            raise ValueError("depth must be standard or deep")
        return v

    @field_validator("lang")
    @classmethod
    def check_lang(cls, v: str) -> str:
        if v not in ("zh", "en"):
            raise ValueError("lang must be zh or en")
        return v


# ═══════════════════════════════════════════════════════
# Entity Version 模型
# ═══════════════════════════════════════════════════════

class EntityVersion(BaseModel):
    """实体历史版本。"""
    version_id: int
    entity_id: str
    version_number: int
    data: dict
    created_at: str
