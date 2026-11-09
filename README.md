# EcomCrypt

## 当前状态与月度维护（2026-11-08 起，取代下方 ChatGPT 阶段的轮次流程）

目录现有 **837 个作品**（2026-11-09 首次月度流程写入 2026 年 269 篇，其中预印本 207 篇；更早年份的积压尚未筛）。2026-11-09 用户决定：预印本只认 arXiv、IACR ePrint、SSRN、RePEc 及已登记的经济/金融/OR 工作论文系列；拒收名称非英文的 venue；GameSec 归入 EconCS。2026-11-08 按用户决定：拒收 MDPI、IEEE Access、Hindawi，删除 6 篇（`data/venue_removals_v1.json`）；按新标准删除 8 篇“把交叉领域用于其他领域”的论文（`data/scope_removals_v2.json`）。两者都在构建时生效，账本只追加、记录保留，改配置即可恢复。

- 筛选标准：[SCREENING.md](SCREENING.md)（机器版 `data/screening_rubric_v2.json`）。
- venue：登记表 `data/venue_registry_v1.json`（新增 75 个，含 GameSec、ACSAC、RAID、TARK、AIJ、JSAC、TNSE、Quantitative Finance、DSS、PNAS 等，并为 DBLP 匹配补了 `dblp` 字段）；拒收规则 `data/venue_policy_v2.json`。
- 查看 venue 范围：打开 [VENUES.md](VENUES.md)（按组列出全部放行 venue，“加入”列标出 11-08 新增，文末是拒收清单）。
- 交给 ChatGPT 的任务：[CHATGPT_TASKS.md](CHATGPT_TASKS.md)。
- 流程配置：`data/pipeline_config_v1.json`（模型、单次运行预算上限、并发、回看天数）。

### 为什么以前慢，现在怎么做

以前每 10 分钟一轮、每轮 250 条，由代理逐条补证据，4,619 条待审里 4,147 条只是缺摘要。现在改为一次性批处理：

1. **本地 DBLP**：每月下载官方 XML 快照（约 0.94 GB 压缩，CC0，Dagstuhl 镜像，不访问被反爬保护的 dblp.org 检索接口），流式解析约 15 分钟，只保留通过预筛的记录。不需要解压到磁盘。
2. **增量来源**：OpenAlex（关键词、引用目录论文的新作、目录作者的新作，各自带水位线），arXiv API，IACR ePrint 官方 OAI-PMH。ACM DL 没有开放接口，靠 DBLP + Crossref + OpenAlex 覆盖。
3. **去重记忆**：`.cache/pipeline/store.sqlite` 以 DOI／arXiv／DBLP key／OpenAlex ID／规范化题名把所有来源归并到同一作品；每个作品在同一版 rubric 下只筛一次。每次运行把筛选决定导出到 `data/screening_ledger_v2.jsonl`（进 git），缓存丢了可 `restore`。
4. **筛选**：关键词预筛 → LLM 题名初筛（80 篇/请求）→ 批量补摘要（Semantic Scholar 500 篇/请求）→ LLM 摘要判定（12 篇/请求，8 路并发）→ 书目核实 → 入库。只有低置信度和缺全文的少数论文进人工队列。

### 首次运行（在本机 PowerShell，项目根目录）

```powershell
& .\scripts\save-key.ps1 semanticscholar      # 可选，强烈建议：补摘要最快的来源
& .\scripts\monthly.ps1 init                 # 同步目录 + 导入 ChatGPT 阶段的缓存与待审队列（不联网）
& .\scripts\monthly.ps1 dblp --download      # 约 1 GB 下载 + 15 分钟解析；也可 --file 指定手动下载的文件
& .\scripts\monthly.ps1 run                  # 抓增量、筛选、核实；默认只出报告不改目录
# 看 .out/monthly/<日期>/report.md 后：
& .\scripts\monthly.ps1 run --apply --skip-feeds
python scripts/build.py check; python -m unittest discover -s tests; node --test tests/test_catalog.mjs
```

### 每月一次

```powershell
& .\scripts\monthly.ps1 dblp --download      # 新的月度快照已发布时；已导入的版本会自动跳过
& .\scripts\monthly.ps1 run --apply
```

月报 `.out/monthly/<日期>/report.md` 只列三类需要人看的东西：拟收录清单、人工复核队列、按出现次数排序的未登记 venue。venue 在登记表或拒收表里加一行后运行 `monthly.ps1 refresh`；单篇人工决定用 `monthly.ps1 decide <DOI|arxiv:ID|题名> include|exclude --note "..."`。预算按次运行封顶（默认 $2，`--budget` 可改），用完即停，未筛的留到下次，不会重复付费。

API 密钥不是系统环境变量：OpenAlex 与 DeepSeek 以 Windows DPAPI 加密保存在 `%LOCALAPPDATA%\EconCSDirectory\*.dpapi`，包装脚本运行时临时载入、退出时清除。Semantic Scholar 密钥用 `save-key.ps1 semanticscholar` 存同一位置（不存也能跑，只是限速更严）。

---

