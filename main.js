import { createClient } from "https://esm.sh/genlayer-js";
import { studionet } from "https://esm.sh/genlayer-js/chains";

// Updated Contract Address for GenLayer Studio Dev
const CONTRACT_ADDRESS = "0xc1f999c0a23901c5A0Bb1388d99fa109a30fd7Db";
const CHAIN_ID_HEX = "0xf22d"; // 61997 in hex
const RPC_URL = "https://studio-dev.genlayer.com/api";

const studioChain = {
  ...studionet,
  id: 61997,
  name: "GenLayer Studio Dev",
  rpcUrls: {
    default: { http: [RPC_URL] },
    public: { http: [RPC_URL] }
  }
};

const readClient = createClient({
  chain: studioChain
});

let userAccount = null;
let writeClient = null;

// Utility functions

function byId(id) {
  return document.getElementById(id);
}

function log(message, type = "info") {
  const output = byId("output");
  if (!output) return;

  const time = new Date().toLocaleTimeString();
  const line = document.createElement("div");

  line.textContent =
    `[${time}] ${type.toUpperCase()}: ` +
    (typeof message === "string"
      ? message
      : JSON.stringify(message, null, 2));

  output.prepend(line);
}

function errorMessage(error) {
  return (
    error?.shortMessage ||
    error?.reason ||
    error?.message ||
    String(error)
  );
}

function getValue(id) {
  return byId(id)?.value?.trim() || "";
}

function parseDisplay(value) {
  if (typeof value !== "string") return value;

  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

// Network management

async function ensureNetwork() {
  if (!window.ethereum) {
    throw new Error("MetaMask or a compatible wallet was not found.");
  }

  try {
    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: CHAIN_ID_HEX }]
    });
  } catch (error) {
    if (error.code !== 4902) {
      throw error;
    }

    await window.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [
        {
          chainId: CHAIN_ID_HEX,
          chainName: "GenLayer Studio Dev",
          nativeCurrency: {
            name: "GEN",
            symbol: "GEN",
            decimals: 18
          },
          rpcUrls: [RPC_URL],
          blockExplorerUrls: [
            "https://explorer-studio-dev.genlayer.com"
          ]
        }
      ]
    });

    await window.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: CHAIN_ID_HEX }]
    });
  }
}

// Wallet connection

async function connectWallet() {
  try {
    if (!window.ethereum) {
      throw new Error("Please install MetaMask or a compatible wallet.");
    }

    await ensureNetwork();

    const accounts = await window.ethereum.request({
      method: "eth_requestAccounts"
    });

    if (!accounts || !accounts.length) {
      throw new Error("The wallet did not return an account.");
    }

    userAccount = accounts[0];

    writeClient = createClient({
      chain: studioChain,
      provider: window.ethereum,
      account: userAccount
    });

    const button = byId("connectBtn");

    if (button) {
      button.textContent =
        `${userAccount.slice(0, 6)}...${userAccount.slice(-4)}`;
    }

    const dot = document.querySelector(".status-dot");

    if (dot) {
      dot.classList.add("connected");
      dot.style.backgroundColor = "#10b981";
    }

    log(`Wallet connected: ${userAccount}`, "success");

    return userAccount;
  } catch (error) {
    log(errorMessage(error), "error");
    return null;
  }
}

// Wallet validation

async function ensureWallet() {
  if (!userAccount || !writeClient) {
    const account = await connectWallet();

    if (!account) {
      throw new Error("Please connect your wallet first.");
    }
  } else {
    await ensureNetwork();
  }
}

// Contract write operations

async function write(functionName, args = [], options = {}) {
  await ensureWallet();

  log(`Waiting for transaction confirmation: ${functionName}`);

  const writeParams = {
    address: CONTRACT_ADDRESS,
    functionName,
    args
  };

  if (options.value) {
    writeParams.value = options.value;
  }

  const result = await writeClient.writeContract(writeParams);

  const txId =
    typeof result === "string"
      ? result
      : (
          result?.txId ||
          result?.hash ||
          JSON.stringify(result)
        );

  log(
    `Request ${functionName} submitted. ID: ${txId}`,
    "success"
  );

  return result;
}

// Contract read operations

async function read(functionName, args = []) {
  const result = await readClient.readContract({
    address: CONTRACT_ADDRESS,
    functionName,
    args
  });

  log(
    `${functionName}:\n${parseDisplay(result)}`,
    "success"
  );

  return result;
}

// Application functions

