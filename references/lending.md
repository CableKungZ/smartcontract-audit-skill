# Lending / Borrowing Protocols

Covers: pooled lending (Aave/Compound-style), isolated-pair lending (Morpho
Blue, Fraxlend), CDP/stablecoin vaults (Maker, Liquity), and any contract that
lets a user borrow against collateral.

Read `defi.md` alongside this file — the oracle section there is the single
largest source of losses in this category and is not repeated here.

## Interest accrual

- **`accrueInterest()` / `updateState()` not called at the top of every
  user-facing function.** Any path that reads or writes a balance without
  settling first uses a stale index. Check *all* of: `supply`, `withdraw`,
  `borrow`, `repay`, `liquidate`, `transfer` of the receipt token,
  `setInterestRateModel`, `addReserves`, and every view used for a health check.
- Index applied **after** the state change instead of before → the borrower
  gets a free block of interest, or is charged for a block they didn't hold.
- `borrowIndex` growth computed from `block.number` — wrong across chains and
  L2s; use `block.timestamp`. On Arbitrum `block.number` is an L1-ish value and
  will badly under-accrue interest.
- Compounding done with a linear approximation over long gaps without bound
  (`rate * dt` where `dt` can be months after an idle market) — either cap `dt`
  or use a proper exponent.
- Interest-rate model: division by `totalBorrows == 0`; utilization > 1e18 when
  reserves are counted twice; kink math overflowing at extreme utilization;
  `borrowRate` unbounded above (a rate spike bricks repayment through overflow).
- Reserve factor taken from interest but not excluded from `totalSupply`-backed
  cash → the last withdrawer is short.

## Collateral & health factor

- Health computed **before** the state change, or with cached prices from
  earlier in the transaction.
- Health checked only on the borrowed asset, not after a *withdrawal* of
  collateral, or not after a *transfer* of the collateral receipt token
  (aToken/cToken transfers must re-check the sender's health).
- Collateral factor / LTV per asset with no cap, settable instantly by an admin
  → an admin (or a compromised key) makes every position instantly liquidatable
  or instantly over-borrowable. Needs a timelock and a hard upper bound.
- A newly listed collateral asset with no supply cap and a thin oracle is the
  standard path to protocol insolvency. Verify: supply cap, borrow cap,
  isolation mode, and an oracle whose manipulation cost exceeds the cap.
- Same asset used as both collateral and borrow with no restriction →
  self-borrow leverage loops that amplify any pricing error.
- Collateral that can be frozen by a third party (USDC blocklist, a KAP-20
  `adminTransfer`, a pausable token) — a frozen collateral asset means positions
  cannot be liquidated. See `kub.md` for the KAP case specifically.

## Liquidation

- **Liquidation bonus too large** relative to the close factor → liquidating
  pushes the position *further* underwater, creating bad debt out of a healthy-
  ish position. Model it: after seizing `debt * (1 + bonus)` of collateral, is
  the remaining position's health better or worse?
- **No close factor cap** → a whale position is liquidated 100% in one tx,
  maximizing the borrower's loss and the MEV opportunity.
- **Fully-underwater positions cannot be liquidated** (the seize math reverts
  when collateral < debt) → bad debt is never cleared and silently accrues onto
  the last withdrawers. There must be an explicit bad-debt path: socialize the
  loss across suppliers, or absorb it into a reserve/backstop.
- **Self-liquidation profitable**: borrower liquidates their own position to
  capture the bonus. Usually acceptable, but confirm it can't be combined with a
  flash loan to extract more than it costs.
- Liquidation callable in the same block as the price update, with the price
  coming from a manipulable source → attacker moves the price, liquidates,
  moves it back (Mango, Cream class).
- Small-position dust: liquidating a $1 position costs more gas than the bonus,
  so nobody does → dust positions accumulate as bad debt. Enforce a minimum
  borrow size.
- Liquidation blocked while the protocol is paused, but interest keeps accruing.
- Auction-based liquidation (Maker/Liquity style): bid decay with no floor,
  no keeper incentive, and winnable at ~0 during congestion — this is exactly
  MakerDAO Black Thursday (2020).

## Receipt / share tokens (cToken, aToken, debt tokens)

- **Exchange-rate donation attack** on an empty market: attacker mints 1 wei of
  cToken, donates the underlying directly, `exchangeRate` inflates, later
  depositors round to 0 shares — then borrows against the inflated collateral
  value. This is the Compound-V2-fork bug that took Hundred Finance, Midas and
  Onyx. Mitigation: seed the market atomically at listing, or use virtual
  shares. See `liquidity.md` for the general form.
- Rounding direction: minting shares rounds **down**, redeeming rounds
  **down** on the underlying — always against the user. One inversion plus a
  loop drains the reserve.
- Debt tokens must be non-transferable, or transferring debt bypasses the health
  check.
- `transfer` of the collateral receipt not re-checking the sender's health.

## Flash loans & atomic composition

- Every value the protocol reads must be asked: *can an attacker move this
  within one transaction?* Reserves, spot prices, share prices, total supply,
  and governance voting power all can.
- Reentrancy back into `borrow`/`liquidate` from inside a flash-loan callback,
  or from an ERC777/ERC677 underlying.
- **Donation-to-self**: Euler (2023, $197M) — `donateToReserves` made the
  caller's own position liquidatable without a health check, then they
  self-liquidated at a discount. Any function that changes a position's health
  must end with a health assertion, no exceptions.
- Fee rounding to zero on small flash loans; `flashLoan` reentering itself.

## Governance & admin

- Voting power from `balanceOf` at call time → flash-loanable. Use
  `ERC20Votes`/checkpointed snapshots at a past block.
- `setPriceOracle`, `supportMarket`, `setCollateralFactor`, `setInterestRateModel`
  with no timelock — list each one as a centralization finding with the loss on
  compromise stated.
- Pause that blocks `repay` or `liquidate` (not just `borrow`) → positions
  cannot be saved and bad debt grows during the pause.
- Reserve withdrawal (`reduceReserves`) that can dip into supplier cash.

## Checklist

1. Solvency invariant in one line:
   `cash + totalBorrows >= totalSupplyUnderlying + reserves`. Find the path
   that breaks it.
2. For every function: does it call `accrueInterest()` first, and does it end
   with a health check if it touched a position?
3. Write the full liquidation with numbers: a position at 101% health, price
   drops 10%, who calls what, what does the liquidator get, what is the
   position's health afterwards?
4. Empty-market scenario, written with numbers, always.

## Reference incidents

- Euler Finance (2023, $197M) — missing health check after `donateToReserves`.
- Mango Markets (2022, $114M) — thin-market oracle manipulation → over-borrow.
- Cream Finance (2021, $130M) — manipulated yUSD collateral price.
- Hundred Finance / Midas / Onyx — Compound-fork empty-market donation attack.
- MakerDAO Black Thursday (2020) — zero-bid liquidation auctions under congestion.
- Venus / BNB (2021) — oracle spike on a thin market → $100M+ bad debt.
