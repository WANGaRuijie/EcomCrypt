# EcomCrypt 筛选标准（rubric 2026-11-v2）

机器可读版本：`data/screening_rubric_v2.json`（LLM 提示词和关键词预筛都从这里生成）。改动标准时同时改两处，并把 JSON 里的 `version` 加一；旧版本的筛选结果保留，不会被覆盖。

## 一句话

**E 侧（经济／博弈／激励）× T 侧（区块链／密码学／安全／系统）只要有真实交叉，就收；只在一侧，或把这个交叉拿去用在别的领域，就不收。**

## 两侧各指什么

| E 侧：经济、策略 | T 侧：技术 |
| --- | --- |
| 博弈论、均衡、策略／理性参与者 | 区块链、分布式账本、加密货币、智能合约、DeFi、稳定币、rollup、支付通道、共识 |
| 机制设计、拍卖、市场设计、合约理论、激励相容 | 密码学与密码协议（MPC、秘密分享、承诺、零知识、公平交换） |
| 激励、奖励、手续费、定价、贿赂、合谋、带策略分析的投票／治理 | 计算机／网络／系统安全，隐私，对手模型 |
| 微观经济、产业组织、货币经济、金融（资产定价、微观结构、银行、借贷） | 分布式、并行、调度、P2P、数据库系统——**系统本身是研究对象时** |
| OR/MS：有策略或经济行为的优化／随机模型；信息系统经济学 | 形式化方法（验证、模型检测、定理证明、策略逻辑）——**用于策略或激励性质时** |
| 对上述系统的实证经济学／金融（激励、费用、价格、福利、市场结构的测量） | |

## 收录（include）

交叉不必是论文的主体，但必须真实存在：

- 带激励／策略分析的区块链协议，包括设计本身依赖激励的奠基作（Bitcoin、带奖励分析的 Backbone、PoS 等）；
- 区块链与加密资产的经济学、金融学（含实证）；
- 用于区块链或密码学的博弈论、机制设计；
- 理性密码学、理性对手；安全博弈与攻防经济学（不要求区块链，也不要求计算机安全对象：巡逻、网络拦截、审计等攻防博弈都算）；
- 博弈论／机制设计指导的分布式、并行、数据库、区块链、密码系统设计（新主题 **Incentive-Aware Systems Design**）；
- 博弈论 + 形式化方法：对区块链、密码、安全、分布式协议的均衡、激励相容等性质做形式化验证或模型检测；rational verification；用于这类系统的策略逻辑与图上博弈；
- 带策略分析的 DAO／链上治理；MEV、交易排序、费用市场；AMM／DEX；质押、借贷、清算、稳定币设计。

## 不收（exclude，需给出代码）

| 代码 | 含义 | 例子 |
| --- | --- | --- |
| `single_side_T` | 纯密码学、纯安全、纯区块链／系统工程，没有经济、策略或激励成分 | 新的共识协议只做性能；新的 ZK 证明系统；只验证功能正确性的智能合约形式化验证 |
| `single_side_E` | 纯博弈论、机制设计、经济、金融、OR，没有区块链／密码／安全／系统对象。隐私只有作为机制设计或博弈对象时才算 T 侧（差分隐私机制、隐私拍卖、隐私定价与合同、带策略分析的个人数据市场）；隐私监管、隐私偏好或企业隐私做法的实证与描述研究属于这一类（2026-11-10 决定） | 一般拍卖理论；股票市场金融；GDPR 对广告市场的影响 |
| `application_domain` | 把 E×T 机制用到**别的领域**，而不是研究这些系统本身。研究区块链对其他行业的**经济影响**不算（如比特币矿工电力需求对 hashprice 的响应，应收录）；用区块链改善能源问题、让电网指导区块链设计仍不收 | 博弈论指导的区块链激励用于边缘计算卸载；IoT、车联网、无人机、无线频谱、智能电网与能源交易、医疗、供应链、联邦学习／众包激励、元宇宙服务 |
| `forecasting_only` | 只做币价／收益预测、技术交易、ML 预测，没有机制、市场结构或激励问题 | LSTM 预测比特币价格 |
| `no_contribution` | 教程、入门、泛综述、观点文章 | 例外：同行评审 venue 上系统化 E×T 交叉本身的 SoK（仅对综述和 SoK：arXiv、SSRN、ePrint 不算同行评审；有自己模型或数据分析的预印本不受影响） |
| `superficial` | 经济侧只是装饰：题名有“博弈”“激励”，但没有模型、分析或可测的经济结论 | |

`needs_fulltext`：标题和摘要不足以判断（缺摘要、摘要很短，或交叉可能存在但不清楚）。明显不在范围内的论文不用这个标签。

## 主题标签

foundations、mining、pos、tfm、mev、amm、defi、economics（Markets & Platforms）、tokenomics、economic-security、governance、rational-cryptography，以及新增的 incentive-systems。收录时至少给一个。

## Venue 质量门槛（按 venue 决定一次，不逐篇）

- **放行**：`data/venue_registry_v1.json` 中所有 venue（core 和 targeted）。预印本只认登记表里的渠道：arXiv、IACR ePrint、SSRN、RePEc，以及 NBER、CEPR、CESifo、Cowles、BIS、ECB、IMF、美联储系列、Optimization Online（显示为 Preprint）。
- **拒收**：`data/venue_policy_v2.json`。2026-11-08 用户决定拒收 MDPI 全系、IEEE Access、Hindawi（按 DOI 前缀，未列出的刊名也覆盖），以及 SCIRP、Science Publishing Group、IJACSA。Frontiers in Blockchain 保留。2026-11-09 用户决定拒收其他预印本库和机构知识库（Zenodo、Figshare、Research Square、OSF、HAL、ECCC 等；同一作品有被接受的版本时不受影响；DROPS 上的 LIPIcs 正式论文集保留），以及名称非英文的 venue（已登记的双语刊名除外）。
- **未登记**：既不在登记表也不在拒收表。候选会被暂存、不花 LLM 费用；月报按出现次数列出这些 venue，在登记表里加一行即放行，在拒收表里加一行即永久跳过，下次运行自动重新分流。
- 只有书系名（Lecture Notes in Computer Science 等）或缺 venue 的记录先通过 Crossref／DBLP 解析出真实会议，再判断。

## 流程中的门槛顺序

1. venue 门槛（拒收的直接丢弃，未登记的暂存）；
2. 关键词预筛（便宜、偏召回；引用了目录论文的候选和旧审查队列跳过这一步）；
3. LLM 题名初筛（只删明显不相关的）；
4. 摘要补全（OpenAlex → Semantic Scholar → arXiv → Crossref）；
5. LLM 摘要判定（include / exclude / needs_fulltext，附原文摘录，摘录必须出现在题名或摘要里，容忍连字符、Unicode 差异和个别漏词，但至少 90% 的词要按原文顺序出现，否则自动降级）；
6. 书目核实（OpenAlex + Crossref，本地 DBLP 记录作为证据），再次检查 venue，与目录去重；
7. 置信度 high／medium 的 include 进入目录（`--apply`），其余进入人工复核队列。

人工决定用 `monthly.ps1 decide <DOI|arxiv:ID|题名> include|exclude --note "..."` 记录到 `data/editorial_decisions_v2.json`，优先于模型结果，且永久生效。

对手模型本身不算经济成分：安全、共识、攻击类论文，必须建模或度量收益、成本、激励或理性策略行为才算交叉（2026-11-09）。
