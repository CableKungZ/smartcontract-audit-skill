# Custody: Deposit / Withdraw, Escrow, and Wrapped Receipts

Covers every contract whose job is to **hold value that belongs to someone
else** and give it back:

- plain deposit/withdraw vaults and balance ledgers
- escrow — funds held against a condition, a milestone, or a counterparty
- lock-and-receipt — lock X for a period, receive a transferable claim
- wrapped tokens — lock X, mint Y 1:1 (ETH→WETH, KUB→KKUB, bridge mints)
- payment splitters, treasuries and fee sinks holding user-owed balances

They share two invariants. Everything in this file is a way one of them breaks.

> **1. Solvency** — the contract always holds at least what it owes.
> **2. Custody** — only the owner of a balance can move that balance out.

Load alongside `arithmetic.md` (the liveness rules — a deposit you cannot
withdraw is as bad as one that was stolen) and, for anything on KUB, `kub.md`.

---

## 1. The custody rule: the operator must never be able to take user funds

State this as a hard requirement, and test it as one. **In no case** may an
owner, admin, operator, upgrader, guardian, keeper, or any role reachable by a
single party be able to move a user's balance to an address the user did not
choose.

This is not a preference to weigh against convenience. A contract that holds
customer funds and also lets the operator withdraw them is not an escrow, a
vault, or a wrapper — it is a deposit account at an unlicensed custodian, and
the report should say so plainly in the executive summary rather than filing it
as one finding among many.

### How to prove it, mechanically

1. **Enumerate every path that moves value out.** Grep every `transfer`,
   `safeTransfer`, `transferFrom`, `call{value:`, `send`, `_burn` paired with a
   payout, and every `delegatecall`. `scripts/scan.py` lists these.
2. **For each one, identify the destination**: is it `msg.sender`, an address
   recorded at deposit time, or a parameter?
3. **A destination that is a parameter is the finding.** `withdrawTo(address to,
   uint256 amount)` behind `onlyOwner` is an unconditional drain, whatever the
   comment above it says.
4. **Then check the amount**: even when the destination is fixed, an amount
   that is not bounded by *that address's* recorded balance is the same bug.
5. **Then check the accounting**: an admin function that *edits* a balance
   (`setBalance`, `adjust`, `credit`) is equivalent to a withdrawal, one step
   removed.

Write the conclusion into the report as a sentence a reader can rely on, e.g.
*"value leaves only through `withdraw()` and `claim()`, both of which pay
`msg.sender` an amount bounded by `balanceOf[msg.sender]`"*. "No issues found"
does not give the reader that.

### The patterns, and how to rate them

| Pattern | Severity |
|---|---|
| `onlyOwner` function sending user funds to an arbitrary address | **Critical** |
| `sweep` / `recoverERC20` / `rescueTokens` that does not exclude the deposit asset | **Critical** — this is the most common form, and "excluding" it while a second path still reaches it does not count |
| Admin can write user balances directly | **Critical** |
| Upgradeable custody contract — the proxy admin can add a drain tomorrow | **Critical** if the admin is an EOA; **High** behind a timelocked multisig, and it must be in the executive summary |
| `delegatecall` to an admin-supplied target | **Critical** |
| Emergency withdrawal that pays the admin "for redistribution" | **Critical** — off-chain promises are not a mitigation |
| Fee taken from principal rather than from yield | **High** |
| Admin can pause `withdraw` | **High** — freeze, not theft, but see `arithmetic.md` |
| Admin sets a fee with no upper bound, applied on withdrawal | **High** — a 100% withdrawal fee is a drain with extra steps |
| Admin picks the destination of *yield only*, principal untouchable | **Medium/Low**, disclose it |

### What a correct sweep looks like

Recovering genuinely stray tokens is legitimate; the fix is to bound it to the
surplus rather than to trust the caller:

```solidity
// Only the excess above what users are owed can ever leave.
function recover(IERC20 token, address to) external onlyOwner {
    uint256 surplus = token.balanceOf(address(this));
    if (address(token) == address(depositToken)) {
        surplus -= totalDeposits;          // reverts if it would dip into backing
    }
    token.safeTransfer(to, surplus);
}
```

