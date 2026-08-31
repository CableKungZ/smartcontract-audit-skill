# Other Contract Types

Shorter catalogs for types that don't warrant their own file. Always load
`methodology.md`, `arithmetic.md` and `gas.md` alongside these.

---

## Launchpad / IDO / Presale

- **Refund path missing or broken** when the soft cap is not met → contributor
  funds locked forever. This is the single most common launchpad finding.
- Hard cap enforced per-transaction but not cumulatively → the cap is bypassed
  by splitting the buy.
- The last contribution that crosses the hard cap: reverted (griefable — an
  attacker fills the cap to block others) or partially accepted with the excess
  refunded? Only the second is correct.
- Whitelist by merkle proof with no `nonce`/round in the leaf → a proof from
  round 1 is replayed in round 2. Root updatable by the owner with no timelock.
- Price/rate settable by the owner **during** the sale.
- `claim()` before `finalize()`; claiming twice because `claimed[user]` is set
  after the transfer (reentrancy) rather than before.
- Vesting: cliff/duration arithmetic underflowing before the cliff
  (`block.timestamp - start` when `start` is in the future); `released` not
  capped at `total` → over-release; a linear formula that rounds to 0 for small
  allocations so a small holder can never claim anything.
- Owner can withdraw raised funds before the sale succeeds, or withdraw the
  sale token that buyers have not yet claimed.
- Native-currency sale using `transfer` (2300 gas) for refunds → contract
  wallets cannot be refunded. Use `call` + pull.
- Contribution accounting in a loop over contributors for the refund → see the
  unbounded-loop DoS in `gas.md`. Refunds must be pull.

## Governance / DAO

- **Voting power from `balanceOf` at vote time → flash-loanable.** Must be a
  checkpointed snapshot at a past block (`ERC20Votes`, `getPastVotes`).
- Proposal threshold, quorum, and voting delay/period settable by a passing
  proposal with no timelock between execution and effect.
- Timelock's admin is the governor, but the governor can also be changed
  without the timelock → the delay is bypassable.
- Proposal payload hashed without `value`/`target`/`calldata` → a different
  payload executes than the one voted on.
- Vote delegation not re-checkpointed on transfer → double-counted voting power.
- No cancel/guardian path for a malicious passing proposal; or `cancel` callable
  by anyone.
- Quorum computed against a `totalSupply` that the proposal itself can mint.
- Execution loop over an unbounded action array (`gas.md`).

## Airdrop / Merkle distributor

- Root updatable by the owner after claims start → previous claimants'
  entitlement changed, or the owner grants themselves an allocation.
- `claimed` bitmap/mapping set **after** the token transfer → reentrancy allows
  multiple claims (use CEI, and prefer a bitmap for gas — `gas.md`).
- Leaf without the index/amount/address all bound together, or a leaf whose
  encoding collides with an internal node (second-preimage): always hash leaves
  with a distinct prefix or double-hash (`keccak256(bytes.concat(keccak256(...)))`),
  as OZ's `MerkleProof` guidance describes.
- No expiry/sweep, or a sweep that can pull unclaimed funds immediately.
- Proof arrays unbounded in length → gas griefing; and on L2s the proof is
  calldata, which dominates cost.

## NFT marketplace / auction

- Signed order without `nonce` + `deadline` + `chainId` + contract address →
  replay; no on-chain cancellation path.
- Royalty and fee subtracted with rounding that lets the seller receive more
  than the sale price, or that underflows for a 1-wei sale.
- `safeTransferFrom` to a contract buyer reentering `buy()` before the listing
  is deleted → the same NFT is sold twice.
- Auction: bid refunds pushed in a loop or with `transfer` → a contract bidder
  that reverts on receive blocks all later bids (a classic, and it lets the
  attacker win at their own price).
- Auction extension (anti-sniping) missing, or extendable forever by 1-wei bids.
- Price computed from a Dutch-auction curve using `block.timestamp` with no
  floor → underflow at the end of the window.
- ERC-2981 royalties treated as enforceable — they are not; say so.

## Bridges / cross-chain messaging

- **→ `defi.md` bridge section** for the core checks. Additionally:
- Per-token and global mint rate limits absent — a single verification bug
  becomes unlimited mint. Rate limits are the only mitigation that survives a
  verification failure.
- Validator/guardian set update accepted from a message signed by the *old*
  set with no threshold increase or delay.
- Message replay across chains: the digest must include source **and**
  destination chain ids, the source contract, and a nonce.
- Reorg handling: a deposit finalized after N confirmations where N is too low
  for the source chain (Polygon historically needed far more).
- Wrapped-token contract whose `mint` is callable by a bridge address that can
  be changed without a timelock.

## Multi-sig-guarded protocol admin (any type)

Every protocol has this, and it belongs in every report:

- Enumerate every privileged function, the role that can call it, the address
  holding that role, and whether it is an EOA, a multisig (what threshold?), or
  a timelock (what delay?).
- For each: what is the maximum loss if that key is compromised today?
- Is there a function that can change the role holder without a delay?
- Can the admin brick the contract (see the liveness section of
  `arithmetic.md`)? Renounce ownership? Set a fee above 100%?

Report this as an explicit **Centralization** finding with the severity from
`methodology.md` — documented + timelocked multisig is Low/Medium; a single
undocumented EOA that can move user funds is High or Critical.
