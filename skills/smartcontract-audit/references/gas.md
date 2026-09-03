# Loops, Gas Spending & Optimization

Two separate jobs, and they must not be confused in the report:

- **Gas as a security issue** — a loop or a gas assumption that lets someone
  brick a function or grief users. These are real findings (Medium→Critical).
  See also the liveness section of `arithmetic.md`.
- **Gas as an efficiency issue** — the same result for less gas, no security
  impact. These are **Informational**. Never inflate a gas optimization into a
  High just because it saves money.

Cheap-gas chains (BNB, Polygon, KUB, Avalanche) flip the balance: griefing loops
that are uneconomic on Ethereum L1 are cheap there, so a "theoretical" DoS is a
real one. On L2s (Arbitrum, Optimism, Base) **calldata dominates cost**, so
storage micro-optimizations matter far less than payload size.

---

## 1. Loops — the security pass

For every `for` / `while` in the codebase, answer four questions and write the
answers down. Any loop where the answer to (1) is "a user" and to (2) is
"unbounded" is a finding.

1. **Who controls the iteration count?** The contract, an admin, or any user?
2. **What is the maximum count?** A constant, an admin-set cap, or unbounded?
3. **How much does one extra iteration cost the attacker?** If pushing an entry
   costs less than it costs everyone else, it is a griefing vector.
4. **What breaks when the loop exceeds the block gas limit?** If a function
   users *need* (withdraw, liquidate, claim) dies, that is Critical/High. If
   only a convenience view dies, Low.

### Patterns

- **Unbounded array a user can grow**, iterated in a required function:
  `stakers[]`, `positions[]`, `rewardTokens[]`, `pools[]`, `holders[]`,
  `withdrawQueue[]`. Attacker creates N cheap entries → function is dead forever.
  Fix: pull pattern, pagination (`processFrom(uint start, uint end)`), or a hard
  cap enforced **on the growth path**, not on the loop.
- **Push payments in a loop.** One reverting or gas-burning recipient blocks
  everyone. Always pull. If push is required, wrap each transfer in a
  try/catch with a bounded gas stipend and record failures for later pull.
- **External call inside a loop.** Each callee can revert or consume all
  forwarded gas. Cost is unpredictable and attacker-controlled.
- **Nested loops** over user-growable sets → O(n²), dies far earlier than it looks.
- **Loop with a storage write per iteration** (~5,000–20,000 gas each): the real
  ceiling is a few hundred iterations, not thousands. Compute the actual limit
  and state it in the finding.
- **Unbounded `delete` of an array** — deleting is not free.
- **Loop bound read from storage inside the condition**
  (`for (uint i; i < arr.length; ++i)`) — an `SLOAD` per iteration; cache it.
  Efficiency only, unless the length can change during the loop.
- **Array shifting on removal** (`for` loop to compact after a `delete`) — use
  swap-and-pop instead. O(n) → O(1), and removes a DoS.
- **`i++` in an unchecked-able counter** — `unchecked { ++i; }` is the standard
  idiom; safe because the loop bound already prevents overflow.

### Off-chain-growable sets

A loop over "all users" is almost never correct on-chain. The right shape is
either an accumulator (`accRewardPerShare` — O(1) per user) or a merkle root
computed off-chain with an O(log n) proof. If the code loops over holders to
distribute anything, that is a design-level finding, not a tweak.

---

## 2. Gas griefing & assumptions

- **`transfer` / `send` (2300 gas stipend)** — breaks with smart-contract
  wallets, multisigs, and any receiver with a non-trivial `receive()`. Also
  breaks whenever an EIP changes opcode pricing. Use
  `call{value: x}("")` with `nonReentrant` and CEI.
- **63/64 rule (EIP-150).** A caller can supply just enough gas that the
  sub-call runs out while the outer call still succeeds. Any "the callback must
  have succeeded" assumption is unsound. Check the return value *and* require a
  gas floor (`require(gasleft() > MIN_GAS)`) before the sub-call.
- **Return-data bombs.** `(bool ok, bytes memory data) = target.call(...)` copies
  all returndata into memory — an untrusted callee returns megabytes and the
  caller runs out of gas. Use assembly with a bounded `returndatacopy`
  (`excessivelySafeCall`) when the callee is untrusted.
