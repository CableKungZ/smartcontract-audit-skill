# Token Contracts

Covers: ERC-20 / ERC-721 / ERC-1155 / ERC-4626 shares, and the KUB Chain
KAP-20 / KAP-721 / KAP-1155 / KAP-22 equivalents (see `kub.md`).

## ERC-20

### Supply & minting
- `mint` reachable by a non-owner, by a role the owner can grant itself, or by a
  "minter" contract that is itself upgradeable → unlimited supply (Critical).
- No `maxSupply` cap, or cap checked *after* `_mint`.
- `burn(address,uint256)` without an allowance check → burn anyone's tokens.
- Mint in `constructor` to `msg.sender` while docs claim a vesting schedule —
  compare code to the tokenomics the project publishes; a mismatch is a finding.

### Transfer hooks / fee-on-transfer
- Tax/fee logic in `_transfer` (`_update` in OZ v5) that:
  - can be raised to 100% by the owner after launch (honeypot — Critical),
  - has no upper bound (`require(fee <= MAX_FEE)` missing),
  - applies to `transferFrom` used by AMM pairs → breaks Uniswap
    `swapExactTokensForTokens` (must use the `SupportingFeeOnTransferTokens`
    variants), and breaks any integrator's `amount`-based accounting.
- `swapBack`/auto-liquify inside `_transfer`: reentrancy into the router, DoS
  when the router reverts, sandwichable, and it fires on the victim's gas.
- Blocklist / `isBlacklisted` — document it as a centralization risk with the
  freeze impact stated. Combined with an unbounded fee it is a rug.
- Max-wallet / max-tx limits that also apply to the pair or the router → trading
  bricks.

### Standard compliance
- `transfer`/`transferFrom` returning nothing (USDT-style) — legal but every
  integrator must use `SafeERC20`. Flag if *this* contract calls other tokens
  without it.
- `approve` race condition; prefer `increaseAllowance`, or document.
- `decimals()` not 18 and integrators assume 18.
- `permit` (EIP-2612): missing `deadline`, `nonce` not incremented, `DOMAIN_
  SEPARATOR` cached across a chain fork without a `chainId` recheck,
  `ecrecover` result not checked against `address(0)`.
- OZ v5 removed `_beforeTokenTransfer`; forks that kept it silently lose hooks.

### Rebasing / elastic supply
- `balanceOf` computed from shares — any integrator holding a raw balance
  snapshot is wrong. Check the token is not used as AMM/lending collateral.
- Rounding in `sharesToTokens` lets dust be farmed via repeated small transfers.

## ERC-721

- `_mint` vs `_safeMint`: `_safeMint` gives the receiver control (reentrancy into
  a mint function with a per-wallet cap → cap bypass, the classic free-mint
  drain). Apply CEI and `nonReentrant`, or use `_mint` where appropriate.
- Per-wallet mint limit tracked by `msg.sender` → bypass with fresh wallets;
  by `tx.origin` → broken by AA. State the intended guarantee.
- `tokenURI` not frozen; owner can rewrite metadata post-sale (Low, but disclose).
- Royalty (`ERC2981`) is not enforceable on-chain — don't call it a guarantee.
- `approve`/`setApprovalForAll` left dangling after a sale (marketplace logic).
- `totalSupply` loops over minted ids; enumerable extension makes transfers O(n).
- Signature-gated allowlist mint without `nonce` + `chainId` + contract address
  in the digest → replay across chains/contracts.

## ERC-1155

- `_mintBatch` array length mismatch not checked (OZ checks; forks often don't).
- `onERC1155Received` / `onERC1155BatchReceived` reentrancy on every
  `safeTransferFrom`, including inside batch loops.
- Same id reused for both a fungible and non-fungible meaning → accounting
  confusion in integrators.

## ERC-4626 vault shares

- **First-depositor / inflation attack**: attacker deposits 1 wei, donates a
  large amount directly to the vault, second depositor's shares round to 0.
  Fixes: virtual shares/assets offset (OZ v4.9+), dead shares minted at deploy,
  or a minimum initial deposit burned. Absent → High/Critical depending on
  whether a bootstrap deposit is enforced in the deploy script.
- Rounding direction: `deposit`/`mint` must round shares **down**, `withdraw`/
  `redeem` must round shares **up** (against the user). Any inversion is a
  value-extraction loop.
- `totalAssets()` reading `balanceOf(this)` → donation-manipulable, and
  double-counts pending yield/fees.
- `maxWithdraw`/`previewRedeem` diverging from the actual `redeem` path — breaks
  integrators that trust the preview.

## KUB / KAP-specific

See `kub.md` for `adminTransfer`, `adminApprove`, `internalTransfer`,
`externalTransfer`, `AdminProjectRouter`, `Committee` and KYC-level checks.
Short version: KAP-20 has privileged transfer functions by design — audit that
they are wired to the *correct* committee/admin router and cannot be repointed
by a compromised or arbitrary address.

## Reference incidents

- Uranium Finance (2021, $50M): a constant changed from `1000` to `10000` in one
  place only — always diff forked math against upstream.
- Countless "honeypot" tokens: unbounded owner-settable sell tax.
- Meebits / free-mint reentrancy via `_safeMint` — supply cap bypass.
