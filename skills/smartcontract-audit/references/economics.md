# Value Accounting & Design Review

The rest of `references/` asks *"can this be exploited?"*. This file asks a
different question, and in protocols that distribute value it usually finds the
larger problem:

> **Where does every unit of value end up, and does that match what the design
> claims?**

Code can be free of exploitable bugs and still route value to the wrong party,
or leave value permanently unreachable. Both belong in the report, but they are
not the same kind of finding:

- **Value-extraction** — a privileged party can take or destroy value that
  belongs to participants. This is a security finding with a normal severity.
  It does not matter whether anyone has used the lever yet.
- **Unreachable value** — nobody takes anything, but the shape of the design
  leaves capital that participants can never get back. This is a *design*
  finding. Report it with a computed number, a stated method, and a concrete
  alternative — never as an adjective.

---

## 1. Build the value map first

Before reading for bugs, write down where value goes. Answer each of these with
a number read from the deployed parameters, not from the documentation:

1. Total units in play — supply, raise, deposits. What are the slices?
2. How much reaches participants as something they can actually trade or redeem?
3. How much is placed as liquidity or reserve — and how much of *that* is
   reachable given the finite size of the float (§3)?
4. How much reaches a privileged party, at what cost to them, and can they
   realise it immediately or is it locked/vested?
5. What is the true round-trip cost, counting **every** fee, including any
   folded into a quote function rather than charged as a visible fee?
6. At each state transition, what is the remainder, and where does it go?

Put the answers in an appendix table in the report. Every economic sentence in
the report must trace back to a row in that table.

### Patterns worth a finding

- **Residual sweep at a transition.** Sending `balanceOf(address(this))` to an
  admin-controlled address at the end of a migration, graduation or settlement
  is a distribution sized by whatever happens to be left over. It is not a
  disclosed fee. Two things make it worse: the recipient is mutable, and the
  size depends on parameters the same party controls (§2). Correct designs
  **burn** the remainder or **lock it as liquidity**. A genuine protocol cut
  should be a fixed, disclosed, vested percentage.
- **Stacked fee paths.** A fee folded into the pricing function *plus* a
  separate configurable fee means the advertised rate is not the real rate, and
  setting the visible fee to zero does not make trading free. If the emitted
  event carries only the post-fee amount, integrators cannot discover the
  difference. Report it as a transparency finding even when nothing is stolen.
- **Allocations absent from the public documentation.** Compare the code's
  distribution against whatever the project tells users. A mismatch is a finding
  regardless of which one is more generous.
- **A value sink that is a single mutable address.** On its own this is a
  governance finding; combined with either pattern above the severity rises.

---

## 2. Parameter binding: global mutable vs. per-item snapshot

The highest-severity structural pattern in factory-style contracts (launchpads,
vault factories, market creators):

> Pricing or settlement parameters live in **global** storage, are read at
> settlement time, and can be changed by an admin — so a single transaction
> retroactively reprices, strands, or force-settles **every** item the contract
> has ever created.

For each parameter that influences pricing, settlement or distribution, answer:

- Is it **snapshotted into the item's own struct at creation**, or read live
  from a global?
- Who can change it, within what bounds, after what delay?
- What happens to items already mid-life when it changes? Note this is a finding
  even for an *honest* change made for a new item — cross-item corruption does
  not require malice, and it is easy for a team to miss.
- Can changing it, in the same transaction as a settlement, **increase the
  changer's own share**? That combination is the difference between a
  misconfiguration and a deliberate lever, and it should be rated accordingly.
- Can it be set so that a required condition becomes unsatisfiable — a threshold
  raised above anything reachable, a divisor pushed to zero? Then it is also the
  permanent-freeze case from `arithmetic.md`, arrived at through economics.

**The remediation is the same shape every time**, and the recommendation should
say all four parts: snapshot the parameters per item at creation; read the
snapshot everywhere downstream; bound every setter; make setters apply only to
items created afterwards.

### Adjacent levers to enumerate every time