- **Refund-based designs.** Gas refunds were cut by EIP-3529; any contract that
  relied on `selfdestruct`/`SSTORE` refunds for economics is broken.
- **Keeper/relayer reimbursement** computed from `gasleft()` deltas without a
  cap → a griefing caller inflates the reimbursement. Cap it and use `basefee`.
- **`block.gaslimit` / `gasleft()` in business logic** — chain-dependent and
  changes across upgrades; never use as a security condition.
- **Deployment size.** Contracts above the EIP-170 24,576-byte limit will not
  deploy. If the contract is near the limit, flag it: adding the recommended
  fixes may push it over. Split into libraries or enable the optimizer with a
  documented `runs` value.
- **L2 calldata cost.** On OP-stack/Arbitrum, calldata is the dominant cost.
  Large `bytes` arguments, long merkle proofs, and `string` errors are
  expensive there; custom errors and compact encoding matter more than SLOADs.

---

## 3. Optimization checklist (report as Informational)

Ordered by real impact, biggest first. Only recommend these when they do not
reduce clarity or safety — a bug introduced by a gas tweak is not a saving.

**Storage (the only place with big wins)**
- Cache repeated `SLOAD`s in a `memory`/stack variable. A warm `SLOAD` is 100
  gas, a stack read is 3. Re-reading `totalSupply` five times in one function
  is the most common easy win.
- Pack struct fields and state variables into shared 32-byte slots — but only
  when they are written together, and only with `SafeCast` on every narrowing
  write (see `arithmetic.md`). Bad packing costs gas and adds truncation bugs.
- Write a storage slot once, at the end, instead of incrementally in a loop.
- `immutable` for values set in the constructor and never changed; `constant`
  for compile-time values. Both move the value into bytecode (~2,100 gas saved
  per read vs a cold `SLOAD`).
- Avoid zero→non-zero writes where a non-zero sentinel works (20,000 vs 5,000
  gas) — e.g. the OpenZeppelin `ReentrancyGuard` 1/2 pattern.
- `delete` a slot you are done with only if the refund is actually claimable.

**Calldata & memory**
- `calldata` instead of `memory` for external function array/struct/string
  parameters — avoids a full copy.
- Custom errors (`error InsufficientBalance(uint256 have, uint256 want);`)
  instead of `require` strings — smaller bytecode and cheaper reverts.
- `bytes32` instead of `string` for fixed short identifiers.

**Control flow**
- Short-circuit: put the cheapest and most-likely-failing condition first in
  `&&` / `||` chains.
- `unchecked { ++i; }` in loop counters where the bound proves no overflow.
- `++i` over `i++` (marginal; do not restructure code for it).
- Avoid redundant checks the compiler or a library already performs
  (`SafeERC20` already reverts; do not re-`require` the return).
- Prefer `external` over `public` for functions never called internally.

**Anti-patterns — do NOT recommend these**
- Assembly for arithmetic "to save gas" — it removes the ≥0.8 overflow checks
  and reintroduces exactly the bugs in `arithmetic.md`.
- Removing a `require` because "it can't happen".
- Removing `nonReentrant` from a function with an external call.
- Removing events to save gas — they are the only incident-response signal.
- Unbounded optimizer `runs` without checking the 24KB deploy limit.

---

## 3b. Choosing the fix — three options, ship the cheapest that holds

A recommendation is a design decision made on the client's behalf, so do not
make it by reflex. For every Critical / High / Medium finding, sketch **three**
fixes before writing one down, then pick with the rule below. Cost the loser
options in one line each; ship one.

Sketch them at three different points on the spectrum, cheapest first:

1. **A guard.** One `require`, a reordering, a different rounding direction, a
   constant changed. No new state. Often free.
2. **Restructured math or state.** Same storage layout, different accounting —
   a checkpoint instead of a scan, snapshotting a parameter, `mulDiv` instead of
   `a * b / c`.
3. **A new mechanism.** New storage, a new pattern (pull-payment, merkle claim,
   accumulator, two-step transfer), or a library.

Score each on five columns and put the table in your working notes:

| Option | Gas on the hot path | New storage | Removes the bug or narrows it? | New attack surface | Lines to review |

