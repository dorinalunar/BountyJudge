<div align="center">
  <img src="logo.svg" alt="BountyJudge Logo" width="200" />
  <h1>BountyJudge</h1>
  <p><b>Automated Web3 Bounty Verification Protocol via GenVM AI Consensus</b></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![GenLayer](https://img.shields.io/badge/Network-Studio_Dev-6366f1.svg)]()
  [![GenVM](https://img.shields.io/badge/GenVM-v0.3.0-059669.svg)]()
  [![Python](https://img.shields.io/badge/Contract-Python-3776AB.svg)]()
</div>

---

**BountyJudge** is a decentralized protocol built on GenLayer that automates the verification and dispute resolution process for Web3 bounties. By leveraging Python Intelligent Contracts and GenVM's AI consensus, it objectively evaluates submitted evidence (GitHub, X) without human intervention or centralized bias.

## 🌟 Key Features

- **🤖 AI-Driven Consensus:** Utilizes GenVM v0.3 LLM nodes (`prompt_comparative`) to evaluate bounty submissions deterministically, removing subjective human bias.
- **💰 Native Token Escrow & Secure Payouts:** Built-in financial mechanics allow creators to lock physical native tokens in escrow (`fund_bounty` via `@gl.public.write.payable`). Approved contributors receive actual token payouts directly to their EOAs (`claim_reward` via external `_Wallet(Address).emit_transfer()`).
- **🛡️ Refund & Credit Mechanics:** Prevents stranded funds. Overpayments or invalid funding attempts are recorded in a local credit ledger and can be safely retrieved via `withdraw_credit`. Unclaimed bounties can be refunded via `refund_bounty`.
- **🌐 Strict Security Validations:** Enforces robust URL parsing (`urllib.parse`) to prevent domain spoofing, alongside string sanitization and evidence truncation guards to ensure contract stability.
- **💻 Comprehensive dApp:** A fully responsive frontend featuring an integrated on-chain terminal, transaction logs, escrow/refund management, and a unified validator dashboard.

## 🏗 Architecture & Tech Stack

- **Smart Contract:** Python (GenLayer Intelligent Contract via `py-genlayer` SDK)
- **Consensus Mechanism:** GenVM v0.3.0 Nondeterministic AI Execution
- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (No build steps required)
- **Network:** GenLayer Studio Dev / Studio Next (Chain ID: 61997)
- **Contract Address:** `0xF6B15B728D1EB441E9e8D60E99863f79aFd26E58`

## 📁 Repository Structure

- `BountyJudge.py` — The core Intelligent Contract handling state, native token escrow logic, roles, and AI consensus.
- `main.js` — Application logic handling wallet connection, RPC interactions, and network switching.
- `index.html` — The frontend user interface.
- `test_bounty_judge.py` — Unit test suite mocking GenVM v0.3.0 dependencies and physical transfers.
- `BountyJudge_ONCHAIN_PROOF.md` — Documented on-chain transaction logs proving the escrow/payout architecture.
- `logo.svg` — Project branding asset.

## 📝 Smart Contract Interface

The `ProofBountyJudge` contract implements a robust state management system. Core methods include:

**Bounty & Escrow Management:**
- `create_bounty` — Initialize a new bounty with criteria and reward amount.
- `fund_bounty` — (Payable) Physically deposit native tokens into the contract's escrow. Excess funds or invalid deposits are safely credited back.
- `set_bounty_active` — Toggle bounty availability (creator only).

**Submissions, Rewards & Refunds:**
- `submit_work` — Submit a proof URL (strictly validated against allowed domains).
- `claim_reward` — Execute a physical external token transfer to claim the escrowed payout upon receiving an `APPROVED` status.
- `refund_bounty` — Allows the creator to reclaim their escrow if no approved submission is waiting.
- `withdraw_credit` — Retrieve any tokens that could not be escrowed during funding.

**Validation & Consensus:**
- `cross_check` / `cross_check_batch` — Trigger GenVM AI validators to assess evidence.
- `add_validator` / `remove_validator` — Admin controls for validator node management.

## 🚀 Getting Started

Since the frontend is built with vanilla web technologies, running the dApp locally is completely frictionless:

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/dorinalunar/BountyJudge.git](https://github.com/dorinalunar/BountyJudge.git)
   cd BountyJudge
   ```
2. **Launch the dApp:**
   Open `index.html` in any modern web browser.
3. **Connect & Interact:**
   Click **Connect Wallet**. The dApp will automatically prompt you to add and switch to the **GenLayer Studio Dev** network (Chain 61997), then you can begin interacting with the smart contract.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.