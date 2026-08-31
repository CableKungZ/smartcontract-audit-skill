# Audit Methodology

## Severity rubric

Five levels. Severity is set by **impact first**, then adjusted down by
**likelihood** and **privilege required**. Aligned with the Immunefi
Vulnerability Severity Classification System and Code4rena/Sherlock practice.

| Severity | Impact | Typical examples |
|---|---|---|
| **Critical** | Direct, permanent loss or freeze of user/protocol funds; or anyone can mint/drain. No special privilege needed, or privilege is trivially obtainable. | Reentrancy drains the pool; reward-accounting bug lets anyone withdraw others' principal; unprotected `initialize()` → attacker owns proxy; integer over/underflow inflates balance; `delegatecall` to attacker input. |
| **High** | Theft of *yield only* (not principal); temporary freeze of funds with a recovery path; loss that requires an attacker-favourable but plausible condition. | Stake/unstake loop farms rounding dust into real money; claim front-run by `notifyRewardAmount`; missing slippage on an internal swap; a trusted role *can* rug but is multisig; funds locked until an admin unpauses. |
| **Medium** | Griefing / DoS where attacker cost ≈ damage; value leak bounded and slow; issue needs an unusual precondition (oracle rogue, specific ordering). | Unbounded loop over stakers makes `updatePool` revert past N users; block-stuffing delays withdrawals; precision loss that leaks dust but not exploitable at scale; first-depositor share inflation when a deployer bootstrap step is documented but skippable. |
| **Low** | Protocol fails to deliver a promised return but loses nothing; edge case with negligible impact; defence-in-depth gap. | Rewards under-accrue by 1 wei/block; missing event; `block.number`-based timing drifts on L2 but only affects UI estimates. |
| **Informational** | No security impact. Style, gas, standards compliance, documentation. | Missing `SPDX`; `public` that could be `external`; unused variable; no NatSpec on external funcs. |

Notes:
- **Trusted-role rug** = High if the role is a multisig/timelock, Critical if it's
  a single EOA and undocumented, Low/Info if fully documented and expected. Always
  list centralization risks explicitly with the trust assumption named.
- **Likelihood downgrade**: only drop a level when a *concrete* precondition gates
  the exploit (privileged caller, external oracle failure, attacker must be first
  depositor with an empty pool). "Unlikely in practice" is not enough.
- The user asked for Critical/High/Low — Medium and Informational still get
  reported; they map onto "High-ish" and "Low-ish" if a 3-bucket view is wanted.

## Process

1. Fix scope: exact files, exact commit hash (or the verified on-chain address).
   Everything else is out of scope and noted as a trust assumption (libraries,
   oracles, tokens, admin keys, the compiler).
2. Build the mental model: roles & permissions table, value-flow diagram (deposit
   → accounting → withdraw → rewards), external-call inventory, and — for
   anything that distributes value — the money map in `economics.md` §1.
3. Line-by-line read of in-scope code. Then walk this file + the type-specific
   catalogs as a checklist.
4. For every candidate: write the exploit path as concrete steps with values. If
   you can't, it's probably Info or not a finding.
5. **Verify by trying to refute** (below), then de-duplicate.
6. Classify, then write description / impact / recommendation.
7. Generate the HTML report, ending in a tiered remediation roadmap
   (`economics.md` §5).

## Audit dimensions

Read across dimensions, not just across files, and **say in the report which
dimensions you covered** — it tells the reader what was not covered:

1. **Access control** — who can call what, and what a compromised key costs.
2. **Core protocol logic** — the state machine: deposit/withdraw, settlement,
   graduation, liquidation, whatever this contract's critical transition is.
3. **Economics & value extraction** — where the money ends up (`economics.md`).
4. **Low-level Solidity safety** — arithmetic, casts, reentrancy, external
   calls, gas (`arithmetic.md`, `gas.md`).
5. **Domain mathematics** — curve math, share math, tick math, interest math.

## Verification: refute before you report

A candidate finding is not a finding until you have **tried to kill it**.
Re-check each one specifically against the things that would make it false:

- checked arithmetic in Solidity ≥0.8 (does it revert rather than wrap?),
- a modifier or `require` further up the call path that you missed,
- the token actually in use (a clean OpenZeppelin ERC-20 has no transfer hooks;
  a `.transfer()` payout to an EOA is fine, to a contract it is not),
- whether the caller you assumed can actually reach that state,
- whether the "attacker" is in fact a trusted role, which changes the severity
  rather than removing the finding.

Then **de-duplicate**: several symptoms of one root cause are **one** finding
with several `location`s, not several findings. Report both counts in the
methodology section — "N verified, M distinct after de-duplication" tells the
reader that padding was removed, not added.