## 历史记录（ChatGPT 阶段，2026-11-06 至 11-08）


用户定向更新（60轮停止后，不新增轮次）：8篇指定论文已加入，目录582作品590发表条目。CONCUR移入TCS，分组改为OR/MS、Data Management and Analytics，联合会议简称iThings Joint，完整名称保留。FC2016奖励函数论文正式出版年为2017。6篇完成原文/作者稿模型审读，另2篇采用出版社预览/原始索引协议说明的有界编辑审查，具体限制留证；不冒充8篇完整证明审计。115项测试及重建/venue检查通过，浏览器核实分组与计数。原DeepSeek账本仍$1.7475942/$3，无新增调用；自动化保持PAUSED。未推送部署。证据：`.out/user-venues-eight-papers-2026-11-08/review.json`。

第60轮（第二阶段12/12）：采用已有作者Aniket Kate的Liar, Liar, Coins on Fire!（CCS2015），直接审读作者公开12页会议稿的可追责断言、抵押惩罚、矿工算力比例与离线支付同步限制。CPC用户seed仍因原文403保留待审，不以摘要替代完整模型。574作品582发表条目；250条不同候选初筛（core2/adjacent13/out158/uncertain77），原文/书目各完成1篇，未称250篇完整核实。115项测试及重建/venue通过。本轮DeepSeek上界$0.0374697，原累计$1.7475942/$3，全部结算。达到累计60轮上限，停止后续发现；优先来源仍余51条，停止不表示覆盖完整。阶段二最终覆盖与未解决队列另存，第一阶段报告保留。全部变更仅本地，未推送部署。

第59轮（第二阶段11/12）：将第55轮待审的Token-based Platform Finance推进为正式采用（JFE2022，144(3)，972–991；在线2021-10-10）。新找到作者公开的20页正式排版稿并核对模型、承诺代价及费用扩展；未将补摘要当作版本核实。NBER/SSRN关联与两位作者的索引身份仍保留待核，不猜测合并。573作品581发表条目；250条不同候选完成初筛（core2/adjacent9/out165/uncertain74），完成1篇此前待审的原文/实质贡献及书目核实，未称250篇完整核实。115项测试及重建/venue通过，原文和哈希已存。本轮DeepSeek上界$0.0380217，原累计$1.7101245/$3，全部结算。优先来源前沿余50条；仍有高潜力待审，不能称已找完。累计上限60轮保持，未推送部署。

第58轮（第二阶段10/12）：从已有作者待审采用Ergodic Mean-Payoff Games for the Analysis of Attacks in Crypto-Currencies（CONCUR2018），直接审读官方17页模型、矿池扣块/双花/简化PoS案例与实验。有限零和最坏情形与示例矿工迁移概率不泛化为真实网络利润均衡；补正缓存arXiv标签，关联预印本不重复计数。572作品580发表条目；250条不同候选完成初筛（core1/adjacent5/out151/uncertain93），独立原文及书目核实各1篇，未称250篇完整核实。115项测试及重建/venue通过，官方HTML/PDF与哈希已留存。本轮DeepSeek上界$0.0357624，原累计$1.6721028/$3，全部结算。优先来源前沿余49条待审，仍未收敛；累计60轮上限保持，未推送部署。

第57轮（第二阶段9/12）：新增已有Zikas作者FairMM（CSCML2022，MEV+RationalCryptography），核实19页正式书目并从UCLA作者公开链接取得28页长版，审读票据排序、罚没/收益上限及做市激励证明。保障依赖诚实观察者、reward>gas、collateral>收益上限与账本时限；不泛化为任意做市商保证。原MuhammadHamzaIshaq/MuhammadIshaq及连字署名差异留证。CSCML归Security&Crypto/targeted，未猜索引ID。571作品579发表条目；250条不同候选初筛（core12/adjacent12/out112/uncertain114），仅1篇独立原文/书目核实，未称250篇完整核实。115项测试及重建/venue通过。本轮DeepSeek上界$0.0386661，原累计$1.6363404/$3，全部结算。前沿余49条来源待审，未收敛，累计60轮上限保持。未推送部署。

用户定向更新：新增A2MM（arXiv2021预印本；AMM+MEV），已读原文模型与评估，正式版未核实；570作品578发表条目。首页介绍、灰色斜体说明与RuijieWang页脚按用户文字替换；Topics淡蓝、Venues暖米色并加强边框间距。115项测试、重建及venue检查通过，预算不变，未推送部署。

第56轮（第二阶段8/12）：已有Zikas作者缓存新增Byzantine Agreement with a Rational Adversary（ICALP2012），审读12页会议稿的效用定义、可行性与部分证明；已知偏好/单一集中理性对手的条件不等于任意恶意多数容忍，长版证明未全核。核正该篇JonathanKatz/索引JonathanI.Katz署名，原输入保留。569作品577发表条目。续接106条初筛，core15/adjacent8/out71/uncertain12，均无自动采用；此前完成132条未重筛，失败付费12条单列证据恢复，不重付。原文/书目各核实1篇，未完成250完整核实目标。89Python/26网页与重建/venue通过。本轮DeepSeek上界$0.0245448，原累计$1.5976743/$3，全部结算；优先来源前沿余38条，未收敛，60轮上限保持，未推送部署。


