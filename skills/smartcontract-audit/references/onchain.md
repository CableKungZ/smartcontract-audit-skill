# On-Chain State Verification

**Load this whenever the contract is already deployed and an address is known.**

The audit reads source; the money sits behind state. Who holds `owner` *today*,
what the proxy actually points at, whether the deployed bytecode is the source
you read, what the bridge's verifier config is set to — none of that is in the
repo, and every one of them has been the whole story in a real incident.

If no address was given, skip this file and write one sentence in Scope: *source
only; on-chain state, deployed bytecode and role holders were not verified.*
That sentence is the finding when it is missing.

All commands are Foundry's `cast`. Set the RPC once:

```bash
export ETH_RPC_URL=https://...          # or cast --rpc-url ... on each call
A=0xTheContract
```

---

## 1. Is the deployed code the code you audited?

```bash
cast code $A | wc -c                     # 2 = no code at all (EOA or not deployed)
cast codehash $A
forge build && cast keccak $(jq -r .deployedBytecode.object out/X.sol/X.json)
```

Then open the address on the explorer and check whether the source is verified
there at all, and whether it is the same source you were given.

- Build the repo at the audited commit with the **same** solc version, optimizer
  setting and runs, and compare the runtime bytecode (metadata hash at the tail
  differs by design — compare the prefix, or build with `--no-metadata`).
- A mismatch means you audited something else. Stop and say so; it outranks
  every other finding in the report.
- Unverified source on the explorer is itself worth reporting: users cannot
  check what you checked.

## 2. Proxy: what is actually behind it?

ERC-1967 slots, readable directly:

```bash
# implementation: keccak256("eip1967.proxy.implementation") - 1
cast storage $A 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
# admin: keccak256("eip1967.proxy.admin") - 1
cast storage $A 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
# beacon: keccak256("eip1967.proxy.beacon") - 1
cast storage $A 0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50
```

- Is the implementation the contract you audited, or something else?
- Is the admin an EOA, a multisig, or a timelock? **`cast code <admin>`** — an
  admin with no code is an EOA, whatever the docs claim.
- Is the implementation itself initialized? An uninitialized implementation is
  the Kinto/Parity class (`postmortems.md` §6):
  `cast call <impl> "owner()(address)"` returning the zero address on a
  contract that has an `initialize` is the live version of that finding.
- UUPS: does `_authorizeUpgrade` gate on a role that is actually held?

## 3. Roles and their real holders

```bash
cast call $A "owner()(address)"
cast call $A "pendingOwner()(address)"
cast call $A "paused()(bool)"
cast call $A "hasRole(bytes32,address)(bool)" $ROLE $WHO
cast call $A "getRoleMemberCount(bytes32)(uint256)" $ROLE
cast call $A "getRoleAdmin(bytes32)(bytes32)" $ROLE
cast keccak "MINTER_ROLE"                       # role ids are keccak of the name
```

For each holder found:

```bash
cast code <holder> | wc -c                       # 2 => EOA
cast call <holder> "getThreshold()(uint256)"     # Safe
cast call <holder> "getOwners()(address[])"      # Safe
cast call <holder> "getMinDelay()(uint256)"      # OZ TimelockController
```

**The table the report must contain** — this is the centralization pass with
real addresses instead of assumptions:

| Role | Address | EOA / multisig / timelock | Threshold | Delay | Loss if compromised today |
|---|---|---|---|---|---|

An EOA in that table that can move user funds is High or Critical on its own,
whatever the source review said. Remember EIP-7702: an EOA holding a role may
already be delegated to a contract (`postmortems.md` §7) — `cast code` on it
returns the delegation designator if so.

## 4. Parameters as configured, not as coded

Read every setter's current value and compare against the source's defaults and
its documented intent — fees, caps, rates, oracles, token addresses, treasury:

```bash
cast call $A "feeBps()(uint256)"
cast call $A "rewardRate()(uint256)"
cast call $A "oracle()(address)" && cast call <oracle> "decimals()(uint8)"
cast call $A "totalSupply()(uint256)"
```

- A fee set above the source's documented maximum means the cap is missing or
  was raised — find which.
- An oracle address that is not the one in the deploy script, a token address
  that is not the canonical one: both are findings, and both are invisible in
  source review.
- Immutables are baked into bytecode, not storage: read them through their
  getters, and confirm they match what the constructor was called with
  (`cast tx <deploy-tx>` for the args).

## 5. Cross-chain / messaging configuration

`postmortems.md` §5 asks for this — here is how to actually read it. For
LayerZero endpoints:

```bash
cast call $ENDPOINT "getConfig(address,address,uint32,uint32)(bytes)" \
     $LIB $A $EID $CONFIG_TYPE
cast call $A "peers(uint32)(bytes32)" $EID       # OApp trusted remote
```

- Number of required DVNs / verifiers, and the threshold. **1-of-1 is Critical.**
- Whether the app set its own config or inherited the endpoint default (the
  default can change without the app doing anything).
- The trusted-remote / peer mapping for every chain the protocol lives on.
- Any inbound rate limit, and its current window and cap. No rate limit on an
  inbound mint path is High even when verification looks sound.

## 6. Balances vs accounting

The solvency invariant, checked against the chain rather than the source:

```bash
cast call <token> "balanceOf(address)(uint256)" $A
cast call $A "totalStaked()(uint256)"            # or totalAssets/totalSupply
```

- Held balance must cover every obligation the contract records. A shortfall
  today is an incident, not a finding — escalate immediately.
- An excess is worth a line too: donated tokens are the input to the
  exchange-rate attacks in `postmortems.md` §4.

## 7. History

```bash
cast logs --address $A "OwnershipTransferred(address,address)" --from-block 0
cast logs --address $A "Upgraded(address)" --from-block 0
cast logs --address $A "Paused(address)" --from-block 0
```

- Every past upgrade: was there a window where the implementation was something
  else? Users who interacted then were exposed to code nobody audited.
- Ownership transfers to and from EOAs, and how long each held it.
- A pause that was used tells you an incident already happened — ask.

---

## What goes in the report

1. The bytecode-vs-source verdict, in the method section, in one sentence.
2. The roles table from §3, in the centralization finding.
3. The configured-parameter table from §4 where any value differs from the
   source's default or the documentation.
4. The messaging config from §5 for any cross-chain contract, including the
   verifier threshold as a number.
5. The block number everything was read at — on-chain state moves, and a report
   without a block height is not reproducible.
