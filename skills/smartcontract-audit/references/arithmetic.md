# Arithmetic, Overflow & Contract Liveness

**Load this file on every audit, regardless of contract type.**

Two linked concerns:
1. Does any expression exceed the range of the type it is stored in?
2. Can any *required* code path be made to revert permanently — i.e. can the
   contract be **bricked** (funds frozen, no recovery)?

In Solidity ≥0.8 an overflow is not a silent wrap, it is a **revert**. That
turns every arithmetic bug into a potential liveness bug. A `withdraw()` that
reverts forever is the same outcome as stolen funds, but with no attacker to
sue. Audit arithmetic as a DoS class, not only as a value class.

---

## 1. Type-range audit (do this mechanically)

Build a table: every state variable and struct field, its type, its maximum
value, and the largest realistic value it must hold. Any row where the second
column can be exceeded is a finding.

| Type | Max | Breaks at |
|---|---|---|
| `uint8` | 255 | any counter, any percentage stored as bps |
| `uint16` | 65,535 | user counts, tick indices, seconds in a week (604800 — overflows) |
| `uint32` | ~4.29e9 | **unix timestamps overflow in 2106**; block numbers on fast chains; token amounts with any decimals |
| `uint40` | ~1.1e12 | safe for timestamps until year ~36812; too small for wei |
| `uint64` | ~1.84e19 | 18.4 tokens at 18 decimals — **far too small for token amounts** |
| `uint96` | ~7.9e28 | fine for most token supplies; overflows for high-supply meme tokens (1e15 × 1e18 = 1e33) |
| `uint112` | ~5.19e33 | Uniswap V2 reserve type — overflows for a token with supply > 5.19e15 at 18 decimals |
| `uint128` | ~3.4e38 | safe for amounts; **not** safe for `amount * 1e18 * 1e18` intermediates |
| `uint160` | — | an `address`; casting a hash to it is fine, casting it back is not |
| `uint256` | ~1.15e77 | intermediates like `a * b * PRECISION` where `a,b ≈ 1e30` |

### What to check, line by line

- **Packed structs.** Storage packing (`uint128 amount; uint128 rewardDebt;` in
  one slot) is the most common place a real value silently exceeds the type.
  Every write into a narrow field needs a bound. In ≥0.8 a *downcast* is
  **not** checked — `uint128(x)` truncates silently. Use
  `SafeCast.toUint128(x)` (OpenZeppelin) so it reverts instead of corrupting.
  Grep for `uint\d{1,3}\(` and inspect every hit.
- **Intermediates before division.** `a * b / c` overflows on `a * b` even
  though the result fits. With `PRECISION = 1e18` and 18-decimal amounts,
  `amount * PRECISION * PRECISION` overflows at amounts above ~1.15e41 — reachable
  for a high-supply token. Use `Math.mulDiv` (OZ) / `FullMath.mulDiv` (Uniswap),
  which computes the 512-bit intermediate.
- **Accumulators that only grow.** `accRewardPerShare`, `borrowIndex`,
  `price0CumulativeLast`, `feeGrowthGlobal`, `totalRewardsDistributed`. These
  are monotonic and never reset. State the value after 10 years at the
  maximum rate and compare against the type max. If it overflows, the contract
  reverts on every interaction from that moment on → **dead**.
  - Note: Uniswap's cumulative accumulators are *designed* to wrap and are in
    `unchecked` blocks. Do not "fix" those; do verify a fork kept `unchecked`,
    because in ≥0.8 without it they revert instead of wrapping.
- **`type(uint256).max` sentinels.** `approve(spender, type(uint256).max)`,
  `amount = type(uint256).max` meaning "all". Any arithmetic on the sentinel
  (`amount + fee`, `amount * rate`) overflows. Handle the sentinel before the math.
- **Signed types.** `int256` min is `-2^255`; `-x` on `type(int256).min`
  reverts, and `abs()` on it overflows. Casting `uint256 → int256` above
  `2^255-1` silently produces a negative number (unchecked in ≥0.8) — use
  `SafeCast.toInt256`.
- **Exponentiation.** `a ** b` overflows fast. Compound-interest loops
  (`for (i=0; i<n; i++) x = x * rate / 1e18`) with an unbounded `n` both
  overflow and burn unbounded gas.
- **Decimal mismatch.** See the dedicated section below — it is the most common
  source of silently-wrong money in multi-token contracts.

### Decimals — normalize before you do anything else

ERC-20 `decimals()` is **not** part of the mandatory standard and is **not**
always 18. Real, widely-held tokens ship 6 (USDC, USDT), 8 (WBTC), 2, 0, and 24.
Nothing prevents a token from returning a different value than it did yesterday
if `decimals()` is not immutable. Any contract that touches two tokens, or that
lets an admin swap a token address, must normalize.

**Where it goes wrong:**

