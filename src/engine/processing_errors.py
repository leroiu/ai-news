"""Pipeline 处理错误的结构化语义。"""

from __future__ import annotations

from collections.abc import Iterable


class ProcessingError(RuntimeError):
    """一个阶段对一组文章的可重试处理失败。"""

    def __init__(
        self,
        stage: str,
        failure_kind: str,
        article_ids: Iterable[str],
        message: str,
    ) -> None:
        self.stage = stage
        self.failure_kind = failure_kind
        self.article_ids = tuple(dict.fromkeys(article_ids))
        super().__init__(message)


class StageProcessingError(ProcessingError):
    """阶段内一个或多个批次失败；成功批次的结果仍然保留。"""

    def __init__(self, stage: str, failures: list[ProcessingError]) -> None:
        self.failures = failures
        article_ids = [
            article_id
            for failure in failures
            for article_id in failure.article_ids
        ]
        kinds = sorted({failure.failure_kind for failure in failures})
        super().__init__(
            stage=stage,
            failure_kind="+".join(kinds) or "stage_error",
            article_ids=article_ids,
            message=(
                f"{stage} 阶段有 {len(self.article_ids)} 篇文章处理失败"
                f"（{', '.join(kinds) or 'stage_error'}）"
            ),
        )
