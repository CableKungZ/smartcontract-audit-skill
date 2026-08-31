# Reference Implementations

Battle-tested contracts to compare an audited contract against. Two uses:

1. **Diff a fork against its upstream.** Most forks are exploited because of a
   *small* deviation from the original, not a novel bug — Uranium Finance lost
   $50M to one constant changed in one branch. If the code is a fork, find the
   upstream tag it came from and diff it line by line before anything else.
2. **Cite the canonical fix in a recommendation.** "Use OpenZeppelin's
   `ReentrancyGuard`" with a link is a better recommendation than prose.

> Always pin a **tag/commit**, never `main` — these repos change, and an
> audit report that cites a moving target is not reproducible.

---

## Libraries — the default recommendation for almost every fix

| What | Where | Notes |
|---|---|---|
| OpenZeppelin Contracts | https://github.com/OpenZeppelin/openzeppelin-contracts | The reference. v5.x removed `_beforeTokenTransfer` (use `_update`) and changed `Ownable`'s constructor — forks that mix v4 and v5 idioms are a common finding. |
| OZ Upgradeable | https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable | `Initializable`, `__gap`, `_disableInitializers()`. |
| `SafeCast`, `Math.mulDiv` | OZ `utils/` | The fix for nearly every finding in `arithmetic.md`. |
| Solmate | https://github.com/transmissions11/solmate | Gas-optimized, **fewer safety checks by design** (e.g. `SafeTransferLib` does not check the token has code). Using it is fine; using it without knowing what it omits is a finding. |
| Solady | https://github.com/Vectorized/solady | Extremely optimized assembly. Same caveat, more so. |
| PRBMath | https://github.com/PaulRBerg/prb-math | Fixed-point math with overflow-safe `mulDiv`, `exp`, `log`. |
| Uniswap `FullMath` | https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/FullMath.sol | 512-bit `mulDiv` — the standard fix for "intermediate overflows before division". |
| Chainlink contracts | https://github.com/smartcontractkit/chainlink-evm/tree/develop/contracts | `AggregatorV3Interface`, and the L2 sequencer-uptime feed example. |

### Check the pinned library version against known advisories

**Do this before reading any inherited contract.** "Uses OpenZeppelin" is not a
safety property — a specific version is. Resolve the version actually compiled:

```
grep -r "@openzeppelin" package.json remappings.txt        # declared
sed -n 's/.*"@openzeppelin\/contracts": "\(.*\)".*/\1/p' package-lock.json
git -C lib/openzeppelin-contracts describe --tags          # forge submodule
npm audit --omit=dev                                       # authoritative
```

A submodule pinned to a commit is the common trap: `package.json` says `^5.0.0`
while `lib/` sits on a 4.x commit from two years ago. Report the version and the
resolution method in the report's method section.

**OpenZeppelin Contracts advisories** (`@openzeppelin/contracts` and
`-upgradeable` share version numbers). If the pinned version falls in a
vulnerable range **and** the contract uses the affected component, it is a
finding at the listed severity — not an informational note.

