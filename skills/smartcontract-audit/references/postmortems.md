# Incident-Derived Checks (2024 – 2026)

**Load this file on every audit.** Everything here is a check that a *real*
protocol failed, with the incident that proves it is reachable. Each entry is
written as something to look for in the code in front of you, not as history.

Walk it after the type catalogs. When one applies, cite the incident in the
finding — a reviewer argues with an opinion, not with $128M.

> Two framing rules that come out of every post-mortem below:
> - **Capital is not a precondition.** Flash loans make "the attacker would need
>   $200M" a non-argument. If the exploit closes in one transaction, price it as
>   if the attacker is infinitely funded.
> - **A 1-wei error is a finding.** Every large 2025–2026 arithmetic loss was a
>   sub-wei bias multiplied by an attacker-chosen repeat count. Ask "what happens
>   if this is called 10,000 times in one transaction?", not "is this material?".

---

## 1. Rounding *inconsistency* between paired conversions

**Balancer V2, Nov 2025, ~$128M** (Composable Stable Pools, plus forks on
several chains). Scaling up used one rounding direction, scaling back down used
another. Each `EXACT_OUT` swap in a crafted `batchSwap` moved the invariant a
fraction in the attacker's favour; repeated inside one transaction it suppressed
the BPT price enough to drain the pools.

Check:

- Find every **pair** of conversion helpers — `upscale`/`downscale`,
  `toShares`/`toAssets`, `wrap`/`unwrap`, `normalize`/`denormalize`. Both
  directions must round **toward the protocol**, and the pair must be consistent.
  A rounding direction that is correct in isolation can be wrong as a pair.
- Any invariant (`D`, `k`, `totalAssets`) recomputed from scaled balances: the
  scaling must not let the recomputed invariant come out *lower* than the true
  one on a user-controlled path.
- `EXACT_OUT` / "give me exactly N out" paths get audited less than `EXACT_IN`.
  Read them first; the residual is where the bias hides.
- Multi-hop / batch entry points let a per-hop error compound with no external
  call in between. Treat the batch function as its own attack surface, not as a
  loop over an already-audited one.
- **Write the property test:** deposit-then-withdraw, or swap-then-swap-back,
  must never return more than it took, for any sequence and any repeat count.

## 2. The overflow check itself is wrong

**Cetus (Sui), May 2025, ~$223M.** `checked_shlw` compared against
`0xFFFFFFFFFFFFFFFF << 192` instead of `1 << 192`, so values that *do* overflow
passed the guard. The attacker picked a razor-thin tick range so a single
liquidity number slipped through and wrapped.

Check:

- Do not tick off "has an overflow guard". Read the **constant and the
  comparison operator** in every hand-rolled `checked_*`, `mulDiv`, `sqrt`,
  `shl`/`shr`, `toUintN` or assembly math helper, and verify the boundary by
  hand: what is the largest input that passes, and does it overflow?
- Every custom math library gets a fuzz test at the boundary. Recommend one in
  the report if the repo has none — this class is invisible to review at normal
  magnitudes and trivial for a fuzzer.
- Extreme-but-legal parameters (a 1-tick range, `liquidity = 1`, a 200-tick
  width, `amount = type(uintN).max`) are the inputs that reach these branches.
  Test at the edges of the *allowed* range, not at realistic values.
- `unchecked` blocks and inline assembly opt out of 0.8's protection. Every one
  needs a written justification of why it cannot overflow.

## 3. Repeat-call amplification in withdraw / rebalance accounting

**Bunni V2, Sep 2025, ~$8.4M.** A rounding-direction bug in the withdraw path's
idle-balance accounting: one withdrawal looked harmless, but a crafted sequence
of sized withdrawals walked the pool's total liquidity down and the attacker out.

Check:

- Any function that recomputes a global (total liquidity, idle balance, a
  distribution curve) from the *post*-operation state: check whether calling it
  in small increments produces a different total than one large call. That
  difference is the exploit.
- Custom hooks over a mature core (Uniswap V4 hooks, ERC-4626 wrappers, vault
  strategies): the core's invariants no longer hold — the hook's own accounting
  is unaudited surface. Do not inherit confidence from the underlying protocol.
- Property to state in the report: *splitting an operation into N smaller ones
  must never yield more than doing it once.*

## 4. Fresh / empty market + donation → exchange-rate manipulation

**Resupply, Jun 2025, ~$9.6M** — a market deployed two hours earlier, donated
into, one wei of shares priced at the whole vault. **sDOLA / Llamalend, Mar
2026, ~$240K** — same shape, flash-loan funded. This is the ERC-4626 inflation
attack, and it keeps landing because the vulnerable window is *deployment*, not
steady state.

Check:

- `totalAssets()` derived from `asset.balanceOf(address(this))` → donatable.
  Internal accounting, or a virtual-offset design (OZ `ERC4626._decimalsOffset`),
  is the fix; cite it.
- The `totalSupply == 0` branch of every share-price function. Who can be the
  first depositor, and what does the second depositor receive?
- **Permissionless or fast market creation** is the risk multiplier: a market
  listed with negligible liquidity is exploitable the moment it exists. Require
  seeded liquidity (dead shares burned at creation), a minimum-deposit floor,
  and a delay or guardian before a new market can be borrowed against.
- Any oracle that is "the exchange rate of a vault we deployed" — a share price
  *is* a price feed, and it inherits every manipulation property of one.
- Rounding at 1 wei: `shares == 0` on a real deposit, or `assets == 0` on a real
  redeem, must revert rather than silently succeed.

## 5. Cross-chain trust configuration is part of the contract