const app = {
  connectWallet,

  // Create a bounty
  async createBounty() {
    const description = getValue("b_desc");
    const criteria = getValue("b_crit");
    const reward = getValue("b_reward");

    if (!description || !criteria || !reward) {
      return log(
        "Please enter the description, criteria, and reward.",
        "error"
      );
    }

    if (parseInt(reward) <= 0 || isNaN(parseInt(reward))) {
         return log("Reward amount must be greater than 0.", "error");
    }

    try {
      await write("create_bounty", [
        description,
        criteria,
        reward
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Submit work
  async submitWork() {
    const bountyId = getValue("s_bounty_id");
    const proofUrl = getValue("s_url");

    if (!bountyId || !proofUrl) {
      return log(
        "Please enter the bounty ID and proof URL.",
        "error"
      );
    }

    let url;

    try {
      url = new URL(proofUrl);
    } catch {
      return log("Please enter a valid URL.", "error");
    }

    if (url.protocol !== "https:") {
      return log(
        "An HTTPS link is required.",
        "error"
      );
    }

    const allowed = [
      "github.com",
      "x.com",
      "twitter.com",
      "etherscan.io"
    ];

    if (
      !allowed.some(
        domain =>
          url.hostname === domain ||
          url.hostname.endsWith(`.${domain}`)
      )
    ) {
      return log(
        "Allowed sources: github.com, x.com, twitter.com, etherscan.io.",
        "error"
      );
    }

    try {
      await write("submit_work", [
        bountyId,
        proofUrl
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Fund a bounty (with real tokens)
  async fundBounty() {
    const bountyId = getValue("f_bounty_id");
    const amount = getValue("f_amount");

    if (!bountyId || !amount) {
      return log("Please enter the bounty ID and deposit amount.", "error");
    }

    try {
      await ensureWallet();
      log(`Waiting for transaction confirmation to fund bounty ${bountyId} with ${amount} tokens...`);

      // Convert amount in GEN to WEI (18 decimals)
      const weiAmount = BigInt(parseFloat(amount) * 10**18);
      await write("fund_bounty", [bountyId], { value: weiAmount });

    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Claim a reward
  async claimReward() {
    const submissionId = getValue("c_sub_id");

    if (!submissionId) {
      return log(
        "Please enter the approved submission ID.",
        "error"
      );
    }

    try {
      await write("claim_reward", [
        submissionId
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Refund a bounty
  async refundBounty() {
    const bountyId = getValue("r_bounty_id");

    if (!bountyId) {
      return log(
        "Please enter the bounty ID.",
        "error"
      );
    }

    try {
      await write("refund_bounty", [
        bountyId
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Withdraw credit
  async withdrawCredit() {
    try {
      await write("withdraw_credit", []);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Check one submission
  async crossCheck() {
    const id = getValue("v_sub_id");

    if (!id) {
      return log(
        "Please enter the submission ID.",
        "error"
      );
    }

    try {
      await write("cross_check", [id]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Check multiple submissions
  async crossCheckBatch() {
    const raw = getValue("v_batch_ids");

    if (!raw) {
      return log(
        "Please enter a JSON array of IDs.",
        "error"
      );
    }

    try {
      const ids = JSON.parse(raw);

      if (
        !Array.isArray(ids) ||
        ids.length > 20 ||
        ids.some(
          x =>
            typeof x !== "string" &&
            typeof x !== "number"
        )
      ) {
        throw new Error(
          'Expected a JSON array with up to 20 IDs, for example ["1","2"].'
        );
      }

      await write("cross_check_batch", [
        JSON.stringify(ids)
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Add a validator
  async addValidator() {
    const address = getValue("a_addr");

    if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
      return log(
        "Please enter a valid wallet address.",
        "error"
      );
    }

    try {
      await write("add_validator", [address]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Remove a validator
  async removeValidator() {
    const address = getValue("a_addr");

    if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
      return log(
        "Please enter a valid wallet address.",
        "error"
      );
    }

    try {
      await write("remove_validator", [address]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Activate or deactivate a bounty
  async setBountyActive(active) {
    const id = getValue("t_bounty_id");

    if (!id) {
      return log(
        "Please enter the bounty ID.",
        "error"
      );
    }

    try {
      await write("set_bounty_active", [
        id,
        Boolean(active)
      ]);
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Migrate submission types
  async migrateSubmissions() {
    try {
      await write(
        "migrate_submission_types",
        []
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get bounty details
  async getBounty() {
    const id = getValue("q_id");

    if (!id) {
      return log(
        "Please enter the bounty ID.",
        "error"
      );
    }

    try {
      await read(
        "get_bounty_details",
        [id]
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get submission audit
  async getAudit() {
    const id = getValue("q_id");

    if (!id) {
      return log(
        "Please enter the submission ID.",
        "error"
      );
    }

    try {
      await read(
        "get_submission_audit",
        [id]
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get submission status
  async getStatus() {
    const id = getValue("q_id");

    if (!id) {
      return log(
        "Please enter the submission ID.",
        "error"
      );
    }

    try {
      await read(
        "get_submission_status",
        [id]
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get credit balance for an address
  async getCredit() {
    const address = getValue("q_credit_addr");

    if (!/^0x[0-9a-fA-F]{40}$/.test(address)) {
      return log(
        "Please enter a valid wallet address.",
        "error"
      );
    }

    try {
      await read(
        "get_credit",
        [address]
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get current contract escrow balance
  async getEscrowBalance() {
    try {
      await read(
        "get_escrow_balance",
        []
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get platform configuration
  async getPlatformConfig() {
    try {
      await read(
        "get_platform_config",
        []
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get platform statistics
  async getPlatformStats() {
    try {
      await read(
        "get_platform_stats",
        []
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  },

  // Get contract owner
  async getOwner() {
    try {
      await read(
        "get_owner",
        []
      );
    } catch (error) {
      log(errorMessage(error), "error");
    }
  }
};

// Expose application functions to the HTML
window.app = app;

// Listen for wallet changes
if (window.ethereum) {
  window.ethereum.on?.(
    "accountsChanged",
    accounts => {
      userAccount = accounts?.[0] || null;
      writeClient = null;

      if (!userAccount && byId("connectBtn")) {
        byId("connectBtn").textContent =
          "Connect Wallet";
      }
    }
  );

  window.ethereum.on?.(
    "chainChanged",
    () => {
      writeClient = null;
      userAccount = null;
    }
  );
}