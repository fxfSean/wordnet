# Word Study 微信小程序

这是可在微信开发者工具中导入的原生小程序。全英文界面使用本地 NGSL 学习者词库。主页以沉浸式单屏展示今日进度、连续学习天数和 Learn/Review 入口；学习计划页可设置每日新卡目标、词书单元范围、发音口音和自动播放。学习卡先显示单词，揭晓后显示英文释义、例句（如有中文翻译则一并显示）和笔记。

P0 版本已加入：

- **单词与例句发音**：英音/美音切换、进入新卡自动播放、例句单独播放。
- **词条详情分层**：释义、例句、词组、词根、词族、同义/反义、笔记。
- **词书与单元范围**：11 本内置词书（NGSL、NAWL、TSL、BSL、NGSL-Spoken、New Dolch、CET-4、CET-6、考研、IELTS、TOEFL）、按单元起止范围学习、每日新卡目标。新增词书只需扩展 `scripts/extra_books.py` / `scripts/exam_books.py` 和 `data/wordlists`。
- **学习统计**：今日/7 天/30 天、连续天数、学习时长、掌握分布、14 天柱状图。
- **备份恢复**：导出为 JSON 文件（可分享）或剪贴板；支持从文件/剪贴板导入，包含进度、笔记和设置。
- **本地笔记**：学习页弹窗记笔记，词书详情页也可编辑。
- **更丰富的词条数据**：每义项最多两条例句，WordNet 同义词、反义词、派生词；词根拆解（`un-`、`bio`、`-graphy` 等）来自开放的希腊/拉丁词根数据；词组搭配来自考试词表配套数据。
- **沉浸式布局**：首页/学习页使用深色渐变背景、半透明 Learn/Review 数据条和底部操作栏；学习计划页使用**书架式词书封面**选择词书；词书详情采用大词头 + Tab + 例句卡片；统计页使用米白纸张卡片。未内置竞品图片或字体，均以 CSS 和系统字体实现。
- **双主题切换**：保留深绿色森林主题（Dark），新增暖纸色亮色主题（Light）。首页右上角、学习页底部、拼写练习顶部和词书计划页的 **Appearance** 均可切换；选择保存在本地设置中，原生导航栏颜色会跟随当前页面切换。

### 结合竞品页面补充的核心能力

- **三档评分**：认识 / 模糊 / 忘记。模糊会保留已有阶段但 30 分钟后重新到期，忘记 10 分钟后到期。
- **每组学习量**：学习计划页可设置 10/15/20/30 张，控制单次会话长度。
- **学习页详情入口**：学习卡上的 Details 会打开当前词的完整词条页，复用释义、例句、词族、同义/反义和笔记 Tab。
- **我的内容**：集中查看学习中的词、已收藏词、句库和笔记，并可进入拼写/听写练习。
- **句库**：学习页和词书详情页都可收藏例句，支持播放和移除。
- **拼写 / 听写练习**：按当前词书/单元抽题，支持拼写模式和听音拼写模式。
- **日历与打卡**：统计页显示当月学习日历、连续天数、累计打卡天数和学习热力等级。


## 构建和本地验证

```powershell
npm ci
npm test
```

`npm test` 会先运行 `scripts/prepare_data.py` 重新生成词库，再执行 TypeScript 编译和 Node 测试。项目根目录可导入微信开发者工具。

## 数据生成

`scripts/prepare_data.py` 从同级 `vocab-pipeline/data/interim/learner-preview.jsonl` 读取词库，并可选读取：

- `vocab-pipeline/data/state/pipeline.sqlite3`：NGSL 排名、词书链接、WordNet 同义词
- `vocab-pipeline/data/raw/wordnet30`：反义词和派生词指针
- `vocab-pipeline/data/interim/example-zh.jsonl`：例句中文翻译
- `vocab-pipeline/data/interim/definition-zh.jsonl`：释义中文翻译

生成结果：

- `miniprogram/data/catalog.gz.js`：gzip + base64 压缩后的词条、义项、例句、同义词/反义词/派生词、书/单元/排名
- 运行时由 `miniprogram/lib/fflate.js`（0.8.3，MIT，见 `LICENSES/fflate.txt`）解压；当前主包约 1.9 MB，低于微信 2 MB 单包限制

缺少可选输入时仍可构建，只是对应字段为空。

## 内置词书

