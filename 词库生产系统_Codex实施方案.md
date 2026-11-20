# 英英释义词库生产系统：Codex 可执行技术方案 V1.0

日期：2026-11-13
状态：开发规格（不是已实现功能）

## 0. 目标与边界

开发独立 Python CLI 项目 `vocab-pipeline`，将**已获合法使用许可**的词表与 Princeton WordNet 3.0 词义数据匹配，使用可替换 LLM 生成学习者友好的英文释义与例句，经过结构化校验、自动语义检查、人工审核后，生成可供微信小程序/CloudBase 导入的版本化 JSONL。第一批 500 个 lemma 验证，之后扩展 2,000，再到 10,000+。

不开发：小程序 UI、云函数、图片、音频、在线用户学习算法、实时查询 LLM。不得从商业词典爬取受保护内容。WordNet 授权声明及各词表许可必须留档；WordNet 不能直接提供 CET/CEFR 级别、词频或考试词表归属。

**成功定义**：相同源数据+配置+固定模型输出缓存可重现相同导出；中断可续跑；未审核记录不可发布；所有发布义项可追溯到来源；导入幂等。

## 1. 技术栈

- Python >=3.11，`uv` 管理依赖和锁文件（若环境不具备 uv，允许 pip + venv，但文档须统一一种）。
- CLI：Typer；数据模型：Pydantic v2；HTTP：httpx；重试：tenacity；测试：pytest；格式/静态检查：ruff。
- WordNet：下载**指定版本 3.0** 原始数据库并记录 SHA256、许可证，不使用隐式自动下载；解析可用 `nltk.corpus.reader.WordNetCorpusReader` 或自定义适配器，必须测试 3.0 版本一致性。
- 本地状态：SQLite（SQLAlchemy 或标准 sqlite3），事务写入；交付 JSONL UTF-8。
- LLM：OpenAI-compatible HTTP 适配器，环境变量提供 base_url/model/key；不在代码中硬编码供应商；必须支持 mock/offline 模式。
- 配置：`config/*.yaml` + `.env`，密钥不得提交 Git。

## 2. 项目目录

```text
vocab-pipeline/
  pyproject.toml
  uv.lock
  .env.example
  .gitignore
  README.md
  LICENSES/
    README.md
  config/
    pipeline.yaml
    prompt_v1.txt
  data/
    raw/                 # 不提交第三方原始内容
    interim/
    output/
    state/
  src/vocab_pipeline/
    __init__.py
    cli.py
    config.py
    models.py
    storage.py
    provenance.py
    ingest.py
    normalize.py
    wordnet_adapter.py
    sense_selection.py
    llm_client.py
    prompts.py
    validate.py
    review.py
    export.py
    report.py
  tests/
    fixtures/
    test_normalize.py
    test_wordnet.py
    test_llm_schema.py
    test_validation.py
    test_resume.py
    test_review.py
    test_export.py
  docs/
    schema.md
    provenance.md
    runbook.md
    review_guide.md
```

## 3. 输入与授权

### 3.1 输入 CSV

`data/raw/wordlists/<book_id>.csv`：`lemma,source_ref,rank`（rank 可空）；`book_id` 在配置中定义。禁止默认附带来源不明的考试词表。提供 20 条**自行编写的开发 fixture**供端到端测试。正式数据导入前，在 `data/raw/sources.yaml` 逐个记录：来源、URL、获取日期、许可证名称/文本位置、允许商用/修改/再分发/云端存储与否、是否要求署名、审核人、审核日期。未知许可标记 `blocked`，禁止进入正式发布。

### 3.2 WordNet

从 Princeton WordNet 官方渠道获取 3.0，校验版本及 SHA256；保存原始 synset offset、POS、lemma、原始 gloss、example（如有）及来源信息。注意 WordNet 的 synset 不等于考试词汇常用义；不得按 synset 枚举顺序当作词频排序。多义词必须按 POS/sense 单独建模。

## 4. 数据模型（Pydantic v2）

```python
class SourceRef(BaseModel):
    source_name: str
    source_version: str
    source_id: str
    license_id: str

class CandidateSense(BaseModel):
    sense_id: str                # 稳定 ID：wn30:<pos>:<offset>
    lemma: str
    pos: Literal['noun','verb','adj','adv']
    source_definition: str
    source_examples: list[str] = []
    source: SourceRef
    selection_status: Literal['candidate','selected','excluded','needs_review']

class GeneratedSense(BaseModel):
    sense_id: str
    simple_definition: str
    example_en: str
    target_level: Literal['A1','A2','B1','B2','C1','C2','unknown']
    model_id: str
    prompt_version: str
    generation_hash: str
    validation_errors: list[str] = []
    review_status: Literal['pending','approved','rejected','needs_revision'] = 'pending'
    reviewer: str | None = None
    reviewed_at: str | None = None

class PublishedSense(BaseModel):
    sense_id: str
    pos: str
    definition_en: str
    example_en: str
    source: SourceRef

class PublishedWord(BaseModel):
    word_id: str                 # 稳定：w_<normalized_lemma>（冲突时可逆编码）
    lemma: str
    senses: list[PublishedSense]
    book_ids: list[str]
    content_version: int
```

规范化：Unicode NFKC、trim、大小写标准化但保留原拼写展示字段；连字符、撇号、词组不得粗暴删除；词形还原单独记录，不能自动把 `saw` 强制合并到 `see`。单词与义项 ID 必须稳定；如果 WordNet 无匹配，写入 `unmatched`，不得让 LLM 虚构来源义项。

## 5. 流水线与状态机

`INGESTED -> NORMALIZED -> MATCHED -> SELECTED -> GENERATED -> VALIDATED -> APPROVED -> EXPORTED`

失败/分支：`UNMATCHED`, `AMBIGUOUS`, `GENERATION_FAILED`, `VALIDATION_FAILED`, `REJECTED`, `BLOCKED_LICENSE`。状态持久化到 SQLite，使用 `job_id`, `record_id`, `input_hash`, `pipeline_version`, `attempt_count`, `last_error`, `updated_at`。每个阶段幂等；相同 `input_hash + prompt_version + model_id + generation_config` 不重复付费生成。允许 `--retry-failed`，不得无界重试。

### 阶段 A：导入
- 校验 CSV 表头、空值、重复、编码、来源许可；导入多个词书时按 lemma 去重，保留多词书关联。
- 输出：总数、去重数、无效词数、授权阻断数。

### 阶段 B：WordNet 匹配
- 按 lemma + POS 查找 synset；保存所有候选，不自行臆断哪个是“最常见”。
- V1 义项选择：仅在人工维护的 `sense_selection.csv` 指定 `sense_id` 后标记 `selected`；可允许明确的单义项自动选择，其他多义词 `needs_review`。这保证不会错误地把冷僻义作为学习首义。
- 未匹配的词进入人工补充队列；无合规补充来源时不发布。

### 阶段 C：LLM 生成
- 每个 selected sense 单独调用；传入 lemma、POS、WordNet gloss、源例句（如有）、目标语言难度。
- 只允许生成简明释义和**原创例句**，不得新增语义、编造词性或覆盖来源。
- 使用严格 JSON Schema/Pydantic 解析；temperature 可配置，默认 0；模型输出缓存原文和解析结果，日志脱敏。
- 并发默认 3，限流、指数退避，429/5xx 重试最多 3 次；超限记录失败可恢复；按请求/输出 token 和估计费用写报告。

提示词最低要求：

```text
You are producing learner-friendly English dictionary entries.
Use ONLY the supplied sense as the semantic ground truth.
Return one JSON object matching the schema, no markdown.
Write one short plain-English definition and one original natural example.
Do not include Chinese. Do not include the target lemma or its inflections in the definition.
Do not add new meanings, etymologies, frequencies or unsupported CEFR claims.
If the sense cannot be safely simplified, return needs_human_review=true with a reason.
```

`target_level` 仅表示**生成目标**，不是权威 CEFR 词级认证；模型不能自证准确性。

### 阶段 D：自动验证
- 结构字段、非空、长度（释义 4–30 个英文词，例句 4–25 词；阈值可配置）。
- 检测中文/CJK、HTML、异常控制字符、目标 lemma/词形在释义中的泄漏。
- 例句必须包含目标词或合理词形（可配置，词形检查不能只用子串）。
- 简单词汇覆盖率：使用经授权/人工确认的基础词汇表；超出阈值仅告警，不直接等同错误。
- 语义一致性：使用第二次 LLM 或人工复核；**LLM 自检只是风险信号，不构成审核通过**。
- 输出 error codes：`SCHEMA_INVALID`, `LEMMA_LEAK`, `NON_ENGLISH`, `EXAMPLE_MISMATCH`, `SENSE_DRIFT_SUSPECTED`, `TOO_COMPLEX`, `LICENSE_BLOCKED`。

### 阶段 E：人工审核
- 第一版使用 `review_queue.csv` 导出和 `review_decisions.csv` 导入，不开发 Web 审核后台。
- 审核列：lemma, sense_id, pos, source_gloss, generated_definition, example, warnings, decision, edited_definition, edited_example, reviewer, reviewed_at。
- `decision`：approve/revise/reject；修订后重新校验；所有操作写审计记录。
- **发布门禁：仅 `approved` 且 license 状态 `allowed` 的记录可进入正式 JSONL**。开发 fixture 只能进入 `--environment dev` 输出。

### 阶段 F：导出
- `words.jsonl`：一行一个 PublishedWord，稳定排序；`wordbooks.jsonl`；`wordbook_items.jsonl`；`manifest.json`（版本、SHA256、源许可证清单、词数/义项数、生成日期、schema_version）。
- 发布时要求词条至少一个已批准义项，`sense_id` 唯一，词书关联有效；重复运行相同输入输出字节一致（manifest 的构建时间需单独处理，不影响内容 hash）。
- `--dry-run` 可生成差异报告；未来 CloudBase 导入脚本按 `_id` upsert，不清除用户学习进度；内容升级增加 `content_version`。

## 6. CLI 合同

