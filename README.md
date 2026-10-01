# BountyJudge

<div align="center">
  <img src="logo.svg" alt="BountyJudge Logo" width="200" />
</div>

<br />

**BountyJudge** is a decentralized GenLayer platform for verifying Web3 bounties. It uses Python Intelligent Contracts and GenVM AI consensus to automatically and objectively evaluate evidence (GitHub, X) without human intervention.

## 🌟 Key Features

- **🤖 AI-Driven Consensus:** Utilizes GenVM's LLM nodes to evaluate bounty submissions deterministically, removing subjective human bias.
- **🏆 Decentralized Bounties:** Anyone can create, manage, and define acceptance criteria for on-chain tasks.
- **🔒 Secure Validation:** Includes strict domain whitelisting (GitHub, X, Etherscan), string sanitization, and evidence truncation guards to ensure contract stability.
- **💻 Interactive dApp:** A premium, fully responsive frontend featuring an integrated on-chain terminal, transaction logs, and a unified validator dashboard.

## 🏗 Architecture & Tech Stack

- **Smart Contract:** Python (GenLayer Intelligent Contract via `py-genlayer` SDK)
- **Consensus Mechanism:** GenVM Nondeterministic AI Execution & Equivalence Principle (`prompt_comparative` / `strict_eq`)
- **Frontend:** Vanilla JavaScript, HTML5, CSS3
- **Network:** GenLayer Testnet

## 📁 Repository Structure

- `BountyJudge.py` - The core Intelligent Contract handling state, roles, and AI consensus logic.
- `main.js` - Application logic handling ABI mapping, wallet connection, and contract interactions.
- `index.html` - The frontend user interface.
- `logo.svg` - Project branding asset.

## 🚀 Getting Started

Since the frontend is built with vanilla web technologies, running the dApp locally is incredibly simple:

1. Clone the repository: `git clone https://github.com/dorinalunar/BountyJudge.git`
2. Navigate to the project folder: `cd BountyJudge`
3. Open `index.html` in any modern web browser.
4. Click **Connect Wallet** to connect to the GenLayer testnet and start interacting with the platform.

## 📝 Smart Contract Details

The `ProofBountyJudge` contract implements a robust state management system for platform stats, bounty tracking, and submission validation. Key contract methods include:
- `create_bounty` & `submit_work`
- `add_validator` & `remove_validator`
- `cross_check` & `cross_check_batch` (Triggering AI evaluation)

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
