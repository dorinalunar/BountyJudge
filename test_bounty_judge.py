import unittest
from unittest.mock import patch, MagicMock
import json
import sys

# Mock GenLayer (gl) environment for local testing
mock_gl = MagicMock()
mock_gl.Contract = object  # Stub for the base contract class
sys.modules['genlayer'] = mock_gl

# Now import our contract
from BountyJudge_2 import ProofBountyJudge

class TestProofBountyJudge(unittest.TestCase):

    def setUp(self):
        """Setup environment before each test."""
        self.owner_address = "0xOwner123"
        self.user_address = "0xUser456"
        self.validator_address = "0xValidator789"

        # Mock transaction sender as owner
        mock_gl.message.sender_address = self.owner_address
        self.contract = ProofBountyJudge()

    def test_initialization(self):
        """Test proper contract initialization."""
        self.assertEqual(self.contract.owner, self.owner_address)
        self.assertEqual(self.contract.bounty_counter, "0")
        self.assertEqual(self.contract.submission_counter, "0")

        # Owner should be the first validator
        validators = json.loads(self.contract.validators_json)
        self.assertTrue(validators.get(self.owner_address))

    def test_add_validator_success(self):
        """Test adding a validator by the owner."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.add_validator(self.validator_address)

        validators = json.loads(self.contract.validators_json)
        self.assertTrue(validators.get(self.validator_address))

    def test_add_validator_unauthorized(self):
        """Test that a regular user cannot add a validator."""
        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.add_validator("0xNewValidator")
        self.assertTrue("ERR_UNAUTHORIZED" in str(context.exception))

    def test_create_bounty_success(self):
        """Test successful bounty creation."""
        mock_gl.message.sender_address = self.owner_address
        bounty_id = self.contract.create_bounty(
            description="Build a dApp",
            criteria="Must use Python",
            reward_amount="100"
        )
        self.assertEqual(bounty_id, "1")
        self.assertEqual(self.contract.bounty_counter, "1")

        bounties = json.loads(self.contract.bounties_json)
        self.assertEqual(bounties["1"]["description"], "Build a dApp")
        self.assertEqual(bounties["1"]["is_funded"], False)
        self.assertEqual(bounties["1"]["is_paid"], False)

    def test_create_bounty_empty_fields(self):
        """Test protection against empty fields during bounty creation."""
        mock_gl.message.sender_address = self.owner_address
        with self.assertRaises(Exception) as context:
            self.contract.create_bounty("", "Criteria", "100")
        self.assertTrue("ERR_EMPTY_FIELDS" in str(context.exception))

    def test_fund_bounty_success(self):
        """Test successful funding of a bounty."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "100")
        
        # Fund the bounty
        self.contract.fund_bounty("1", "100")
        
        bounties = json.loads(self.contract.bounties_json)
        self.assertTrue(bounties["1"]["is_funded"])
        self.assertEqual(bounties["1"]["funded_amount"], "100")

    def test_submit_work_success(self):
        """Test successful proof submission from an allowed domain."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")

        mock_gl.message.sender_address = self.user_address
        sub_id = self.contract.submit_work("1", "https://github.com/dorinalunar/repo")

        self.assertEqual(sub_id, "1")
        self.assertEqual(self.contract.submission_counter, "1")

    def test_submit_work_strict_domain_bypass(self):
        """Test blocking of domain substring spoofing (e.g., attacker.com/github.com)."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")

        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            # Attempting to bypass using a valid domain as a path
            self.contract.submit_work("1", "https://attacker.com/github.com/my-proof")
        self.assertTrue("ERR_UNAUTHORIZED_EVIDENCE_SOURCE" in str(context.exception))

    def test_submit_work_invalid_url(self):
        """Test URL format validation."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")

        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.submit_work("1", "ftp://github.com/repo")
        self.assertTrue("ERR_INVALID_URL" in str(context.exception))

    def test_cross_check_unauthorized(self):
        """Test that a regular user cannot trigger AI consensus."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")
        self.contract.submit_work("1", "https://github.com/test")

        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.cross_check("1")
        self.assertTrue("ERR_UNAUTHORIZED_VALIDATOR" in str(context.exception))

    def test_claim_reward_success(self):
        """Test claiming a reward for an approved submission."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "100")
        self.contract.fund_bounty("1", "100")
        
        mock_gl.message.sender_address = self.user_address
        self.contract.submit_work("1", "https://github.com/test")

        # Force approve submission to simulate AI consensus
        submissions = json.loads(self.contract.submissions_json)
        submissions["1"]["status"] = "APPROVED"
        self.contract.submissions_json = json.dumps(submissions)

        # Claim reward as submitter
        mock_gl.message.sender_address = self.user_address
        result = self.contract.claim_reward("1")
        
        self.assertTrue(self.user_address in result)
        
        # Verify state changes
        submissions = json.loads(self.contract.submissions_json)
        bounties = json.loads(self.contract.bounties_json)
        self.assertTrue(submissions["1"]["is_claimed"])
        self.assertTrue(bounties["1"]["is_paid"])
        self.assertFalse(bounties["1"]["is_active"])
        self.assertEqual(bounties["1"]["paid_to"], self.user_address)

    def test_claim_reward_unapproved(self):
        """Test claiming a reward fails if submission is not approved."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "100")
        
        mock_gl.message.sender_address = self.user_address
        self.contract.submit_work("1", "https://github.com/test")
        
        # Submission status is PENDING by default
        with self.assertRaises(Exception) as context:
            self.contract.claim_reward("1")
        self.assertTrue("ERR_SUBMISSION_NOT_APPROVED" in str(context.exception))

if __name__ == '__main__':
    unittest.main()