优先作者待审前沿：`.out/scheduled-curation/round-060/priority-author-review-frontier.json`；未解决条目续审，已读来源ID不重复初筛。全量书目不加过滤，内容审查排序先看交叉领域线索，再看指定作者；缺摘要不作为负面判断。
第二阶段：已停止定时触发（达到60轮上限）；已有作者深挖、原文贡献及正式版本核实优先。已完成累计60轮，第二阶段12/12，累计60轮上限与原3美元账本保持。250条为目标，未完成时如实保留游标。

## 漏项修复与完整作者书目补查（2026-11-07）

用户指出的JCO漏项已修正：`Discouraging pool block withholding attacks in Bitcoin` 正式版为Journal of Combinatorial Optimization 43(2),444–459,2022，DOI `10.1007/s10878-021-00768-4`；原2020预印本已关联隐藏，旧题名仍可搜索。JCO加入ORMS，Bo Li经机构ORCID核实后加入优先作者补查。此前正式记录已在缓存中，但预印本标题Bitcoin(s)差异、两源退避及作者完全无ID使正式版/作者入口未接通，不能只归因于venue。作者普查现额外纳入没有researcher行的完全无ID署名；它们是待核发表观察，不代表已判定为不同人。78项Python、21项网页与重建/venue检查通过，无新增付费调用。可追溯报告：`.out/jco-venue-recall-2026-11-07/review.json`。

本次取得43,912条不同来源记录，503/882个已关联作者索引身份的书目到达末页，379个尚未完成，另11条缺OpenAlex身份记录待核。首次429限流后停止；游标、原始记录及全项目退避已保存。484条交叉题名提名中有346条未筛来源（332个题名组），均不算已收录。报告：`.out/recall-audit-2026-11-07/summary.json`。77项Python、20项网页及重建通过；543个作品、551个发表条目保持，DeepSeek无新增调用，原累计上界$1.1941008/$3。

发现过不等于审查完。旧流程把缺摘要、摘要太短、引文校验失败的结果写成 `screened`，随后又按历史 ID 去重，造成待核问题不再被跟进。Mining Pools 的历史引文校验失败、Underlying Incentives 的过短摘要、Welfare-Increasing Collusion 的缺摘要均有旧报告可追溯。另有正式版/改题核实卡点，不能全部归因于摘要。

现在 `review_evidence` 是独立的持久待审通道，保留原始输入、实际提供给模型的摘要、历次分类与编辑结论。缺摘要不作负面范围结论；交叉领域题名与负面分类冲突时需补查出版方/作者原文。题名仅触发复核，不授权收录。已有摘要不会被空响应覆盖，也不再截去第1,800字符后的内容。已有收录的证据审计遇到不确定时保留原目录，不能因缺摘要直接删除。

作者资格来自所有已采用作品及其会议/期刊条目的署名关联，venue 优先级只影响顺序。此前只读作品主记录漏掉了仅关联期刊版的作者，例如 Nick Arnosti；现已修复。作者名单按精确 OpenAlex ID 去重，不按相似姓名猜合并。无索引 ID 的署名与身份冲突另留待核。

```powershell
python scripts/recall_audit.py
& .\scripts\discover.ps1 sweep --max-pages 1200 --page-size 100
python scripts/bibliography_report.py
```

书目补查不加主题、venue、年份、摘要或引用数限制，仅排除撤稿记录；每25位作者以 OR 合并查询，减少合著论文重复下载。`.out/bibliography-sweep/manifest.json` 保存固定分组与真实游标，重复运行续页，不从头开始。只有接口返回组末页，才将该组作者标为 **OpenAlex 书目拉取完成**；这不代表索引覆盖全部真实发表、身份都正确，或论文已逐篇审完。页数为单次安全上限，不是覆盖结论；限流/错误保留游标并退避。

`.out/bibliography-sweep/coverage.json` 报告实际覆盖及缺少身份的作者，`review-candidates.json` 只提名交叉领域题名候选。`.out/evidence-review/queue.json` 保存历史证据补查队列，独立于新发现的已处理 ID；旧模型标签不覆盖编辑结论。每轮优先消化有实质潜力的待审，不能为耗尽队列把不相关应用批量采用，也不应为缺摘要重复付费分类。尚有此类高潜力前沿时，不得宣称收敛。上述命令不调用付费 LLM，DeepSeek 原累计3美元账本保持不变。

并发约束：人工大批补查期间持有 `.out/scheduled-curation/run.lock`，定时轮次不得启动；结束后登记发现图、覆盖与未完游标，再释放空锁。不要在前一补查进程未结束时启动另一份补查。

本地核查快照（2026-11-07，用户补充挖矿种子；自动化已完成24轮）：543个作品、551个发表条目。新增MiningPools(AAMAS2015)及UnderlyingIncentives(CACM2018)，保留DOI/早期Queue版本待核实观察。自动筛选改为每10分钟，沿用原预算、质量门槛与停止条件。DeepSeek无新增调用，累计费用上界$1.1941008/$3。报告见 `.out/user-mining-seeds-2026-11-07/summary.json`；未推送或部署。