**Kelp DAO, Apr 2026, ~$292M** — the largest DeFi loss of the year. A `1/1` DVN
configuration on LayerZero meant one verifier stood between a forged message and
a mint. The attackers took over two RPC nodes that verifier read from and DDoSed
the honest ones to force failover, then minted 116,500 unbacked rsETH.

Check — for any contract that mints, releases or unlocks on an inbound message:

- **Read the messaging configuration on-chain and put it in the report.** The
  DVN / oracle+relayer / validator set, the threshold, and whether the app uses
  the endpoint's *default* config (defaults change under you). A 1-of-1 verifier
  is a Critical finding on its own — name it as a single point of failure
  regardless of who operates it.
- **Who can change that configuration, and with what delay?** A config setter
  with no timelock is equivalent to a mint function.
- **Rate limits are the only control that survives a verification failure.**
  Per-token and global caps on inbound mint/release, per window, are mandatory.
  Their absence is High even when verification looks sound.
- The message digest must bind source **and** destination chain id, the source
  contract, the receiver, and a nonce; replay onto another chain the protocol
  also deploys to is the default failure.
- A backing invariant checked on-chain: supply minted from messages must never
  exceed what is locked. If it can only be checked off-chain, say so.
- Verifiers reading from RPC infrastructure are a liveness *and* integrity
  dependency. It sits outside the contract, so put it in `trust_assumptions`
  explicitly rather than leaving it unstated.

## 6. Uninitialized / freshly deployed proxies

**Kinto, Jul 2025, ~$1.55M.** Attackers watched for newly deployed ERC-1967
proxies that had not been initialized yet and initialized them against their own
implementation. Parity (2017) is the same bug, eight years earlier.

Check:

- Deployment and `initialize()` must happen in **one transaction** (factory,
  constructor args, or `CREATE2` + atomic init). A deploy script that
  initializes in a second transaction is a live finding, not a process nit —
  say so, with the window named.
- `_disableInitializers()` in the implementation's constructor;
  `reinitializer(n)` guarded; no unguarded `initialize` reachable twice through
  the proxy.
- Storage layout across an upgrade: appended variables only, `__gap` preserved,
  and no layout mismatch between a proxy and any `delegatecall` adapter it uses
  — a mismatch turns an ordinary write into an owner overwrite.
- Modifiers on **newly added** functions in an upgrade. The access-control
  regression happens in the diff, not in the original.

## 7. EIP-7702 breaks "msg.sender is an EOA"

**QNT pool drain, 2026.** An admin EOA delegated its code under EIP-7702; a call
routed through it passed the pool's admin check and moved tokens. Separately,
2026 research found a majority of sampled 7702 authorizations pointing at
malicious contracts, with millions drained by automated delegation phishing.

Check:

- Any use of `tx.origin == msg.sender`, `msg.sender.code.length == 0`,
  `extcodesize`, or `isContract()` as a security control: it no longer
  distinguishes anything. Delete it and gate on an explicit allowlist instead.
- Privileged roles held by EOAs must be treated as *potentially delegated
  contracts* in the centralization section — one signature can give an admin
  address arbitrary code without changing the address.
- A delegated account can re-enter. Reentrancy guards belong on paths previously
  assumed safe because "only EOAs call this".
- Wallet/account contracts: initialization must be bound to the account, and
  storage must not be assumed empty (`wallet.md`).

## 8. Emergency controls that expire, and forks that inherit the bug

Also from Balancer: the pools that were drained were the ones whose **pause
window had expired**; newer pools were paused in time and survived. The exploit
then propagated the same day to forks on other chains.

Check:

- Every pause / guardian / emergency function: does it have an expiry, a
  deadline, or a window? Print the date it stops working and put it in the
  report. A pause that expires is a pause that is absent on the day it matters.
- Who can pause, and can they act within minutes? A pause behind a 48h timelock
  is not an incident control.
- Unpause must exist and must not be renounceable (`arithmetic.md`).
- If the code is a fork, check the upstream's **security advisories and incident
  history**, not only its current source (`examples.md` for the upstreams).
  Being a fork of a project that was exploited is a finding until the patch is
  confirmed present in this copy.

## 9. Library version — check the exact one in use

A dependency version is a vulnerability class of its own: OpenZeppelin 4.9.4
executed every `Multicall` subcall twice, and 4.1.0–4.3.1 left every UUPS
implementation `selfdestruct`-able. See the advisory table in `examples.md` and
resolve the **actual pinned version** (`package-lock.json`, `foundry.lock`,
the vendored `lib/` commit) before trusting any inherited contract.

## 10. What audits do not cover — say it out loud

Across H1 2026, compromised keys and infrastructure caused a larger share of
losses than contract bugs (Drift, ~$295M, was social engineering; Bybit, $1.4B
in 2025, was a compromised signing flow). None of that is a contract finding —
but the contract decides how much a compromised key is worth.

For every audit, state in the report:

- The maximum loss if each privileged key is compromised **today** (this is why
  the centralization pass matters).
- Whether mint / withdrawal / bridge-release paths have **rate limits**. If a
  single key or a single verifier can move everything in one transaction, that
  is the finding, independent of how well the key is guarded.
- That key management, signing infrastructure, RPC endpoints, the frontend and
  CI/CD are **out of scope** — in `trust_assumptions`, in those words.

---

## Sources

Post-mortems worth reading in full: BlockSec, Halborn, Cyfrin, Dedaub,
OpenZeppelin and Certora publish per-incident analyses; `hacked.slowmist.io`
and `rekt.news` index the rest. When citing an incident in a finding, link the
technical post-mortem, not a news article.