- **Unbounded fee setter.** At the denominator the fee takes the entire trade;
  above the denominator the subtraction underflows and every trade reverts
  protocol-wide. Cap it in code (a hard `require` on the setter), and add
  `require(amountOut > 0)` so a fully-consumed trade cannot succeed silently.
- **Single-key, one-step, zero-address-unguarded admin.** Two-step transfer,
  explicit non-zero check, separate the parameter role from the value sink,
  multisig plus timelock on both.
- **Trusting a permissionless external primitive during settlement.** If the
  settlement path reads the state of something anyone can create first — a pool,
  a market, a registry entry — that state can be pre-set adversarially so the
  settlement's own slippage check fails, blocking it indefinitely for the cost of
  one transaction. Either create-and-initialise inside the settlement path, or
  validate the external state against an internally-derived value before
  trusting it. If the team controls that factory, gating creation is the
  cheapest fix.

---

## 3. Reachable liquidity

Value can be lost with nobody taking it. The common case in AMM settlements:

**Liquidity provided across an unbounded price range.** A concentrated-liquidity
position minted at the extreme ticks spreads the quote asset from zero to
infinity. The token float is finite, so selling the entire float moves the price
only so far — and every unit of quote asset sitting below that point is
unreachable. Participants cannot withdraw it, and no attacker holds it. It is
simply gone, as a consequence of the position's shape.

### Quantify it or don't claim it

Do not write "a significant portion is stranded". Compute it:

1. Read the real settlement parameters: quote raised, tokens placed, float size,
   settlement price.
2. Using the standard amounts-for-liquidity relations, compute the quote asset
   remaining in the position after a range of sell-pressure scenarios — the whole
   float, the float plus any privileged allocation, and a multiple of the float.
3. Tabulate remaining and unreachable-percentage per scenario, and state which
   relations you used.

| Sell-pressure scenario | Quote remaining | Unreachable share |
|---|---|---|
| Entire float sold | *computed* | *computed* |
| Float + privileged allocation sold | *computed* | *computed* |
| Multiple of float sold | *computed* | *computed* |

Report the numbers you computed for *this* deployment. Do not carry a percentage
over from another protocol or another review — the answer depends entirely on
the ratio of the raise to the float and on where the range ends.

### The alternative, and why one change does several things

A position with a **bounded lower tick** is, algebraically, a constant product
with a constant offset added to the quote side. Because the price curve
terminates at a finite lower bound instead of asymptoting to zero, the quote
asset stays withdrawable all the way down to that bound. The same single change
yields three effects:

- unreachable capital falls to a small geometric residue plus accrued swap fees;
- depth increases for the same deposited value, because liquidity is packed into
  the band where trading actually happens, which reduces slippage proportionally;
- the token acquires a genuine lower price bound rather than trending to zero.

Choosing the lower bound is an off-chain calibration, fixed as an `immutable` at
deployment. The condition to solve is: *the range's token capacity between the
settlement price and the lower bound should equal the circulating float* — so
the float is exactly able to traverse the range. Derive the bound from the
standard tick relation between price and tick index, rounded to the pool's tick
spacing. Then have the contract **prove the calibration at runtime**:

- the quote leg must bind exactly, with no unexpected refund;
- the range must absorb the entire float down to the bound, within a small
  tolerance band;
- the token leg must be a sensible fraction of the float.

Recommend all three guards together. Their purpose is that a mis-derived
parameter reverts loudly at settlement instead of silently reproducing the
original problem.

A compounding note worth making explicitly in the report: any remainder that was
being swept to an admin address (§1) can instead be placed into the same locked
position, which removes the allocation and deepens the book in one change rather
than two.

---

## 4. Comparison with alternatives

A computed number persuades more when the reader can place it. Where the
protocol sits in a category with well-known alternatives, add a comparison of
**structural properties**, not opinions:

- how the alternative handles the remainder at settlement,
- whether its parameters are per-item or global,
- whether liquidity is bounded or unbounded,
- whether any privileged party holds an unlocked allocation.

Rules that keep this honest:

- Every cell must be sourced — public documentation, on-chain parameters, or a
  published post-mortem. Never estimate a competitor's number to strengthen a point.
