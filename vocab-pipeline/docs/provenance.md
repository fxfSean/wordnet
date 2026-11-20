# 来源登记与 WordNet 3.0

将 `config/sources.example.yaml` 复制到 `data/raw/sources.yaml`。在 `config/pipeline.yaml` 的 `books` 中列出已配置的词书 ID。登记词书来源、版本、原始 URL、取得日期、许可证标识和名称、许可证文件路径、权限、署名条件和审核信息。日期使用 YYYY-MM-DD。许可证路径可相对于登记文件所在目录。

来源须经审核标记为 `allowed`，并具备商用、修改、再分发和云端存储权限。未登记、未审核、禁止相关用途、缺少必填信息或缺少许可文件时，有效许可状态为 `blocked`。同一词条的每条词书关联单独保留许可状态。混合来源中只要有一条允许的关联，词条可参与匹配。受阻关联仍保留为溯源记录。

WordNet 输入使用经确认的 Princeton WordNet 3.0 原始数据库。将发行版的 `dict` 中四组 `index.*` 和 `data.*` 原样放入 `data/raw/wordnet30`，在登记表填写实际取得来源并保存随发行版提供的许可证。数据库依赖字节偏移，解包后应保留原始换行。许可参考 [Princeton WordNet 3.0 许可证](https://wordnet.princeton.edu/documentation/wnlicens7wn)。

根据核验过的发行文件准备 `sha256.json`。其格式是以文件名为键、64 位小写十六进制 SHA256 为值的 JSON 对象，包含 `index.noun`、`data.noun`、`index.verb`、`data.verb`、`index.adj`、`data.adj`、`index.adv`、`data.adv`。匹配时程序核对摘要和 3.0 文件头。登记及摘要随匹配结果保存在 SQLite。文件结构参考 [Princeton WordNet 数据库格式](https://wordnet.princeton.edu/documentation/wndb5wn)。

SQLite 的 `p1_books` 保存词书输入快照，`p1_words` 保存规范化词条、原拼写、来源引用、词书关联和候选义项，`p1_wordnet` 保存最近一次匹配所用的来源和摘要。阶段状态可在 `records` 中按 `job_id = 'p1'` 查询，词书记录 ID 带有 `book:` 前缀。

使用 `prepare-wordnet` 安装官方包时会一并校验并记录 `index.sense`、四个词性的 `*.exc` 及 `LICENSE` 摘要。既有本地八文件清单仍可用于匹配。若缺少辅助数据，例外还原或历史语料推荐的证据相应减少。[WordNet 发行包说明](https://wordnet.princeton.edu/documentation/wnpkgs7wn) · [词义标注数说明](https://wordnet.princeton.edu/documentation/cntlist5wn)