OpenZeppelin's `ERC20Wrapper._recover` is the reference for this shape.

---

## 2. Solvency

State the invariant explicitly in the report, and say where the code enforces
it — if nowhere, that is a finding by itself:

```
depositToken.balanceOf(address(this)) >= totalDeposits          // ledger vault
address(this).balance                 >= totalSupply()          // native wrapper
sum(balanceOf[user]) == totalDeposits                           // the ledger agrees with itself
```

Ways the two sides drift apart:

- **Fee-on-transfer or deflationary deposit asset.** Crediting the requested
  `amount` while receiving less over-credits every depositor, and the last one
  out finds the contract short. Measure the real delta —
  `before = balanceOf(this); safeTransferFrom(...); credited = balanceOf(this) - before;`
  — or reject such tokens explicitly.
- **Rebasing deposit asset.** A fixed ledger over a balance that moves on its
  own cannot stay solvent. Either the design is share-based (§6) or it is broken.
- **A deposit or withdrawal fee taken out of principal**, which makes
  `totalDeposits > held` from the first transaction. A fee must come out of the
  withdrawer's own payout, never out of the pool backing everyone else.
- **Rounding that favours the user on both sides.** See the shares rules in
  `liquidity.md` — withdraw rounds down, deposit credits round down.
- **Decimals mismatch** between the credited unit and the held token. See
  `arithmetic.md`.
- **`totalDeposits` decremented on a path that does not pay out**, or not
  decremented on one that does. Once it underflows, every withdrawal reverts
  forever — the classic way a vault dies.
- **Donations** should leave a harmless surplus (`held > owed`). Check nothing
  lets a caller claim the surplus in a way that can reach into the backing, and
  that no accounting reads `balanceOf(this)` where it should read `totalDeposits`.

Recommend an `assert` on the invariant at the end of deposit and withdraw, plus
a Foundry invariant test — for this contract class it is the single highest-value
test the team can add.

---

## 3. Deposit

- **Credit exactly what arrived**, measured (above), not what was requested.
- **Zero-amount deposits** that still push an entry onto an array → unbounded
  growth, see `gas.md`.
- **Deposit on behalf of another address** (`depositFor(user)`) is fine, but the
  credit must go to `user` and the pull must come from `msg.sender` — swapping
  those lets anyone spend someone else's approval.
- **Native and ERC-20 paths in one function**: a `payable` deposit that also
  takes an `amount` parameter must reject the case where both are set, or one is
  credited and the other silently kept.
- **Reentrancy** via the deposit asset's transfer hook (ERC-777/ERC-677) or a
  native `receive` — apply checks-effects-interactions and `nonReentrant`.
- **A deposit cap** must be checked *after* computing the received amount.
- **Accounting written before the transfer succeeds**, with an unchecked return
  value on a non-standard token — use `SafeERC20`.

## 3b. Every value-moving line, mechanically

Deposit and transfer paths are the only lines that actually move value, so a bug
here is Critical by default — theft or insolvency, not inconvenience. Prose
checks get nodded at; this one is a table. **One row per** `transfer` /
`transferFrom` / `safeTransfer*` / `call{value:}` / `_transfer` / `_update` /
`_mint` / `_burn` in scope. No exceptions, including the ones that look
obviously fine.

| Line | Asset | `from` | `to` | Who authorized `from`? | Requested | Actually moved | Credited |
|---|---|---|---|---|---|---|---|
| Vault.sol:71 | `depositToken` | `msg.sender` | `address(this)` | the caller | `amt` | `amt - fee` | **`amt`** ← mismatch |

Then answer these five against the filled table. Each one is a Critical that has
shipped in real contracts, and each is invisible unless you read the line's
arguments rather than its name.

