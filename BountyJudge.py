# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
from genlayer.types import Address
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

MAX_BATCH_SIZE = 20
SCHEMA_VERSION = 9  # payable escrow + native GEN payout and refund

ALLOWED_EVIDENCE_DOMAINS = ["github.com", "x.com", "twitter.com", "etherscan.io"]

def _sanitize(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace('"', "'").split())

def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))

def _is_valid_domain(url: str) -> bool:
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower().split(":")[0]
        if not netloc:
            return False
        return any(netloc == domain or netloc.endswith("." + domain) for domain in ALLOWED_EVIDENCE_DOMAINS)
    except Exception:
        return False

def _evaluate_submission(description: str, criteria: str, proof_url: str) -> str:
    clean_desc = _sanitize(description)
    clean_crit = _sanitize(criteria)
    clean_url = _sanitize(proof_url)

    evidence = ""
    fetch_error = None

    try:
        raw = gl.nondet.web.render(clean_url, mode="text")
        if raw is None or str(raw).strip() == "":
            raw = gl.nondet.web.render(clean_url, mode="html")
        
        raw_str = str(raw) if raw is not None else ""
        
        if not raw_str.strip():
            fetch_error = "ERR_EVIDENCE_EMPTY"
        else:
            sanitized_raw = _sanitize(raw_str)
            if len(sanitized_raw) > 4000:
                evidence = sanitized_raw[:4000] + "\n\n[SYSTEM WARNING: EVIDENCE TRUNCATED]"
            else:
                evidence = sanitized_raw
                
    except Exception as exc:
        fetch_error = f"ERR_FETCH_FAILED: {_sanitize(str(exc))[:100]}"

    if fetch_error:
        return _dumps({"is_approved": False, "reasoning": fetch_error})

    prompt = (
        "You are an objective auditor for a Web3 bounty platform.\n"
        f"Bounty description: {clean_desc}\n"
        f"Acceptance criteria: {clean_crit}\n"
        f"Evidence URL: {clean_url}\n"
        f"Evidence content: {evidence}\n"
        "Does the evidence fully meet the acceptance criteria?\n"
        'Return JSON with exactly: {"is_approved": true/false, "reasoning": "short explanation"}'
    )

    try:
        result = gl.nondet.exec_prompt(prompt, response_format="json")
    except Exception:
        return _dumps({"is_approved": False, "reasoning": "ERR_PROMPT_FAILED"})

    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = {"is_approved": False, "reasoning": "ERR_JSON_PARSE_FAILED"}

    if not isinstance(result, dict):
        result = {"is_approved": False, "reasoning": "ERR_NON_DICT"}

    raw_approved = result.get("is_approved")
    if type(raw_approved) is bool:
        approved = raw_approved
    else:
        approved = False

    reasoning = _sanitize(str(result.get("reasoning", "")))[:500]
    return _dumps({"is_approved": approved, "reasoning": reasoning})


@gl.evm.contract_interface
class _Wallet:
    """An account on the chain layer. A wallet (EOA) has no methods, only a balance."""

    class View:
        pass

    class Write:
        pass


def _pay(address: str, amount: int) -> None:
    """Send native GEN from this contract's balance to a wallet.

    A wallet lives on the chain layer, so the transfer has to be an EXTERNAL message:
    it leaves through the contract's ghost contract and is applied on finalization.
    An internal message only reaches other Intelligent Contracts; sent to a wallet it
    is emitted and never credited.
    """
    _Wallet(Address(address)).emit_transfer(value=amount)


def _now() -> int:
    """Transaction datetime as unix seconds; identical for every validator."""
    return int(datetime.now(timezone.utc).timestamp())


