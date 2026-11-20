# 正式词表候选来源报告

核验日期为 2026-11-16。范围包括 CET4、CET6、考研英语和基础英语。许可判断针对具体词表文件及拟提取字段。下表区分文件实测行数、上游声明数量与考纲词目数。全流程的规范化、有效和入库数量要在接入后实测。本次无正式入库。

## 候选清单

| 词书和候选 | 版本、更新时间及数量 | 数据许可与本地存储 | 结论和来源 |
| --- | --- | --- | --- |
| 基础英语 · NGSL 官方统计表 | NGSL 1.2，2023 年修订。官方 CSV 实测 2,809 条数据行，包含 lemma 与频率排名 | CC BY-SA 4.0。允许商用、本地复制和存储、修改及再分发。发布时需署名、注明修改，并以相同许可发布改编的词表 | **推荐首批接入**。使用官方有排名的 CSV。[项目说明与许可](https://www.newgeneralservicelist.com/new-general-service-list) · [官方 CSV](https://www.newgeneralservicelist.com/s/NGSL_12_stats.csv) · [许可条款](https://creativecommons.org/licenses/by-sa/4.0/) · [项目版本历史](https://charliebrownecompany.squarespace.com/faqs-4) |
| CET4 · WordTyper | JSON 2.0.0，文件标注 2026-07-27。固定提交中实测 3,815 行，原始拼写精确去重仍为 3,815 | 仓库声明 MIT，并说明考试词表来自 ECDICT 标签。MIT 条款允许商用、本地复制、修改及再分发，须保留版权与许可通知。考试标签的原始来源和许可仍待核验 | **待确认**。可作为四级备考词表候选。[固定版本 JSON](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/vocabularies/cet4.json) · [数据声明](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/NOTICE.md) · [MIT 文本](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/LICENSE) |
| CET6 · WordTyper | JSON 2.0.0，文件标注 2026-07-27。实测 5,371 行，原始拼写精确去重仍为 5,371 | 同上，具体考试标签的上游许可待核验 | **待确认**。保留该文件的六级口径，待核实与四级的包含关系。[固定版本 JSON](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/vocabularies/cet6.json) · [数据声明](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/NOTICE.md) |
| 考研英语 · WordTyper | JSON 2.0.0，文件标注 2026-07-27。实测 4,787 行，原始拼写精确去重仍为 4,787 | 同上，具体考试标签的上游许可待核验 | **待确认**。来源声明未给出英语一、英语二各自的覆盖口径。[固定版本 JSON](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/vocabularies/kaoyan.json) · [数据声明](https://github.com/grhliu/wordtyper-vocabularies/blob/b5790cafcad1795873410e984c834ef1ddac20ac/NOTICE.md) |
| CET4、CET6、考研 · ECDICT 上游 CSV | 仓库快照 `39cfb967`，2026-11-02 提交。三个考试标签的独立计数未核验，词典总收词数不能作为各词书数量 | 仓库提供 MIT。作者披露字典汇入过多处释义、音标及词汇资料，README 未逐项给出考试标签的原始快照和授权。拟用字段的商用、再分发及生产本地存储资格待确认 | **待确认**。若能补齐考试成员关系的来源和许可，优先从上游 CSV 按精确 `tag` 提取 `word`，减少下游依赖。[固定版本 CSV](https://github.com/skywind3000/ECDICT/blob/39cfb9672c0906b63569e0453c2e6ab9ab182a/ecdict.csv) · [上游来源与字段说明](https://github.com/skywind3000/ECDICT/blob/39cfb9672c0906b63569e0453c2e6ab9ab182a/README.md) · [MIT 文本](https://github.com/skywind3000/ECDICT/blob/master/LICENSE) |
| CET4、CET6 · exam-data/CETVocabulary | 仓库快照 `83eaa58b`，2026-10-22 提交。项目自报合计 5,278，分级数量未核验 | 数据 CC BY-NC-SA 4.0。允许非商业条件下本地存储、改编与分享，分享改编时需署名及相同许可。代码 MIT | **阻断商用导入**。[固定版本数据说明](https://github.com/exam-data/CETVocabulary/tree/83eaa58b181bc388dc7a662d00179e3d888d900a) · [许可条款](https://creativecommons.org/licenses/by-nc-sa/4.0/) |
| 考研英语一 · exam-data/NETEMVocabulary | 发布版 v7.1；仓库快照 `b1850fdd`，2026-10-22 提交。按 2024 英语一考纲，项目自报 5,530 | 数据 CC BY-NC-SA 4.0。允许非商业条件下本地存储、改编与分享，分享改编时需署名及相同许可。代码 MIT | **阻断商用导入**。适用范围为英语一。[发布记录](https://github.com/exam-data/NETEMVocabulary/releases) · [固定版本数据说明](https://github.com/exam-data/NETEMVocabulary/tree/b1850fdd51fca9143006ef54bca99b246d56c934) |
| CET4、CET6 · 中国教育考试网官方大纲 | 2016 年修订版。大纲自报 5,418 个词目，包含同形异义分列和变体，分级数量未核验 | 下载页和大纲未找到允许批量提取后商用、再分发的授权。拟议用途下的批量本地存储权限也待确认 | **待确认，仅作考纲对照**。可用来解释第三方词量与官方词目数的口径差异。[考试院大纲目录](https://cet.neea.edu.cn/xhtml1/folder/16113/1588-1.htm) · [官方 PDF](https://cet.neea.edu.cn/res/Home/1704/55b02330ac17274664f06d9d3db8249d.pdf) |
| 基础英语 · Hugging Face 上的 NGSL 派生来源 | NGSL 1.2。Fluency 来源清单记录上游 Parquet 提交和摘要，列出 2,809 行，镜像更新时间未核验 | 清单标注 CC BY-SA 4.0。许可允许商用、本地存储、改编与再分发，须遵守署名与相同许可。清单指向 NGSL 已停用的旧域名，本次未独立核验镜像文件及其版本对应关系 | **备查**。直接选作者维护的 CSV。[公开数据仓库来源清单](https://huggingface.co/datasets/iamzhangship/fluency-ecdict-offline/blob/main/focus_word_sources/SOURCE.md) · [作者的域名说明](https://charliebrownecompany.squarespace.com/faqs-4) |

## 推荐接入方案

1. 先接 `basic_ngsl_1_2`。用户确认后，将官方统计 CSV、下载地址、取得日期、版本和 SHA256 作为来源快照。登记官方许可文本及审核信息。把署名、变更说明和 CC BY-SA 4.0 条款随可分发的词表保留。
2. 考试词表继续使用 `blocked`。优先核实 ECDICT 三个考试标签分别来自哪一版词表、上游是否允许目标用途，以及 CET6 是否累计包含 CET4。WordTyper 的三个固定 JSON 是可复核的下游候选。如果最终采用这一路线，产品名称应标明是某一来源的备考词表，官方大纲覆盖率需要独立核对。
3. 下载与转换只接受通过现有许可核验的固定源。转换器提取 `lemma`、`source_ref` 和可用的 `rank`，把来源版本和原记录定位信息保存在词书关联层。沿用项目的 NFKC 和大小写、空白规范化，保留原拼写、连字符、撇号和词组。词形映射需要单独的来源记录，存在歧义时保留原词。
4. 词表原始文件、许可和词书成员关系独立于 WordNet 数据保管。通过 `word_id` 关联词条，再由匹配阶段关联 `sense_id`。来源词书的许可条件随其成员关系保留。
5. 以词书 ID、来源版本和文件摘要识别重复运行。相同摘要重复执行不插入数据，新版本先计算新增、更新及移除的关联，再在 SQLite 事务中更新该词书。多词书共享的 `word_id` 保持稳定。
6. 每套词书输出原始数据行数、无效行数、规范化重复数、有效唯一词数、实际入库的词书关联数及失败明细。另报增量新增、更新、移除和无变化数量。失败明细保留原记录定位和原因。数据源下载或许可校验失败时，保留上一份已成功导入的快照。

建议本轮仅批准 NGSL 1.2 作为首个正式接入源。考试三套待补齐可商用的来源证据后再单独确认。
