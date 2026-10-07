# { "Depends": "py-genlayer:15qfivjvy80800rh998pcxmd2m8va1wq2qzqhz850n8ggcr4i9q0" }

from genlayer import *
import json
from typing import Any
from urllib.parse import urlparse

MAX_BATCH_SIZE = 20
SCHEMA_VERSION = 8  # Incremented schema version for real token transfers

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
        raw = gl.get_webpage(clean_url, mode="text")
        if raw is None or str(raw).strip() == "":
            raw = gl.get_webpage(clean_url, mode="html")
        
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
        result = gl.exec_prompt(prompt)

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


class ProofBountyJudge(gl.Contract):
    owner: str
    validators_json: str
    bounties_json: str
    submissions_json: str
    bounty_counter: str
    submission_counter: str

    def __init__(self):
        self.owner = str(gl.message.sender_address)
        self.validators_json = _dumps({self.owner: True})
        self.bounties_json = "{}"
        self.submissions_json = "{}"
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
            "is_active": True,
            "is_funded": False,
            "is_paid": False,
            "paid_to": "",
        }
        self._save("bounties_json", bounties)
        return bounty_id

    @gl.public.write
    def fund_bounty(self, bounty_id: str) -> bool:
        """Physically receives GEN tokens to fund the bounty."""
        msg_value = getattr(gl.message, 'value', 0)
        if msg_value <= 0:
            raise Exception("ERR_NO_FUNDS_SENT")
            
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            raise Exception("ERR_NOT_FOUND")
            
        bounty = bounties[bounty_id]
        if not bounty.get("is_active", False):
            raise Exception("ERR_BOUNTY_INACTIVE")
        if bounty.get("is_funded", False):
             raise Exception("ERR_BOUNTY_ALREADY_FUNDED")

        expected_amount = int(bounty["reward_amount"])
        if msg_value < expected_amount:
            raise Exception(f"ERR_INSUFFICIENT_FUNDS: Expected {expected_amount}, got {msg_value}")

        bounty["funded_amount"] = str(msg_value)
        bounty["is_funded"] = True
        bounties[bounty_id] = bounty
        self._save("bounties_json", bounties)
        return True

    @gl.public.write
    def set_bounty_active(self, bounty_id: str, is_active: bool) -> None:
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            raise Exception("ERR_NOT_FOUND")
        bounty = bounties[bounty_id]
        if str(gl.message.sender_address) not in (bounty["creator"], self.owner):
            raise Exception("ERR_UNAUTHORIZED")
        
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

        try:
            result_json = gl.eq_principle.prompt_comparative(
                leader_fn,
                principle=(
                    "`is_approved` must be exactly the same. "
                    "`reasoning` may be similar in meaning."
                ),
            )
        except Exception:
            result_json = gl.eq_principle.strict_eq(leader_fn)

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
        sub["last_checked_at"] = int(getattr(gl.block, "timestamp", 0) or 0)

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
        """Physically transfers the escrowed tokens to the approved submitter."""
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
        
        try:
            gl.transfer(submitter_addr, amount_to_pay)
        except Exception as e:
            raise Exception(f"ERR_TRANSFER_FAILED: {str(e)}")

        sub["is_claimed"] = True
        bounty["is_paid"] = True
        bounty["paid_to"] = submitter_addr
        bounty["is_active"] = False

        submissions[submission_id] = sub
        bounties[sub["bounty_id"]] = bounty
        self._save("submissions_json", submissions)
        self._save("bounties_json", bounties)

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
                    "is_approved": False,
                    "status": "ERROR_EXECUTION",
                    "reason": _sanitize(str(exc))[:120],
                })
        return _dumps(results)

    @gl.public.write
    def migrate_submission_types(self) -> str:
        caller = str(gl.message.sender_address)
        if caller != self.owner:
            raise Exception("ERR_UNAUTHORIZED")

        submissions = self._load("submissions_json")
        migrated_count = 0

        for sid, sub in submissions.items():
            if "leader_result" in sub and isinstance(sub["leader_result"].get("is_approved"), str):
                val = sub["leader_result"]["is_approved"].lower()
                sub["leader_result"]["is_approved"] = (val == "true")
                migrated_count += 1

        if migrated_count:
            self._save("submissions_json", submissions)

        return f"Migrated {migrated_count} submissions."

    @gl.public.view
    def get_platform_config(self) -> str:
        return _dumps(
            {"max_batch_size": MAX_BATCH_SIZE, "schema_version": SCHEMA_VERSION}
        )

    @gl.public.view
    def get_bounty_details(self, bounty_id: str) -> str:
        bounties = self._load("bounties_json")
        if bounty_id not in bounties:
            return _dumps({"error": "ERR_NOT_FOUND"})
        return _dumps(bounties[bounty_id])

    @gl.public.view
    def get_submission_status(self, submission_id: str) -> str:
        submissions = self._load("submissions_json")
        if submission_id not in submissions:
            return _dumps({"error": "ERR_NOT_FOUND"})
        s = submissions[submission_id]
        return _dumps(
            {
                "status": s["status"],
                "has_been_checked": int(s.get("last_checked_at", 0)) > 0,
                "last_checked_at": s.get("last_checked_at", 0),
            }
        )

    @gl.public.view
    def get_submission_audit(self, submission_id: str) -> str:
        submissions = self._load("submissions_json")
        if submission_id not in submissions:
            return _dumps({"error": "ERR_NOT_FOUND"})
        s = submissions[submission_id]
        return _dumps(
            {
                "version": SCHEMA_VERSION,
                "submission_id": s["submission_id"],
                "bounty_id": s["bounty_id"],
                "status": s["status"],
                "is_claimed": s.get("is_claimed", False),
                "resolution_reason": s.get("resolution_reason", ""),
                "leader_result": s.get("leader_result", {}),
                "timestamp": s.get("last_checked_at", 0),
            }
        )

    @gl.public.view
    def get_platform_stats(self) -> str:
        return _dumps(
            {
                "total_bounties": int(self.bounty_counter),
                "total_submissions": int(self.submission_counter),
                "owner": self.owner,
            }
        )

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner