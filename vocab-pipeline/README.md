# vocab-pipeline

英英释义词库生产系统的 P0 骨架和 P1 来源与匹配流程。需要 Python 3.11 或更高版本和 uv。以下命令在本目录运行。

```sh
uv sync
uv run vocab --help
uv run vocab init-state
uv run vocab mock-response tests/fixtures/candidate.json
uv run pytest -q
uv run ruff check .
```

`init-state --db PATH` 可指定 SQLite 库路径。运行 `uv run vocab mock-response CANDIDATE.json` 可从单条 CandidateSense JSON 得到确定性的模拟响应。模拟响应是测试占位文本。默认配置为 `config/pipeline.yaml`，可通过 `--config` 指定其他文件。Mock 无需 API 凭据。

`.env.example` 列出后续 LLM 对接所需设置。配置加载时，进程环境变量优先于 `.env`。自行编写的 20 条输入位于 `tests/fixtures/dev20.csv`，仅供开发测试。

| 交付 | 文件 |
| --- | --- |
| 项目元数据和依赖锁 | `pyproject.toml`、`uv.lock` |
| 命令入口 | `src/vocab_pipeline/cli.py` |
| 配置与环境变量 | `config/pipeline.yaml`、`.env.example`、`src/vocab_pipeline/config.py` |
| 数据模型与 SQLite | `src/vocab_pipeline/models.py`、`src/vocab_pipeline/storage.py` |
| 离线模拟 | `src/vocab_pipeline/mock.py` |
| 测试和 fixture | `tests/` |
| 来源许可与实现决策 | `LICENSES/README.md`、`docs/decisions.md` |

## P1 来源、导入和选义

投入正式数据前，按 [来源登记说明](docs/provenance.md) 配置词书、许可证、WordNet 目录和摘要。以下用 `example_book` 作为已配置词书的示例 ID。

```sh
uv run vocab sources check --registry data/raw/sources.yaml
uv run vocab ingest --book example_book --file data/raw/wordlists/example_book.csv
uv run vocab normalize
uv run vocab match-wordnet --wordnet-dir data/raw/wordnet30
uv run vocab select-senses --decisions data/interim/sense_selection.csv
```

各处理命令输出 JSON 计数，支持用 `--db` 和 `--registry` 指定独立的状态库和登记表。选义文件表头为 `lemma,sense_id`，义项 ID 从 SQLite 的 `p1_words` 候选记录中获取。未知候选会使整份决策回滚。

### 导入官方 NGSL 1.2

在登记表中将已审核的 `basic_ngsl_1_2` 来源登记为版本 `"1.2"`、许可 ID `CC-BY-SA-4.0`，URL 填 [官方统计 CSV](https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv)，许可文件指向留档的 [CC BY-SA 4.0 正文](https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt)，并标记需署名。作者为 Charles Browne、Brent Culligan 和 Joseph Phillips。

```sh
uv run vocab sources check
uv run vocab sources import-ngsl
```

命令校验获准快照的 SHA256，保存原始 CSV，并按规范化词形去重，保留原拼写和 SFI 排名。命令输出原始、重复、无效、有效、实际写入及增量计数和失败列表。相同快照重跑的 `imported` 为零。若上游文件变化，需核验新快照和许可并更新固定摘要后再导入。发布适用的改编词表时，保留署名、许可和变更说明。

### WordNet 3.0 匹配和推荐

```sh
uv run vocab prepare-wordnet
uv run vocab sources check
uv run vocab match-wordnet --wordnet-dir data/raw/wordnet30 --book basic_ngsl_1_2
uv run vocab show-wordnet bank
uv run vocab wordnet-report --out data/interim/wordnet-quality.json
```

`prepare-wordnet` 下载固定 SHA256 的 Princeton 原始发行包，可加 `--archive PATH` 使用本地压缩包。若目录已安装，命令校验文件摘要。匹配支持使用已有的本地目录和 `--checksums PATH`。在 `data/raw/sources.yaml` 登记已审核的 WordNet 3.0 来源，许可文件指向发行包内的 `LICENSE`。详细规则见 [来源登记](docs/provenance.md)。

`--limit N` 限制本轮处理的词数，已有相同配置结果的词会跳过。可用 `--retry-failed` 重查已标记为未匹配的词。下载、校验或匹配阶段发生异常时，修复输入后重跑原命令。

精确词形和分词性的还原候选共同保存。形态还原对单词应用 WordNet 例外表及基础后缀规则，词组保留精确匹配。`index.sense` 提供的是历史语义语料标注数，默认最多推荐三项，排位阈值并列或证据不足时标记 `needs_review`。推荐优先考虑精确匹配。可在配置中调整 `wordnet_recommendation_limit` 和 `wordnet_min_tag_count`。人工选义仍使用 `select-senses`。

报告按词条归类，有精确候选即计为精确匹配，仅包含还原候选则计为词形还原匹配。比例和平均义项数以各词书全部词条为分母。词级 `needs_review` 反映规则推荐的证据不足。

### AI 学习者释义草稿

将 `.env.example` 复制为本地 `.env`，在本地配置 API 密钥。环境变量优先于 `.env`。DeepSeek 使用 JSON 模式，其他 Chat Completions 服务设置 `LLM_PROVIDER=openai_compatible`，按服务能力决定是否启用 `LLM_JSON_MODE`。其他模型需明确填写每百万输入和输出 Token 的美元单价。内置 DeepSeek 费率按官方峰值、输入未命中缓存估算。[DeepSeek 价格](https://api-docs.deepseek.com/quick_start/pricing/)

```sh
uv run vocab ai --help
uv run vocab ai generate --trial --dry-run
uv run vocab ai generate --trial --execute
uv run vocab ai estimate --book basic_ngsl_1_2
uv run vocab ai generate --book basic_ngsl_1_2 --word-limit 20 --limit 30 --execute
uv run vocab ai generate --word bank --sense-id wn30:noun:08420278 --force --execute
uv run vocab ai retry --failed --execute
uv run vocab ai report --out data/interim/ai-trial-report.json
```

`--limit` 限制义项数，`--word-limit` 限制新增任务涉及的词数，`--word` 可重复传入。默认使用已选或规则推荐的未排除义项。试跑固定选用 NGSL 的 20 个词、每词一个义项。生成前输出预计请求数及费用，缺省为预演，传入 `--execute` 才调用真实 API。按原参数重跑可继续未落库任务，失败项通过 `retry --failed` 重试。Prompt 位于 `config/prompts/<prompt_version>/`。修改模板或模型会产生新的任务标识，`--force` 保留历史版本。

结果存放在 SQLite 的 `ai_generations`，命中、失败和费用保留在 `ai_requests`。预算以 UTC 日期和单个数据库为范围，单次处理可预留重试费用并按响应 Token 调整。缺少费用回执的请求保留估算预留额。进程中断后，已提交结果会被跳过。服务端已收到但客户端尚未来得及保存的请求有可能在恢复时再次发出。

自动检查覆盖格式、目标词泄漏、长度、词形、原例句复用、同词不同义项的重复释义和基础词汇覆盖。语义检查使用模型返回的结构化自检信号，仅作风险提示。所有草稿仍需人工核对，报告中的机器通过率仅统计基础检查。

### 本地查词预览

从项目目录运行 `uv run vocab preview`，打开 [本地预览](http://127.0.0.1:8765/)。浏览器调用 `GET /api/word?lemma=bank`，后端只读 SQLite。网页显示各义项的 WordNet 原文、已有 AI 草稿及审核状态，也可展开查看接口 JSON。端口冲突时用 `--port`，使用另一份状态库时用 `--db`。

学习者视图默认请求 `GET /api/learner-word?lemma=bank`。义项依照 `display_order` 排列，`is_primary` 控制首屏。更多义项只包含其余入选条目。有人工选义时使用选中项，否则使用已有 WordNet 推荐。规则初排仍是预览数据。可运行 `uv run vocab export-learner --out data/interim/learner-preview.jsonl` 导出同样的结构。

`uv run vocab rank-learner --limit 20` 预演 AI 选义，输出请求量和费用估算。明确预算后可加 `--execute --budget <USD>`。AI 仅返回现有义项的 ID 和顺序，通过校验的结果独立存入 SQLite。学习者视图与导出会读取对应版本的选义记录，释义继续使用 WordNet 原文。