**The rule, in order:**

1. **Fully removes the bug** — an option that only narrows it is not a fix and
   does not compete. Cheapness never buys a partial fix.
2. **No loop over anything a user can grow.** A fix that iterates is a new
   finding in this file. O(1) alternatives, in the order you should reach for
   them: an accumulator / checkpoint (`accRewardPerShare` style), pull instead
   of push, a mapping instead of an array scan, a merkle root instead of an
   on-chain list, an off-chain index with an on-chain proof.
3. **Cheapest of what is left**, priced with the table below — count the hot
   path (the function users call most), not the deploy cost.
4. **Ties break on fewest storage slots, then fewest lines.**
5. **Keeps the flexibility the contract already has.** A fix that hard-codes a
   value the owner legitimately needs to tune has cost the protocol something;
   say so and pick again.

**Do not over-engineer the fix.** These are rejections, not preferences:

- No new role, module, interface, config struct, or upgrade path for a bug that
  a `require` or a reordering closes.
- No oracle, no timelock, no pausability introduced *by the fix* — each is its
  own centralization finding, and you would be trading a Medium for a High.
- No library dependency for arithmetic the compiler already checks. `mulDiv` and
  `SafeCast` earn their place; a `SafeMath` import in ≥0.8 does not.
- Do not answer a Low with a rewrite. Match the fix's size to the severity.
- If the honest fix is "delete this function", say that. It is usually the
  cheapest option and it is almost never the one a client is offered.

**Prices to compute with** (mainnet, post-Shanghai; L2s invert this — calldata
dominates, storage matters less):

| Operation | Gas |
|---|---|
| `SSTORE` zero → non-zero | 20,000 |
| `SSTORE` non-zero → non-zero | 2,900 |
| `SSTORE` non-zero → zero | 2,900, refund 4,800 |
| `SLOAD` cold / warm | 2,100 / 100 |
| `TSTORE` / `TLOAD` (EIP-1153) | 100 / 100 |
| External call, cold / warm target | 2,600 / 100 |
| `keccak256` | 30 + 6 per word |
| Calldata byte, non-zero / zero | 16 / 4 |
| `require` with a short string | ~24 when it passes |
| Memory expansion | quadratic past ~700 words — the reason "just build an array" is not free |

Worked example — a reentrancy in `withdraw()`:

- **(1) Reorder to checks-effects-interactions** — zero gas, removes the bug
  entirely. **Ships.**
- **(2) `nonReentrant`** — 20,000 + 2,900 with a storage lock, ~200 with a
  transient-storage lock on a chain that has EIP-1153. Correct, but it pays for
  a guard that ordering already provides. One line: *"also correct, costs ~2.9k
  per call and does not remove the ordering bug it hides."*
- **(3) Pull-payment withdrawal queue** — a new mapping, a new function, a new
  griefing surface. One line: *"warranted only if the callee must be untrusted
  and re-entry is expected by design."*

Report the winner as the recommendation, and name the runner-up in one sentence
so the client can see the trade was considered — not three options for them to
choose between. Choosing is the audit's job.

---

## 4. What to put in the report

- A **Gas & Loop analysis** section listing every loop with: location, who
  controls the bound, the maximum count, and the verdict (safe / DoS finding).
- Security-relevant loop and gas issues as normal findings with their real
  severity.
- Optimizations as a single Informational finding with a table
  (location → change → approximate saving), not one finding per tweak.
- If the project has no gas benchmarks, recommend `forge snapshot` /
  `forge test --gas-report` in CI so regressions surface.
- For every Critical/High/Medium recommendation, the §3b winner **and** the
  one-line reason the runner-up lost. A recommendation with no alternative
  considered is a guess.

## Reference incidents

- GovernMental (2016): a payout loop grew past the block gas limit — ~1,100 ETH
  permanently stuck. The canonical unbounded-loop death.
- Multiple airdrop/dividend contracts bricked by looping over holders.
- Istanbul (EIP-1884) repricing broke contracts relying on the 2300 stipend —
  the reason `transfer` is no longer recommended.
- Compound-fork MasterChef clones dying on `massUpdatePools` after too many
  pools were added.
