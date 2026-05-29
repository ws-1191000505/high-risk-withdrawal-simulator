# High Risk Withdrawal Simulator

高风险交易账户出金规则模拟器，用于比较“新高出半”和“盈利出半”在不同胜率、盈亏比、连续回撤场景下的表现。

## 结论

对高波动策略而言，**新高出半更适合作为主规则**。

它只在账户突破历史权益高点后提取新增利润的一半，能保留更多交易账户缓冲和复利空间；“盈利出半”虽然出金更快，但会更早削薄账户权益，在连续亏损场景下更容易触发爆仓。

本次模拟中，“盈利出半”的爆仓概率更高的场景占比为 **88.9%**；在低胜率、高盈亏比的高波动组合中，这一占比为 **100.0%**。因此，“盈利出半”更适合提款型账户，“新高出半”更适合需要长期运行、等待少数大行情兑现的高波动策略。

## 模拟内容

- 胜率：35% / 45% / 55%
- 盈亏比：1.2R / 2.0R / 3.0R
- 压力场景：无强制连亏、前期 6 连亏、中段 8 连亏、后段 10 连亏
- 指标：资金曲线、最大回撤、累计出金、爆仓概率

## 文件

- `high_risk_withdrawal_simulator.py`：模拟器脚本
- `results/high_risk_withdrawal_report_cn.md`：中文结论报告
- `results/withdrawal_rule_summary.csv`：完整场景汇总
- `results/withdrawal_rule_comparison.csv`：两套规则差值
- `results/withdrawal_rule_curves.svg`：代表性资金曲线
- `results/high_volatility_rule_differences.svg`：高波动场景差值热力图

## 使用

```bash
python high_risk_withdrawal_simulator.py
```

运行后会重新生成 `results/` 目录下的报告、CSV 和 SVG 图表。