从项目根目录复验：

```powershell
python scripts/build.py check
python -m unittest discover -s tests
node --test tests/test_catalog.mjs
```

定时任务优先消化不同的缓存候选，不设最低新增数。旧待审复核与新候选分别计数；来源失败和待核实记录不算覆盖完成。DBLP 返回非 JSON 时暂停新查询一小时，退避状态保存在元数据缓存中，期间仍可读取有效缓存。

用户定向复核（2026-11-07）：`data/topic_reviews_v1.json` 保存有理由的多主题修正，不改写 Golden Seed 原始分类。`data/discovery_priority_v1.json` 保存优先作者、已审种子和液态民主待审候选。一般液态民主只作引用发现线索，仍需核实区块链或策略安全关联与实质贡献。定向复核报告逐一解释缺摘要、书目卡点、改题与分拆关系。

作者发现现在先处理优先作者、再续接未完成分页、最后选择新的排名作者。进度保存在 `.cache/author-discovery/frontier.json`，迁移既有成功访问与未完游标；“访问过”不等于“书目全部完成”。报告给出实际选中作者，不应把排名偏移当身份。显式 `--author-id` 只查指定身份；对已完整返回的作者，复查会明确标记，不算首次发现。文献全部返回也不等于全部经过范围或贡献审阅。

从项目根目录运行以下命令。包装脚本只临时加载原 Windows DPAPI OpenAlex 凭据，不加载或调用 DeepSeek；现有环境变量优先，退出时清理本次加载的值。每页最多 50 条，页数是本次请求上限，未完成的作者游标留给后续运行。

```powershell
& .\scripts\discover.ps1 authors --author-id A5047798226 --authors 1 --pages 4 --output .out/targeted/yaish.json
& .\scripts\discover.ps1 authors --author-id A5103275698 --authors 1 --pages 4 --output .out/targeted/ke-wu.json
& .\scripts\discover.ps1 citations --seed-id extra-012 --seed-id extra-013 --pages 1 --output .out/targeted/citations.json
& .\scripts\discover.ps1 parallel --authors 2 --author-offset 48 --seeds 2 --seed-offset 38 --pages 2 --output-dir .out/targeted/parallel
```

定时轮次应读取实际 `selected_authors` 与 `author_progress`，更新已完成/未完游标；续接旧作者不算新增作者，不应再要求本轮作者 ID 都未访问。发现图保存到状态的 `discovery_graph_paths` 后，按历史来源、DOI、题名与版本身份去重，才进入候选筛选。不要为验证重复执行付费筛查。

50 篇 Golden Seeds、9 个主题。目录可选 By Author（按匹配的出版记录数排序）或 By Paper（年份降序、同年标题 A–Z）。同一出版记录在每位合作者的条目下各出现一次。

当前工作目录原为空。初版沿用本机 `econcs-directory-starter.zip` 的静态网页、JSON、Python 和 Actions 分层，将可发布文件集中在 `site/`。种子来自「研究地图设计」中的用户清单。个人主页位于独立的 Jekyll 仓库。

## 本地运行

需要 Python 3.12 或更新版本。页面使用浏览器原生 HTML、CSS 和 JavaScript，无安装或编译步骤。以下命令从项目根目录运行。

