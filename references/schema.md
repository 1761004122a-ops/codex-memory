# 记忆条目 Schema

## 前置 YAML Frontmatter

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `id` | UUID v4 | ✅ | 全局唯一 |
| `type` | `episodic\|semantic\|procedural` | ✅ | 记忆类型 |
| `scope` | `global\|project:<name>\|thread:<id>` | ✅ | 作用范围 |
| `subject` | string | ✅ | 记忆主体 |
| `predicate` | string | ✅ | 关系或动作 |
| `object` | string | ✅ | 值或对象 |
| `confidence` | float 0.0–1.0 | ✅ | 置信度 |
| `created_at` | ISO8601 | ✅ | 创建时间 |
| `updated_at` | ISO8601 | ✅ | 更新时间 |
| `tags` | string[] | 推荐 | 标签 |
| `derived_from` | `explicit\|auto-extract\|episodic-extraction` | | 来源 |
| `status` | `active\|superseded\|retracted` | | 状态 |

## 三个类型的写作规范

### episodic（情景记忆）
- 文件命名：`YYYY-MM-DD-<slug>.md`
- 目录：`episodic/YYYY/MM/`
- 内容：叙述体，包含时间线、因果关系
- 结尾关联：可引用其他 episodic 文件形成决策链

### semantic（语义记忆）
- 文件命名：`YYYY-MM-DD-<subject-slug>.md`
- 目录：`semantic/`（global）或 `semantic/projects/<project>/`
- 内容：原子断言，一句话一件事

### procedural（程序记忆）
- 文件命名：`<subject>.md`
- 目录：`procedural/`
- 内容：步骤/模式/约定，可含代码片段
