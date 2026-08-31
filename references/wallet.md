# Wallet / Account Contracts

Covers: multisig, smart accounts (ERC-4337 / EIP-7702), social recovery,
timelocks, vesting/escrow wallets, and custodial wallet factories
(incl. Bitkub NEXT-style — see `kub.md`).

## Signature verification

- **Replay**: the signed digest must bind `nonce` + `chainId` + `address(this)`
  (+ the target and calldata). Missing any one → replay across txs, chains,
  or sibling wallets deployed from the same factory.
- `ecrecover` returning `address(0)` on a malformed signature must be rejected —
  otherwise a garbage signature "verifies" as owner `address(0)` if that slot is
  ever set or compared loosely.
- **Malleability**: if `v`/`r`/`s` are handled manually, enforce
  `s <= secp256k1n/2` and `v ∈ {27,28}`. Prefer OZ `ECDSA`.
- Duplicate signers accepted in a threshold loop → 1 key satisfies `n-of-m`.
  Enforce strictly increasing signer addresses.
- EIP-1271 (`isValidSignature`) on a contract owner: the check must be made
  against the *current* state and must not be reentrant; a smart-contract signer
  can change its answer between validation and execution.
- Signature over a hash that a user can be tricked into signing elsewhere
  (no EIP-712 domain, or a domain shared with another contract).

## Execution

- `delegatecall` to a user-supplied target = full takeover of the wallet's
  storage. If the wallet supports it (Safe's `Enum.Operation.DelegateCall`),
  the risk must be documented and modules allowlisted.
- Batched `execute(address[], bytes[], uint256[])`: array length mismatch;
  `msg.value` reused across iterations; a failing sub-call swallowed
  (`(bool ok,) = call(...)` with the result ignored).
- Return-data bombs from an untrusted callee → gas griefing; use
  `excessivelySafeCall` or bound returndata.
- Gas forwarding: a sub-call given 63/64 of gas can be made to fail while the
  outer call succeeds (EIP-150 1/64 rule) — relevant to any "relayer paid on
  success" design.

## Ownership & recovery

- Single-step owner transfer → typo bricks the wallet. Use `Ownable2Step`.
- `removeOwner` that can drop below `threshold`, or set `threshold = 0`.
- Social recovery with no timelock/veto window → a compromised guardian set
  takes the wallet instantly.
- Guardian set changeable by a single guardian.
- Recovery that doesn't invalidate pending queued transactions.

## Timelock

- `execute` callable before `eta`; `eta` set in the past; grace period unbounded.
- The timelock's `admin` can shorten the delay without going through the delay.
- Queued payloads not hashed with `value`/`target` → a different payload executes.
- Anyone can `cancel` — or nobody can.

## ERC-4337 smart accounts

- `validateUserOp` must not have side effects beyond nonce/prefund and must not
  access forbidden opcodes/storage (bundlers will drop it — a liveness bug).
- Paymaster: `validatePaymasterUserOp` that doesn't bound `maxCost` → drained
  deposit; missing check that `postOp` reverting can't lock funds.
- `initCode` factory: the counterfactual address must depend on the owner, or
  someone front-runs deployment of *your* address with *their* owner.
- Nonce key handling for parallel nonces; missing `EntryPoint`-only modifier on
  `validateUserOp` and `execute`.
- Session keys with no expiry, no target allowlist, or no spend cap.

## EIP-7702 delegated EOAs

- The delegate contract runs in the EOA's storage: an uninitialized-storage or
  `selfdestruct`-style pattern is catastrophic. Initialization must be bound to
  the account and non-front-runnable.
- Delegation persists across chains unless `chainId` is pinned in the
  authorization.

## Custodial / factory wallets

- Deterministic (`CREATE2`) address collision or front-run initialization —
  initialize in the same transaction as the deploy.
- Admin able to `execute` arbitrary calls on behalf of a user: this is the whole
  trust model, so state it explicitly as a centralization finding with the
  scope of the power (can it move funds? change the owner?) and the key custody
  (EOA vs multisig vs HSM).
- `receive()` missing → the wallet cannot accept ETH; or present with logic that
  can revert → refunds to the wallet fail.
- Missing `onERC721Received` / `onERC1155Received` → NFTs sent to the wallet are
  stuck.
- No sweep path for tokens the wallet was not designed to hold.

## Checklist

1. Enumerate every way a state change can be authorized. For each: what is
   signed, what binds it to this chain/contract/nonce?
2. Enumerate every way value leaves the wallet.
3. Write the "attacker has one guardian key / one owner key / the relayer key"
   scenario for each.

## Reference incidents

- Parity multisig (2017): unprotected `initWallet` → library `selfdestruct`,
  $150M+ frozen. Still the archetype for uninitialized-proxy findings.
- Multichain/Anyswap router: approvals to an arbitrary-call target.
- Numerous 4337 paymaster griefing reports: unbounded `maxCost`.
