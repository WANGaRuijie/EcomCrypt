# EconCS × Blockchain venue 清单

2026-11-09 版本。共 480 个 venue 或发现渠道，分为 11 组。

core 表示优先回填，targeted 表示结合主题和种子关系筛选。两者在月度流程中都放行，区别只影响排序。
“加入”列标出 2026-11-08 新增的 venue；文末列出已拒收的 venue。修改 data/venue_registry_v1.json 后运行 python scripts/venues.py build。
会议和工作坊必须有正式 proceedings；期刊按正式发表版本核实。
预印本和工作论文已有正式会议或期刊版时不重复计数。

SBC 等尚无正式 proceedings 证据的报告渠道不在本轮检索范围。
[SBC 官方说明](https://www.sbc-conference.com/2026/)

source_ids 需经索引核实才填写。空列表表示待解析。
采集器使用 --venue ID 按完整名称解析 OpenAlex source，歧义结果进入覆盖报告。

## EconCS（37）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| ec | EC | ACM Conference on Economics and Computation | 会议 | core |  |
| teac | TEAC | [ACM Transactions on Economics and Computation](https://dl.acm.org/journal/teac) | 期刊 | core |  |
| wine | WINE | Conference on Web and Internet Economics | 会议 | core |  |
| sagt | SAGT | International Symposium on Algorithmic Game Theory | 会议 | core |  |
| www | WWW | The Web Conference | 会议 | core |  |
| aamas | AAMAS | International Conference on Autonomous Agents and Multiagent Systems | 会议 | core |  |
| aaai | AAAI | AAAI Conference on Artificial Intelligence | 会议 | targeted |  |
| ijcai | IJCAI | International Joint Conference on Artificial Intelligence | 会议 | targeted |  |
| uai | UAI | Conference on Uncertainty in Artificial Intelligence | 会议 | targeted |  |
| neurips | NeurIPS | Advances in Neural Information Processing Systems | 会议 | targeted |  |
| icml | ICML | International Conference on Machine Learning | 会议 | targeted |  |
| iclr | ICLR | International Conference on Learning Representations | 会议 | targeted |  |
| aistats | AISTATS | International Conference on Artificial Intelligence and Statistics | 会议 | targeted |  |
| jair | JAIR | Journal of Artificial Intelligence Research | 期刊 | targeted |  |
| jaamas | JAAMAS | Autonomous Agents and Multi-Agent Systems | 期刊 | targeted |  |
| jmlr | JMLR | Journal of Machine Learning Research | 期刊 | targeted |  |
| ecai | ECAI | European Conference on Artificial Intelligence | 会议 | targeted |  |
| adt | ADT | International Conference on Algorithmic Decision Theory | 会议 | targeted |  |
| comsoc | COMSOC | [International Workshop on Computational Social Choice](https://comsoc-community.org/workshops.html) | 工作坊 | targeted |  |
| tcss | IEEE TCSS | IEEE Transactions on Computational Social Systems | 期刊 | targeted |  |
| gamesec | GameSec | Conference on Decision and Game Theory for Security | 会议 | core | **2026-11-08 新增** |
| aij | AIJ | Artificial Intelligence | 期刊 | targeted | **2026-11-08 新增** |
| tark | TARK | Conference on Theoretical Aspects of Rationality and Knowledge | 会议 | targeted | **2026-11-08 新增** |
| forc | FORC | Symposium on Foundations of Responsible Computing | 会议 | targeted | **2026-11-08 新增** |
| facct | FAccT | ACM Conference on Fairness, Accountability, and Transparency | 会议 | targeted | **2026-11-08 新增** |
| eaamo | EAAMO | ACM Conference on Equity and Access in Algorithms, Mechanisms, and Optimization | 会议 | targeted | **2026-11-08 新增** |
| aies | AIES | AAAI/ACM Conference on AI, Ethics, and Society | 会议 | targeted | **2026-11-08 新增** |
| tmlr | TMLR | Transactions on Machine Learning Research | 期刊 | targeted | **2026-11-08 新增** |
| kr | KR | International Conference on Principles of Knowledge Representation and Reasoning | 会议 | targeted | **2026-11-08 新增** |
| prima | PRIMA | International Conference on Principles and Practice of Multi-Agent Systems | 会议 | targeted | **2026-11-08 新增** |
| eumas | EUMAS | European Conference on Multi-Agent Systems | 会议 | targeted | **2026-11-08 新增** |
| ice-economies | ICE Economies | International Conference on Information and Computation Economies | 会议 | targeted | **2026-11-09 新增** |
| weis | WEIS | Workshop on the Economics of Information Security | 工作坊 | targeted | **2026-11-09 新增** |
| sigecom-exchanges | SIGecom Exch. | ACM SIGecom Exchanges | 期刊 | targeted | **2026-11-09 新增** |
| www-companion | WWW Companion | Companion Proceedings of the ACM Web Conference | 工作坊 | targeted | **2026-11-09 新增** |
| netecon | NetEcon | Workshop on the Economics of Networks, Systems and Computation | 工作坊 | targeted | **2026-11-09 新增** |
| gamenets | GameNets | International Conference on Game Theory for Networks | 会议 | targeted | **2026-11-09 新增** |

## Blockchain（24）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| aft | AFT | Conference on Advances in Financial Technologies | 会议 | core |  |
| fc | FC | Financial Cryptography and Data Security | 会议 | core |  |
| fc-workshops | FC Workshops | Financial Cryptography and Data Security Workshops | 工作坊 | core |  |
| tokenomics | Tokenomics | International Conference on Blockchain Economics, Security and Protocols | 会议 | core |  |
| defi-ccs | DeFi@CCS | ACM CCS Workshop on Decentralized Finance and Security | 工作坊 | core |  |
| cbt | CBT | International Workshop on Cryptocurrencies and Blockchain Technology | 工作坊 | core |  |
| cvcbt | CVCBT | Crypto Valley Conference on Blockchain Technology | 会议 | core |  |
| icbc | ICBC | IEEE International Conference on Blockchain and Cryptocurrency | 会议 | core |  |
| ieee-blockchain | IEEE Blockchain | IEEE International Conference on Blockchain | 会议 | targeted |  |
| dapps | DAPPS | IEEE International Conference on Decentralized Applications and Infrastructures | 会议 | targeted |  |
| bcca | BCCA | International Conference on Blockchain Computing and Applications | 会议 | targeted |  |
| ledger | Ledger | Ledger | 期刊 | core |  |
| cryptoeconomic-systems | Cryptoeconomic Systems | Cryptoeconomic Systems | 期刊 | core |  |
| dlt | DLT | Distributed Ledger Technologies: Research and Practice | 期刊 | core |  |
| jbba | JBBA | The Journal of the British Blockchain Association | 期刊 | targeted |  |
| marble | MARBLE | [International Conference on Mathematical Research for Blockchain Economy](https://link.springer.com/chapter/10.1007/978-3-031-68974-1_8) | 会议 | targeted |  |
| frontiers-blockchain | Front. Blockchain | Frontiers in Blockchain | 期刊 | targeted |  |
| gbc | GBC | IEEE Global Blockchain Conference | 会议 | targeted |  |
| bcra | BCRA | Blockchain: Research and Applications | 期刊 | targeted | **2026-11-08 新增** |
| brains | BRAINS | Conference on Blockchain Research & Applications for Innovative Networks and Services | 会议 | targeted | **2026-11-08 新增** |
| bsci | BSCI | ACM Workshop on Blockchain-enabled Networked Sensor Systems / Secure Critical Infrastructure (AsiaCCS) | 工作坊 | targeted | **2026-11-08 新增** |
| fab | FAB | International Conference on Blockchain Economics, Security and Protocols (Tokenomics) and FAB | 会议 | targeted | **2026-11-09 新增** |
| j-blockchain-res | J. Blockchain Res. | Journal of Blockchain Research | 期刊 | targeted | **2026-11-09 新增** |
| iet-blockchain | IET Blockchain | IET Blockchain | 期刊 | targeted | **2026-11-09 新增** |

## TCS（61）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| jacm | JACM | Journal of the ACM | 期刊 | core |  |
| sicomp | SICOMP | [SIAM Journal on Computing](https://www.siam.org/publications/siam-journals/siam-journal-on-computing/) | 期刊 | core |  |
| algorithmica | Algorithmica | [Algorithmica](https://link.springer.com/journal/453) | 期刊 | core |  |
| toc | ToC | Theory of Computing | 期刊 | core |  |
| toct | TOCT | ACM Transactions on Computation Theory | 期刊 | core |  |
| talg | TALG | ACM Transactions on Algorithms | 期刊 | core |  |
| tcs | TCS | Theoretical Computer Science | 期刊 | core |  |
| jcss | JCSS | Journal of Computer and System Sciences | 期刊 | core |  |
| information-and-computation | Inf. Comput. | Information and Computation | 期刊 | core |  |
| tocs-theory | TOCS (Theory) | Theory of Computing Systems | 期刊 | core |  |
| distributed-computing | Distributed Computing | Distributed Computing | 期刊 | core |  |
| sidma | SIDMA | SIAM Journal on Discrete Mathematics | 期刊 | targeted |  |
| ipl | IPL | Information Processing Letters | 期刊 | targeted |  |
| computational-complexity | Comput. Complexity | Computational Complexity | 期刊 | targeted |  |
| cj | CJ | The Computer Journal | 期刊 | targeted |  |
| ijfcs | IJFCS | International Journal of Foundations of Computer Science | 期刊 | targeted |  |
| stoc | STOC | ACM Symposium on Theory of Computing | 会议 | core |  |
| focs | FOCS | IEEE Symposium on Foundations of Computer Science | 会议 | core |  |
| soda | SODA | ACM-SIAM Symposium on Discrete Algorithms | 会议 | core |  |
| itcs | ITCS | Innovations in Theoretical Computer Science Conference | 会议 | core |  |
| icalp | ICALP | International Colloquium on Automata, Languages, and Programming | 会议 | core |  |
| esa | ESA | European Symposium on Algorithms | 会议 | core |  |
| stacs | STACS | Symposium on Theoretical Aspects of Computer Science | 会议 | core |  |
| approx | APPROX | Approximation Algorithms for Combinatorial Optimization Problems | 会议 | targeted |  |
| random | RANDOM | Randomization and Computation | 会议 | targeted |  |
| ccc | CCC | Computational Complexity Conference | 会议 | targeted |  |
| csr | CSR | International Computer Science Symposium in Russia | 会议 | targeted |  |
| mfcs | MFCS | Mathematical Foundations of Computer Science | 会议 | targeted |  |
| cav | CAV | International Conference on Computer Aided Verification | 会议 | targeted |  |
| tacas | TACAS | International Conference on Tools and Algorithms for the Construction and Analysis of Systems | 会议 | targeted |  |
| fm | FM | International Symposium on Formal Methods | 会议 | targeted |  |
| esop | ESOP | European Symposium on Programming | 会议 | targeted |  |
| popl | POPL | ACM SIGPLAN Symposium on Principles of Programming Languages | 会议 | targeted |  |
| oopsla | OOPSLA | ACM SIGPLAN Conference on Object-Oriented Programming Systems, Languages, and Applications | 会议 | targeted |  |
| lmcs | LMCS | Logical Methods in Computer Science | 期刊 | targeted |  |
| jsait | IEEE JSAIT | IEEE Journal on Selected Areas in Information Theory | 期刊 | targeted |  |
| concur | CONCUR | International Conference on Concurrency Theory | 会议 | targeted |  |
| ijtcs-faw | IJTCS-FAW | International Joint Conference on Theoretical Computer Science – Frontiers of Algorithmic Wisdom | 会议 | targeted | **2026-11-08 新增** |
| latin | LATIN | Latin American Symposium on Theoretical Informatics | 会议 | targeted | **2026-11-08 新增** |
| cocoon | COCOON | International Computing and Combinatorics Conference | 会议 | targeted | **2026-11-08 新增** |
| isaac | ISAAC | International Symposium on Algorithms and Computation | 会议 | targeted | **2026-11-08 新增** |
| fsttcs | FSTTCS | Foundations of Software Technology and Theoretical Computer Science | 会议 | targeted | **2026-11-08 新增** |
| walcom | WALCOM | International Conference and Workshops on Algorithms and Computation | 会议 | targeted | **2026-11-08 新增** |
| fct | FCT | International Symposium on Fundamentals of Computation Theory | 会议 | targeted | **2026-11-08 新增** |
| ciac | CIAC | International Conference on Algorithms and Complexity | 会议 | targeted | **2026-11-08 新增** |
| swat | SWAT | Scandinavian Symposium and Workshops on Algorithm Theory | 会议 | targeted | **2026-11-08 新增** |
| wads | WADS | Algorithms and Data Structures Symposium | 会议 | targeted | **2026-11-08 新增** |
| tamc | TAMC | Theory and Applications of Models of Computation | 会议 | targeted | **2026-11-08 新增** |
| cocoa | COCOA | International Conference on Combinatorial Optimization and Applications | 会议 | targeted | **2026-11-08 新增** |
| aaim | AAIM | International Conference on Algorithmic Aspects in Information and Management | 会议 | targeted | **2026-11-08 新增** |
| lics | LICS | ACM/IEEE Symposium on Logic in Computer Science | 会议 | targeted | **2026-11-08 新增** |
| atva | ATVA | International Symposium on Automated Technology for Verification and Analysis | 会议 | targeted | **2026-11-08 新增** |
| qest | QEST | International Conference on Quantitative Evaluation of Systems | 会议 | targeted | **2026-11-08 新增** |
| gandalf | GandALF | International Symposium on Games, Automata, Logics, and Formal Verification | 会议 | targeted | **2026-11-08 新增** |
| fmbc | FMBC | Workshop on Formal Methods for Blockchains | 工作坊 | targeted | **2026-11-08 新增** |
| sr-workshop | SR | International Workshop on Strategic Reasoning | 工作坊 | targeted | **2026-11-08 新增** |
| ifm | iFM | International Conference on integrated Formal Methods | 会议 | targeted | **2026-11-08 新增** |
| vmcai | VMCAI | International Conference on Verification, Model Checking, and Abstract Interpretation | 会议 | targeted | **2026-11-08 新增** |
| isola | ISoLA | International Symposium on Leveraging Applications of Formal Methods | 会议 | targeted | **2026-11-09 新增** |
| tit | IEEE TIT | IEEE Transactions on Information Theory | 期刊 | targeted | **2026-11-09 新增** |
| jlamp | JLAMP | Journal of Logical and Algebraic Methods in Programming | 期刊 | targeted | **2026-11-09 新增** |

## Systems（85）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| podc | PODC | ACM Symposium on Principles of Distributed Computing | 会议 | core |  |
| disc | DISC | International Symposium on Distributed Computing | 会议 | core |  |
| opodis | OPODIS | International Conference on Principles of Distributed Systems | 会议 | core |  |
| sss | SSS | International Symposium on Stabilization, Safety, and Security of Distributed Systems | 会议 | core |  |
| sirocco | SIROCCO | International Colloquium on Structural Information and Communication Complexity | 会议 | core |  |
| icdcs | ICDCS | IEEE International Conference on Distributed Computing Systems | 会议 | core |  |
| srds | SRDS | International Symposium on Reliable Distributed Systems | 会议 | core |  |
| dsn | DSN | IEEE/IFIP International Conference on Dependable Systems and Networks | 会议 | core |  |
| netys | NETYS | International Conference on Networked Systems | 会议 | targeted |  |
| nsdi | NSDI | USENIX Symposium on Networked Systems Design and Implementation | 会议 | core |  |
| sosp | SOSP | ACM Symposium on Operating Systems Principles | 会议 | core |  |
| osdi | OSDI | USENIX Symposium on Operating Systems Design and Implementation | 会议 | core |  |
| eurosys | EuroSys | European Conference on Computer Systems | 会议 | core |  |
| atc | ATC | USENIX Annual Technical Conference | 会议 | targeted |  |
| socc | SoCC | ACM Symposium on Cloud Computing | 会议 | targeted |  |
| middleware | Middleware | ACM/IFIP International Middleware Conference | 会议 | targeted |  |
| sigcomm | SIGCOMM | ACM SIGCOMM Conference | 会议 | targeted |  |
| conext | CoNEXT | International Conference on Emerging Networking Experiments and Technologies | 会议 | targeted |  |
| infocom | INFOCOM | IEEE International Conference on Computer Communications | 会议 | targeted |  |
| imc | IMC | ACM Internet Measurement Conference | 会议 | targeted |  |
| sigmetrics | SIGMETRICS | ACM SIGMETRICS International Conference on Measurement and Modeling of Computer Systems | 会议 | targeted |  |
| tocs | TOCS | ACM Transactions on Computer Systems | 期刊 | core |  |
| tpds | TPDS | IEEE Transactions on Parallel and Distributed Systems | 期刊 | core |  |
| tdsc | TDSC | IEEE Transactions on Dependable and Secure Computing | 期刊 | core |  |
| tcc-cloud | TCC (Cloud) | IEEE Transactions on Cloud Computing | 期刊 | targeted |  |
| ton | TON | IEEE/ACM Transactions on Networking | 期刊 | targeted |  |
| jdc | JDC | Journal of Parallel and Distributed Computing | 期刊 | targeted |  |
| sigmod | SIGMOD | ACM SIGMOD International Conference on Management of Data | 会议 | targeted |  |
| vldb-pvldb | VLDB/PVLDB | Proceedings of the VLDB Endowment | 期刊 | targeted |  |
| icde | ICDE | IEEE International Conference on Data Engineering | 会议 | targeted |  |
| pods | PODS | ACM Symposium on Principles of Database Systems | 会议 | targeted |  |
| tods | TODS | ACM Transactions on Database Systems | 期刊 | targeted |  |
| vldb-journal | VLDB Journal | The VLDB Journal | 期刊 | targeted |  |
| pomacs | POMACS | Proceedings of the ACM on Measurement and Analysis of Computing Systems | 期刊 | targeted |  |
| tsc | IEEE TSC | IEEE Transactions on Services Computing | 期刊 | targeted |  |
| ijnm | IJNM | International Journal of Network Management | 期刊 | targeted |  |
| globecom | GLOBECOM | IEEE Global Communications Conference | 会议 | targeted |  |
| comsnets | COMSNETS | International Conference on Communication Systems & Networks | 会议 | targeted |  |
| smartnets | SmartNets | International Conference on Smart Applications, Communications and Networking | 会议 | targeted |  |
| iot-journal | IEEE IoT J. | IEEE Internet of Things Journal | 期刊 | targeted |  |
| tii | IEEE TII | IEEE Transactions on Industrial Informatics | 期刊 | targeted |  |
| allerton | Allerton | Allerton Conference on Communication, Control, and Computing | 会议 | targeted |  |
| metacom | MetaCom | IEEE International Conference on Metaverse Computing, Networking and Applications | 会议 | targeted |  |
| ithings-joint | iThings Joint | IEEE International Conference on Internet of Things (iThings) and IEEE Green Computing and Communications (GreenCom) and IEEE Cyber, Physical and Social Computing (CPSCom) and IEEE Smart Data (SmartData) | 会议 | targeted |  |
| jsac | JSAC | IEEE Journal on Selected Areas in Communications | 期刊 | targeted | **2026-11-08 新增** |
| tnse | TNSE | IEEE Transactions on Network Science and Engineering | 期刊 | targeted | **2026-11-08 新增** |
| tnsm | TNSM | IEEE Transactions on Network and Service Management | 期刊 | targeted | **2026-11-08 新增** |
| comnet | Comput. Netw. | Computer Networks | 期刊 | targeted | **2026-11-08 新增** |
| jnca | JNCA | Journal of Network and Computer Applications | 期刊 | targeted | **2026-11-08 新增** |
| fgcs | FGCS | Future Generation Computer Systems | 期刊 | targeted | **2026-11-08 新增** |
| tc | TC | IEEE Transactions on Computers | 期刊 | targeted | **2026-11-08 新增** |
| tmc | TMC | IEEE Transactions on Mobile Computing | 期刊 | targeted | **2026-11-08 新增** |
| perf-eval | Perf. Eval. | Performance Evaluation | 期刊 | targeted | **2026-11-08 新增** |
| ifip-networking | IFIP Networking | IFIP Networking Conference | 会议 | targeted | **2026-11-08 新增** |
| icdcn | ICDCN | International Conference on Distributed Computing and Networking | 会议 | targeted | **2026-11-08 新增** |
| icnp | ICNP | IEEE International Conference on Network Protocols | 会议 | targeted | **2026-11-08 新增** |
| hotnets | HotNets | ACM Workshop on Hot Topics in Networks | 工作坊 | targeted | **2026-11-08 新增** |
| spaa | SPAA | ACM Symposium on Parallelism in Algorithms and Architectures | 会议 | targeted | **2026-11-08 新增** |
| ipdps | IPDPS | IEEE International Parallel and Distributed Processing Symposium | 会议 | targeted | **2026-11-08 新增** |
| europar | Euro-Par | European Conference on Parallel Processing | 会议 | targeted | **2026-11-08 新增** |
| icpp | ICPP | International Conference on Parallel Processing | 会议 | targeted | **2026-11-08 新增** |
| topc | TOPC | ACM Transactions on Parallel Computing | 期刊 | targeted | **2026-11-08 新增** |
| toit | TOIT | ACM Transactions on Internet Technology | 期刊 | targeted | **2026-11-08 新增** |
| cidr | CIDR | Conference on Innovative Data Systems Research | 会议 | targeted | **2026-11-08 新增** |
| edbt | EDBT | International Conference on Extending Database Technology | 会议 | targeted | **2026-11-08 新增** |
| icdcs-workshops | ICDCS Workshops | IEEE International Conference on Distributed Computing Systems Workshops | 工作坊 | targeted | **2026-11-09 新增** |
| edcc-companion | EDCC-C | European Dependable Computing Conference Companion | 工作坊 | targeted | **2026-11-09 新增** |
| icde-workshops | ICDE Workshops | IEEE International Conference on Data Engineering Workshops | 工作坊 | targeted | **2026-11-09 新增** |
| wetseb | WETSEB | Workshop on Emerging Trends in Software Engineering for Blockchain | 工作坊 | targeted | **2026-11-09 新增** |
| icpads | ICPADS | IEEE International Conference on Parallel and Distributed Systems | 会议 | targeted | **2026-11-09 新增** |
| iscc | ISCC | IEEE Symposium on Computers and Communications | 会议 | targeted | **2026-11-09 新增** |
| lcn | LCN | IEEE Conference on Local Computer Networks | 会议 | targeted | **2026-11-09 新增** |
| icccn | ICCCN | International Conference on Computer Communications and Networks | 会议 | targeted | **2026-11-09 新增** |
| icsoc | ICSOC | International Conference on Service-Oriented Computing | 会议 | targeted | **2026-11-09 新增** |
| mobihoc | MobiHoc | ACM International Symposium on Mobile Ad Hoc Networking and Computing | 会议 | targeted | **2026-11-09 新增** |
| nca | NCA | IEEE International Symposium on Network Computing and Applications | 会议 | targeted | **2026-11-09 新增** |
| noms | NOMS | IEEE/IFIP Network Operations and Management Symposium | 会议 | targeted | **2026-11-09 新增** |
| smds | SMDS | IEEE International Conference on Smart Data Services | 会议 | targeted | **2026-11-09 新增** |
| tosem | TOSEM | ACM Transactions on Software Engineering and Methodology | 期刊 | targeted | **2026-11-09 新增** |
| tweb | TWEB | ACM Transactions on the Web | 期刊 | targeted | **2026-11-09 新增** |
| pacmse | PACMSE | Proceedings of the ACM on Software Engineering | 期刊 | targeted | **2026-11-09 新增** |
| emse | EMSE | Empirical Software Engineering | 期刊 | targeted | **2026-11-09 新增** |
| tcns | TCNS | IEEE Transactions on Control of Network Systems | 期刊 | targeted | **2026-11-09 新增** |
| simpat | SIMPAT | Simulation Modelling Practice and Theory | 期刊 | targeted | **2026-11-09 新增** |
| ijndc | IJNDC | International Journal of Networked and Distributed Computing | 期刊 | targeted | **2026-11-09 新增** |

## Security & Crypto（61）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| ieee-s-p | IEEE S&P | IEEE Symposium on Security and Privacy | 会议 | core |  |
| ccs | CCS | ACM SIGSAC Conference on Computer and Communications Security | 会议 | core |  |
| usenix-security | USENIX Security | USENIX Security Symposium | 会议 | core |  |
| ndss | NDSS | [Network and Distributed System Security Symposium](https://www.ndss-symposium.org/) | 会议 | core |  |
| crypto | CRYPTO | International Cryptology Conference | 会议 | core |  |
| eurocrypt | EUROCRYPT | International Conference on the Theory and Applications of Cryptographic Techniques | 会议 | core |  |
| asiacrypt | ASIACRYPT | International Conference on the Theory and Application of Cryptology and Information Security | 会议 | core |  |
| tcc | TCC | Theory of Cryptography Conference | 会议 | core |  |
| pkc | PKC | International Conference on Practice and Theory of Public-Key Cryptography | 会议 | core |  |
| csf | CSF | IEEE Computer Security Foundations Symposium | 会议 | core |  |
| esorics | ESORICS | European Symposium on Research in Computer Security | 会议 | core |  |
| acns | ACNS | International Conference on Applied Cryptography and Network Security | 会议 | core |  |
| cans | CANS | International Conference on Cryptology and Network Security | 会议 | targeted |  |
| africacrypt | AFRICACRYPT | International Conference on Cryptology in Africa | 会议 | targeted |  |
| latincrypt | LATINCRYPT | International Conference on Cryptology and Information Security in Latin America | 会议 | targeted |  |
| asiaccs | ASIACCS | ACM Asia Conference on Computer and Communications Security | 会议 | targeted |  |
| euros-p | EuroS&P | IEEE European Symposium on Security and Privacy | 会议 | core |  |
| isc | ISC | Information Security Conference | 会议 | targeted |  |
| acisp | ACISP | Australasian Conference on Information Security and Privacy | 会议 | targeted |  |
| pets-popets | PETS/PoPETs | Proceedings on Privacy Enhancing Technologies | 期刊 | core |  |
| tches | TCHES | IACR Transactions on Cryptographic Hardware and Embedded Systems | 期刊 | targeted |  |
| tosc | ToSC | IACR Transactions on Symmetric Cryptology | 期刊 | targeted |  |
| journal-of-cryptology | Journal of Cryptology | Journal of Cryptology | 期刊 | core |  |
| tifs | TIFS | IEEE Transactions on Information Forensics and Security | 期刊 | core |  |
| tops | TOPS | ACM Transactions on Privacy and Security | 期刊 | core |  |
| jcs | JCS | Journal of Computer Security | 期刊 | core |  |
| ijis | IJIS | International Journal of Information Security | 期刊 | targeted |  |
| iacr-cic | IACR CiC | IACR Communications in Cryptology | 期刊 | core |  |
| journal-cybersecurity | J. Cybersecurity | Journal of Cybersecurity | 期刊 | targeted |  |
| spw | IEEE S&P Workshops | IEEE Security and Privacy Workshops | 工作坊 | targeted |  |
| eurospw | EuroS&P Workshops | IEEE European Symposium on Security and Privacy Workshops | 工作坊 | targeted |  |
| cscml | CSCML | [International Symposium on Cyber Security, Cryptology, and Machine Learning](https://www.cscml.org/) | 会议 | targeted |  |
| acsac | ACSAC | Annual Computer Security Applications Conference | 会议 | targeted | **2026-11-08 新增** |
| raid | RAID | International Symposium on Research in Attacks, Intrusions and Defenses | 会议 | targeted | **2026-11-08 新增** |
| ares | ARES | International Conference on Availability, Reliability and Security | 会议 | targeted | **2026-11-08 新增** |
| securecomm | SecureComm | International Conference on Security and Privacy in Communication Networks | 会议 | targeted | **2026-11-08 新增** |
| scn | SCN | International Conference on Security and Cryptography for Networks | 会议 | targeted | **2026-11-08 新增** |
| ct-rsa | CT-RSA | The Cryptographers' Track at the RSA Conference | 会议 | targeted | **2026-11-08 新增** |
| icics | ICICS | International Conference on Information and Communications Security | 会议 | targeted | **2026-11-08 新增** |
| provsec | ProvSec | International Conference on Provable Security | 会议 | ['Provable Security'] | **2026-11-08 新增** |
| wpes | WPES | ACM Workshop on Privacy in the Electronic Society | 工作坊 | targeted | **2026-11-08 新增** |
| codaspy | CODASPY | ACM Conference on Data and Application Security and Privacy | 会议 | targeted | **2026-11-08 新增** |
| computers-security | Comput. Secur. | Computers & Security | 期刊 | targeted | **2026-11-08 新增** |
| ieee-sp-magazine | IEEE S&P Mag. | IEEE Security & Privacy | 期刊 | targeted | **2026-11-08 新增** |
| dcc | DCC | Designs, Codes and Cryptography | 期刊 | targeted | **2026-11-08 新增** |
| indocrypt | INDOCRYPT | International Conference on Cryptology in India | 会议 | targeted | **2026-11-08 新增** |
| inscrypt | Inscrypt | International Conference on Information Security and Cryptology (China) | 会议 | targeted | **2026-11-08 新增** |
| icisc | ICISC | International Conference on Information Security and Cryptology (Korea) | 会议 | targeted | **2026-11-08 新增** |
| wisa | WISA | International Conference on Information Security Applications | 会议 | targeted | **2026-11-08 新增** |
| iwsec | IWSEC | International Workshop on Security | 会议 | targeted | **2026-11-08 新增** |
| sacrypt | SAC (Crypto) | Selected Areas in Cryptography | 会议 | targeted | **2026-11-08 新增** |
| pqcrypto | PQCrypto | International Conference on Post-Quantum Cryptography | 会议 | targeted | **2026-11-08 新增** |
| imacc | IMACC | IMA International Conference on Cryptography and Coding | 会议 | targeted | **2026-11-08 新增** |
| dbsec | DBSec | IFIP Conference on Data and Applications Security and Privacy | 会议 | targeted | **2026-11-08 新增** |
| nordsec | NordSec | Nordic Conference on Secure IT Systems | 会议 | targeted | **2026-11-08 新增** |
| ispec | ISPEC | International Conference on Information Security Practice and Experience | 会议 | targeted | **2026-11-08 新增** |
| apkc | APKC | ACM ASIA Public-Key Cryptography Workshop | 工作坊 | targeted | **2026-11-09 新增** |
| acsac-workshops | ACSAC Workshops | Annual Computer Security Applications Conference Workshops | 工作坊 | targeted | **2026-11-09 新增** |
| esorics-workshops | ESORICS Workshops | ESORICS International Workshops | 工作坊 | targeted | **2026-11-09 新增** |
| stast | STAST | Workshop on Socio-Technical Aspects in Security | 工作坊 | targeted | **2026-11-09 新增** |
| ecrime | eCrime | APWG Symposium on Electronic Crime Research | 会议 | targeted | **2026-11-09 新增** |

## Econ（65）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| geb | GEB | [Games and Economic Behavior](https://www.sciencedirect.com/journal/games-and-economic-behavior) | 期刊 | core |  |
| jet | JET | [Journal of Economic Theory](https://www.sciencedirect.com/journal/journal-of-economic-theory) | 期刊 | core |  |
| et | ET | [Economic Theory](https://link.springer.com/journal/199) | 期刊 | core |  |
| te | TE | [Theoretical Economics](https://te.ojs-es.econometricsociety.org/) | 期刊 | core |  |
| aej-micro | AEJ Micro | American Economic Journal: Microeconomics | 期刊 | core |  |
| jmid | JMID | Journal of Mechanism and Institution Design | 期刊 | core |  |
| ijgt | IJGT | International Journal of Game Theory | 期刊 | core |  |
| scw | SCW | Social Choice and Welfare | 期刊 | core |  |
| etb | ETB | Economic Theory Bulletin | 期刊 | core |  |
| red | RED | Review of Economic Design | 期刊 | core |  |
| jmathe | JMathE | Journal of Mathematical Economics | 期刊 | core |  |
| experimental-economics | Experimental Economics | Experimental Economics | 期刊 | core |  |
| jeb-o | JEB&O | Journal of Economic Behavior & Organization | 期刊 | targeted |  |
| jems | JEMS | Journal of Economics & Management Strategy | 期刊 | core |  |
| rand | RAND | The RAND Journal of Economics | 期刊 | core |  |
| ijio | IJIO | International Journal of Industrial Organization | 期刊 | targeted |  |
| joie | JIE | Journal of Industrial Economics | 期刊 | targeted |  |
| aer | AER | American Economic Review | 期刊 | core |  |
| aer-insights | AER: Insights | American Economic Review: Insights | 期刊 | core |  |
| econometrica | Econometrica | Econometrica | 期刊 | core |  |
| qje | QJE | The Quarterly Journal of Economics | 期刊 | core |  |
| restud | ReStud | The Review of Economic Studies | 期刊 | core |  |
| jpe | JPE | Journal of Political Economy | 期刊 | core |  |
| jpe-micro | JPE Micro | Journal of Political Economy Microeconomics | 期刊 | core |  |
| jeea | JEEA | Journal of the European Economic Association | 期刊 | targeted |  |
| ier | IER | International Economic Review | 期刊 | targeted |  |
| qe | QE | Quantitative Economics | 期刊 | targeted |  |
| jedc | JEDC | Journal of Economic Dynamics and Control | 期刊 | targeted |  |
| jpube | JPubE | Journal of Public Economics | 期刊 | targeted |  |
| economic-journal | Economic Journal | The Economic Journal | 期刊 | targeted |  |
| economics-letters | Economics Letters | Economics Letters | 期刊 | targeted |  |
| j-econ-surveys | J Econ Surveys | Journal of Economic Surveys | 期刊 | targeted |  |
| computational-economics | Comput. Econ. | Computational Economics | 期刊 | targeted |  |
| jep | JEP | Journal of Economic Perspectives | 期刊 | targeted |  |
| jel | JEL | Journal of Economic Literature | 期刊 | targeted |  |
| energy-econ | Energy Econ. | Energy Economics | 期刊 | targeted |  |
| cje | CJE | Canadian Journal of Economics | 期刊 | targeted |  |
| institutional-economics | JOIE | Journal of Institutional Economics | 期刊 | targeted |  |
| economic-inquiry | Economic Inquiry | Economic Inquiry | 期刊 | targeted |  |
| applied-economics-letters | Applied Econ. Lett. | Applied Economics Letters | 期刊 | targeted |  |
| igtr | IGTR | International Game Theory Review | 期刊 | targeted | **2026-11-08 新增** |
| dga | DGA | Dynamic Games and Applications | 期刊 | targeted | **2026-11-08 新增** |
| mss | MSS | Mathematical Social Sciences | 期刊 | targeted | **2026-11-08 新增** |
| jpet | JPET | Journal of Public Economic Theory | 期刊 | targeted | **2026-11-08 新增** |
| theory-decision | Theory Decis. | Theory and Decision | 期刊 | targeted | **2026-11-08 新增** |
| eer | EER | European Economic Review | 期刊 | targeted | **2026-11-08 新增** |
| restat | REStat | The Review of Economics and Statistics | 期刊 | targeted | **2026-11-08 新增** |
| jle | JLE | The Journal of Law and Economics | 期刊 | targeted | **2026-11-08 新增** |
| jleo | JLEO | The Journal of Law, Economics, and Organization | 期刊 | targeted | **2026-11-08 新增** |
| iep | IEP | Information Economics and Policy | 期刊 | targeted | **2026-11-08 新增** |
| economic-modelling | Econ. Model. | Economic Modelling | 期刊 | targeted | **2026-11-08 新增** |
| aej-macro | AEJ Macro | American Economic Journal: Macroeconomics | 期刊 | targeted | **2026-11-08 新增** |
| red-dynamics | RED (Dynamics) | Review of Economic Dynamics | 期刊 | targeted | **2026-11-08 新增** |
| applied-economics | Applied Economics | Applied Economics | 期刊 | targeted | **2026-11-09 新增** |
| int-econ-j | Int. Econ. J. | International Economic Journal | 期刊 | targeted | **2026-11-09 新增** |
| annual-review-econ | Annu. Rev. Econ. | Annual Review of Economics | 期刊 | targeted | **2026-11-09 新增** |
| j-econometrics | J. Econometrics | Journal of Econometrics | 期刊 | targeted | **2026-11-09 新增** |
| jae-applied | J. Appl. Econometrics | Journal of Applied Econometrics | 期刊 | targeted | **2026-11-09 新增** |
| empirical-economics | Empirical Economics | Empirical Economics | 期刊 | targeted | **2026-11-09 新增** |
| ejpe | EJPE | European Journal of Political Economy | 期刊 | targeted | **2026-11-09 新增** |
| public-choice | Public Choice | Public Choice | 期刊 | targeted | **2026-11-09 新增** |
| economica | Economica | Economica | 期刊 | targeted | **2026-11-09 新增** |
| sje | SJE | Scandinavian Journal of Economics | 期刊 | targeted | **2026-11-09 新增** |
| obes | OBES | Oxford Bulletin of Economics and Statistics | 期刊 | targeted | **2026-11-09 新增** |
| j-regul-econ | J. Regul. Econ. | Journal of Regulatory Economics | 期刊 | targeted | **2026-11-09 新增** |

## Finance（60）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| jf | JF | The Journal of Finance | 期刊 | core |  |
| jfe | JFE | Journal of Financial Economics | 期刊 | core |  |
| rfs | RFS | The Review of Financial Studies | 期刊 | core |  |
| rf | RoF | Review of Finance | 期刊 | core |  |
| jfqa | JFQA | Journal of Financial and Quantitative Analysis | 期刊 | core |  |
| jfi | JFI | Journal of Financial Intermediation | 期刊 | core |  |
| jfm | J. Financial Markets | Journal of Financial Markets | 期刊 | core |  |
| jmcb | JMCB | Journal of Money, Credit and Banking | 期刊 | targeted |  |
| jme | JME | Journal of Monetary Economics | 期刊 | targeted |  |
| mathematical-finance | Mathematical Finance | Mathematical Finance | 期刊 | core |  |
| finance-and-stochastics | Finance Stoch. | Finance and Stochastics | 期刊 | core |  |
| siam-jfm | SIAM JFM | SIAM Journal on Financial Mathematics | 期刊 | core |  |
| jbf | JBF | Journal of Banking & Finance | 期刊 | targeted |  |
| jcf | JCF | Journal of Corporate Finance | 期刊 | targeted |  |
| jfs | JFS | Journal of Financial Stability | 期刊 | targeted |  |
| jef | JEF | Journal of Empirical Finance | 期刊 | targeted |  |
| frl | FRL | Finance Research Letters | 期刊 | targeted |  |
| financial-innovation | Financial Innovation | Financial Innovation | 期刊 | targeted |  |
| digital-finance | Digital Finance | Digital Finance | 期刊 | targeted |  |
| icaif | ICAIF | ACM International Conference on AI in Finance | 会议 | targeted |  |
| futures-markets | J. Futures Markets | Journal of Futures Markets | 期刊 | targeted |  |
| applied-mathematical-finance | Applied Math. Finance | Applied Mathematical Finance | 期刊 | targeted |  |
| jimf | JIMF | Journal of International Money and Finance | 期刊 | targeted |  |
| quantitative-finance | Quant. Finance | Quantitative Finance | 期刊 | targeted | **2026-11-08 新增** |
| rcfs | RCFS | The Review of Corporate Finance Studies | 期刊 | targeted | **2026-11-08 新增** |
| raps | RAPS | The Review of Asset Pricing Studies | 期刊 | targeted | **2026-11-08 新增** |
| jfec | J. Fin. Econometrics | Journal of Financial Econometrics | 期刊 | targeted | **2026-11-08 新增** |
| irfa | IRFA | International Review of Financial Analysis | 期刊 | targeted | **2026-11-08 新增** |
| ribaf | RIBAF | Research in International Business and Finance | 期刊 | targeted | **2026-11-09 新增** |
| jifmim | JIFMIM | Journal of International Financial Markets, Institutions and Money | 期刊 | targeted | **2026-11-09 新增** |
| iref | IREF | International Review of Economics & Finance | 期刊 | targeted | **2026-11-09 新增** |
| najef | NAJEF | The North American Journal of Economics and Finance | 期刊 | targeted | **2026-11-09 新增** |
| qref | QREF | The Quarterly Review of Economics and Finance | 期刊 | targeted | **2026-11-09 新增** |
| jbef | JBEF | Journal of Behavioral and Experimental Finance | 期刊 | targeted | **2026-11-09 新增** |
| pbfj | PBFJ | Pacific-Basin Finance Journal | 期刊 | targeted | **2026-11-09 新增** |
| efm | EFM | European Financial Management | 期刊 | targeted | **2026-11-09 新增** |
| finance-stochastics | Finance Stoch. | Finance and Stochastics | 期刊 | targeted | **2026-11-09 新增** |
| ejf | EJF | European Journal of Finance | 期刊 | targeted | **2026-11-09 新增** |
| ijfe | IJFE | International Journal of Finance & Economics | 期刊 | targeted | **2026-11-09 新增** |
| rqfa | RQFA | Review of Quantitative Finance and Accounting | 期刊 | targeted | **2026-11-09 新增** |
| ime | IME | Insurance: Mathematics and Economics | 期刊 | targeted | **2026-11-09 新增** |
| ijaim | IJAIM | International Journal of Accounting and Information Management | 期刊 | targeted | **2026-11-09 新增** |
| bar | BAR | The British Accounting Review | 期刊 | targeted | **2026-11-09 新增** |
| jai | JAI | The Journal of Alternative Investments | 期刊 | targeted | **2026-11-09 新增** |
| global-finance | Global Finance J. | Global Finance Journal | 期刊 | targeted | **2026-11-09 新增** |
| financial-management | Financial Management | Financial Management | 期刊 | targeted | **2026-11-09 新增** |
| arfe | ARFE | Annual Review of Financial Economics | 期刊 | targeted | **2026-11-09 新增** |
| financial-review | Financial Review | Financial Review | 期刊 | targeted | **2026-11-09 新增** |
| faj | FAJ | Financial Analysts Journal | 期刊 | targeted | **2026-11-09 新增** |
| jpm | JPM | The Journal of Portfolio Management | 期刊 | targeted | **2026-11-09 新增** |
| jfsr | JFSR | Journal of Financial Services Research | 期刊 | targeted | **2026-11-09 新增** |
| emr | EMR | Emerging Markets Review | 期刊 | targeted | **2026-11-09 新增** |
| annals-finance | Annals of Finance | Annals of Finance | 期刊 | targeted | **2026-11-09 新增** |
| mfe | MFE | Mathematics and Financial Economics | 期刊 | targeted | **2026-11-09 新增** |
| def | DEF | Decisions in Economics and Finance | 期刊 | targeted | **2026-11-09 新增** |
| tar | TAR | The Accounting Review | 期刊 | targeted | **2026-11-09 新增** |
| jar | JAR | Journal of Accounting Research | 期刊 | targeted | **2026-11-09 新增** |
| jae-accounting | JAE (Accounting) | Journal of Accounting and Economics | 期刊 | targeted | **2026-11-09 新增** |
| frontiers-math-finance | Front. Math. Finance | Frontiers of Mathematical Finance | 期刊 | targeted | **2026-11-09 新增** |
| qfe | QFE | Quantitative Finance and Economics | 期刊 | targeted | **2026-11-09 新增** |

## OR/MS（36）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| management-science | Management Science | Management Science | 期刊 | core |  |
| operations-research | Operations Research | Operations Research | 期刊 | core |  |
| mor | MOR | Mathematics of Operations Research | 期刊 | core |  |
| msom | MSOM | Manufacturing & Service Operations Management | 期刊 | core |  |
| ijoc | IJOC | INFORMS Journal on Computing | 期刊 | core |  |
| orl | ORL | Operations Research Letters | 期刊 | targeted |  |
| ejor | EJOR | European Journal of Operational Research | 期刊 | targeted |  |
| mathematical-programming | Math. Program. | Mathematical Programming | 期刊 | targeted |  |
| siopt | SIOPT | SIAM Journal on Optimization | 期刊 | targeted |  |
| jota | JOTA | Journal of Optimization Theory and Applications | 期刊 | targeted |  |
| pom | POM | Production and Operations Management | 期刊 | targeted |  |
| marketing-science | Marketing Science | Marketing Science | 期刊 | targeted |  |
| isr | ISR | Information Systems Research | 期刊 | core |  |
| misq | MISQ | MIS Quarterly | 期刊 | targeted |  |
| jmis | JMIS | Journal of Management Information Systems | 期刊 | targeted |  |
| decision-sciences | Decision Sciences | Decision Sciences | 期刊 | targeted |  |
| jom | JOM | Journal of Operations Management | 期刊 | targeted |  |
| jco | JCO | Journal of Combinatorial Optimization | 期刊 | core |  |
| decision-analysis | Decision Analysis | Decision Analysis | 期刊 | targeted |  |
| peis | PEIS | Probability in the Engineering and Informational Sciences | 期刊 | targeted |  |
| dss | DSS | Decision Support Systems | 期刊 | targeted | **2026-11-08 新增** |
| ecra | ECRA | Electronic Commerce Research and Applications | 期刊 | targeted | **2026-11-08 新增** |
| ecr | ECR | Electronic Commerce Research | 期刊 | targeted | **2026-11-08 新增** |
| jais | JAIS | Journal of the Association for Information Systems | 期刊 | targeted | **2026-11-08 新增** |
| stochastic-systems | Stoch. Syst. | Stochastic Systems | 期刊 | targeted | **2026-11-08 新增** |
| questa | QUESTA | Queueing Systems | 期刊 | targeted | **2026-11-08 新增** |
| nrl | NRL | Naval Research Logistics | 期刊 | targeted | **2026-11-08 新增** |
| info-management | I&M | Information & Management | 期刊 | targeted | **2026-11-08 新增** |
| annals-or | Annals of OR | Annals of Operations Research | 期刊 | targeted | **2026-11-09 新增** |
| jssse | JSSSE | Journal of Systems Science and Systems Engineering | 期刊 | targeted | **2026-11-09 新增** |
| jors | JORS | Journal of the Operational Research Society | 期刊 | targeted | **2026-11-09 新增** |
| itor | ITOR | International Transactions in Operational Research | 期刊 | targeted | **2026-11-09 新增** |
| omega | Omega | Omega | 期刊 | targeted | **2026-11-09 新增** |
| cor | C&OR | Computers & Operations Research | 期刊 | targeted | **2026-11-09 新增** |
| or-spectrum | OR Spectrum | OR Spectrum | 期刊 | targeted | **2026-11-09 新增** |
| gdn | GDN | Group Decision and Negotiation | 期刊 | targeted | **2026-11-09 新增** |

## Preprints & Working Papers（14）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| arxiv | arXiv | arXiv | 预印本/索引 | core |  |
| iacr-eprint | IACR ePrint | IACR Cryptology ePrint Archive | 预印本/索引 | core |  |
| ssrn | SSRN | SSRN | 预印本/索引 | core |  |
| nber | NBER | National Bureau of Economic Research | 工作论文 | core |  |
| cepr | CEPR | Centre for Economic Policy Research Discussion Papers | 工作论文 | core |  |
| repec | RePEc | Research Papers in Economics | 预印本/索引 | core |  |
| cesifo | CESifo | CESifo Working Papers | 工作论文 | targeted |  |
| cowles | Cowles | Cowles Foundation Discussion Papers | 工作论文 | targeted |  |
| bis-wp | BIS WP | BIS Working Papers | 工作论文 | targeted | **2026-11-08 新增** |
| ecb-wp | ECB WP | ECB Working Paper Series | 工作论文 | targeted | **2026-11-08 新增** |
| imf-wp | IMF WP | IMF Working Papers | 工作论文 | targeted | **2026-11-08 新增** |
| feds | FEDS | Finance and Economics Discussion Series | 工作论文 | targeted | **2026-11-08 新增** |
| nyfed-sr | NY Fed SR | Federal Reserve Bank of New York Staff Reports | 工作论文 | targeted | **2026-11-08 新增** |
| optimization-online | Optimization Online | Optimization Online | 预印本/索引 | targeted | **2026-11-09 新增** |

## Interdisciplinary（36）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| cacm | CACM | [Communications of the ACM](https://cacm.acm.org/) | 期刊 | targeted |  |
| sac | SAC | ACM Symposium on Applied Computing | 会议 | targeted |  |
| jintelsys | Int. J. Intelligent Systems | International Journal of Intelligent Systems | 期刊 | targeted |  |
| epj-data | EPJ Data Science | EPJ Data Science | 期刊 | targeted |  |
| pnas | PNAS | Proceedings of the National Academy of Sciences | 期刊 | targeted | **2026-11-08 新增** |
| csur | CSUR | ACM Computing Surveys | 期刊 | targeted | **2026-11-08 新增** |
| proc-ieee | Proc. IEEE | Proceedings of the IEEE | 期刊 | targeted | **2026-11-08 新增** |
| technology-in-society | Technol. Soc. | Technology in Society | 期刊 | targeted | **2026-11-08 新增** |
| caise-workshops | CAiSE Workshops | International Conference on Advanced Information Systems Engineering Workshops | 工作坊 | targeted | **2026-11-09 新增** |
| ecis | ECIS | European Conference on Information Systems | 会议 | targeted | **2026-11-09 新增** |
| pacis | PACIS | Pacific Asia Conference on Information Systems | 会议 | targeted | **2026-11-09 新增** |
| amcis | AMCIS | Americas Conference on Information Systems | 会议 | targeted | **2026-11-09 新增** |
| hicss | HICSS | Hawaii International Conference on System Sciences | 会议 | targeted | **2026-11-09 新增** |
| chi | CHI | ACM Conference on Human Factors in Computing Systems | 会议 | targeted | **2026-11-09 新增** |
| fdg | FDG | International Conference on the Foundations of Digital Games | 会议 | targeted | **2026-11-09 新增** |
| goodit | GoodIT | ACM International Conference on Information Technology for Social Good | 会议 | targeted | **2026-11-09 新增** |
| asonam | ASONAM | IEEE/ACM International Conference on Advances in Social Networks Analysis and Mining | 会议 | targeted | **2026-11-09 新增** |
| acs-complex | Adv. Complex Syst. | Advances in Complex Systems | 期刊 | targeted | **2026-11-09 新增** |
| appl-netw-sci | Appl. Netw. Sci. | Applied Network Science | 期刊 | targeted | **2026-11-09 新增** |
| chaos-solitons | Chaos, Solitons & Fractals | Chaos, Solitons & Fractals | 期刊 | targeted | **2026-11-09 新增** |
| chaos | Chaos | Chaos: An Interdisciplinary Journal of Nonlinear Science | 期刊 | targeted | **2026-11-09 新增** |
| dgov | DGOV | Digital Government: Research and Practice | 期刊 | targeted | **2026-11-09 新增** |
| electronic-markets | Electronic Markets | Electronic Markets | 期刊 | targeted | **2026-11-09 新增** |
| eswa | ESWA | Expert Systems with Applications | 期刊 | targeted | **2026-11-09 新增** |
| jeim | JEIM | Journal of Enterprise Information Management | 期刊 | targeted | **2026-11-09 新增** |
| pnas-nexus | PNAS Nexus | PNAS Nexus | 期刊 | targeted | **2026-11-09 新增** |
| rsos | R. Soc. Open Sci. | Royal Society Open Science | 期刊 | targeted | **2026-11-09 新增** |
| tfsc | TFSC | Technological Forecasting and Social Change | 期刊 | targeted | **2026-11-09 新增** |
| research-policy | Research Policy | Research Policy | 期刊 | targeted | **2026-11-09 新增** |
| jit | JIT | Journal of Information Technology | 期刊 | targeted | **2026-11-09 新增** |
| ejis | EJIS | European Journal of Information Systems | 期刊 | targeted | **2026-11-09 新增** |
| isj | ISJ | Information Systems Journal | 期刊 | targeted | **2026-11-09 新增** |
| ijim | IJIM | International Journal of Information Management | 期刊 | targeted | **2026-11-09 新增** |
| jbr | JBR | Journal of Business Research | 期刊 | targeted | **2026-11-09 新增** |
| information-sciences | Inf. Sci. | Information Sciences | 期刊 | targeted | **2026-11-09 新增** |
| telecom-policy | Telecomm. Policy | Telecommunications Policy | 期刊 | targeted | **2026-11-09 新增** |

## Preprint（1）

| ID | 简称 | 完整名称 | 类型 | 检索优先级 | 加入 |
| --- | --- | --- | --- | --- | --- |
| dallas-globalization-wp | Dallas Fed WP | Federal Reserve Bank of Dallas, Globalization Institute Working Papers | 工作论文 | targeted |  |

## 已拒收（5）

按 `data/venue_policy_v2.json` 拒收；出版方级规则（MDPI、IEEE Access、Hindawi 等 DOI 前缀）同样适用于未列出的刊名。

| ID | 简称 | 完整名称 | 规则 |
| --- | --- | --- | --- |
| blockchains | Blockchains | Blockchains | mdpi |
| ieee-access | IEEE Access | IEEE Access | ieee-access |
| electronics | Electronics | Electronics | mdpi |
| mathematics | Mathematics | Mathematics | mdpi |
| analytics | Analytics | Analytics | mdpi |