```bash
uv sync
uv run vocab --help
uv run vocab sources check --registry data/raw/sources.yaml
uv run vocab ingest --book cet4_core --file data/raw/wordlists/cet4_core.csv
uv run vocab normalize
uv run vocab match-wordnet --wordnet-dir data/raw/wordnet30
uv run vocab select-senses --decisions data/interim/sense_selection.csv
uv run vocab generate --limit 20 --model mock
uv run vocab generate --limit 500 --resume
uv run vocab validate
uv run vocab review export --out data/interim/review_queue.csv
uv run vocab review import --file data/interim/review_decisions.csv
uv run vocab export --environment dev --out data/output/dev
uv run vocab export --environment production --out data/output/v1
uv run vocab report --format json
uv run pytest -q
uv run ruff check .
```

以上命令为**目标接口规格**，需要 Codex 实现，不代表已经可运行。无 API Key 时 `--model mock` 必须能完成完整开发测试链路。真实 LLM 运行必须要求显式启用，不得因默认配置产生费用。

## 7. 配置与安全

`.env.example`：

```dotenv
LLM_API_KEY=
LLM_BASE_URL=
LLM_MODEL=
LLM_REQUEST_TIMEOUT=45
```

`config/pipeline.yaml`：`wordnet_version: '3.0'`, `batch_size: 50`, `concurrency: 3`, `max_retries: 3`, `prompt_version: v1`, `definition_max_words: 30`, `example_max_words: 25`, `generation_budget_usd: 5`。预算超额须停止新调用。记录 API 错误但绝不记录密钥；禁止把 `.env`、SQLite 状态库和原始受限语料提交 Git。

## 8. 质量验收

- 20 条 fixture：完整离线端到端测试通过；不需要外部 API。
- 500 词试运行：统计匹配率、选义率、生成成功率、自动校验通过率、人工通过率、单词/义项平均成本；**不预设虚假的通过率目标**，根据实际结果决定扩容。
- 必须测试：单义/多义词、同形异义词、词组、连字符、词形变化、WordNet 无匹配、API 429/超时、JSON 非法、重复运行、断点续跑、人工拒绝、未授权阻断、导出幂等。
- 人工审核建议先全审 500 词试点，确认风险类型后再考虑抽检；自动校验不能替代人工审核。
- 每次构建输出 `quality_report.json` 和 `release_manifest.json`，含准确的分母、数量、失败原因、成本和审核覆盖率。

## 9. Codex 分阶段执行计划（一次只做一阶段）

### P0 项目骨架
交付：`pyproject.toml`、CLI、配置、SQLite、models、README、20 条自制 fixture、测试。验收：`uv sync && uv run pytest -q` 成功，`vocab --help` 可运行。**不要调用真实模型**。

### P1 来源与 WordNet
交付：许可登记、CSV 导入、标准化、WordNet 3.0 adapter、候选义项及选义决策导入。验收：单义/多义/未匹配可追溯；来源未知阻断发布。

### P2 LLM 生成
交付：可替换 HTTP 适配器、mock、Prompt v1、结构化输出、限流重试、费用预算、缓存和断点续跑。验收：模拟 429、超时、坏 JSON 均不会导致批次丢失；重跑不重复请求。

### P3 校验与人工审核
交付：校验器、审核 CSV、导入审核决定、修订历史、发布门禁。验收：未经批准或授权不明的内容无法生产导出。

### P4 导出与报告
交付：JSONL、manifest、校验和、diff、质量报告、导入 CloudBase 的字段映射文档（此阶段不需接入真实云环境）。验收：稳定排序、内容 hash 可重现、关联完整。

### P5 500 词试点
交付：真实许可词表、WordNet 数据、500 词处理结果、人工审核报告、成本和问题分布。**必须先获得用户提供或确认的真实词表来源、WordNet 下载方式、LLM 供应商/预算**，不得擅自抓取或付费。验收：报告透明、可重现、可决定是否扩容。

## 10. 给 Codex 的首条指令

> 你是这个项目的实现工程师。请严格以当前技术方案为唯一开发规格。现在**只执行 P0**：搭建 Python CLI 项目、模型、SQLite 状态持久化、mock 模式和 20 条自行编写的 fixture；提供运行测试、文件清单和验收记录。不要调用真实 LLM，不要下载未确认授权的考试词表，不要开发小程序或 CloudBase，不要提前进入 P1。发现规格不明确时先在 `docs/decisions.md` 记录合理默认值；涉及付费、版权或破坏性操作时停止并询问。所有命令应能在 Windows/macOS/Linux 运行，路径使用 pathlib。完成 P0 后等待确认。

## 11. 已知决策与待确认事项

1. **首批词书**：建议 Basic 500 词作为验证集，真实 CET4/CET6 词表来源须确认。
2. **LLM 服务**：先实现兼容协议；真实服务和费用预算由用户配置。
3. **WordNet 版本**：固定 3.0；官方许可文本和数据校验值随正式源文件登记。
4. **审核方式**：V1 CSV 审核；若多人协作再建设审核 UI。
5. **CEFR**：仅用作生成难度目标，不声称获得官方词汇等级。
6. **首版多义词**：必须审核义项选择，不以 WordNet 枚举顺序充当常用义排序。
