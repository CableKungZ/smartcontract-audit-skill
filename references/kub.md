# KUB Chain (Bitkub Chain) — KAP standards

Docs: https://docs.kubchain.com — the standards live under
`quickstart/launching-a-token-on-kub/kap-token-interfaces/`
(`kap-20`, `kap-721`, `kap-1155`, `kap-22`), plus
`build-on-kub/kub-application-protocol-kap`.

KUB is EVM-compatible, so **everything in `methodology.md` applies unchanged**.
What is different is the KAP layer: a compliance/custody framework bolted onto
the ERC standards, which introduces privileged functions that would be
Critical findings on any other chain and are *expected* here. The audit job is
to verify they are wired correctly and scoped, not to flag their existence.

## What KAP adds on top of ERC

| Standard | ERC equivalent | KAP additions |
|---|---|---|
| KAP-20 | ERC-20 | `adminTransfer`, `adminApprove`, `internalTransfer`, `externalTransfer`; `name`/`symbol`/`decimals` are **required**, not optional |
| KAP-721 | ERC-721 | admin/committee transfer equivalents, KYC-gated transfer |
| KAP-1155 | ERC-1155 | same pattern for multi-token |
| KAP-22 | (none) | loyalty-point tokens, non-transferable / restricted-transfer semantics |

Per the docs: `adminTransfer` exists to "automatically create transactions on
behalf of token holders who have been victims of fraudulent transactions", and
"KUB has no control over user settings and access to the `adminTransfer`
function, and it is solely operated by token developers." **The token developer
holds this power, so the whole trust model rests on who that committee address
is.**

## Audit checklist for a KAP token

1. **`adminTransfer` access control.** Docs: "can only be called by the
   Committee address required in the constructor". Verify:
   - the committee address is set in the constructor and is a multisig/timelock,
     not a fresh EOA;
   - there is no setter that lets the current committee hand the role to an
     arbitrary address without a delay — or if there is, file it as a finding
     with the escalation path spelled out;
   - the modifier is actually applied (a KAP fork that declares the function
     `public` with no modifier is an instant Critical).
2. **`adminApprove`** — "only Admin and Super Admin". Same questions. Note that
   admin-set allowances bypass the user entirely.
3. **`internalTransfer` / `externalTransfer`** — "only the Super Admin and the
   Transfer Router". These move tokens between KYC'd addresses on behalf of
   Bitkub NEXT custodial users. Verify:
   - the router address is immutable or timelocked;
   - `internalTransfer` requires **both** parties KYC'd at
     `acceptedKycLevel`; `externalTransfer` requires the sender KYC'd;
   - the KYC contract address cannot be repointed to an attacker contract that
     returns a passing level for everyone;
   - these paths update the same balances/allowances as `transfer` — a fork that
     writes to a parallel mapping desynchronizes `totalSupply`.
4. **`AdminProjectRouter` / project registry.** Role checks typically read
   `adminProjectRouter.isSuperAdmin(addr, PROJECT)` with `PROJECT` a string.
   Verify the project string is fixed, the router is not user-settable, and the
   call's return value is checked (an EOA at that address returns empty data →
   `abi.decode` reverts, or with a low-level call, silently passes).
5. **`acceptedKycLevel`** settable by admin — lowering it to 0 disables the KYC
   gate. Bound it or timelock it.
6. **Blacklist / pause** if the fork adds them: state the freeze impact.
7. **Centralization section is mandatory in the report.** For a KAP token the
   correct output is not "Critical: admin can move user funds" — it is a clearly
   scoped centralization finding naming every privileged function, the exact
   address holding it, whether that address is a multisig/timelock, and what a
   compromise of it would cost users. Severity follows `methodology.md`:
   documented + multisig/timelock → Low/Medium; single undocumented EOA → High
   or Critical.

## Common KAP fork mistakes

- Copying a KAP-20 template and leaving the committee/admin addresses as the
  template's testnet values, or as `msg.sender` at deploy with no transfer step.
- Overriding `_transfer` for fees but not routing `internalTransfer` /
  `externalTransfer` through the same hook → fee bypass, or worse, accounting
  that diverges from `totalSupply`.
- Adding `adminTransfer` to a token that also serves as an LP/staking asset:
  the admin can drain a pool by pulling the pool's balance. Any DeFi protocol on
  KUB that accepts arbitrary KAP-20 tokens inherits every token's committee as a
  trusted party — call this out when auditing a KUB DeFi/swap/staking contract.
- Assuming `transfer` is the only balance-moving path when writing an integrator
  (e.g. a staking contract that snapshots balances) — `adminTransfer` moves
  tokens without the usual caller.

## Chain notes

| Item | Note |
|---|---|
| Consensus | PoSA-style validator set, small and permissioned — `block.timestamp` and censorship assumptions are weaker than L1, similar to BNB Chain. Treat `block.timestamp` as validator-influenceable within seconds. |
| Block time | ~5s (verify against the current docs before quoting it in a report). Never hardcode "per block" reward rates — use per-second. |
| Gas | Cheap → loop/griefing DoS is economically viable. Any unbounded loop is a real finding here, not theoretical. |
| Oracles | Chainlink coverage is limited/absent. Protocols often use an in-house price feed or an AMM spot price — check the feed's operator set, staleness handling, and manipulability. This is usually the highest-severity area on a KUB DeFi audit. |
| Liquidity | Thin pools → AMM TWAPs are cheap to manipulate. A TWAP that is safe on Ethereum may not be safe here; size the manipulation cost against actual pool depth. |
| Bitkub NEXT | Custodial wallet; users' addresses are contract wallets controlled by Bitkub's router. Contracts that assume `msg.sender == tx.origin` or reject contract callers will break NEXT users. Also see `wallet.md`. |
| KUB L2 | Docs describe a KUB Layer 2 network — if the contract targets it, apply the general L2 notes in `methodology.md` (sequencer liveness, `block.number` semantics) and confirm the specifics against the docs. |

> Verify addresses, block time, and the current KAP interface against
> https://docs.kubchain.com before quoting them as fact in a deliverable —
> this file is a checklist, not a substitute for the live spec.