- **Hardcoded `1e18`** anywhere a token amount is scaled — `amount * price / 1e18`,
  `PRECISION = 1e18`, `MIN_DEPOSIT = 1e18`. Correct for WETH, off by 1e12 for
  USDC. Grep for `1e18`, `1 ether`, and `10**18` and check each against the
  token that actually flows through that line.
- **Comparing or adding amounts of two different tokens** without scaling both
  to a common basis. `require(amountIn >= amountOut)` across a 6-decimal and an
  18-decimal token is meaningless.
- **Price feeds have their own decimals**, independent of both tokens. Chainlink
  USD feeds are usually 8 and ETH-quoted feeds 18 — but read `decimals()` from
  the aggregator rather than assuming, and do it per feed.
- **`decimals()` read once and cached** at deploy while the token address is
  mutable — or read from a token that does not implement it at all, so the call
  reverts (or, via a low-level call, silently returns nothing and decodes as 0).
- **Normalizing by scaling down first** (`amount / 10**(18 - d)`) truncates.
  Scale **up** to the common basis, do the arithmetic, then scale down once at
  the end — and watch the intermediate against the overflow rules above.
- **Fee, threshold and minimum constants expressed in token units.** A
  `minFee = 1e18` is 1 USDC-worth of nothing if the fee token is 6-decimal, and
  a `dustThreshold` calibrated for 18 decimals will treat real balances of an
  8-decimal token as dust — or never trigger at all.
- **A configurable fee token.** If an admin can change which token fees are paid
  in, every constant calibrated for the old token is now wrong. This is a real
  finding, not a hypothetical: it silently changes fee amounts by orders of
  magnitude the moment the setter is used.

**What to recommend:**

- Read `decimals()` from each token **at the point of use**, or store it
  alongside the token address in the same struct and re-read it whenever the
  address is set. Never assume, never hardcode.
- Normalize to a single internal basis (18 is the conventional choice) at the
  boundary — on the way in and on the way out — so all internal math works in
  one unit. Use `SafeCast` and `Math.mulDiv` for the conversion, since
  `amount * 10**(18 - d)` is exactly the intermediate-overflow case above.
- Express fees in **basis points of the amount**, not in absolute token units,
  so they are decimals-independent by construction. Where an absolute minimum
  really is needed, store it per token and set it when the token is registered.
- Reject tokens whose `decimals()` is above 18 (or handle them explicitly) — the
  scale-up conversion overflows quickly and most codebases never test it.
- Emit the decimals used in the event, or at minimum in the registration event,
  so an integrator can detect a mismatch off-chain.

**How to file it.** Severity follows the money it moves: a fee or price
computed with the wrong scale is usually High or Critical because it is off by
a factor of 10^n in someone's favour, silently, on every call. A cosmetic
mismatch in a view or an event is Informational. Say which token and which line
in the finding, and give the corrected expression in the `fix` block.

### Precision (the other half of the same read)

- **Division before multiplication** truncates. `(a / b) * c` ≠ `a * c / b`.
  Always multiply first — and then check the intermediate per the rule above.
- **Rounding direction must always favour the protocol.** Shares minted round
  down, debt owed rounds up, fees charged round up, amounts paid out round down.
  One inversion plus a loop is a value-extraction exploit. Write the loop out
  with numbers before filing.
- **Truncation to zero.** `reward * 1e12 / totalStaked` is 0 once `totalStaked`
  exceeds `reward * 1e12`. Compute the result at realistic magnitudes and check
  it is non-zero. A silent zero is worse than a revert — it looks like it works.
- **Fee/bps math.** `amount * feeBps / 10_000` with `feeBps` unbounded, or a
  fee that can be set to > 10000 → the contract takes more than 100% and the
  subtraction underflows and reverts. Bound every bps setter.

---

## 2. Liveness — can this contract be killed?

For each of these, the test is: *is there a state an attacker (or an unlucky
sequence) can reach where a function users need never succeeds again?*

### Arithmetic-induced permanent revert

- **Underflow in accounting.** `totalStaked -= amount` where `totalStaked` has
  drifted below the sum of user balances (fee-on-transfer token, a donation, a
  rounding leak, a forgotten decrement). Once it underflows, **every**
  withdrawal reverts. This is the classic way a staking contract dies.
  Defence: track balances so the invariant cannot drift, or clamp:
  `totalStaked -= amount > totalStaked ? totalStaked : amount` with the reason
  documented.
- **Division by zero.** `totalShares`, `totalStaked`, `totalSupply`,
  `reserve`, `liquidity`, `duration`, `totalAllocPoint` can all reach 0 when the
  last user exits. Guard every denominator, and specifically check the
  "last user withdraws" path end to end.
- **Overflow of a monotonic accumulator** (above) → dead from that block on.
- **A revert inside a `view`** used by another function or by every frontend.

### External-call-induced permanent revert

- **A single reverting recipient in a push loop** blocks everyone. Use pull
  payments. This is the #1 structural liveness bug.
