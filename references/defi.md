# DeFi Protocols

Covers: lending/borrowing, CDP/stablecoins, yield vaults & strategies,
perps/derivatives, bridges. (AMMs → `swap.md`, LP accounting → `liquidity.md`.)

## Oracle & pricing — the single largest loss category

- **Spot price from an AMM** (`getReserves`, `balanceOf`, `getAmountOut`) as a
  valuation source → flash-loan manipulable. Critical whenever it prices
  collateral, mints, or liquidations.
- **Chainlink checklist**: `updatedAt` staleness vs a per-feed heartbeat (not a
  hardcoded 1 day for every feed), `answer > 0`, `answeredInRound >= roundId`
  (deprecated but still seen), `latestRoundData` not `latestAnswer`,
  min/maxAnswer circuit-breaker bounds (the LUNA case: feed floored at $0.10
  while the real price was $0.00001), correct `decimals()` per feed, and the
  **L2 sequencer uptime feed + grace period** on Arbitrum/Optimism/Base.
- TWAP window shorter than the cost to manipulate; Uniswap V3 `observe` with a
  cardinality that was never increased → the TWAP is effectively spot.
- Mixing price sources with different decimals or different quote assets
  (ETH-denominated vs USD-denominated) in one formula.
- LP token priced as `totalValue / totalSupply` using spot reserves →
  manipulable; use the fair-reserves (Alpha Homora) formula.
- No deviation bound between two oracles; no fallback when the primary reverts —
  and conversely, a fallback that is *worse* than the primary is a downgrade attack.

## Lending / borrowing

**→ `lending.md`** — interest accrual, health factors, collateral caps,
liquidation, receipt-token donation attacks and bad debt are covered in full
there. Load it instead of this section for any borrowing protocol.

## Vaults & strategies

- `harvest`/`compound` callable by anyone and sandwichable (the strategy's swap
  has no `minAmountOut`, or `minAmountOut = 0`) → MEV extracts the yield.
- Strategy reports `estimatedTotalAssets()` from spot LP value → share price
  manipulable during `deposit`/`withdraw`.
- Withdrawal that pulls from the strategy incurs a loss not charged to the
  withdrawer → socialized onto remaining depositors.
- Emergency/`sweep` on the want token; strategy migration with no timelock.
- Fee on profit computed on gross rather than net of losses; performance fee
  charged on principal after a loss (high-water mark missing).
- See `token.md` ERC-4626 section for share rounding and inflation.

## CDP / stablecoin

- Mint fee/stability fee accrual not applied before a redemption.
- Redemption at a fixed $1 while the collateral oracle is stale → free money.
- Peg arbitrage path that lets the last redeemer take good collateral and leave
  bad (no pro-rata basket redemption).
- Liquidation auction: no minimum bid decay bound, no `keeper` incentive,
  auctions that can be won at ~0 during network congestion (Black Thursday, MakerDAO 2020).

## Perps / derivatives

- Funding rate computed with `block.number`; skew/imbalance overflow.
- Mark price = index price with no bound → oracle manipulation drains the vault
  (GMX-style: audit the max-position and OI caps).
- PnL settlement rounding that mints value; no cap on total OI vs pool size.

## Bridges

- Message verification: signature threshold, replay protection (`chainId` +
  `nonce` + source contract in the digest), and a per-token mint cap.
- `receiveMessage` trusting `msg.sender` being the relayer without verifying the
  source chain/address (Nomad, Wormhole class).
- Rate limits absent — a single verification bug becomes unlimited mint.

## Flash loans

- Any function reading a manipulable value must be flash-loan-safe. Test every
  price/share/rate read by asking: "can I move this within one transaction?"
- Fee rounding to 0 for small loans; reentrancy back into `flashLoan` itself.
- Governance voting power counted from a flash-loanable balance → snapshot at a
  past block (`ERC20Votes`), never `balanceOf` now.

## Reference incidents

- Cream Finance (2021, $130M): manipulated yUSD price via donation.
- Mango Markets (2022, $114M): thin-market oracle manipulation → over-borrow.
- Euler (2023, $197M): donation to a self-liquidatable position, missing health
  check after `donateToReserves`.
- Compound-fork empty-market donation attacks (Hundred, Midas, Onyx).
- MakerDAO Black Thursday (2020): zero-bid auctions under congestion.