1. **Is any `from` caller-supplied?**
   `token.transferFrom(from, address(this), amt)` where `from` comes from
   calldata spends **any** approval this contract holds. One transaction drains
   every user who ever approved it. The only acceptable `from` is `msg.sender`,
   or an address whose consent is proven in the same transaction — a signature,
   an EIP-2612 `permit`, or an escrow record written by that address earlier.
   "Only the operator calls it with the right value" is not a control.
2. **Is `to` caller-supplied on a paying path?** Paying to an arbitrary address
   is fine *only* when the debit is `msg.sender`'s own balance. A function that
   debits one address and credits another, both from calldata, is the same bug
   as (1) wearing different clothes.
3. **Does credited equal moved?** The row's last two columns must match. If they
   cannot (fee-on-transfer, rebasing, a token with a transfer hook), measure the
   delta or reject the asset — §2 has the mechanics and the solvency invariant
   this breaks.
4. **Can `from == to`?** The self-transfer that mints:

   ```solidity
   uint256 f = bal[from];
   uint256 t = bal[to];          // cached BEFORE the debit
   bal[from] = f - amt;
   bal[to]   = t + amt;          // from == to: balance ends at f + amt
   ```

   Sending to yourself creates `amt` out of nothing. It survives review because
   each line is correct on its own — only the pair is wrong. Check every place
   two balances are read before either is written. OZ's `_update` is safe; a
   hand-rolled `_transfer` or a fork that inlined one is where this lives.
5. **Is the asset address caller-supplied?** `deposit(address token, uint amt)`
   lets an attacker deposit a token they mint for free and withdraw a real one;
   `sweep(address token)` whose allowlist does not *exclude* the user-owned
   asset is the operator draining custody through the front door (§1).

Any row that fails gets the `arithmetic.md` §0 treatment — the exact input, the
expected movement, the actual movement — and is filed Critical or High with a
PoC. A failing row is never an observation.

---

## 4. Withdraw

- **Effects before interactions**: decrement the balance, then send. The reverse
  is drainable by any reentrant recipient.
- **Amount bounded by the caller's own balance**, with the subtraction done in
  checked arithmetic so an accounting bug reverts rather than underflows.
- **Native payouts use `call{value:}`**, not `transfer`/`send` — the 2300-gas
  stipend breaks multisigs, smart-contract wallets and AA accounts, which for a
  custody contract means those users can deposit but never withdraw. Pair with
  CEI so dropping the stipend is safe. See `gas.md`.
- **Withdraw must not depend on an external protocol being live.** If the assets
  are deployed into a strategy, a bridge, or a lending market, there must be a
  path that returns whatever is recoverable rather than reverting while that
  third party is paused. A third party's pause must not become a permanent
  freeze of your users' funds.
- **Withdraw must not depend on an oracle or on reward accounting.** Provide an
  emergency exit that skips reward settlement and external reads entirely, and
  check that it also updates the ledger (a common bug: emergency exit pays out
  but forgets to zero the record).
- **Partial withdrawal** must burn/decrement proportionally, rounding against
  the user.
- **Pausing must never cover `withdraw`.** Pause deposits, pause new positions —
  never the exit. If it does, that is a freeze finding at High or above.
- **Blocklist assets** (USDC-style) or a KAP-20 committee (`kub.md`) can freeze
  a specific user's exit. There is no code fix; it must be disclosed.
- **A withdrawal queue** must be bounded — no unbounded loop over requests, and
  no way for a later request to jump ahead of an earlier one.

## 5. Escrow specifics

Escrow adds a *condition* between deposit and release, and the condition is
where the money goes missing:

- **Who resolves the condition?** If a single party — the operator, a "referee",
  an oracle — can declare the outcome, they effectively control the funds. That
  is the same finding as §1, one level of indirection away. Rate it on what the
  resolver can cause, not on what they are trusted to do.
- **Both outcomes must be reachable.** Release to the payee *and* refund to the
  payer must each have a working path. An escrow with a release path but no
  refund path is a one-way transfer with extra steps.
- **A deadline with a default outcome.** If the resolver never acts, what
  happens? "Nothing" means the funds are locked forever. There must be a
  timeout that lets the payer reclaim, or an agreed default.
