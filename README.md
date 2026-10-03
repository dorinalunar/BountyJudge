<div align="center">
  <img src="logo.svg" alt="BountyJudge Logo" width="200" />
  <h1>BountyJudge</h1>
  <p><b>Automated Web3 Bounty Verification Protocol via GenVM AI Consensus</b></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![GenLayer](https://img.shields.io/badge/Network-GenLayer_Testnet-6366f1.svg)]()
  [![Python](https://img.shields.io/badge/Contract-Python-3776AB.svg)]()
</div>

---

**BountyJudge** is a decentralized protocol built on GenLayer that automates the verification and dispute resolution process for Web3 bounties. By leveraging Python Intelligent Contracts and GenVM's AI consensus, it objectively evaluates submitted evidence (GitHub, X) without human intervention or centralized bias.

## 🌟 Key Features

- **🤖 AI-Driven Consensus:** Utilizes GenVM's LLM nodes (`prompt_comparative` / `strict_eq`) to evaluate bounty submissions deterministically, removing subjective human bias.
- **💰 Escrow Funding & Payouts:** Built-in financial mechanics allow creators to fund bounties (`fund_bounty`), while approved contributors can trustlessly unlock their payouts (`claim_reward`).
- **🛡️ Strict Security Validations:** Enforces robust URL parsing (`urllib.parse`) to prevent domain spoofing, alongside string sanitization and evidence truncation guards to ensure contract stability.
- **💻 Comprehensive dApp:** A fully responsive frontend featuring an integrated on-chain terminal, transaction logs, escrow management, and a unified validator dashboard.

## 🏗 Architecture & Tech Stack

- **Smart Contract:** Python (GenLayer Intelligent Contract via `py-genlayer` SDK)
- **Consensus Mechanism:** GenVM Nondeterministic AI Execution
- **Frontend:** Vanilla JavaScript, HTML5, CSS3 (No build steps required)
- **Network:** GenLayer Studio Testnet

## 📁 Repository Structure

- `BountyJudge.py` — The core Intelligent Contract handling state, escrow logic, roles, and AI consensus.
- `main.js` — Application logic handling ABI mapping, wallet connection, and RPC interactions.
- `index.html` — The frontend user interface.
- `logo.svg` — Project branding asset.

## 📝 Smart Contract Interface

The `ProofBountyJudge` contract implements a robust state management system. Core methods include:

**Bounty & Escrow Management:**
- `create_bounty` — Initialize a new bounty with criteria and reward amount.
- `fund_bounty` — Deposit escrow funds for a specific bounty.
- `set_bounty_active` — Toggle bounty availability.

**Submissions & Rewards:**
- `submit_work` — Submit a proof URL (strictly validated against allowed domains).
- `claim_reward` — Claim the escrowed payout upon receiving an `APPROVED` status.

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
   Click **Connect Wallet** to automatically configure and connect to the GenLayer Testnet, then begin interacting with the smart contract.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.