class ProofBountyJudge(gl.contract.Contract):
    owner: str
    validators_json: str
    bounties_json: str
    submissions_json: str
    credits_json: str
    bounty_counter: str
    submission_counter: str

    def __init__(self):
        self.owner = str(gl.message.sender_address)
        self.validators_json = _dumps({self.owner: True})
        self.bounties_json = "{}"
        self.submissions_json = "{}"
        self.credits_json = "{}"
        self.bounty_counter = "0"
        self.submission_counter = "0"

    def _load(self, field: str):
        return json.loads(getattr(self, field))

    def _save(self, field: str, data) -> None:
        setattr(self, field, _dumps(data))

    def _is_validator(self, addr: str) -> bool:
        vals = self._load("validators_json")
        return bool(vals.get(addr, False))

    def _next_id(self, counter_field: str) -> str:
        n = int(getattr(self, counter_field)) + 1
        setattr(self, counter_field, str(n))
        return str(n)

    def _ensure_bool(self, value: Any) -> bool:
        if type(value) is bool:
            return value
        raise Exception("ERR_INVALID_APPROVAL_TYPE")

    @gl.public.write
    def add_validator(self, address: str) -> None:
        if str(gl.message.sender_address) != self.owner:
            raise Exception("ERR_UNAUTHORIZED")
        addr = str(address)
        if not addr.startswith("0x"):
            raise Exception("ERR_INVALID_ADDRESS")
        vals = self._load("validators_json")
        vals[addr] = True
        self._save("validators_json", vals)

    @gl.public.write
    def remove_validator(self, address: str) -> None:
        if str(gl.message.sender_address) != self.owner:
            raise Exception("ERR_UNAUTHORIZED")
        addr = str(address)
        if addr == self.owner:
            raise Exception("ERR_CANNOT_REMOVE_OWNER")
        vals = self._load("validators_json")
        if addr in vals:
            del vals[addr]
            self._save("validators_json", vals)

    @gl.public.write
    def create_bounty(self, description: str, criteria: str, reward_amount: str) -> str:
        desc = _sanitize(description)
        crit = _sanitize(criteria)
        if not desc or not crit:
            raise Exception("ERR_EMPTY_FIELDS")
        if len(desc) > 2000 or len(crit) > 2000:
            raise Exception("ERR_FIELD_TOO_LONG")
            
        try:
            int_reward = int(reward_amount)
            if int_reward <= 0:
                raise Exception("ERR_INVALID_REWARD_AMOUNT")
        except ValueError:
            raise Exception("ERR_INVALID_REWARD_AMOUNT")

        bounty_id = self._next_id("bounty_counter")
        bounties = self._load("bounties_json")
        bounties[bounty_id] = {
            "bounty_id": bounty_id,
            "creator": str(gl.message.sender_address),
            "description": desc,
            "criteria": crit,
            "reward_amount": str(reward_amount),
            "funded_amount": "0",
            "funder": "",
            "is_refunded": False,
            "is_active": True,
            "is_funded": False,
            "is_paid": False,
            "paid_to": "",
        }
        self._save("bounties_json", bounties)
        return bounty_id

    def _credit(self, address: str, amount: int) -> None:
        """Book GEN this contract holds for `address` and owes back on request."""
        if amount <= 0:
            return
        credits = self._load("credits_json")
        credits[address] = str(int(credits.get(address, "0")) + amount)
        self._save("credits_json", credits)

    @gl.public.write.payable
    def fund_bounty(self, bounty_id: str) -> str:
        """Escrow the reward: GEN sent with this call stays in the contract's balance.

        The method is payable, so `gl.message.value` is the amount attached to the
        transaction. Value sent with a call that reverts is NOT returned by the network,
        so once value is attached this method never raises: whatever cannot be escrowed
        for the bounty is booked as a credit for the sender, who takes it back with
        withdraw_credit(). No amount can get stranded.

          * unknown, inactive, paid or refunded bounty -> everything is credited back
          * a second funder                            -> everything is credited back
          * more than is still missing                 -> the excess is credited back

        The bounty counts as funded when the escrow equals the reward. The first funder
        may top up in several payments.
        """
        msg_value = int(gl.message.value)
        if msg_value <= 0:
            raise Exception("ERR_NO_FUNDS_SENT")
        sender = str(gl.message.sender_address)

        bounties = self._load("bounties_json")
        bounty = bounties.get(bounty_id)
        refusal = ""
        if bounty is None:
            refusal = "ERR_NOT_FOUND"
        elif bounty.get("is_paid", False) or bounty.get("is_refunded", False):
            refusal = "ERR_BOUNTY_ALREADY_SETTLED"
        elif not bounty.get("is_active", False):
            refusal = "ERR_BOUNTY_INACTIVE"
        elif bounty.get("is_funded", False):
            refusal = "ERR_BOUNTY_ALREADY_FUNDED"
        elif bounty.get("funder") not in ("", sender):
            refusal = "ERR_ANOTHER_FUNDER"
        if refusal:
            self._credit(sender, msg_value)
            return _dumps({"escrowed": "0", "credited": str(msg_value), "reason": refusal})

        reward = int(bounty["reward_amount"])
        already = int(bounty.get("funded_amount", "0"))
        accepted = min(msg_value, reward - already)
        excess = msg_value - accepted

        bounty["funded_amount"] = str(already + accepted)
        bounty["funder"] = sender
        bounty["is_funded"] = (already + accepted) == reward
        bounties[bounty_id] = bounty
        self._save("bounties_json", bounties)
        self._credit(sender, excess)
        return _dumps(
            {
                "escrowed": str(accepted),
                "credited": str(excess),
                "is_funded": bounty["is_funded"],
                "funded_amount": bounty["funded_amount"],
            }
        )

    @gl.public.write
    def withdraw_credit(self) -> str:
        """Take back GEN that fund_bounty could not escrow for you."""
        caller = str(gl.message.sender_address)
        credits = self._load("credits_json")
        amount = int(credits.get(caller, "0"))
        if amount <= 0:
            raise Exception("ERR_NO_CREDIT")
        if int(self.balance) < amount:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        # State first, transfer last.
        del credits[caller]
        self._save("credits_json", credits)
        _pay(caller, amount)
        return f"Returned {amount} to {caller}"

    @gl.public.write
    def refund_bounty(self, bounty_id: str) -> str:
        """Return the escrow to whoever funded it, if nobody has earned it.

        Only the funder may call it, and not while an approved submission is waiting to
        claim: an approved worker can never be refunded out of their reward.
        """
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            raise Exception("ERR_NOT_FOUND")
        bounty = bounties[bounty_id]
        caller = str(gl.message.sender_address)
        if caller != bounty.get("funder"):
            raise Exception("ERR_UNAUTHORIZED")
        if bounty.get("is_paid", False) or bounty.get("is_refunded", False):
            raise Exception("ERR_BOUNTY_ALREADY_SETTLED")
        if int(bounty.get("funded_amount", "0")) <= 0:
            raise Exception("ERR_BOUNTY_NOT_FUNDED")
        for sub in self._load("submissions_json").values():
            if sub.get("bounty_id") == bounty_id and sub.get("status") == "APPROVED":
                raise Exception("ERR_APPROVED_SUBMISSION_EXISTS")

        amount = int(bounty["funded_amount"])
        if int(self.balance) < amount:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        # State first, transfer last.
        bounty["is_refunded"] = True
        bounty["is_funded"] = False
        bounty["is_active"] = False
        bounty["funded_amount"] = "0"
        bounties[bounty_id] = bounty
        self._save("bounties_json", bounties)

        _pay(caller, amount)
        return f"Refunded {amount} to {caller}"

    @gl.public.write
    def set_bounty_active(self, bounty_id: str, is_active: bool) -> None:
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            raise Exception("ERR_NOT_FOUND")
        bounty = bounties[bounty_id]
        if str(gl.message.sender_address) != bounty["creator"]:
            raise Exception("ERR_UNAUTHORIZED")
        if bounty.get("is_paid", False) or bounty.get("is_refunded", False):
            raise Exception("ERR_BOUNTY_ALREADY_SETTLED")
        
        bounty["is_active"] = self._ensure_bool(is_active)
        bounties[bounty_id] = bounty
        self._save("bounties_json", bounties)

    @gl.public.write
    def submit_work(self, bounty_id: str, proof_url: str) -> str:
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            raise Exception("ERR_NOT_FOUND")
        bounty = bounties[bounty_id]
        if not bounty.get("is_active", False):
            raise Exception("ERR_BOUNTY_INACTIVE")
        if not bounty.get("is_funded", False):
            raise Exception("ERR_BOUNTY_NOT_FUNDED")

        url = _sanitize(proof_url)
        if not (url.startswith("https://") or url.startswith("http://")):
            raise Exception("ERR_INVALID_URL")
            
        if not _is_valid_domain(url):
            raise Exception("ERR_UNAUTHORIZED_EVIDENCE_SOURCE")

        submission_id = self._next_id("submission_counter")
        submissions = self._load("submissions_json")
        submissions[submission_id] = {
            "submission_id": submission_id,
            "bounty_id": bounty_id,
            "submitter": str(gl.message.sender_address),
            "proof_url": url,
            "status": "PENDING",
            "resolution_reason": "",
            "is_claimed": False,
            "leader_result": {},
            "last_checked_at": 0,
        }
        self._save("submissions_json", submissions)
        return submission_id

    def _run_cross_check(self, submission_id: str) -> bool:
        submissions = self._load("submissions_json")
        if submission_id not in submissions:
            raise Exception("ERR_NOT_FOUND")

        sub = submissions[submission_id]

        if sub.get("status") != "PENDING":
            raise Exception("ERR_SUBMISSION_ALREADY_RESOLVED")

        bounties = self._load("bounties_json")
        bounty = bounties.get(sub["bounty_id"])
        if not bounty:
            raise Exception("ERR_BOUNTY_MISSING")

        description = bounty["description"]
        criteria = bounty["criteria"]
        proof_url = sub["proof_url"]

        def leader_fn() -> str:
            return _evaluate_submission(description, criteria, proof_url)

        # `principle` is positional-only in GenVM v0.3. Passed by keyword it raises
        # TypeError, which the old try/except turned into a silent strict_eq fallback.
        result_json = gl.eq_principle.prompt_comparative(
            leader_fn,
            "`is_approved` must be exactly the same. `reasoning` may be similar in meaning.",
        )

        if isinstance(result_json, dict):
            result = result_json
        else:
            try:
                result = json.loads(result_json)
            except Exception:
                result = {"is_approved": False, "reasoning": "ERR_CONSENSUS_PARSE"}

        raw_approval = result.get("is_approved")
        approved = self._ensure_bool(raw_approval)

        reasoning = _sanitize(str(result.get("reasoning", "")))[:500]

        sub["leader_result"] = {"is_approved": approved, "reasoning": reasoning}
        sub["status"] = "APPROVED" if approved else "REJECTED"
        sub["resolution_reason"] = reasoning
        sub["last_checked_at"] = _now()

        submissions[submission_id] = sub
        self._save("submissions_json", submissions)
        return approved

    @gl.public.write
    def cross_check(self, submission_id: str) -> bool:
        caller = str(gl.message.sender_address)
        if not self._is_validator(caller):
            raise Exception("ERR_UNAUTHORIZED_VALIDATOR")
        raw_approved = self._run_cross_check(submission_id)
        return self._ensure_bool(raw_approved)
        
    @gl.public.write
    def claim_reward(self, submission_id: str) -> str:
        """Pay the escrowed GEN to the submitter of an approved submission.

        Anyone may trigger it; the money can only go to the address that submitted the
        work. The books are updated before the transfer is emitted, and the transfer is a
        native GEN transfer from this contract's balance, applied on finalization.
        """
        submissions = self._load("submissions_json")
        if submission_id not in submissions:
            raise Exception("ERR_NOT_FOUND")
        sub = submissions[submission_id]

        if sub.get("status") != "APPROVED":
            raise Exception("ERR_SUBMISSION_NOT_APPROVED")
        if sub.get("is_claimed", False):
            raise Exception("ERR_ALREADY_CLAIMED")

        bounties = self._load("bounties_json")
        bounty = bounties.get(sub["bounty_id"])
        if not bounty:
            raise Exception("ERR_BOUNTY_NOT_FOUND")
        if bounty.get("is_paid", False):
            raise Exception("ERR_BOUNTY_ALREADY_PAID")
        if not bounty.get("is_funded", False):
            raise Exception("ERR_BOUNTY_NOT_FUNDED")

        amount_to_pay = int(bounty["funded_amount"])
        submitter_addr = sub["submitter"]
        if amount_to_pay <= 0:
            raise Exception("ERR_NOTHING_TO_PAY")
        if int(self.balance) < amount_to_pay:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        # State first, transfer last: a second claim finds is_paid already set.
        sub["is_claimed"] = True
        bounty["is_paid"] = True
        bounty["is_funded"] = False
        bounty["paid_to"] = submitter_addr
        bounty["paid_amount"] = str(amount_to_pay)
        bounty["funded_amount"] = "0"
        bounty["is_active"] = False

        submissions[submission_id] = sub
        bounties[sub["bounty_id"]] = bounty
        self._save("submissions_json", submissions)
        self._save("bounties_json", bounties)

        _pay(submitter_addr, amount_to_pay)
        return f"Reward of {amount_to_pay} claimed by {submitter_addr}"

    @gl.public.write
    def cross_check_batch(self, submission_ids_json: str) -> str:
        caller = str(gl.message.sender_address)
        if not self._is_validator(caller):
            raise Exception("ERR_UNAUTHORIZED_VALIDATOR")

        try:
            ids = json.loads(submission_ids_json)
        except Exception:
            raise Exception("ERR_INVALID_JSON")
        if not isinstance(ids, list):
            raise Exception("ERR_NOT_A_LIST")
        if len(ids) > MAX_BATCH_SIZE:
            raise Exception("ERR_BATCH_LIMIT_EXCEEDED")

        results = []
        for s_id in ids:
            sid = str(s_id)
            try:
                raw_approved = self._run_cross_check(sid)
                is_approved = self._ensure_bool(raw_approved)

                submissions = self._load("submissions_json")
                status = submissions.get(sid, {}).get("status", "NOT_FOUND")

                results.append({
                    "submission_id": sid, 
                    "is_approved": is_approved, 
                    "status": status
                })
            except Exception as exc:
                results.append({
                    "submission_id": sid,
                    "is_approved":