A finding that survives a deliberate attempt to refute it is worth reporting.
One that doesn't gets dropped, or filed as Informational with the mitigating
factor named.

### The self-review pass (run it on every finding before writing the report)

Answer all five, one line each. This is the last gate before the report ships,
and it is where a gated exploit gets downgraded — by you, not by the client's
dev team after delivery.

1. **What precondition makes this *not* exploitable?** Name it, or state
   explicitly that there is none.
2. **Does something else in this repo already block it?** Grep every caller of
   the function, not just the one you found it in — the same reflex as fixing a
   bug at its root. A guard one frame up kills the finding.
3. **Does the PoC actually fail on the unfixed code, and pass on the fix?**
   If there is no PoC, does the waiver survive question 1?
4. **Would the recommended fix break another caller?** A recommendation that
   breaks a working path is a finding you are introducing.
5. **Is the severity still right after 1–4?** Re-derive it from the rubric,
   don't defend the number you wrote first.

Record the outcome in the finding's `review_note` — the surviving precondition,
or what you checked. Drop a finding that fails 1 or 2 **explicitly**: either
delete it, or keep it as Informational with the mitigating factor named. Never
delete silently — a finding that is dropped and then rediscovered by someone
else is worse than one filed as Informational.

### A finding you cannot reproduce is an opinion

Every **Critical** and **High** ships with a runnable proof: a Foundry test that
fails against the unfixed code and passes against the fix, with the real command
and its real output pasted into the finding's `poc` field. `--validate` refuses
to generate the report otherwise.

The only accepted waivers (`poc_waiver`, and each still needs question 1
answered): a centralization finding that requires a privileged key, a repo with
no test harness at all (say so, and recommend one), or a precondition that is
genuinely off-chain. "It was obvious from reading" is not a waiver.

## Compiler version

The compiler is a dependency like any other, and it has a published bug list.
`scripts/scan.py` prints every pragma against it (`solc_bugs.py`, vendored
offline; refresh with `--update`).

- **A floating pragma is a finding.** `^0.8.13` compiles with anything up to
  0.8.x-latest, so the bytecode you read is not provably the bytecode that
  shipped. **Low** on its own; **Medium** when the range spans a version with a
  medium/high bug the code can actually trigger. Recommend pinning one exact
  version, and record the version the deployed bytecode was built with.
- **Match the bug to the code before filing it.** `InlineAssemblyMemorySideEffects`
  only matters if there is inline assembly; `AbiReencodingHeadOverflow...` only
  if a tuple with a static calldata array gets re-encoded. A bug in range that
  the code cannot reach is Informational, and say why it cannot reach it.
- **Below 0.8.0 there are no overflow checks.** Every arithmetic finding gets
  more severe, and the absence of SafeMath on any operation is itself the bug.
- The audit's method section states the exact `solc` version used, the optimizer
  setting and runs, and whether the audited source matches the verified source
  on the explorer.

## Quantify economic claims

Never write "some value is stranded" or "the operator takes a large share".
Compute it from the actual on-chain parameters, put the parameters in an
appendix table, state the method (simulation, closed form, on-chain read), and
let the team reproduce the number. See `economics.md` §3.

## General EVM vulnerability catalog

### Access control
- Missing modifier on state-changing / fund-moving functions (`setRewardRate`,
  `notifyRewardAmount`, `pause`, `sweep`, `recoverERC20`, `setPool`, `upgrade`).
- `recoverERC20` / `sweep` able to pull the staking or reward token → drain.
- `initialize()` not protected (`initializer` modifier) or callable by anyone →
  proxy takeover. Check the implementation contract is also initialized/locked
  (`_disableInitializers()` in constructor).
- Constructor logic in an upgradeable contract (runs on implementation, not proxy).
- `tx.origin` for auth — breaks with account abstraction / phishing.
- Role admin can grant itself other roles; no timelock on privileged setters.
- Two-step ownership transfer missing (`Ownable2Step`) — typo bricks ownership.

### Reentrancy
- State updated *after* external call (violates checks-effects-interactions).
- ERC777 / ERC677 / native `call` transfer hands control to attacker on
  `stake`/`withdraw`/`claim`/`emergencyWithdraw`.
- Cross-function reentrancy: `nonReentrant` on `withdraw` but not `claim`, sharing
  the same accounting.
- Read-only reentrancy: a view used by another protocol returns stale mid-tx state.
- ERC721 `safeTransfer` / ERC1155 callbacks in NFT-staking.

### Arithmetic & precision
- Division before multiplication → truncation (slippage, reward shares).
- Reward-per-share scaling factor too small (`1e12`) for 18-decimal tokens with
  large `totalStaked` → accrual rounds to zero.
