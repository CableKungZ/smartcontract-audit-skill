# Staking / Reward Distribution

Covers: single-token staking, MasterChef-style LP farms, veToken locks, liquid
staking (LST/LSD), NFT staking, validator delegation.

## Reward accounting (the #1 source of Critical findings)

- **`updatePool` / `_updateReward` not called** before every state change that
  affects `totalStaked`, a user's `amount`, or `rewardRate`. Any path that
  changes stake without settling first mints or destroys rewards.
  Check *all* entry points: `deposit`, `withdraw`, `emergencyWithdraw`, `claim`,
  `compound`, `setAllocPoint`, `add(pool)`, `notifyRewardAmount`, `migrate`.
- **`add()` a new pool without `massUpdatePools()`** — the classic MasterChef
  bug. All existing pools retroactively accrue at the new `totalAllocPoint`.
- **`rewardDebt` not updated** on one of the paths, or updated with the *pre*-
  deposit amount → user claims rewards for time they weren't staked.
- **`accRewardPerShare` scaling** too small (`1e12`) for 18-decimal reward tokens
  with large `totalStaked` → per-block accrual truncates to 0. Use `1e18`+ and
  check `reward * PRECISION / totalStaked != 0` at realistic magnitudes.
- **Division by zero / skipped accrual when `totalStaked == 0`** — rewards for
  that window must be either carried forward or explicitly forfeited. If
  `lastUpdateTime` is bumped while `totalStaked == 0`, those rewards are stranded
  in the contract forever (Low/Medium) — or, worse, claimable by the first staker.
- **`rewardRate` recomputed on top-up** (`notifyRewardAmount`): the Synthetix
  pattern `rewardRate = (reward + leftover) / duration` extends the period. Check
  `leftover` is computed from `periodFinish`, and that
  `rewardRate * duration <= balanceOf(rewardToken)` — otherwise the pool promises
  rewards it cannot pay and the last claimers revert.
- **Reward token == staking token** in the same balance: `notifyRewardAmount`
  based on `balanceOf(this)` counts user principal as rewards → principal is
  distributed away. Track `totalStaked` separately and only distribute the excess.

## Stake/unstake rounding loop (High, very common)

If rounding favours the user on *both* entry and exit, a loop extracts value.
Concretely: `shares = amount * totalShares / totalAssets` rounded **down** on
deposit and `assets = shares * totalAssets / totalShares` rounded **down** on
withdraw is safe; any place where one side rounds **up** in the user's favour is
exploitable. Write the loop out with numbers before filing.

- Deposit fee / withdraw fee applied to a shares number rather than assets.
- `amount` re-read from `balanceOf` after a fee-on-transfer token.

## Lock / vesting

- Lock extension does not re-check `maxLockTime`; or `unlockTime` can be set to
  the past (`increaseLock` with `0`).
- veToken: decay computed from `block.number` (drifts per chain) instead of
  `block.timestamp`; slope/bias math that underflows at the boundary week.
- Early-withdraw penalty sent to `totalStaked` accounting without updating
  `accRewardPerShare` → penalty is unclaimable or double-counted.
- `emergencyWithdraw` forfeits rewards but forgets to zero `rewardDebt` →
  user re-deposits and claims the forfeited rewards.
- Lock period bypass: user can `transfer` the staking receipt/NFT to a fresh
  address that has no lock recorded.

## Liquid staking (LST)

- Exchange rate (`stETH`-style) from `totalPooled / totalShares` where
  `totalPooled` reads `address(this).balance` → donation inflates the rate;
  first-depositor share inflation (see `liquidity.md`).
- Rebasing token used as collateral elsewhere; audit assumes fixed balances.
- Withdrawal queue: no per-request cap, unbounded loop over the queue, or
  finalization that lets a later request jump ahead.
- Slashing not socialized — one validator slash makes the last withdrawer eat it.
- Oracle that reports beacon-chain balance: single reporter, no sanity bound on
  rate change per report (a rogue report can mint infinite shares).

## NFT staking

- `onERC721Received` not implemented → NFTs stuck; or implemented and
  reentrant (`safeTransferFrom` hands control back before state is written).
- Ownership tracked in a mapping but the NFT can be transferred out via a
  different function; or `withdraw` checks `ownerOf` instead of the stake record.
- Rarity/multiplier read at claim time rather than at stake time → user restakes
  after a metadata update.

## Access control & funds

- `recoverERC20` / `sweep` / `inCaseTokensGetStuck` not excluding the staking
  token *and* the reward token → admin drain. Excluding only the staking token
  is still a High.
- `setRewardRate` / `setAllocPoint` with no timelock and no upper bound.
- `pause` that blocks `withdraw` (principal freeze) — should only block `deposit`.
- Migrator function (`setMigrator` + `migrate`) — MasterChef's known rug vector.

## Checklist for the report

1. Table every function → who can call it → does it call `updatePool` first?
2. Solvency invariant: `rewardToken.balanceOf(this) >= sum of unclaimed rewards`
   and `stakeToken.balanceOf(this) >= totalStaked`. Find any path that breaks it.
3. Simulate: 2 users, deposit/withdraw interleaved with a `notifyRewardAmount`,
   with numbers. Rounding and ordering bugs show up here.

## Reference incidents

- MasterChef `add()` without `massUpdatePools` — repeated across dozens of forks.
- Popsicle Finance (2021, $20M): rewards not settled on LP token transfer.
- Grim Finance (2021, $30M): reentrancy on deposit with a fee-on-transfer vault.
- Sushi `migrate` — trusted-migrator rug vector by design.