- **Both-agree path.** Payer and payee agreeing should be able to settle without
  the resolver at all.
- **State machine.** Enumerate the states (`Created / Funded / Released /
  Refunded / Disputed / Expired`) and check every transition: no double release,
  no release-then-refund, no refund of an already-released escrow. Set the state
  **before** the payout.
- **Per-escrow isolation.** Funds for escrow A must not be reachable by a
  withdrawal for escrow B. If one balance backs many escrows, check that the
  accounting cannot let one payee drain another's deposit — this is where
  mapping-key bugs and reused ids bite.
- **Fees.** Taken from the escrowed principal reduces what the parties agreed;
  charge them explicitly and disclose, and never let a fee change apply
  retroactively to escrows already funded (the snapshot rule in `economics.md`).
- **Cancellation** by one party alone, after funding, is a finding.
- **Dispute resolution with no bound** — a resolver who can hold funds
  indefinitely is a freeze; add a timeout.
- **The arbiter address must not be settable after funding**, or the operator
  can appoint themselves.

## 6. Wrapped / receipt tokens — the mint surface

For a **1:1 wrapper**, custody and solvency reduce to one property:

> The **only** way to create a receipt is to deposit the underlying, and the
> only way to release the underlying is to burn a receipt.

### Verify the mint surface mechanically

1. Grep every supply-increasing site: `_mint(`, `_update(address(0),`, direct
   `balanceOf[x] +=` / `totalSupply +=`, and assembly writes to the balance
   slot. `scripts/scan.py` flags these under `mint-site`.
2. For each, walk up to every externally reachable entry point.
3. Every one of those entry points must take custody of the matching amount in
   the same transaction. Any that does not is **Critical**.
4. Check the inverse: no path releases the underlying without burning.

Put the conclusion in the report as a sentence: *"`_mint` is reachable only
from `deposit()` and `receive()`, each crediting exactly the value received."*

### What this finds

- **An `onlyOwner` or `MINTER_ROLE` mint on a 1:1 wrapper.** The headline case,
  and the reason to check first. It does not matter that the key is a multisig
  or that it is "emergency only": supply is no longer *provably* backed, so the
  peg becomes a promise. Every AMM pool, lending market and bridge that treats
  the receipt as equivalent to the underlying is exposed to that key.
  **Critical** for an EOA; **High** behind a timelocked multisig — and in the
  executive summary either way, never buried.
- **A mint reachable from a bridge/relayer/oracle role.** Legitimate for a
  bridge-wrapped asset — where that authorisation *is* the security model, see
  `defi.md` — never for a local wrapper.
- **A leftover `mint()` from an OpenZeppelin template.** Common in forks. Check
  the deployed verified source, not just the repository.
- **An upgradeable wrapper.** The admin can add a mint tomorrow. The reference
  wrappers are immutable on purpose; upgradeability here is itself the finding.
- **`initialize()` minting an initial supply** to the deployer — unbacked by
  construction.
- **A second path through "migration" or "recovery".**

### Native wrappers (ETH→WETH, KUB→KKUB)

WETH9 is the reference; any deviation needs a stated reason.

- **`receive()` must mint**, or every direct send is a permanent loss.
- **Burn before sending**, and use `call{value:}` (§4).
- **`selfdestruct` force-feeding** raises the balance above `totalSupply` —
  harmless for the invariant, but any logic reading the balance instead of
  `totalSupply` becomes manipulable.
- **No pause, no blacklist, no upgrade, no owner.** A canonical wrapper is
  chain infrastructure: a pause on `withdraw` freezes every pool that holds it.

### KUB / KKUB

KKUB is the WETH-equivalent on KUB **and** a KAP-20, so it carries the
compliance surface in `kub.md` on top of everything above:

- Enumerate the wrapper's own privileged functions — `adminTransfer`,
  `adminApprove`, blacklist, KYC-gated transfer.
- Separate **moving balances** (fairness, and a freeze risk for the holder) from
  **changing supply** (backing). Different severities; do not blur them.