| Advisory | Component | Vulnerable | Patched | Effect |
|---|---|---|---|---|
| GHSA-5vp3-v4hc-gx76 | `UUPSUpgradeable` | ≥4.1.0 <4.3.2 | 4.3.2 | **Critical** — uninitialized implementation can be `selfdestruct`ed, bricking the proxy (see `postmortems.md` §6). |
| GHSA-fg47-3c2x-m2wr | `TimelockController` | 3.3.0–3.4.1, 4.0.0–4.3.0 | 3.4.2 / 4.3.1 | **Critical** — executor role takes immediate control of the timelock. |
| GHSA-4h98-2769-gh6h | `ECDSA.recover/tryRecover` | ≥4.1.0 <4.7.3 | 4.7.3 | **High** — EIP-2098 compact signatures accepted → malleability; breaks any `usedSignature` replay guard. |
| GHSA-xrc4-737v-9q75 | `GovernorVotesQuorumFraction` | ≥4.3.0 <4.7.2 | 4.7.2 | **High** — lowering quorum makes previously defeated proposals executable. |
| GHSA-qh9x-gcfh-pcrw | `ERC165Checker.supportsInterface` | ≥4.0.0 <4.7.1 | 4.7.1 | **High** — reverts instead of returning false → DoS on registration paths. |
| GHSA-7grf-83vw-6f5x | `ERC165Checker` | ≥2.0.0 <4.7.2 | 4.7.2 | Unbounded gas consumption from a hostile target. |
| GHSA-4g63-c64m-25w9 | `SignatureChecker` | ≥4.1.0 <4.7.1 | 4.7.1 | Reverts on an invalid EIP-1271 signer instead of returning false. |
| GHSA-699g-q6qh-q4v8 | `Multicall` | 4.9.4 only | 4.9.5 | **Every subcall executes twice.** Double-spend on any batched state change. |
| GHSA-wprv-93r4-jj2p | `MerkleProof` multiproofs | ≥4.7.0 <4.9.2 | 4.9.2 | Forge a valid multiproof for arbitrary leaves → unlimited airdrop claims. |
| GHSA-5h3x-9wvq-w4m2 | `Governor` | ≥4.3.0 <4.9.1 | 4.9.1 | Proposal creation frontrun → attacker becomes proposer and cancels. |
| GHSA-93hq-5wgc-jc82 | `GovernorCompatibilityBravo` | ≥4.3.0 <4.8.3 | 4.8.3 | Short `signatures` array trims proposal calldata → executes a different payload than voted. |
| GHSA-m6w8-fq7v-ph4m | `GovernorCompatibilityBravo` | ≥4.3.0 <4.4.2 | 4.4.2 | Explicit function signatures execute with wrong arguments. |
| GHSA-878m-3g6q-594q | `ERC721Consecutive` | ≥4.8.0 <4.8.2 | 4.8.2 | Batch of 1 skips the balance update → later transfer underflows. |
| GHSA-wmpv-c2jp-j2xg | `ERC1155Supply` | ≥4.2.0 <4.3.3 | 4.3.3 | `totalSupply` updated after the receiver callback → reentrancy reads stale supply. |
| GHSA-9c22-pwxw-p6hx | `Initializable` | ≥3.2.0 <4.4.1 | 4.4.1 | Initializer reentrancy → double initialization. |
| GHSA-g4vp-m682-qqmp | `ERC2771Context` | ≥4.0.0 <4.9.3 | 4.9.3 | Short calldata from a custom forwarder → `_msgSender()` returns `address(0)`. |
| GHSA-mx2q-35m2-x2rh | `TransparentUpgradeableProxy` | ≥3.2.0 <4.8.3 | 4.8.3 | Selector clash with the admin interface stops delegation to the implementation. |
| GHSA-9vx6-7xxf-x967 | `Base64.encode` | ≥4.5.0 <5.0.2 | 5.0.2 / 4.9.6 | Reads dirty memory past the buffer. |
| GHSA-9j3m-g383-29qr | `CrossChainEnabledArbitrumL2` | ≥4.6.0 <4.7.2 | 4.7.2 | EOA interactions classified as cross-chain calls. |
| GHSA-9rcw-c2f9-2j55 | `Bytes.lastIndexOf` | ≥5.2.0 <5.4.0 | 5.4.0 | Out-of-bounds read on an empty buffer. |

Current list: https://github.com/OpenZeppelin/openzeppelin-contracts/security/advisories
— re-check it at audit time; this table is a snapshot, not the source of truth.

**Version-migration pitfalls that are not advisories but break forks:**

- **v4 → v5**: `_beforeTokenTransfer`/`_afterTokenTransfer` are gone (use
  `_update`) — a hook that silently stopped running is a real finding, not a
  compile error, in code that overrode it via a diamond of inherited contracts.
  `Ownable` now takes an owner in the constructor; `Ownable()` with no argument
  reverts at deploy. `ERC20Permit` moved to `Nonces`. Custom errors replaced
  string reverts — any off-chain code or test matching on revert strings breaks.
- **Mixing v4 and v5 files** in one project (npm dependency at v5, vendored copy
  at v4) — check for two `Ownable.sol` on different remappings.
