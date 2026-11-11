# 给 ChatGPT 的任务清单（由 Claude 维护）

> 用法：每次只把**一个任务**连同本文件开头的“通用规则”发给 ChatGPT。任务都设计成短上下文、可独立完成、结果可核对。
> 完成后把产出文件放进指定位置，并在本文件对应任务的“状态”一栏写上日期。Claude 下次会读取结果并合并。

## 通用规则（每次都附上）

1. 只读不改：**不要修改 `scripts/` 下任何代码**，不要改 `data/accepted_updates_v1.json`。
2. 产出写到 `.out/chatgpt/<任务ID>.json`（或指定的文件），用 UTF-8 JSON。每条结论都要附**可点开的来源 URL**；查不到就写 `"unknown"`，不要猜。
3. 判断范围时以 `SCREENING.md` 为准（E 侧经济/博弈 × T 侧区块链/密码/安全/系统，有交叉就收；单侧、用于其他领域、纯预测、泛综述不收）。
4. 不要凭作者名气、引用数或 venue 声望判断论文是否收录。
5. 一次最多处理任务里写明的批量，处理完即停。

---

## T1 核对 DBLP venue 字符串（高优先级，在首次 `dblp` 导入前后都有用）

- 背景：`data/venue_registry_v1.json` 每个 venue 有 `dblp` 字段，是 Claude 凭记忆填写的 DBLP `<booktitle>`/`<journal>` 字符串（如 CCS → `"CCS"`，Management Science → `"Manag. Sci."`）。写错会导致该 venue 的 DBLP 记录被当成“未登记”暂存。
- 做法：按 `id` 顺序每次 40 个 venue。到 dblp.org 打开该 venue 的页面，任点一篇论文的 “export record → XML”，读出 `<booktitle>` 或 `<journal>` 的确切文字；DBLP 不收录该 venue 就写 `null`。
- 产出 `.out/chatgpt/T1-dblp-strings-<批次号>.json`：
  `[{"id": "ccs", "current": ["CCS"], "observed": "CCS", "dblp_stream": "conf/ccs", "evidence_url": "https://dblp.org/rec/...xml"}]`
- 补充：11-08 又新增 40 个 venue（地方性 TCS/EconCS/密码会议、FORC/FAccT/EAAMO、TMLR、形式化方法组 LICS/GandALF/FMBC 等），一并核对。`sacrypt`（Selected Areas in Cryptography）的 DBLP 简称与 ACM SAC 都是 "SAC"，请给出它的 DBLP key 前缀（如 `conf/sacrypt`），Claude 再决定怎么区分。
- 状态：未开始

## T2 未登记 venue 的去留（每月跑完 `monthly.ps1 run` 后）

- 输入：`.out/monthly/<日期>/report.md` 中“未登记 venue”表，每次前 30 行。
- 对每个 venue 给出 `allow` / `deny` / `skip`（与本领域无关、书系、数据仓库等）三选一，理由一句话，附出版方或期刊主页 URL。`allow` 时给出建议的 `id`、`label`、完整名称、`group`（取值：EconCS, Blockchain, TCS, Systems, Security & Crypto, Econ, Finance, OR/MS, Data Management and Analytics, Interdisciplinary）、`kind`（journal/conference/workshop）。
- 标准：拒收声誉差、门槛极低的期刊或会议；成立较晚、领域较小但正规的可以接受。不确定就 `skip` 并说明。
- 产出 `.out/chatgpt/T2-venues-<日期>.json`。
- 状态：等首次运行

## T3 人工复核队列（每月跑完后）

- 输入：`report.md` 中“人工复核队列”，每次 15 篇，优先 `needs_fulltext`。
- 打开原文（arXiv、ePrint、出版方页面或作者主页），按 `SCREENING.md` 判 `include` / `exclude`。`include` 给出主题 ID（见 SCREENING.md 主题标签）；`exclude` 给出排除代码。
- 每篇附一句**原文摘录**（逐字，≤200 字符）说明经济侧和技术侧各是什么。
- 产出 `.out/chatgpt/T3-review-<日期>-<批次号>.json`：
  `[{"id": "doi:10.xxx 或 arxiv:2401.01234", "title": "...", "decision": "include", "topics": ["mev"], "code": null, "evidence_T": "...", "evidence_E": "...", "source_url": "...", "note": "..."}]`
- Claude 会把结果转成 `monthly.ps1 decide` 记录（写入 `data/editorial_decisions_v2.json`）。
- 状态：等首次运行

## T4 复核 2026-11-08 的删除与边界论文（一次性）

- 输入：`data/scope_removals_v2.json` 的 `records`（8 篇已删）和 `kept_after_review`（4 篇保留）。
- 读摘要或原文，判断 Claude 的结论是否符合 `SCREENING.md`。只需写出“同意”或“不同意”，不同意时给理由和原文摘录。
- 产出 `.out/chatgpt/T4-scope-audit.json`。
- 状态：未开始

