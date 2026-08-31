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
| Chainlink contracts | https://github.com/smartcontractkit/chainlink/tree/develop/contracts | `AggregatorV3Interface`, and the L2 sequencer-uptime feed example. |

## Staking

| Project | Where | Read it for |
|---|---|---|
| Synthetix `StakingRewards` | https://github.com/Synthetixio/synthetix/blob/v2.101.3/contracts/StakingRewards.sol | The canonical `rewardPerToken` / `notifyRewardAmount` pattern. ~90% of single-token staking contracts are forks of this — diff against it. |
| SushiSwap `MasterChef` | https://github.com/sushiswap/sushiswap/blob/master/protocols/masterchef/contracts/MasterChef.sol | The `accRewardPerShare` / `rewardDebt` pattern, and the `add()`-without-`massUpdatePools` bug and the `migrator` rug vector — both still present in forks today. |
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
| 1inch Aggregation Router | https://github.com/1inch/1inch-contracts | Arbitrary-call routing done with allowlisting — the pattern to compare a custom router against. |

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
| Smart Contract Weakness / DASP | https://dasp.co | Older but still-used taxonomy. |
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