- Rounding direction favours the user on both entry and exit → stake/unstake loop
  extracts value (see `staking.md`).
- `unchecked` blocks that can actually underflow (Solidity <0.8 everywhere).
- Fee-on-transfer / rebasing / deflationary token breaks `amount`-based
  accounting — measure `balanceBefore/After`.
- Casting `uint256` → `uint128`/`uint64` truncation in packed structs.

### Denial of service
- Unbounded loop over a user-growable array (stakers, positions, pools, reward
  tokens) in a function that must succeed (withdraw, updatePool, distribute).
- Push payments in a loop — one reverting recipient blocks everyone. Use pull.
- External call in a loop; gas griefing via a contract recipient that consumes
  all forwarded gas.
- Storage-unbounded mapping iteration.
- `require` on an external call's success where the callee can always revert.

### Upgradeability (proxy)
- Storage layout collision between versions; missing `__gap`.
- Missing `_disableInitializers()` in implementation constructor.
- `selfdestruct` / `delegatecall` in implementation (UUPS: unprotected `_authorizeUpgrade`).
- Reinitialization via a new `reinitializer(n)` left unguarded.
- Immutable variables in an upgradeable contract set in constructor (per-impl, not per-proxy).

### Oracle / pricing
- Spot price from an AMM pool (`getReserves`, `balanceOf`) → flash-loan manipulable.
- Chainlink: no staleness check (`updatedAt`), no `answeredInRound`, no min/max
  bound, ignores `decimals()`, assumes 8 decimals.
- No L2 sequencer-uptime feed check before trusting a Chainlink price on
  Arbitrum/Optimism/Base/Metis.
- TWAP window too short; single-block manipulation.

### External interaction / token handling
- Ignoring ERC20 return value (USDT, BNB reverting-on-false); use `SafeERC20`.
- `approve` race (not resetting to 0); use `safeIncreaseAllowance`.
- Assuming 18 decimals; not reading `decimals()`.
- Trusting `transfer`/`send` (2300 gas) — breaks with smart-contract wallets and
  gas-cost changes.
- Blocklist tokens (USDC) can freeze a withdrawal path.

### Misc
- `block.timestamp` for randomness / tight deadlines — miner tolerance ~±12s.
- `block.timestamp` vs `block.number` for reward accrual — pick timestamp;
  block time is not constant and differs per chain / L2.
- Signature: no `nonce`, no `deadline`, no `chainId` in the signed digest →
  replay; missing `ecrecover` zero-address check; non-EIP-712; malleability if
  checking `s`/`v` manually.
- Front-running / MEV: unprotected `deposit` before a reward top-up; sandwichable
  internal swaps; `claim` sandwiched by a rate change.
- Uninitialized / default-value storage assumed safe.
- `assert` used for input validation (consumes all gas pre-0.8.0; signals
  invariant break post-0.8).

## Chain-specific notes

| Chain | Watch for |
|---|---|
| **Ethereum L1** | High gas → unbounded-loop DoS is more exploitable; MEV/sandwich on any price-touching path; reorgs shallow but non-zero. |
| **Arbitrum** | `block.number` returns an *L1-ish* block number that updates roughly per L1 block — do **not** use it for fine-grained timing or per-block reward accrual; use `block.timestamp` (Arbitrum updates it per block, bounded to L1). `arbBlockNumber()` for real L2 height. Gas model differs (calldata dominant). No mempool → less classic front-running but sequencer can reorder. |
| **Optimism / Base** | `block.number` is the L2 block (2s). Chainlink feeds require the **sequencer uptime feed** + grace period check, else stale-price accepted during downtime. `block.timestamp` set by sequencer. |
| **Polygon PoS** | Deeper reorgs historically — require more confirmations for bridge/settlement logic; cheap gas → griefing loops affordable. |
| **BNB Chain** | ~3s blocks, very cheap gas → loop/griefing and spam economically viable; validator set small/centralized → `block.timestamp` and censorship assumptions weaker; many non-standard tokens. |
| **Avalanche C-Chain** | ~2s, cheap gas; otherwise EVM-standard. |
| **KUB Chain (Bitkub)** | KAP standards add privileged `adminTransfer`/`adminApprove`/`internalTransfer` by design; small validator set; cheap gas; thin liquidity makes AMM TWAPs cheap to manipulate; limited Chainlink coverage. **See `kub.md`.** |
| **General L2** | Never assume 12s/block. Reward rates expressed "per block" drift badly across chains — prefer "per second". Sequencer is a single point of failure for liveness; design withdrawals to not depend on fresh oracle data. |