| 词书 | 可用词数 | 来源 |
| --- | ---: | --- |
| General English | 2,809 | NGSL 1.2 |
| Academic English | 947 | NAWL 1.2 |
| TOEIC English | 1,232 | TSL 1.2 |
| Business English | 1,722 | BSL 1.2 |
| Spoken English | 666 | NGSL-Spoken 1.2 |
| Children's English | 823 | New Dolch List 1.1 |
| CET-4 | 3,650 | KyleBing/english-vocabulary |
| CET-6 | 2,507 | KyleBing/english-vocabulary |
| Postgraduate | 3,778 | KyleBing/english-vocabulary |
| IELTS | 1,209 | hefengxian/ielts-vocabulary |
| TOEFL | 4,531 | KyleBing/english-vocabulary |

原始 CSV 快照位于 `data/wordlists/`，来源、作者和许可见 `data/wordlists/SOURCES.md`。NGSL 系列和 NAWL/TSL/BSL/Spoken/Dolch 来自 New General Service List Project，采用 **CC BY-SA 4.0**；CET/考研/TOEFL 词表来自 KyleBing/english-vocabulary（BSD-3-Clause），IELTS 来自 hefengxian/ielts-vocabulary（MIT）。本项目只保留 headword 和顺序，释义/例句仍来自 WordNet。

> 微信主包限制为 2 MB。CET/考研/IELTS/TOEFL 的完整词表已下载到 `data/wordlists/exam_*.csv`（CET-4 4,544 / CET-6 3,991 / 考研 5,046 / IELTS 1,661 / TOEFL 10,366 个 headword），但主包中先打包“与现有词库交集 + 高频新增核心词”，因此上表是当前可学习数量，不是完整考试大纲数量。完整版建议走云端词书包或独立分包。

需要刷新快照时运行 `python scripts/fetch_wordlists.py`（NGSL 系列）和 `python scripts/fetch_exam_wordlists.py`（考试词表）。新增词书时在 `scripts/extra_books.py` / `scripts/exam_books.py` 增加元数据并放入 CSV 即可。

### 完整考试词书包（云端按需下载）

主包只放核心词；完整 CET/考研/IELTS/TOEFL 词书按需下载并缓存。先构建核心词库，再生成完整包：

```powershell
npm run build
npm run build:packages
```

生成：

```text
data/packages/
  cet4.json.gz      约 136 KB / 4,471 词
  cet6.json.gz      约 216 KB / 3,954 词
  kaoyan.json.gz    约 201 KB / 5,012 词
  ielts.json.gz     约 62 KB / 1,633 词
  toefl.json.gz     约 696 KB / 10,020 词
  manifest.json
```

部署：

1. 把 `data/packages/*.json.gz` 上传到微信云存储或 HTTPS CDN。
2. 在 `src/cloud-config.ts` 里填写：
   - 云存储：`bookPackageFileIds = { cet4: "cloud://.../cet4.json.gz", ... }`
   - 或 HTTPS：`bookPackageBaseUrl = "https://your-cdn.example.com/books"`（需要把域名加入 downloadFile 合法域名）
3. 重新构建并上传小程序。

运行时会先查 `USER_DATA_PATH/book-packages` 缓存；没有缓存才下载，下载后合并进内存词库。未配置或下载失败时自动回退到主包内的核心词。修改包内容后请同步提高 `bookPackageVersion` 让客户端重新下载。

### 词组搭配与词根内容包（按需下载）

词根已随主包下发；完整词组搭配体积较大，放在独立的内容包中：

```powershell
npm run build
npm run build:content
```

生成：

```text
data/packages/
  content.json.gz        约 514 KB / 8,186 词（7,287 词有词组，4,003 词有词根）
  content-manifest.json
```

部署方式与词书包相同：上传 `content.json.gz` 后，在 `src/cloud-config.ts` 填写 `contentPackageFileId`（云存储）或 `contentPackageBaseUrl`（HTTPS CDN）。客户端缓存在 `USER_DATA_PATH/content-packages`，学习页揭晓释义后显示 **Collocations** 和 **Word roots**；词书详情页的 **Phrases** / **Roots** Tab 也会同步出现。未配置时词组自动隐藏，不影响其他功能；修改内容后提高 `contentPackageVersion`。

### 生成中文翻译

```powershell
python scripts/translate_content.py --kind examples --dry-run
python scripts/translate_content.py --kind examples --limit 100
python scripts/translate_content.py --kind definitions
```

脚本使用 OpenAI 兼容接口，读取 `LLM_BASE_URL`（默认 `https://api.deepseek.com/v1`）、`LLM_API_KEY`、`LLM_MODEL`（默认 `deepseek-chat`）。输出为增量 JSONL，重复运行会跳过已翻译内容；生成后重新运行 `npm run build` 即可合并进词库。

### 发音数据