- **Upgradeable ≠ non-upgradeable**: an upgradeable contract that inherits a
  non-upgradeable OZ base has a constructor that never runs on the proxy, so its
  state stays zero. Grep for imports missing the `-upgradeable` suffix.
- `__gap` removed or resized in a fork of an upgradeable OZ base → storage
  collision on the next upgrade.

## Staking

| Project | Where | Read it for |
|---|---|---|
| Synthetix `StakingRewards` | https://docs.synthetix.io/contracts/source/contracts/stakingrewards | The canonical `rewardPerToken` / `notifyRewardAmount` pattern. ~90% of single-token staking contracts are forks of this — diff against it. |
| SushiSwap `MasterChef` | https://github.com/sushiswap/masterchef/blob/master/contracts/MasterChef.sol | The `accRewardPerShare` / `rewardDebt` pattern, and the `add()`-without-`massUpdatePools` bug and the `migrator` rug vector — both still present in forks today. |
| `MasterChefV2` | same repo | The corrected version; use it to show what the fix looks like. |
| Curve `VotingEscrow` (veCRV) | https://github.com/curvefi/curve-dao-contracts/blob/master/contracts/VotingEscrow.vy | The reference lock/decay (slope-bias) math. Vyper. |
| Lido `stETH` | https://github.com/lidofinance/lido-dao | Rebasing LST, share accounting, oracle-reported balances, withdrawal queue. |
| Rocket Pool | https://github.com/rocket-pool/rocketpool | Non-rebasing LST (`rETH`) — the alternative design. |

## Tokens

| Project | Where | Read it for |
|---|---|---|
| OZ `ERC20`, `ERC721`, `ERC1155` | OZ repo `token/` | The baseline every token should match. |
| OZ `ERC4626` | OZ `token/ERC20/extensions/ERC4626.sol` | Virtual shares/assets — the standard mitigation for the inflation attack in `liquidity.md`. |
| OZ `ERC20Votes` / `ERC20Permit` | OZ `extensions/` | Checkpointed voting power (flash-loan-safe) and EIP-2612 done correctly. |
| ERC-20 edge cases | https://github.com/d-xo/weird-erc20 | **Read this on every audit that touches an arbitrary ERC20.** Fee-on-transfer, no-return, rebasing, blocklist, multiple entry points, 0-decimals — each one is a real deployed token. |
| KAP-20 / KAP-721 / KAP-1155 / KAP-22 | https://docs.kubchain.com/quickstart/launching-a-token-on-kub/kap-token-interfaces | The KUB standards. See `kub.md`. |

## Swap / AMM

| Project | Where | Read it for |
|---|---|---|
| Uniswap V2 core + periphery | https://github.com/Uniswap/v2-core · https://github.com/Uniswap/v2-periphery | The `k` invariant check, `MINIMUM_LIQUIDITY`, the `uint112` reserve bound, and the router's slippage/deadline pattern. Every V2 fork must be diffed against this. |
| Uniswap V3 core | https://github.com/Uniswap/v3-core | Tick math, `FullMath`, the swap callback and **why the callback must validate the caller is a factory-deployed pool**. |
| Uniswap V4 | https://github.com/Uniswap/v4-core | Hooks and the singleton/flash-accounting model — a different threat surface (hook permissions, unlock callbacks). |
| Curve StableSwap | https://github.com/curvefi/curve-contract | `get_D`/`get_y` Newton iteration, amplification ramp, and the read-only-reentrancy history. |
| Balancer V2 Vault | https://github.com/balancer/balancer-v2-monorepo | Singleton vault accounting; a useful contrast when auditing a custom pool. |
| 1inch Aggregation Router | https://github.com/1inch/limit-order-protocol | Arbitrary-call routing done with allowlisting — the pattern to compare a custom router against. |

## Lending / DeFi