```sh
python scripts/build.py build
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

在浏览器打开 [本机预览](http://127.0.0.1:8000/)。当前 Windows 工作环境可用下列 PowerShell 命令启动预览。

```powershell
$scholarPython = "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
& $scholarPython -m http.server 8000 --bind 127.0.0.1 --directory site
```

## 核实与验证

```sh
python -m unittest discover -s tests -v
python scripts/build.py check
node --test tests/test_catalog.mjs
python scripts/update.py --candidates tests/fixtures/update_candidates.json --as-of 2026-11-06 --output-dir .out/update-fixture
```

Node.js 仅用于运行网页逻辑测试。验证脚本会检查种子、证据、关联关系和生成的站点 JSON 是否一致。离线候选夹具的报告写入 `.out/update-fixture/report.json`。

重新核实种子时使用以下命令。保留证据与网页快照的变更供审阅。

```sh
python scripts/build.py verify
python scripts/build.py verify --refresh
python scripts/build.py verify --offline
```

`verify` 优先读取 `.cache/metadata/`，按需查询 OpenAlex、DBLP 和 Crossref。可设置 `OPENALEX_API_KEY` 和 `CROSSREF_MAILTO`，提高服务额度和标识查询来源。离线重建直接使用已保存的证据，`verify --offline` 则从本地查询缓存重新做匹配。来源暂时不可用会进入查询记录，低于已存的核实等级时会保护既有种子快照。没有证据支持的字段保持为空。

批量回填优先注册 OpenAlex 并在验证邮箱后获取免费 API key。Crossref 查询无需注册，提供联系邮箱即可使用 polite pool。DBLP 公共搜索无需密钥，做大批量回填时可使用官方 XML 快照。 [OpenAlex 认证](https://help.openalex.org/api/authentication/) · [Crossref REST API](https://www.crossref.org/documentation/retrieve-metadata/rest-api/) · [DBLP 快照](https://dblp.org/faq/How%2Bcan%2BI%2Bdownload%2Bthe%2Bwhole%2Bdblp%2Bdataset.html)

在运行脚本的 PowerShell 窗口输入下面两行。第一行会遮蔽密钥输入。环境变量随窗口关闭而清除。

```powershell
$env:OPENALEX_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'OpenAlex API key' -AsSecureString)).Password
$env:CROSSREF_MAILTO = Read-Host 'Crossref contact email'
```

2026-11-06 初始快照有 40 条已核实和 10 条部分核实记录、106 个研究者标识、41 个机构。OpenAlex 的 50 条种子查询均有响应。Crossref 已通过搜索和 DOI 补查补齐多数记录。DBLP 批量搜索遇到访问限制，个别条目使用可访问的 DBLP 记录页和出版方记录。离线夹具筛出 1 条可收录和 1 条待核实，最终在线试跑处理 50 条候选，1 条待核实、0 条新增。

- `data/golden_seeds_original.md` 保留原始清单。
- `data/golden_seeds_v1.json` 保留稳定种子 ID、分类、来源消息和原始引用。
- `data/verification_v1.json` 保留逐条查询、来源记录、冲突、版本及采用结果。
- `data/primary_evidence_v1.json` 保存对少量特殊版本的出版方或原始文献证据。
- `site/data/directory.json` 是可重建的网页索引。核实状态与原始引用提示分开。

## 更新候选

### Venue 检索清单

完整检索范围见 [VENUES.md](VENUES.md)，包含 224 个 venue 或发现渠道。规范配置位于 `data/venue_registry_v1.json`，网站标签和清单由同一份配置生成。修改配置后运行 `python scripts/venues.py build`。可用以下命令按清单中的 ID 搜索，脚本会先核对 OpenAlex source 的完整名称与类型。

```sh
python scripts/harvest.py --from-year 2004 --to-year 2026 --seed-limit 0 --venue teac --venue geb --venue jet --venue et --year-slices --pages 2 --output .out/venue-search/graph.json
python scripts/venues.py check
```

非唯一的来源匹配进入覆盖报告。没有正式 proceedings 的会议或报告渠道不进入本轮范围；期刊仍按正式发表版本纳入。

### 历史回填与候选图谱

```sh
python scripts/harvest.py --from-year 2004 --to-year 2026 --seed-limit 50 --source S4363608973 --source S7407105243 --proceedings db/conf/atal/aamas2024.bht --preprints --output .out/corpus-baseline/graph.json
python scripts/harvest.py --from-year 2024 --to-year 2026 --seed-limit 0 --year-slices --source S4363608973 --source S7407105243 --preprints --verify-top 5 --output .out/corpus-recent/graph.json
```

回填扫描 OpenAlex 中种子的引用与参考文献，支持逐届 DBLP 论文集 BHT 键、OpenAlex venue ID 和预印本索引。可用 `--seed-offset` 分批遍历种子，或用 `--include-reviewed` 从已纳入的核实作品继续扩展。结果包含候选、引用边、来源、抓取范围和失败原因。候选优先级结合主题线索与连接的不同种子数。低优先级条目仍保留，便于回查覆盖盲区。OpenAlex 翻页需要独立的 `OPENALEX_API_KEY`。没有密钥时，可以用 `--year-slices` 缩小 venue 和预印本查询范围，查看各分区的覆盖状态。[OpenAlex API](https://help.openalex.org/how-to/api-recipes/) · [DBLP 论文集示例](https://dblp.org/db/conf/atal/aamas2024.html)

同一研究成果的正式会议版和期刊版分别展示及计数。已关联正式版本的 arXiv、IACR ePrint 和 SSRN 记录留在版本详情里。LNCS 条目使用有论文集证据支持的会议名。新发现的同名不同 DOI 先进入版本关联队列。

```sh
python scripts/update.py --discover --dry-run
python scripts/update.py --discover
python scripts/update.py --discover --seed-citations --lookback-days 180 --dry-run --output-dir .out/seed-expansion
```

更新任务每月 1 日和 15 日运行，也可以手动触发。发现范围来自有界主题查询和已核实的作者观察名单。规则筛选和来源核实都通过的记录会自动进入暂存预览，报告保留暂缓和排除理由。手动采用时，从预览产物取出累计的 `accepted_updates_v1.json` 放入 `data/`，再运行 `python scripts/build.py build` 和 `check`。待核实队列供抽样审阅。可选 LLM 默认关闭，启用需设置 `OPENAI_API_KEY`，结果只作为分类建议，应用按次运行限制费用，详情见 SPEC。

`--seed-citations` 另外查询引用已核实种子的论文。每次最多取四个不同主题的种子，每个种子最多取八条，沿用同一套去重和核实规则。[OpenAlex 引用查询说明](https://help.openalex.org/how-to/api-recipes/)

### DeepSeek 本地筛选

Windows 上的 `scripts/expand.ps1` 会从当前环境或 `%LOCALAPPDATA%/EconCSDirectory` 中的 `deepseek.dpapi` 和 `openalex.dpapi` 加载密钥。

```powershell
& .\scripts\expand.ps1 --graph .out/corpus-baseline/graph.json --limit 18
& .\scripts\expand.ps1 --graph .out/corpus-baseline/graph.json --limit 18 --apply
```

脚本用标题、venue 和公开摘要筛选，按模型及完整输入缓存结果。默认只写报告。加 `--apply` 后，仅将模型判为核心且 DOI、作者和书目证据通过独立核实的正式版本加入本地账本。按 DeepSeek Flash 峰值价格在请求前预留费用，跨批次累计上限为 3 美元；未确认账单的请求保留全部预留额度。筛选要求摘要同时提供区块链与经济机制/策略贡献的原文证据。 [DeepSeek API 文档](https://api-docs.deepseek.com/)

## GitHub Pages

需要公开发布时，先确定独立的项目仓库和发布授权。将项目提交到该仓库后，在 **Settings → Pages** 将 Source 设为 **GitHub Actions**。在仓库 Actions 变量中设置 `SCHOLAR_PAGES_REPOSITORY` 为该仓库的 `owner/repo`，然后在默认分支手动运行 **Publish standalone Scholar Directory**，勾选 `publish`。工作流只上传 `site/`，并拒绝将个人主页型的 `*.github.io` 仓库用作目标。

经授权启用定期发布时，设置 `SCHOLAR_AUTO_PUBLISH=true`，并给 `scholar-promotion` 环境配置必需的审批人及默认分支权限。候选阶段保持只读。有新增高可信记录且审批通过时，工作流验证累计账本、提交数据快照并发布。也可手动运行更新，取消 `dry_run` 并勾选 `publish`。若默认分支规则拒绝工作流写入，继续使用暂存产物和手动发布路径。公开发布失败时，之前的 Pages 部署继续提供服务，可用手动工作流从当前有效账本重试。

[GitHub Pages 自定义工作流文档](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)


严格交叉领域扩展（累计预算 3 美元）：

```powershell
& .\scripts\expand.ps1 --audit-existing --output .out/scope-audit.json --apply
& .\scripts\expand.ps1 --graph .out/intersection-campaign/seed-network.json --all-candidates --limit 240 --output .out/strict-expansion.json --apply
```

`--all-candidates` 会将标题未命中规则的记录也交给模型。优先处理多种子引用邻居和主题候选，未处理部分仍留在图中。每批结果持续写报告；脚本全部完成并通过目录校验后才替换本地目录。缓存、累计预算和密钥存储不可删除后当作新预算继续运行。


2026-11-06 严格扩展结果见 `data/discovery_campaign_v1.json`；此前扩展记录的领域复查及移除证据见 `data/scope_audit_v1.json`。两批共新增 57 个作品，复查移除 2 个，保留 50 篇原始种子。该轮结束时共有 116 个作品节点。所有新增记录均通过双重摘要证据及独立书目核实。

此次种子网络抓取 3,655 条候选、6,077 条引用边；venue 扫描另抓取 1,536 条候选。分页有上限，venue 清单仍有未运行项。FC、EUROCRYPT、AFT、NSDI 的 OpenAlex 来源解析不唯一或未匹配；DBLP 补抓返回 HTTP 429，报告保留失败，不计作已覆盖。`--hydrate-dblp` 可将成功抓取的 DBLP 记录按精确 DOI 关联 OpenAlex，供后续摘要筛选。目录尚不代表本领域完整覆盖。


### 扩大范围与 cs.GT 预印本（2026-11-07）

在 EconCS × Blockchain 以外，允许收录博弈论 × 密码学/安全，统一标为 **Rational Cryptography and Security**。仅有普通博弈论或普通密码学贡献仍不足以收录。预印本以 **Preprint** 为 venue 子类；发现正式版后展示正式版并隐藏对应预印本。

```powershell
python scripts/add_seeds.py
python scripts/build.py build
python scripts/arxiv_harvest.py --query 'cat:cs.GT' --pages 15 --output .out/expanded-scope/cs-gt.json
python scripts/arxiv_harvest.py --query 'cat:cs.GT AND (all:blockchain OR all:cryptography OR all:security OR all:bitcoin OR all:ethereum)' --pages 10 --output .out/expanded-scope/cs-gt-focused.json
& .\scripts\expand.ps1 --graph .out/expanded-scope/cs-gt-focused.json --all-candidates --limit 1200 --target-additions 100 --output .out/expanded-scope/report.json --apply
```

11 篇新增种子保存在 `data/additional_seeds_v1.json`。其中软件附件不充当论文，正式会议版优先于索引中误标的预印本。`--target-additions 100` 是停止目标；最终收录数仍取决于证据、候选和预算。未达到目标时报告如实保留结果。

浏览链接可使用 `?view=paper` 直接进入按论文排列；`?view=author` 进入按作者排列。筛选条件在两种视图间共用。


2026-11-07 本轮完成 1,494 次筛查（1,356 个不同来源记录），两批主扩展分别新增 100 和 103 个作品，安全边界复查新增 7 个，另加入 11 篇用户种子。当前共 337 个作品、343 条可见出版/预印本记录，其中 111 条为 Preprint。140 条符合领域但书目未通过的记录留在待核查队列。报告见 `data/discovery_campaign_v2.json`，累计 DeepSeek 费用上界为 $0.343206，沿用 $3 硬上限，没有待确认计费的预留。41 项 Python 测试、12 项页面逻辑测试及重建校验通过；两种视图已在实际浏览器中检查。没有推送或公开部署。


### 多主题、作者分组与正式版核查

论文保留原有主题，可由明确的题名和已核实摘要证据增加多个标签；`topic_annotations` 保存匹配证据，新模型分类支持 `topics` 数组。没有依据时不强行添加第二个主题。右栏使用显眼的 By Author / By Paper 按钮。

ID 缺失的同名署名此前被分到了另一个条目。显示层现在将其关联到唯一同名的已知身份，同一作品只记一次。不同 ID 的同名身份保留独立，见 `data/identity_audit_v1.json`；不会仅凭同名覆盖 ORCID。Rafael Frongillo 和 Aviv Yaish 的重复显示已有回归测试。

```powershell
python scripts/publication_watch.py
python scripts/build.py build
python scripts/build.py check
python -m unittest discover -s tests
node --test tests/test_catalog.mjs
```

核查清单由 `data/proceedings_watch_config_v1.json` 管理。目前覆盖 AFT 2023–2026 和 ITCS 2025–2026；正式版依据保存在 `data/publication_watch_v1.json`。题名与完整顺序署名匹配后，将预印本升级为正式版本并保留旧记录；不同会议和期刊版本分别展示。工作流 `publication-watch.yml` 可手动运行，也按月两次生成只读审阅产物，不自动提交或部署。DBLP 当前返回反机器人 HTML，不能将它计作成功核实；此时使用官方出版方记录。尚未覆盖全部近期会议。

出版核查还支持 `python scripts/publication_watch.py --discover-latest`，从 AFT/ITCS 官方会议索引发现最新三卷，结合固定回填卷核查。工作流使用此选项，后续新卷不依赖猜测编号。

新增论文筛选可优先处理出版方候选：

```powershell
& .\scripts\expand.ps1 --graph .out/recent-proceedings/graph.json --all-candidates --prefer-publisher --limit 1200 --target-additions 100 --output .out/recent-proceedings/expansion.json --apply
```

监督检索补充的候选种子及官方归档记录保存在 `data/supervisor_seeds_v1.json`；DBLP 当前响应状态见 `data/provider_status_v1.json`。

经作者本人论文清单确认的跨 ID 显示合并保存在 `data/author_display_aliases_v1.json`，目前额外修正 Elaine Shi 的分裂条目。保留原始 ID，不覆盖原始 ORCID。

作者或会议正式确认接受、但尚无可核实 proceedings DOI 的记录单独保存在 `data/venue_acceptance_evidence_v1.json`。这类论文使用已确认的 conference 标签，详情注明正式书目待补，继续链接原始稿件，不猜测正式 DOI。


本轮修复与扩展结果见 `data/discovery_campaign_v3.json`：新增 142 个作品；当前 479 个作品、485 条可见记录，171 个作品拥有多个主题。七份官方论文集共核查 449 条论文记录，匹配 16 个作品的正式版；接受证据与已出版证据分别保存。累计费用上界 $0.798285，预算仍为 $3。47 项 Python 测试、14 项网页测试与重建一致性验证通过。Rafael Frongillo、Aviv Yaish、Elaine Shi 各只有一个显示分组。其他冲突身份继续保留待核查；没有推送或部署。


### 作者深挖与编辑质量关卡

DBLP 仅作可用时的核对来源。主发现链改为：种子/已审阅论文的引用关系 → 新论文和作者提名 → 已确认作者的分页发表记录 → 领域与实质贡献筛选 → 来源质量及书目核实。作者身份使用 OpenAlex ID，不按名字搜索后直接认人；主题匹配、作者名气和引用数不能直接决定收录。新作者提名先审阅，禁止无界多跳扩张。

```powershell
python scripts/author_discovery.py --authors 20 --pages 3 --graph .out/intersection-campaign/seed-network.json --output .out/author-first/graph.json
& .\scripts\expand.ps1 --graph .out/author-first/graph.json --all-candidates --limit 1200 --output .out/author-first/screen.json
```

发现需要 OpenAlex 密钥（沿用已有环境变量或 Windows 凭据加载方式）；默认筛选不写目录。通过 `--offset` 分批继续，不应把一页结果当完整作者履历。

`data/quality_policy_v1.json` 将书目可靠性、范围匹配和编辑质量分开。优先来源仍须贡献筛选；targeted、未知来源和预印本不再自动采用，进入 `review_quality`。这不是低声誉或掠夺性判断。经过逐篇审核的论文可以在 `paper_overrides` 中附 DOI 或来源 ID、decision、reason 和 evidence 后单独处理，因此不把顶会等级当永久门槛。明确排除的来源必须另附证据。既有目录先保留，分流审计见 `data/quality_audit_v1.json`。

用户编辑偏好已记录：Electronics 重点复核；IEEE Access 逐篇复核，不一票否决；两者都暂停自动采用。学科归类与质量判断分开，新增 JOIE、Energy Economics、CJE（ECON），Journal of Futures Markets、European Finance Review 历史别名、ICAIF（Finance），JOM（OR/MS & Platforms）等映射。分类不等于质量背书。


### 最新浏览与并行发现

左栏名称统一为 Econ、ORMS。Venue 优先采用配置缩写，未归类记录可使用原始 venue 中明确给出的括号缩写；完整名称保留在悬浮提示和搜索中。Preprint 使用紫色。网页详情不展示原始发现输入，JSON 与证据文件继续保留可追溯数据。

新增 Blockchain Governance (Game Theory)，必须同时有区块链/DAO 治理场景与策略分析证据（均衡、激励、投票、贿赂或联盟等），描述性治理不自动加此标签。原始 50 篇种子及九类输入保留，派生目录现为十类。

无 ID 的中间名变体，仅在名字/姓氏相符、中间缩写不冲突、至少有一个共同作者且候选唯一时合并显示。不同 ID 的身份继续按已确认的别名与证据处理。

```powershell
python scripts/discovery_parallel.py --authors 12 --author-offset 12 --seeds 8 --seed-offset 8 --pages 2
```

两条发现分支并行运行后合并去重；不会自动收录或扩张作者提名。试跑结果见 `data/parallel_discovery_v1.json`：1,380 条候选，其中 1,207 条尚未收录；1,071 条引用边、177 位待审新作者。


### 主题与二级选择菜单更新

ECAI、ADT、COMSOC 归入 EconCS 检索清单；仅已有收录论文的 venue 会出现在左栏。COMSOC 官方说明其 proceedings 为非正式，保留发现渠道属性，不误作正式发表版。

原 Blockchain Economics 细化为 Tokenomics & Adoption、Economic Security、Markets & Platforms。前两类按题名或已核实摘要中的明确证据赋予；原 economics 标签在有更具体分类时替换，未匹配者保留在 Markets & Platforms。Blockchain Governance 去掉显示名称后缀，博弈论贡献门槛不变。原始种子数据不变，派生目录现为 12 类。

主题按 Protocol & Incentives、Markets & Finance、Economics、Governance & Security 分组；每个主题组和 venue 组均有独立 Select All / Deselect All 按钮。顶部按钮控制整个 Topics 或 Venues。各按钮只修改目标范围；全不选仍显示零结果。


### 作者姓名优先合并（用户最新规则）

用户明确指出此小领域同名概率很低。显示分组现优先规范化姓名，跨 OpenAlex/ORCID 分裂 ID 的同名记录合并，统一大小写、重音、连字符、中间名省略与缩写。初始字母展开、姓名顺序异常等仍结合共同作者；明显冲突的完整中间名不直接抹去。原始 ID 和论文署名不覆盖，同一论文在一个作者下只计一次。作者索引基于整个目录生成，切换筛选保持相同归属；历史 ID 链接仍可打开合并后的分组。审计见 `data/author_display_resolution_v2.json`，显示合并不等于确认原始 ORCID 都正确。


### 基础性文献与菜单归类

按用户明确要求恢复 Algorand（SOSP 2017，DOI 10.1145/3132747.3132757），作为 Foundations / PoS 的基础参考，证据和人工纳入理由保存在 `data/foundational_context_v1.json`。它独立于自动扩展账本，严格范围复查不应删除用户选定的基础参考；其他纯工程论文不因此自动放行。基础参考也进入作者与引用发现的锚点。

Governance 独立成为主题分组，Cryptography & Security 单独分组。所有原 Other venues 和 Multidisciplinary 合入 Interdisciplinary；缺少 venue 的 Unlisted 独立成为二级分组，仍有自己的全选与取消全选按钮。未解析来源继续保留质量待审状态。

Interdisciplinary 下将未归类 venue 按原始名称分别列出，可独立勾选和筛选；不再提供聚合 Other 子选项。Unlisted 仅包含 venue 缺失记录。


2026-11-07 venue分类审计：修正SOSP别名、Journal of Cybersecurity、Frontiers in Blockchain等缺失分类，并区分工作坊与主会、Applied期刊与短同名刊。当前569条可见发表逐一检查，29条显示映射发生修正；85项Python/22项网页测试及数据检查通过。OpenAlex健康检查成功；48轮定时任务保持暂停。证据：`.out/venue-audit-2026-11-07/summary.json`。


第二阶段已达累计60轮上限，停止后续扩展；574作品582发表记录，预算与遗漏详见`.out/scheduled-curation/final-coverage-phase2.md`。仍有高潜力未解决前沿，不能称覆盖完整。自动化已由工具设为PAUSED并核实，后续触发取消，运行记录保留。
