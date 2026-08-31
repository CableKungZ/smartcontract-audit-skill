# Liquidity / LP Accounting

Covers: LP token mint/burn, share math, zaps, liquidity managers/vaults over
V3 positions, and anything that converts assets ↔ shares.

## First-depositor / share-inflation attack

The canonical bug in every shares-based contract.

1. Attacker deposits the minimum (1 wei) → gets 1 share.
2. Attacker transfers a large amount of the underlying **directly** to the
   contract (donation), so `totalAssets` is huge and `totalShares == 1`.
3. Victim deposits `X`; `shares = X * 1 / totalAssets` rounds to **0** (or to a
   value far below fair) → victim's funds are absorbed by the attacker's share.

Check for one of these mitigations, and say which is present:
- `MINIMUM_LIQUIDITY` burned on first mint (Uniswap V2: 1000 shares to `address(0)`),
- virtual shares/assets offset (OpenZeppelin ERC4626 `_decimalsOffset`),
- internally-tracked `totalAssets` that ignores donations,
- an enforced seed deposit in the deployment script (only mitigates if the
  deploy is atomic — otherwise it's front-runnable, keep the finding at High).

## Share math

- Rounding direction, every path: **mint/deposit rounds shares down, burn/
  withdraw rounds assets down** (i.e. always against the user). One inverted
  rounding + a loop = value extraction. Write out the loop with numbers.
- `totalSupply == 0` branch computing shares differently — verify it can only be
  reached once, and that it can't be re-reached by burning all shares.
- `sqrt(a*b)` on first mint overflowing, or `sqrt` implemented with a bad
  Babylonian loop (off-by-one at perfect squares).
- Precision loss when the two assets have different decimals (USDC 6 / WETH 18) —
  normalize before multiplying.

## Add / remove liquidity

- `addLiquidity` without `amountAMin`/`amountBMin` → the ratio is sandwichable
  and the excess is left as dust or stolen. Same rule as `swap.md`: the caller
  supplies the bound.
- Leftover/refund path after an imbalanced add: unrefunded dust accumulates and
  is claimable by the next caller.
- `removeLiquidity` with `minOut = 0` on a manipulated pool.
- Fee-on-transfer / rebasing tokens in a pair: reserves drift from balances,
  `skim` becomes a free-money function for whoever calls it.
- Zap-in: swap half then add — the swap needs its own slippage bound, and the
  intermediate balance must not be claimable by a reentrant call.

## Concentrated-liquidity managers

- Rebalance callable permissionlessly with pool-derived bounds → sandwich the
  rebalance and extract the range.
- Position value computed from `slot0.sqrtPriceX96` (spot) during deposit/
  withdraw → flash-loan manipulable share price. Price positions with a TWAP.
- Uncollected fees not included in `totalAssets` → a depositor immediately after
  a large fee accrual gets a discount; or included but claimable twice.
- `mint`/`burn` on the underlying pool without settling the manager's own
  accounting first.
- Range with 0 liquidity → division by zero on withdraw.

## LP token as collateral / price feed

- `lpPrice = (reserve0 * p0 + reserve1 * p1) / totalSupply` uses spot reserves →
  manipulable. Use the fair-reserves formula (Alpha Homora) or Chainlink's
  LP-token methodology.
- Read-only reentrancy: `getReserves`/`get_virtual_price` read mid-`burn` while
  ETH is being sent, returning a stale ratio. Guard with the pool's own lock
  check or a TWAP.

## Withdrawal & liveness

- Withdrawal that requires an external protocol to be non-paused → user funds
  frozen by a third party. Provide an emergency path that accepts a loss.
- Withdraw queue with an unbounded loop over requests.
- Pausing that blocks `withdraw` — see `staking.md`.

## Checklist

1. State the solvency invariant in one line, then hunt for the path that breaks it.
2. For each of deposit / withdraw / mint / burn: what is `totalAssets` at that
   moment, and can an attacker change it in the same transaction (donation,
   flash loan, swap)?
3. First-deposit scenario, written with numbers, always.

## Reference incidents

- Uniswap V2 `MINIMUM_LIQUIDITY` — the mitigation that exists because of this.
- Compound-fork / Hundred Finance empty-market donation attacks.
- Curve read-only reentrancy (2023) affecting LP-token pricing in lending markets.
- Balancer boosted-pool rounding (2023) — precision loss in a shares path.