| Project | Where | Read it for |
|---|---|---|
| Aave V3 | https://github.com/aave/aave-v3-core | Health factor, isolation mode, supply/borrow caps, e-mode, liquidation logic. The modern reference. |
| Compound V2 | https://github.com/compound-finance/compound-protocol | The most-forked lending codebase — and the source of the empty-market donation attack. If the target is a Compound fork, that attack is your first check. |
| Compound V3 (Comet) | https://github.com/compound-finance/comet | Single-borrow-asset design; much smaller surface. |
| Morpho Blue | https://github.com/morpho-org/morpho-blue | Minimal isolated-market lending (~650 lines) — the best short read for understanding the invariants. |
| Liquity V1 | https://github.com/liquity/dev | Stability pool + redemption CDP design with no governance. |
| MakerDAO `dss` | https://github.com/makerdao/dss | `Vat` accounting, liquidation auctions. Dense but authoritative. |
| Yearn V3 vaults | https://github.com/yearn/yearn-vaults-v3 | Strategy/vault split, loss reporting, profit unlocking. |
| GMX V2 | https://github.com/gmx-io/gmx-synthetics | Perps: OI caps, funding, oracle-price keeper design. |

## Wallets & accounts

| Project | Where | Read it for |
|---|---|---|
| Safe (Gnosis Safe) | https://github.com/safe-global/safe-smart-account | Threshold signature verification with strictly-increasing signers, module/guard architecture, `delegatecall` risk surface. |
| ERC-4337 `EntryPoint` + `SimpleAccount` | https://github.com/eth-infinitism/account-abstraction | `validateUserOp` rules, paymaster flow, factory/counterfactual addresses. |
| OZ `TimelockController` | OZ `governance/TimelockController.sol` | The reference timelock; compare any custom one against it. |
| OZ `Governor` | OZ `governance/` | Snapshot-based voting power — the fix for flash-loan governance. |
| Sablier / OZ `VestingWallet` | https://github.com/sablier-labs/v2-core · OZ `finance/` | Vesting/streaming math. |

## Security corpora — use these as test oracles

| Resource | Where | Use |
|---|---|---|
| SWC Registry | https://swcregistry.io | Stable IDs (`SWC-107` reentrancy, `SWC-128` DoS-by-gas-limit) to cite in findings. |
| Smart Contract Security Field Guide | https://scsfg.io | Modern, maintained taxonomy — the practical replacement for the old DASP top-10. |
| Damn Vulnerable DeFi | https://github.com/theredguild/damn-vulnerable-defi | Each challenge is a real bug class in minimal form — the fastest way to calibrate on flash-loan, oracle and reentrancy attacks. |
| Ethernaut | https://github.com/OpenZeppelin/ethernaut | Fundamentals: delegatecall, storage layout, `tx.origin`, uninitialized proxies. |
| Solodit | https://solodit.xyz | Aggregated findings from Code4rena, Sherlock, Spearbit, Trail of Bits — search by contract type before starting an audit to see what auditors actually found in similar code. |
| Rekt leaderboard | https://rekt.news/leaderboard | Post-mortems of the largest losses, with root causes. |
| Immunefi severity system | https://immunefi.com/immunefi-vulnerability-severity-classification-system-v2-3 | The rubric `methodology.md` aligns to. |
| Code4rena reports | https://code4rena.com/reports | Full published audit reports — useful as report-writing models, not just bug lists. |
| Trail of Bits `building-secure-contracts` | https://github.com/crytic/building-secure-contracts | Guidance plus the Echidna/Slither docs. |

## Tooling to recommend in a report

| Tool | Where | Recommend when |
|---|---|---|
| Slither | https://github.com/crytic/slither | Always. `scripts/slither_to_findings.py` in this repo imports its JSON. |
| Foundry (`forge`) | https://github.com/foundry-rs/foundry | Always — invariant/fuzz tests are the practical defence against the arithmetic bugs in `arithmetic.md`. `forge test --gas-report` for `gas.md`. |
| Echidna | https://github.com/crytic/echidna | Property-based fuzzing when invariants are non-trivial. |
| Halmos / Kontrol | https://github.com/a16z/halmos · https://github.com/runtimeverification/kontrol | Symbolic execution for arithmetic-heavy math. |
| Mythril | https://github.com/Consensys/mythril | Symbolic execution; noisier than Slither. |
| `solc --model-checker-engine chc` | built into solc | Free bounded model checking for overflow/underflow. |
| Tenderly / OpenZeppelin Defender | https://tenderly.co · https://defender.openzeppelin.com | Post-deployment monitoring — recommend alongside any centralization or liveness finding. |