开发版默认使用 `src/cloud-config.ts` 中的 `audioEndpoint`（有道）生成单词发音，使用 `sentenceAudioEndpoint`（百度翻译 TTS）生成例句音频。正式上线前请替换为自有 TTS 或音频 CDN，并确认服务条款与缓存策略。例句音频为在线合成，较长句子在部分网络环境下可能失败，UI 会提示 `Audio unavailable`。真机调试时需在小程序后台把对应域名加入 **downloadFile 合法域名**，或在开发者工具中勾选“不校验合法域名”。

## 学习与复习规则

学习进度存于当前设备。学习单元以 lemma 和 WordNet sense ID 的组合定位，避免多个同义词共用同一 synset 时串进度。复习优先于新卡，Know 逐步推进至 120 天，Don't know 重置为 10 分钟后重新到期。学习页停留时会自动检查重新到期的卡，并按分钟累计学习时长；单次计时最多按 6 小时计入，避免挂机虚增。

内置词书来自 New General Service List Project（NGSL、NAWL、TSL、BSL、NGSL-Spoken、New Dolch），署名 Charles Browne、Brent Culligan、Joseph Phillips 等项目作者，采用 CC BY-SA 4.0；具体来源和许可见 `data/wordlists/SOURCES.md`。义项来自 Princeton WordNet 3.0；词组搭配来自 KyleBing/english-vocabulary（BSD-3-Clause）；词根来自 jupsh/anki-word-roots 及其引用的 Wikipedia 希腊/拉丁词根条目（CC BY-SA 4.0）。[NGSL 上游与许可](https://www.newgeneralservicelist.com/new-general-service-list) · [WordNet 许可](https://wordnet.princeton.edu/license-and-commercial-use)

## 备份与同步

统计页提供导出/导入。导出优先写入小程序用户目录并调用 `wx.shareFileMessage` 分享，不支持时回退到剪贴板；导入支持 `wx.chooseMessageFile` 选择 JSON，或从剪贴板粘贴。备份包含 `progress`、`history`、`notes`、`savedWords`、`settings`、`book`、`unitStart`、`unitEnd`，并兼容旧版本仅含 `goal/progress/history` 的数据。

当前学习记录仍以本地为准，尚未写入云端。下一步接入 `vocabApi` 时，应把每条评分作为带 `eventId` 的事件上传，在服务端按 `(openid, event_id)` 幂等写入，再拉取 `user_word_progress` 合并。

## 下一步云端联调

1. 客户端已配置 `fans-app-dev-d9girw5u7fd52b3fa`。开发者工具可列出该环境的云函数，但当前 AppID 的环境列表仅显示 prod。云端联调前确认小程序已绑定目标 dev 环境，再验证小程序运行时调用权限。
2. 目标环境使用 PostgreSQL。本地迁移草案在 `cloudbase/migrations/`，使用独立的 `vocab` schema，供服务器端访问。部署时需要核验目标环境的迁移历史及云函数数据库角色权限。
3. 实现 `vocabApi` 的进度写入/拉取，使用微信上下文中的 OPENID。进度写入和事件去重应在同一事务中执行，按 OPENID 和事件 ID 保证幂等。跨设备同步队列保留原事件 ID。
4. 保留本地调度函数的测试用例用于云端算法验收，联调每日学习、到期复习和离线重传。
5. 确认正式词库及来源许可后生成云端导入包。考试词书需在授权完成后补入。词根/词组内容已接入开放许可数据，云端正式版仍需复核来源与署名。

PostgreSQL 以 `(word_id, sense_id)` 标识义项。查询时由 `vocabApi` 按 `display_order` 组装前端的义项数组，只返回审批通过的正式内容。写入时由云函数从微信上下文获取 OPENID，在同一事务内记录事件和更新进度；重传用 `(openid, event_id)` 找到原事件及返回结果。

目前云函数源码在 `cloudbase/functions/vocabApi/`。首版提供 `health`、`wordbook.list` 和 `word.lookup`。后两项要求微信调用上下文。SQL 读取函数只授权服务端角色，查词限定为已启用词书中的已审批义项。学习记录写入和同步尚未接入此版本。

### 导入 NGSL 开发预览

`python scripts/prepare_cloud_import.py --out <新的输出目录>` 对照本地 SQLite 和学习者 JSONL 验证释义与例句来源，再生成 PostgreSQL SQL 批次。先执行 `0000.sql` 创建词书，再执行后续批次。批次按稳定主键插入，重复导入会跳过已存在资料。导入的义项默认为 `pending`，新词书默认为停用。审核和启用词书完成后，正式查词接口才会返回这些数据。
