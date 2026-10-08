# BountyJudge — escrow and payout fix, verified on chain

| | |
|---|---|
| Network | GenLayer Studio Dev / Studio Next, chain `61997`, GenVM `v0.3.0` |
| Contract | `0xF6B15B728D1EB441E9e8D60E99863f79aFd26E58` |
| Source | `BountyJudge.py`, sha256 `c672bb5b771f915cf69799bdb36a18abd56e5fbb78680dac32c504fa406eba34` |
| On-chain code sha256 | `c672bb5b771f915cf69799bdb36a18abd56e5fbb78680dac32c504fa406eba34` (`gen_getContractCode`) |
| Funder / owner / validator | `0x38409cCa5F5ca70F3fe189638a87862318b478dd` (test account) |
| Worker | `0x68D0CaF57A525AD9146B7dF81c8c5E3871ba7Bf9` (test account) |

This deployment was made with throwaway test accounts to prove the fix. Deploy your own copy from
your own account before resubmitting, and replace the address and hashes above.

## What was wrong

1. `fund_bounty` was `@gl.public.write`, not payable, and read the amount with
   `getattr(gl.message, "value", 0)`. It could not receive GEN.
2. `claim_reward` called `gl.transfer(...)`, which does not exist.
3. The first working replacement, `gl.chain.Account(addr).emit_transfer(amount)`, still paid
   nobody: it emits an *internal* message, and a wallet (EOA) is not an Intelligent Contract. The
   transaction succeeded, the message was emitted, and the contract balance never moved. A wallet
   has to be paid with an *external* transfer through an EVM contract interface.
4. Value sent with a call that reverts is not returned. A first test with a wrong amount left
   1 GEN stuck in the contract. `fund_bounty` therefore never raises once value is attached.

## What changed

- Runner and API moved to GenVM v0.3 (`import genlayer as gl`, `gl.contract.Contract`,
  `gl.nondet.web.render`), the version Studio Dev runs.
- `fund_bounty` is `@gl.public.write.payable` and reads `gl.message.value`. What it cannot escrow
  (unknown or closed bounty, a second funder, an excess) is booked as a credit for the sender.
- `withdraw_credit` returns that credit.
- `claim_reward` updates the books first, then pays with
  `_Wallet(Address(submitter)).emit_transfer(value=amount)`, an external native transfer.
- `refund_bounty`: the funder gets the escrow back, unless an approved submission is waiting.
- `set_bounty_active` is creator-only. The platform owner can no longer freeze someone's escrow.
- `submit_work` requires a funded bounty.
- `prompt_comparative` gets its principle positionally, and the `strict_eq` fallback is gone.
  `principle=` raises `TypeError` in v0.3, so the old code always fell through to `strict_eq`.
- New views: `get_escrow_balance`, `get_credit`.
## Transactions

Balances are in GEN. Contract balance is read with `eth_getBalance`.

| # | Caller | Call | Result | Contract balance | Tx |
|---|--------|------|--------|-----------------:|----|
| 1 | worker | `fund_bounty("99")` with 1 GEN, no such bounty | accepted, 1 GEN credited to the sender | 1 | `0x0bdbbd56769ad0ce424cf59b615f7c7f18e36a3c77c7d6a7f160ae141f526b4f` |
| 2 | worker | `withdraw_credit()` | 1 GEN back in the worker's wallet | **0** | `0x959451e1ec8e9b38a58f875e58d3197478272f13dcb45ec2fa2c856d1ca4b440` |
| 3 | funder | `create_bounty(…, 2 GEN)` | bounty 1 | 0 | `0xfe1e6b7601c28549ab3c9a473894d5a475990f78387219d37398a2f33fde7c0d` |
| 4 | funder | `create_bounty(…, 1 GEN)` | bounty 2 | 0 | `0x64c00ad6601096d3a111f4b8ff81ac72c9439a7686c66a66ec8e7c11c5cb3392` |
| 5 | funder | `fund_bounty("1")` with 2 GEN | escrowed | 2 | `0x0eace0cd5c178c339d00d34b965be03b4c1be22ae9e4e4e0e1f1fc927176be18` |
| 6 | funder | `fund_bounty("2")` with 1 GEN | escrowed | **3** | `0xf420f23c5fd08bc547c6d9b3290ebd850e1d22df1b81e1d86ba97d06862424d8` |
| 7 | worker | `submit_work("1", github.com/dorinalunar/repo)` | submission 1, pending | 3 | `0x8160a580512fb8e56ee110e68beab26830abedf7e605ea243dd817c938de17ee` |
| 8 | validator | `cross_check("1")` | **APPROVED** by consensus | 3 | `0xf6d3c973c195e04f6ca1ba366e3416803f59f797d57361d7b69b845776326fe3` |
| 9 | funder | `refund_bounty("1")` | reverted: `ERR_APPROVED_SUBMISSION_EXISTS` | 3 | `0xf08613594f762de2b845fe125b862e4b9bf355c7b9dc994506e2122b519f464c` |
| 10 | funder | `claim_reward("1")` | **2 GEN paid to the worker** | **1** | `0x2e8b2fd8ac3c1efd0f1d6a4063e2c1e13fe8cabe03c9beabb44c78395d62b00e` |
| 11 | funder | `claim_reward("1")` again | reverted: `ERR_ALREADY_CLAIMED` | 1 | `0x9e6b0dac2ee4c3a81edb0d629f5bef2634e2fc9666744bd8a22437a7f7c207a9` |
| 12 | worker | `refund_bounty("2")` | reverted: `ERR_UNAUTHORIZED` | 1 | `0x72fe80453116c07ba1dd5dfd4f9643c1acd2e03fab5bb0248b76bd0afe4512f3` |
| 13 | funder | `refund_bounty("2")` | **1 GEN back to the funder** | **0** | `0xaaa7be4eda17c8431863b4cb178ad508cb4163017fe0e08b727b4e87d976ae6f` |

Wallet balances around the two payouts (wei):

- worker, step 10: `47899297863749983887` → `49999219232999993416` (+2 GEN, plus a fee refund)
- funder, step 13: `1491997958504499980248` → `1492997832193249979425` (+1 GEN, minus the call's fee)

A payout is applied when the transaction is finalized, a few seconds to a couple of minutes after
it is accepted, so a balance read immediately after `claim_reward` can still show the old value.

## Reproduce

```bash
curl -s -X POST [https://studio-dev.genlayer.com/api](https://studio-dev.genlayer.com/api) -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":["0xF6B15B728D1EB441E9e8D60E99863f79aFd26E58"]}' \
  | python3 -c "import sys,json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(sys.stdin)['result'])).hexdigest())"
shasum -a 256 BountyJudge.py
From a dapp, send the reward with the write itself (genlayer-js 2.x):await client.writeContract({ address, functionName: "fund_bounty", args: ["1"], value: 2n * 10n ** 18n, fees });
