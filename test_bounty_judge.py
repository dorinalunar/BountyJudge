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

    def test_create_bounty_empty_fields(self):
        """Test protection against empty fields during bounty creation."""
        mock_gl.message.sender_address = self.owner_address
        with self.assertRaises(Exception) as context:
            self.contract.create_bounty("", "Criteria", "100")
        self.assertTrue("ERR_EMPTY_FIELDS" in str(context.exception))

    def test_submit_work_success(self):
        """Test successful proof submission from an allowed domain."""
        # First, create a bounty
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")
        
        # User submits work
        mock_gl.message.sender_address = self.user_address
        sub_id = self.contract.submit_work("1", "https://github.com/dorinalunar/repo")
        
        self.assertEqual(sub_id, "1")
        self.assertEqual(self.contract.submission_counter, "1")

    def test_submit_work_unauthorized_domain(self):
        """Test blocking of unauthorized domains (e.g., google.com)."""
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")
        
        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.submit_work("1", "https://google.com/my-proof")
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
        # Create a bounty and a submission
        mock_gl.message.sender_address = self.owner_address
        self.contract.create_bounty("Task", "Crit", "50")
        self.contract.submit_work("1", "https://github.com/test")
        
        # User tries to verify
        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.cross_check("1")
        self.assertTrue("ERR_UNAUTHORIZED_VALIDATOR" in str(context.exception))

if __name__ == '__main__':
    unittest.main()