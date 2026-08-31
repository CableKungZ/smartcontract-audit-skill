# Swap / DEX / Router

Covers: AMM cores (V2 constant-product, V3 concentrated, stable/curve-style),
routers, aggregators, and any contract that performs a swap internally.

## Slippage & deadline (checked on every swap path, including internal ones)

- `amountOutMin == 0` or a caller-supplied value that the contract itself sets to
  0 → guaranteed sandwich. **Any protocol-internal swap** (harvest, liquidation,
  fee conversion, zap) with no `minOut` is High at minimum.
- `minOut` derived on-chain from the same pool being swapped (`getAmountsOut`
  then pass as `minOut`) is *not* slippage protection — it moves with the
  manipulation. It must come from the caller or an independent oracle.
- `deadline = block.timestamp` (inside the same tx) is a no-op — the value must
  come from the caller.
- Missing deadline entirely → a signed/pending tx can be held and executed later
  at a worse price.

## Constant-product (V2) core

- `swap()` invariant check `k_after >= k_before` performed with fee applied to
  the *correct* input amount; forks that changed the fee constant in one of the
  two places (Uranium: `1000` → `10000` in one branch only) drain the pool.
- `skim` / `sync` interaction with fee-on-transfer and rebasing tokens.
- `_update` overflow of `reserve0/1` when cast to `uint112`.
- Reentrancy: the optimistic-transfer flash-swap callback happens before the `k`
  check; the lock must cover `mint`/`burn`/`swap`/`sync`.
- Price accumulators (`price0CumulativeLast`) using `block.timestamp` truncated
  to `uint32` — overflow handling must be unchecked-by-design, not a bug.

## Concentrated liquidity (V3-style)

- Tick math: `sqrtPriceX96` rounding direction in `getAmountsForLiquidity`
  (must round against the LP on mint, against the trader on swap).
- `tickSpacing` not enforced; ticks outside `MIN_TICK/MAX_TICK`.
- Callback (`uniswapV3SwapCallback`) not validating `msg.sender` is a pool
  deployed by the canonical factory → anyone calls the callback and steals the
  approved tokens from users of your periphery contract. **Very common Critical
  in forks and in integrating contracts.**
- Fee growth accounting inside/outside the range; `feeGrowthGlobal` underflow is
  intentional (wrapping) — don't "fix" it, but verify the fork kept `unchecked`.
- Oracle cardinality never increased → `observe` ≈ spot.

## Stable-swap / curve-style

- Newton iteration `getD`/`getY` not converging; missing iteration cap or a cap
  so low the result is wrong.
- Amplification coefficient ramp (`ramp_A`) without a rate limit → admin can
  step A and extract via an imbalanced swap.
- Imbalanced-deposit fee missing → free arbitrage on adding liquidity.
- Read-only reentrancy in `get_virtual_price` during a `remove_liquidity` ETH
  transfer — any lending market pricing the LP token with it gets a stale value
  (the Curve/Vyper class of incidents).

## Routers & aggregators

- Arbitrary-call routers (`call(target, data)`) where `target` is user-supplied →
  the router's own approvals/balances are drained. Must allowlist targets and
  forbid the token contracts themselves as targets.
- Leftover approvals to a target after a partial fill.
- `msg.value` handling in a multicall loop: `msg.value` is constant per call, so
  a loop can spend the same ETH twice.
- Fee-on-transfer tokens: `amountOut` measured by expectation instead of
  `balanceAfter - balanceBefore`.
- Path validation: a path whose last token is not the requested `tokenOut`;
  unchecked path length.
- WETH unwrap sending ETH to a contract that reverts → DoS on a shared path.

## MEV

- Every price-touching user action is sandwichable; the mitigation is
  caller-supplied `minOut` + deadline, not on-chain cleverness.
- Reward/fee-conversion swaps executed by a permissionless keeper should either
  accept a keeper-supplied `minOut` with an oracle sanity bound, or run through
  a private mempool. Note the assumption in the report.

## Checklist

1. List every external call that moves price. For each: who supplies `minOut`?
   Who supplies `deadline`? If the answer is "the contract", it's a finding.
2. For every callback function: does it verify `msg.sender`?
3. Diff any forked math against upstream line by line — constants especially.

## Reference incidents

- Uranium Finance (2021, $50M): single constant mismatch in the `k` check.
- Curve/Vyper reentrancy-lock bug (2023, ~$70M): read-only reentrancy on
  `get_virtual_price`.
- Many V3-fork periphery drains via unvalidated `uniswapV3SwapCallback`.