- **Unbounded loops.** An array a user can grow (stakers, positions, pools,
  reward tokens, NFT ids) iterated in a function that must succeed. Past N
  entries the call exceeds the block gas limit and the function is dead forever
  — and the attacker chooses N. Cheap-gas chains (BNB, KUB, Polygon) make this
  cheap to trigger, so treat it as a real finding there, not a theoretical one.
  Fix: pagination, pull pattern, or a hard cap enforced on the *growth* path.
- **`require(success)` on a call the callee controls.** If a third-party
  protocol pauses, self-destructs, or blocklists this contract, the dependent
  path dies. Provide an emergency path that accepts the loss.
- **Blocklist tokens** (USDC, USDT): a blocklisted recipient in a required
  transfer freezes the whole path. On KUB, a KAP-20 committee can move balances
  out from under the contract — see `kub.md`.
- **Fee-on-transfer / rebasing tokens** breaking an exact-amount assertion:
  `require(received == amount)` reverts forever with such a token.
- **Return-data bombs / gas griefing**: an untrusted callee returning megabytes
  makes the caller run out of gas. Bound returndata.
- **63/64 gas rule (EIP-150)**: a sub-call can be made to fail while the outer
  call succeeds. Any "paid on success" design must not assume the sub-call got
  all the gas.

### Configuration-induced bricking

- **Ownership transferred to a wrong or zero address** in a single step →
  every `onlyOwner` function dead. Use `Ownable2Step`.
- **`renounceOwnership` left inherited** on a contract that needs an owner for
  upgrades, fee changes, or emergency withdrawal. Override and revert it unless
  renouncing is genuinely intended.
- **All owners removed / threshold set above the owner count** in a multisig.
- **A one-time setter** (`setToken`, `initialize`) set to a wrong address with
  no way to correct it.
- **Timelock delay set to a value larger than the timelock's own grace period**
  → nothing can ever execute, including the fix.
- **Pause with no unpause path**, or unpause gated behind a role that can be
  renounced.
- **UUPS proxy**: `_authorizeUpgrade` reverting unconditionally, or an upgrade
  to an implementation with no `upgradeTo` → the proxy can never be upgraded
  again. Also: an uninitialized implementation that can be `selfdestruct`ed
  (Parity, 2017 — $150M frozen, the archetype of this whole section).

### Positive checks to require in the report

Every audited contract should be able to answer yes to these. Each "no" is a
finding, severity by the value at risk:

1. Can every user retrieve their principal on a path that touches **no**
   external contract other than the asset token itself?
2. Is there a state where that path reverts? Name it or prove there isn't.
3. Is every loop bounded by a constant, or by a value only an admin can grow?
4. Is every denominator provably non-zero at the point of division?
5. Does every narrowing cast use `SafeCast`, or have a proven bound?
6. Does every monotonic accumulator fit its type for the contract's intended
   lifetime at the maximum configured rate?
7. Is there an emergency withdrawal that skips reward accounting, external
   calls, and oracle reads?

---

## Severity guidance

- Permanent freeze of user principal with no recovery → **Critical**
  (`methodology.md` treats permanent freeze as equivalent to loss).
- Freeze with an admin recovery path (unpause, upgrade, admin sweep) → **High**,
  and the recovery itself becomes a centralization finding.
- Overflow/underflow producing a *wrong value* rather than a revert
  (unchecked block, silent downcast) → severity by the value it moves;
  usually High or Critical because it mints or destroys balance.
- A loop that dies only past an unrealistic N, or a `uint32` timestamp
  overflowing in 2106 → **Low/Informational**, but state the horizon explicitly
  rather than dropping it.

## How to actually find these

- Grep the diff: `unchecked`, `uint8|uint16|uint32|uint64|uint96|uint112|uint128`,
  `int256(`, `/`, `**`, `for (`, `while (`, `.call{`, `type(uint`.
  `scripts/scan.py` in this repo does this pass and prints the hits with line
  numbers — start there, then read the surrounding logic.
- For each division: write the denominator's minimum value.
- For each narrow type: write its maximum realistic value.
- For each loop: write who can grow the bound and by how much per transaction.
- Then run a fuzz/invariant test (Foundry `invariant_`) on the solvency and
  "principal is always withdrawable" properties. Recommend this in the report if
  the project has no invariant tests — for arithmetic bugs it catches what
  review misses.

## Reference incidents

- Parity multisig (2017): library `selfdestruct` → $150M permanently frozen.
- BeautyChain / BEC (2018): `batchTransfer` multiplication overflow (pre-0.8)
  minted ~1e58 tokens.
- Uniswap V2 `uint112` reserves: the reason a max supply assumption exists.
- Numerous MasterChef forks bricked by `totalAllocPoint` reaching 0 (division
  by zero in `updatePool`) after all pools were set to 0 allocation.
- Compound (2021, $80M): a single `>=` vs `>` in a reward accrual path.
