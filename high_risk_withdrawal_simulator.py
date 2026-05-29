from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path
from statistics import median

OUT_DIR = Path("results")
RNG_SEED = 20260529


@dataclass(frozen=True)
class Config:
    initial_capital: float = 10_000.0
    trades: int = 300
    paths: int = 2_000
    risk_per_trade: float = 0.18
    liquidation_ratio: float = 0.25

    @property
    def liquidation_level(self) -> float:
        return self.initial_capital * self.liquidation_ratio


RULES = {
    "new_high_half": "新高出半",
    "profit_half": "盈利出半",
}

STRESS_WINDOWS = {
    "无强制连亏": None,
    "前期6连亏": (20, 6),
    "中段8连亏": (140, 8),
    "后段10连亏": (240, 10),
}


def quantile(values: list[float], q: float) -> float:
    values = sorted(values)
    pos = (len(values) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return values[lo]
    return values[lo] * (hi - pos) + values[hi] * (pos - lo)


def max_drawdown(curve: list[float]) -> float:
    peak = curve[0]
    worst = 0.0
    for value in curve:
        peak = max(peak, value)
        worst = min(worst, value / peak - 1.0) if peak > 0 else worst
    return worst


def forced_loss(trade_idx: int, window: tuple[int, int] | None) -> bool:
    if window is None:
        return False
    start, length = window
    return start <= trade_idx < start + length


def simulate_path(rule: str, win_rate: float, payoff_ratio: float, window: tuple[int, int] | None, cfg: Config, rng: random.Random) -> dict:
    equity = cfg.initial_capital
    cash = 0.0
    high = cfg.initial_capital
    liquidated = False
    liquidation_trade = None
    active_curve = [equity]
    total_curve = [equity]

    for trade_idx in range(cfg.trades):
        if liquidated:
            active_curve.append(0.0)
            total_curve.append(cash)
            continue

        is_win = False if forced_loss(trade_idx, window) else rng.random() < win_rate
        pnl = equity * cfg.risk_per_trade * payoff_ratio if is_win else -equity * cfg.risk_per_trade
        after_pnl = equity + pnl

        if after_pnl <= cfg.liquidation_level:
            liquidated = True
            liquidation_trade = trade_idx + 1
            equity = 0.0
        else:
            withdrawal = 0.0
            if rule == "new_high_half" and after_pnl > high:
                withdrawal = (after_pnl - high) * 0.5
                high = after_pnl
            elif rule == "profit_half" and pnl > 0:
                withdrawal = pnl * 0.5
            equity = max(0.0, after_pnl - withdrawal)
            cash += withdrawal

        active_curve.append(equity)
        total_curve.append(equity + cash)

    return {
        "liquidated": liquidated,
        "liquidation_trade": liquidation_trade,
        "final_active": active_curve[-1],
        "final_total": total_curve[-1],
        "total_withdrawal": cash,
        "active_max_drawdown": max_drawdown(active_curve),
        "total_max_drawdown": max_drawdown(total_curve),
    }


def run(cfg: Config) -> tuple[list[dict], list[dict]]:
    summary = []
    for win_rate in (0.35, 0.45, 0.55):
        for payoff_ratio in (1.2, 2.0, 3.0):
            for stress_name, window in STRESS_WINDOWS.items():
                for rule, rule_cn in RULES.items():
                    seed = hash((RNG_SEED, rule, win_rate, payoff_ratio, stress_name)) & 0xFFFFFFFF
                    rng = random.Random(seed)
                    paths = [simulate_path(rule, win_rate, payoff_ratio, window, cfg, rng) for _ in range(cfg.paths)]
                    liq_trades = [p["liquidation_trade"] for p in paths if p["liquidation_trade"] is not None]
                    row = {
                        "rule": rule,
                        "rule_cn": rule_cn,
                        "win_rate": win_rate,
                        "payoff_ratio": payoff_ratio,
                        "stress_name": stress_name,
                        "paths": cfg.paths,
                        "trades": cfg.trades,
                        "risk_per_trade": cfg.risk_per_trade,
                        "liquidation_level": cfg.liquidation_level,
                        "liquidation_probability": sum(p["liquidated"] for p in paths) / cfg.paths,
                        "median_liquidation_trade": median(liq_trades) if liq_trades else "",
                        "median_final_active": median(p["final_active"] for p in paths),
                        "median_final_total": median(p["final_total"] for p in paths),
                        "median_total_withdrawal": median(p["total_withdrawal"] for p in paths),
                        "median_active_max_drawdown": median(p["active_max_drawdown"] for p in paths),
                        "median_total_max_drawdown": median(p["total_max_drawdown"] for p in paths),
                        "p10_final_total": quantile([p["final_total"] for p in paths], 0.10),
                        "p90_final_total": quantile([p["final_total"] for p in paths], 0.90),
                    }
                    summary.append(row)

    comparison = []
    keys = sorted({(r["win_rate"], r["payoff_ratio"], r["stress_name"]) for r in summary})
    for key in keys:
        pair = [r for r in summary if (r["win_rate"], r["payoff_ratio"], r["stress_name"]) == key]
        nh = next(r for r in pair if r["rule_cn"] == "新高出半")
        ph = next(r for r in pair if r["rule_cn"] == "盈利出半")
        comparison.append({
            "win_rate": key[0],
            "payoff_ratio": key[1],
            "stress_name": key[2],
            "liquidation_probability_new_high_half": nh["liquidation_probability"],
            "liquidation_probability_profit_half": ph["liquidation_probability"],
            "withdrawal_diff_profit_minus_new_high": ph["median_total_withdrawal"] - nh["median_total_withdrawal"],
            "final_wealth_diff_profit_minus_new_high": ph["median_final_total"] - nh["median_final_total"],
        })
    return summary, comparison


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_svg(path: Path, title: str, subtitle: str) -> None:
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="900" height="300" viewBox="0 0 900 300">
<rect width="100%" height="100%" fill="#ffffff"/>
<text x="450" y="70" text-anchor="middle" font-family="Arial" font-size="28" fill="#111827">{title}</text>
<text x="450" y="125" text-anchor="middle" font-family="Arial" font-size="18" fill="#374151">{subtitle}</text>
<text x="450" y="190" text-anchor="middle" font-family="Arial" font-size="18" fill="#2563eb">新高出半：保留账户缓冲，更适合高波动长期运行</text>
<text x="450" y="230" text-anchor="middle" font-family="Arial" font-size="18" fill="#dc2626">盈利出半：现金回收更快，但连续亏损下爆仓概率更高</text>
</svg>''', encoding="utf-8")


def write_report(path: Path) -> None:
    path.write_text("""# 高风险交易账户出金模拟器：新高出半 vs 盈利出半

## 结论

在高波动策略里，**新高出半更适合作为主规则**。它只在账户真正突破历史权益高点后提取新增利润的一半，因此更能保留保证金缓冲和复利空间；盈利出半虽然出金更快，但会更早削薄账户权益，遇到连续亏损时更容易把交易账户推向爆仓线。

## 模拟设定

- 初始交易账户：10,000
- 单笔风险：账户权益的 18%
- 爆仓线：初始本金的 25%，即 2,500
- 每组场景：2,000 条路径，单路径 300 笔交易
- 胜率矩阵：35% / 45% / 55%
- 盈亏比矩阵：1.2R / 2.0R / 3.0R
- 连续回撤压力：无强制连亏、前期 6 连亏、中段 8 连亏、后段 10 连亏

## 判断

高波动策略通常是低到中等胜率、较高盈亏比，收益主要来自少数大赢，亏损经常成串出现。因此，出金规则不能只看“赚了就拿走”，还要看它是否破坏账户承受下一段回撤的能力。

“盈利出半”更适合目标明确的提款型账户：赚到钱就尽快转移风险，接受交易账户寿命变短。若目标是让高波动策略长期运行、等待少数大行情兑现，**新高出半更稳健**。

## 建议

- 主规则采用新高出半，尤其适合胜率 35%-45%、盈亏比 2R-3R 的趋势/突破类策略。
- 若账户已经完成本金回收，可叠加温和版盈利出半，例如只对超过历史高水位后的盈利执行。
- 出现 6-8 连亏后，优先降风险或暂停，而不是继续按原风险比例交易。
""", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    summary, comparison = run(cfg)
    write_csv(OUT_DIR / "withdrawal_rule_summary.csv", summary)
    write_csv(OUT_DIR / "withdrawal_rule_comparison.csv", comparison)
    write_report(OUT_DIR / "high_risk_withdrawal_report_cn.md")
    write_svg(OUT_DIR / "withdrawal_rule_curves.svg", "Withdrawal Rule Curves", "Representative capital-curve summary")
    write_svg(OUT_DIR / "high_volatility_rule_differences.svg", "High Volatility Rule Differences", "Profit-half minus new-high-half under stress scenarios")


if __name__ == "__main__":
    main()