- If you use a composite score, publish how it is computed, or drop the score
  and keep the structural columns.
- Keep any post-remediation figure in a clearly separate column and label it a
  projection.
- Compare to designs, not to teams. The report is about mechanisms.

---

## 5. Sequencing the fixes

A flat list of fixes leaves the team to guess the order. Close the report with
sequenced stages, where the first stage is a **precondition**: while anything in
it is open, the contract should not hold user funds.

| Stage | Concern | Typically closes |
|---|---|---|
| **1 — precondition** | Value extraction and permanent freeze | the Critical/High findings where a privileged party, or an attacker, can take or lock participant value |
| **2** | Governance | multisig and timelock on privileged setters, two-step role transfers, checked calls or pull payments, one transparent fee path |
| **3** | Distribution | per-address caps, launch-window protection, and anything else where the code's allocation differs from the stated one |
| **4** | Capital efficiency | the structural change from §3 |

List the finding ids each stage closes, so the mapping back to the register is
explicit and the team can verify completion.

---

## 6. Keeping this kind of section credible

- **Every number carries its derivation.** Parameters in an appendix, method
  named (on-chain read, closed form, simulation), so the team can reproduce it
  and disagree with it on the merits.
- **Separate measured from projected.** Anything about the post-fix state is a
  projection and must be labelled one.
- **Distinguish "unfair" from "exploitable".** Say plainly which findings are
  security issues and which are design or transparency issues. Conflating them
  is the fastest way for a team to dismiss the whole report.
- **Show the diff for the structural change.** For the one change that matters
  most, a `- old` / `+ new` block beats several paragraphs — the report
  generator's `code` / `fix` fields render exactly this.
- **State the limits of your own conclusions.** Advisory, scoped to the code and
  commit reviewed, not a warranty; residual risk stays with the team.

---

## 7. Curve-based sale contracts — specific checks

For bonding curves, presales, and any contract that sells along a price function
before settling into a market:

- **Virtual reserve semantics.** Is the virtual portion ever backed by real
  assets? If settlement never occurs, is the real portion still recoverable?
- **Settlement threshold.** Reachable at the current parameters? Who can move
  it, and does moving it strand in-flight items? (§2 and `arithmetic.md`.)
- **Quote and fee.** One fee path or several? Does the emitted event carry the
  true cost, including anything folded into the quote?
- **The pre-settlement exit must work for contracts, not just EOAs.** If the
  refund or sell path pays out with a fixed 2300-gas stipend, every vault,
  aggregator and smart-contract wallet that bought in is trapped with no exit.
  Use a checked call with checks-effects-interactions. See `gas.md`.
- **A value sink that can revert** blocks every path that pays it — often
  creation and purchase, i.e. the whole product. Pull payments, or a checked call
  whose failure does not revert the user's action.
- **Distribution protection.** Without a per-address cap or a launch window, the
  opening block belongs to bots. Whether that matters is a product decision, but
  it should be a stated one.
- **Recovery path** when settlement becomes impossible: gated, conditioned on a
  provable precondition (a timeout, or demonstrably blocking external state),
  and event-emitting.
- **The settlement mint's own slippage floor** is a denial-of-service surface
  whenever the price it checks against can be pre-set by anyone (§2).

## Background reading

| Topic | Where | For |
|---|---|---|
| Concentrated liquidity math | https://github.com/Uniswap/v3-core · https://github.com/Uniswap/v3-periphery | The amounts-for-liquidity and tick/price relations every bounded-range calculation needs. |
| Uniswap V3 whitepaper | https://uniswap.org/whitepaper-v3.pdf | The derivation behind those relations, including the virtual-reserve offset. |
| Curve-sale → concentrated settlement, in production | https://github.com/MeteoraAg/dynamic-bonding-curve | A worked design for settling a curve sale into a concentrated position with locked liquidity. Read it for the design; the code is Solana/Anchor. |
| Share and first-depositor math | `references/liquidity.md` | The other place rounding and reachability interact. |
| Launchpad access control | `references/misc.md` | The non-economic half of the same contract. |
