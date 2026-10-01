# { "Depends": "py-genlayer:15qfivjvy80800rh998pcxmd2m8va1wq2qzqhz850n8ggcr4i9q0" }

from genlayer import *
import json
from typing import Any

MAX_BATCH_SIZE = 20
SCHEMA_VERSION = 6  # Incremented schema version for evidence controls update

# Stronger evidence-source controls
ALLOWED_EVIDENCE_DOMAINS = ["github.com", "x.com", "twitter.com", "etherscan.io"]

def _sanitize(text: str) -> str:
    if not text:
        return ""
    return " ".join(str(text).replace('"', "'").split())

def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _evaluate_submission(description: str, criteria: str, proof_url: str) -> str:
    """Nondeterministic leader task: fetch evidence + LLM judgment."""
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
        
        # Explicit handling for failed proof retrieval
        if not raw_str.strip():
            fetch_error = "ERR_EVIDENCE_EMPTY"
        else:
            sanitized_raw = _sanitize(raw_str)
            
            # Explicit handling for truncated proofs
            if len(sanitized_raw) > 4000:
                evidence = sanitized_raw[:4000] + "\n\n[SYSTEM WARNING: EVIDENCE WAS TRUNCATED DUE TO SIZE LIMIT. Evaluate based on available text.]"
            else:
                evidence = sanitized_raw
                
    except Exception as exc:
        fetch_error = f"ERR_FETCH_FAILED: {_sanitize(str(exc))[:100]}"

    # Short-circuit LLM execution if evidence cannot be retrieved
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

    # Strict type checking & Fail-Closed Guard
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
        """Strict type check to enforce native booleans and prevent truthy string bugs."""
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

        bounty_id = self._next_id("bounty_counter")
        bounties = self._load("bounties_json")
        bounties[bounty_id] = {
            "bounty_id": bounty_id,
            "creator": str(gl.message.sender_address),
            "description": desc,
            "criteria": crit,
            "reward_amount": str(reward_amount),
            "is_active": True,
            "is_funded": False,
        }
        self._save("bounties_json", bounties)
        return bounty_id

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
        if not url.startswith("https://"):
            raise Exception("ERR_INVALID_URL")
            
        # Implementing stronger evidence-source controls
        is_allowed_source = any(domain in url for domain in ALLOWED_EVIDENCE_DOMAINS)
        if not is_allowed_source:
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

        # Strict validation of is_approved
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
        """Converts legacy string 'true'/'false' into actual strict booleans."""
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