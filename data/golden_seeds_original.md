### 一、奠基与系统（5）

1. **Nakamoto**, *Bitcoin: A Peer-to-Peer Electronic Cash System*, 2008。一切的起点。
2. **Bonneau, Miller, Clark, Narayanan, Kroll, Felten**, *SoK: Research Perspectives and Challenges for Bitcoin and Cryptocurrencies*, S&P 2015。早期最好的综述，入门首选。
3. **Garay, Kiayias, Leonardos**, *The Bitcoin Backbone Protocol: Analysis and Applications*, EUROCRYPT 2015。第一次给出最长链的形式化安全性（common prefix / chain quality / chain growth）。
4. **Sompolinsky, Zohar**, *Secure High-Rate Transaction Processing in Bitcoin* (GHOST), FC 2015。分叉选择规则与吞吐量。
5. **Eyal, Gencer, Sirer, van Renesse**, *Bitcoin-NG: A Scalable Blockchain Protocol*, NSDI 2016。把领导者选举和交易打包分开。

### 二、挖矿激励与 Selfish Mining（6）

6. **Babaioff, Dobzinski, Oren, Zohar**, *On Bitcoin and Red Balloons*, EC 2012。交易转发的激励问题，EC 圈最早的区块链论文之一。
7. **Eyal, Sirer**, *Majority is not Enough: Bitcoin Mining is Vulnerable*, FC 2014。Selfish mining 的原始论文。
8. **Sapirshtein, Sompolinsky, Zohar**, *Optimal Selfish Mining Strategies in Bitcoin*, FC 2016。用 MDP 求最优策略和阈值。
9. **Eyal**, *The Miner’s Dilemma*, S&P 2015。矿池之间的 block withholding 博弈。
10. **Kiayias, Koutsoupias, Kyropoulou, Tselekounis**, *Blockchain Mining Games*, EC 2016。用博弈论刻画矿工在分叉上的选择。
11. **Carlsten, Kalodner, Weinberg, Narayanan**, *On the Instability of Bitcoin Without the Block Reward*, CCS 2016。只剩手续费时的 undercutting 攻击，引出后来的 TFM 研究。

### 三、经济学视角（5）

12. **Budish**, *The Economic Limits of Bitcoin and the Blockchain*, NBER WP 2018。安全成本必须随攻击收益线性增长，是"流量与存量"论证的源头。
13. **Huberman, Leshno, Moallemi**, *Monopoly without a Monopolist: An Economic Analysis of the Bitcoin Payment System*, RES 2021。手续费市场的排队论模型。
14. **Leshno, Strack**, *Bitcoin: An Axiomatic Approach and an Impossibility Theorem*, AER: Insights 2020。用公理刻画 PoW 奖励规则。
15. **Arnosti, Weinberg**, *Bitcoin: A Natural Oligopoly*, ITCS 2019。成本异质性导致挖矿集中。
16. **Biais, Bisière, Bouvard, Casamatta**, *The Blockchain Folk Theorem*, RFS 2019。最长链是均衡，分叉也是均衡。

### 四、交易费机制设计 TFM（6）

17. **Lavi, Sattath, Zohar**, *Redesigning Bitcoin’s Fee Market*, WWW 2019。Monopolistic price 机制。
18. **Roughgarden**, *Transaction Fee Mechanism Design*, EC 2021（JACM 2024）。定义 UIC/MMIC/OCA-proof，分析 EIP-1559。TFM 必读。
19. **Chung, Shi**, *Foundations of Transaction Fee Mechanism Design*, SODA 2023。不可能性定理，以及有限区块下的设计。
20. **Ferreira, Moroz, Parkes, Stern**, *Dynamic Posted-Price Mechanisms for the Blockchain Transaction-Fee Market*, AFT 2021。
21. **Leonardos, Monnot, Reijsbergen, Skoulakis, Piliouras**, *Dynamical Analysis of the EIP-1559 Ethereum Fee Market*, AFT 2021。base fee 更新规则的动力学分析。
22. **Bahrani, Garimidi, Roughgarden**, *Transaction Fee Mechanism Design with Active Block Producers*, FC 2024。把 MEV 纳入 TFM 后的不可能性结果。

### 五、MEV 与交易排序（6）

23. **Daian, Goldfeder, Kell, Li, Zhao, Bentov, Breidenbach, Juels**, *Flash Boys 2.0: Frontrunning, Transaction Reordering, and Consensus Instability in DEXs*, S&P 2020。MEV 概念的出处。
24. **Zhou, Qin, Torres, Le, Gervais**, *High-Frequency Trading on Decentralized On-Chain Exchanges*, S&P 2021。三明治攻击的形式化。
25. **Qin, Zhou, Gervais**, *Quantifying Blockchain Extractable Value: How Dark is the Forest?*, S&P 2022。大规模实证测量。
26. **Babel, Daian, Kelkar, Juels**, *Clockwork Finance: Automated Analysis of Economic Security in Smart Contracts*, S&P 2023。用形式化方法计算可提取价值的上界。
27. **Kelkar, Zhang, Goldfeder, Juels**, *Order-Fairness for Byzantine Consensus* (Aequitas), CRYPTO 2020。从共识层面防止重排。
28. **Ferreira, Parkes**, *Credible Decentralized Exchange Design via Verifiable Sequencing Rules*, STOC 2023。可验证的排序规则，以及排序操纵的下界。

