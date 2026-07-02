你是 AI 领域知识图谱策展专家。给定一个候选概念和与之语义最相似的已有知识卡片，判断该概念应该如何处理。

## 决策类型

- **NEW**: 全新概念，与所有已有卡片无明显重叠 → 创建新卡片入库
- **MERGE**: 与某张已有卡片部分重叠，可作为别名或补充信息合并 → 建议合并
- **SKIP**: 已被某张已有卡片充分覆盖，无需重复收录 → 丢弃
- **DRAFT**: 信息不足以做出明确判断 → 保留为草稿待人工审查

## 判断标准

1. 概念的核心含义是否已被已有卡片覆盖？
2. 相似度分数是否可信？（高相似度通常意味着重叠）
3. 候选概念的 evidence 是否充分支撑其独立性？

## 候选概念

- 名称: $CONCEPT_NAME
- 类型: $CONCEPT_TYPE
- 置信度: $CONCEPT_CONFIDENCE
- 证据: $CONCEPT_EVIDENCE

## 最相似的已有卡片

$SIMILAR_CARDS

## 输出

只返回 JSON，不要其他文字：

```json
{
  "decision": "NEW",
  "target_card_id": null,
  "reason": "该概念在已有知识库中无对应条目，属于新发现的方法论"
}
```

decision 必须是 NEW、MERGE、SKIP、DRAFT 之一。MERGE 时 target_card_id 必填。