- KYC gating means any pool or staking contract holding KKUB must itself satisfy
  the gate, or transfers in and out revert. Trace that the contract in scope can
  actually receive and send it.
- A frozen holder cannot unwrap — permanent freeze of that user's underlying.
- Any protocol accepting the wrapper inherits its committee. Name the address in
  the trust assumptions.
- **Diff the deployed, verified source of the specific address in scope against
  WETH9** and list every deviation. Verify the interface against
  https://docs.kubchain.com rather than from memory.

### 1:1 vs share-based — do not mix them up

Applying the 1:1 invariant to a share-based design produces false findings;
applying share logic to a 1:1 wrapper misses real ones.

| | 1:1 wrapper | Share-based receipt |
|---|---|---|
| Examples | WETH, KKUB, WBNB, bridge mints | ERC-4626 vaults, rETH, most LSTs |
| Invariant | `held >= totalSupply` | `assets/shares` non-decreasing |
| Credit on deposit | exactly the deposit | `deposit * shares / assets`, rounded **down** |
| Extra underlying arriving | harmless surplus | changes the rate for everyone |
| First depositor | no special case | **inflation attack** — `liquidity.md` |
| Privileged mint | breaks backing (Critical) | dilutes holders (Critical) |
| Any multiplication in the wrap path | suspicious — ask why | expected |

Rebasing receipts are a third shape: the balance moves without a transfer, which
breaks any integrator that caches it. If the contract in scope *holds* one,
check it does not snapshot the balance.

---

## Checklist to run

1. List every path that moves value out, with its destination and its bound.
   State the conclusion as a sentence in the report.
2. State the solvency invariant and say where the code enforces it.
3. For deposit and withdraw: does custody change by exactly the accounted
   amount, **measured** rather than assumed?
3b. Fill the §3b table — one row per value-moving line. No row may have a
   caller-supplied `from` or asset address, no row may credit more than it
   measured, and no balance pair may be read before either is written.
4. Can any privileged role move user balances, edit the ledger, pause the exit,
   set an unbounded fee, or upgrade the contract? Name the address and the loss
   for each — and put the answer in the executive summary.
5. Can any user be permanently prevented from withdrawing? Answer the liveness
   checks in `arithmetic.md`.
6. For escrow: is every outcome reachable, is there a timeout, and can the
   resolver be changed after funding?
7. For a wrapper: is the design 1:1 or share-based, and does every line agree?

## Reference implementations

| Contract | Where | Read it for |
|---|---|---|
| WETH9 | https://github.com/gnosis/canonical-weth/blob/master/contracts/WETH9.sol | The canonical 1:1 native wrapper: no owner, no mint, no pause, no upgrade. Diff any native wrapper against it. |
| Solmate `WETH` | https://github.com/transmissions11/solmate/blob/main/src/tokens/WETH.sol | Modern rewrite of the same invariants. |
| OZ `ERC20Wrapper` | https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC20Wrapper.sol | 1:1 ERC-20-over-ERC-20, and `_recover` bounded to the surplus — the correct shape for a sweep. |
| OZ `Escrow` / `ConditionalEscrow` / `RefundEscrow` | https://github.com/OpenZeppelin/openzeppelin-contracts/tree/release-v4.9/contracts/utils/escrow | Minimal escrow with a real refund path; useful as a baseline to diff a custom escrow against. Removed in v5 (pin the v4.9 tag), so a project still using it is on an old OZ line — worth a note. |
| OZ `VestingWallet` | https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/finance/VestingWallet.sol | Pull-payment release accounting done correctly. (`PaymentSplitter` was removed in v5.) |
| OZ `ERC4626` | https://github.com/OpenZeppelin/openzeppelin-contracts/blob/master/contracts/token/ERC20/extensions/ERC4626.sol | The share-based alternative for the comparison above. |
| KAP standards | https://docs.kubchain.com/quickstart/launching-a-token-on-kub/kap-token-interfaces | What a KUB wrapper additionally carries — see `kub.md`. |