### 六、AMM（6）

29. **Angeris, Kao, Chiang, Noyes, Chitra**, *An Analysis of Uniswap Markets*, Cryptoeconomic Systems 2021（arXiv 2019）。
30. **Angeris, Chitra**, *Improved Price Oracles: Constant Function Market Makers*, AFT 2020。CFMM 的凸分析框架。
31. **Milionis, Moallemi, Roughgarden, Zhang**, *Automated Market Making and Loss-Versus-Rebalancing* (LVR), arXiv 2022。LP 损失的正确度量，影响很大。
32. **Lehar, Parlour**, *Decentralized Exchange: The Uniswap Automated Market Maker*, Journal of Finance。AMM 与限价订单簿的均衡比较。
33. **Capponi, Jia**, *The Adoption of Blockchain-based Decentralized Exchanges*, 2021。LP 激励、gas 与抢跑。
34. **Goyal, Ramseyer, Goel, Mazières**, *Finding the Right Curve: Optimal Design of Constant Function Market Makers*, EC 2023。

### 七、DeFi 偏金融（5）

35. **Gudgeon, Perez, Harz, Livshits, Gervais**, *The Decentralized Financial Crisis*, CVCBT 2020。DeFi 的系统性风险。
36. **Gudgeon, Werner, Perez, Knottenbelt**, *DeFi Protocols for Loanable Funds: Interest Rates, Liquidity and Market Efficiency*, AFT 2020。借贷协议的利率模型。
37. **Qin, Zhou, Livshits, Gervais**, *Attacking the DeFi Ecosystem with Flash Loans for Fun and Profit*, FC 2021。
38. **Klages-Mundt, Minca**, *(In)Stability for the Blockchain: Deleveraging Spirals and Stablecoin Attacks*, Cryptoeconomic Systems 2021。去中心化稳定币的去杠杆螺旋。
39. **Werner, Perez, Gudgeon, Klages-Mundt, Harz, Knottenbelt**, *SoK: Decentralized Finance (DeFi)*, AFT 2022。

### 八、Incentive Security 与 PoS（6）

40. **Luu, Teutsch, Kulkarni, Saxena**, *Demystifying Incentives in the Consensus Computer*, CCS 2015。Verifier’s dilemma。
41. **Pass, Shi**, *FruitChains: A Fair Blockchain*, PODC 2017。用协议设计让 selfish mining 无利可图（近似纳什均衡）。
42. **Brown-Cohen, Narayanan, Psomas, Weinberg**, *Formal Barriers to Longest-Chain Proof-of-Stake Protocols*, EC 2019。最长链 PoS 中的 predictable selfish mining 与 nothing-at-stake。
43. **Ferreira, Weinberg**, *Proof-of-Stake Mining Games with Perfect Randomness*, EC 2021。
44. **Schwarz-Schilling, Neu, Monnot, Asgaonkar, Tas, Tse**, *Three Attacks on Proof-of-Stake Ethereum*, FC 2022。
45. **Budish, Lewis-Pye, Roughgarden**, *The Economic Limits of Permissionless Consensus*, EC 2024。把 Budish 的论证推广到 PoS，并讨论 slashing 的作用。

### 九、Rational Cryptography（5）

46. **Halpern, Teague**, *Rational Secret Sharing and Multiparty Computation*, STOC 2004。理性密码学的开山论文。
47. **Garay, Katz, Maurer, Tackmann, Zikas**, *Rational Protocol Design: Cryptography Against Incentive-Driven Adversaries*, FOCS 2013。RPD 框架。
48. **Badertscher, Garay, Maurer, Tschudi, Zikas**, *But Why Does It Work? A Rational Protocol Design Treatment of Bitcoin*, EUROCRYPT 2018。用 RPD 解释比特币为什么在实践中安全。
49. **Bentov, Kumaresan**, *How to Use Bitcoin to Design Fair Protocols*, CRYPTO 2014。用押金和惩罚实现 fairness。
50. **Shi, Chung, Wu**, *What Can Cryptography Do for Decentralized Mechanism Design?*, ITCS 2023。密码学如何绕过 TFM 的不可能性结果，连接了第四组和第九组。这些可以作为seed，待会，我会让你连接到本地codex，让你直接开始开发。现在让我们构思整个工作流程