## T5 现有目录的全量范围抽查（一次性，分批）

- 输入：`site/data/directory.json` 的 `papers`，按数组顺序每批 40 篇，只看 `title`、`venue`、`year`、`topic_ids`。
- 只挑出**疑似**违反 SCREENING.md 的论文（单侧、用于其他领域、纯预测、泛综述），附理由和来源 URL；没问题的不用列。
- 产出 `.out/chatgpt/T5-directory-audit-<批次号>.json`：`[{"id": "discovered-...", "title": "...", "suspected_code": "application_domain", "reason": "...", "source_url": "..."}]`
- 状态：未开始（共约 15 批）

## T6 小型接口核实（一次性，很快）

在浏览器里直接打开下面的 URL，记录是否返回正常结果（HTTP 状态、结果数），产出 `.out/chatgpt/T6-api-checks.json`：

1. OpenAlex 标题+摘要布尔检索：`https://api.openalex.org/works?filter=from_publication_date:2026-10-01,title_and_abstract.search:blockchain%20OR%20bitcoin&per_page=5`
2. OpenAlex 按引用过滤：`https://api.openalex.org/works?filter=cites:W2795048425&per_page=5`
3. DBLP 月度快照目录：`https://drops.dagstuhl.de/entities/collection/10.4230/dblp.xml`，记下最新一期的文件名和下载 URL 格式是否为 `https://drops.dagstuhl.de/storage/artifacts/dblp/xml/<年>/dblp-<年>-<月>-01.xml.gz`。
4. IACR ePrint OAI：`https://eprint.iacr.org/oai?verb=ListRecords&metadataPrefix=oai_dc&from=2026-11-01`，记下单页记录数、是否有 `resumptionToken`。

- 状态：未开始

## T-MR 2026-11-09 人工复核包（一次性）

- 把 `.out/chatgpt/manual-review-2026-11-09/PROMPT.md` 的内容粘贴到 ChatGPT 新对话，并上传同目录的 `review-data.json`。
- 产出 `result.json` 放回同目录，Claude 会核对后合并。venue 和收录决定在合并前由用户过目。
- 状态：等待用户发送

## T-2026-11-09b 筛选复核与作者单位（已完成，2026-11-10 合并）

材料在 `.out/chatgpt/review-2026-11-09b/`。
- 筛选：上传 `screening-data.json`，提示词见 `PROMPT-screening.md`，结果文件为 `screening-result.json`。
- 单位：共 8 份 `affiliations-NN.json`，每次对话一份，提示词见 `PROMPT-affiliations.md`，结果文件为 `affiliations-NN-result.json`。

结果放回同一目录后，由 Claude 合并：筛选结论写进 `data/editorial_decisions_v2.json`，核实结果走 promote，单位写进 `data/author_affiliations_v1.json` 的 `manual_affiliations`。

## T-2026-11-10 中等把握收录复核（已完成，2026-11-10 合并）

材料在 `.out/chatgpt/review-2026-11-10/`。上传 `medium-data.json`（327 篇），提示词见 `PROMPT-medium.md`，结果文件为 `medium-result.json`，放回同一目录。

合并方式：没被列出的论文按 `store_key` 走 `promote --apply`（keys 批次）；`flags` 里的论文放进 `review_confidence` 并写明理由，不删除任何东西。

结果：标出 121 篇，其中 110 篇排除、11 篇拿不准，都已放进 `review_confidence`；其余 206 篇写入目录（205 篇新增）。可能被误杀、值得主人看一眼的有：Q019 Sprints（USENIX Security）、Q114 "On the stability of stablecoins"、Q100 和 Q196（交易所被攻击对币价的影响）、Q142 和 Q287（现货 ETF）、Q292（DeFi 量价关系）。

主人 2026-11-10 裁定捞回 Q019、Q114、Q100、Q196（已写入 `data/editorial_decisions_v2.json` 并进入目录）。Q142、Q287、Q292 仍在 `review_confidence`。

## T-2026-11-10b 中等把握收录复核，第二批（已完成，2026-11-11 合并）

材料在 `.out/chatgpt/review-2026-11-10b/`。上传 `medium-data.json`（131 篇，id 为 R001 起），提示词见同目录的 `PROMPT-medium.md`，结果文件为 `medium-result.json`，放回同一目录。合并方式同上。

结果：标出 26 篇，其中 16 篇排除、10 篇拿不准，都已放进 `review_confidence`；其余 105 篇里写入 104 篇。没写入的是 R126（也是第一批的 Q318）"SoK: Blockchain Decentralization"：只有 arXiv 版的 SoK 按 `promote.in_batch` 必须等主人决定。主人 2026-11-11 裁定收录 R126，并捞回 R066、R071、R088、R112，都已进入目录。
