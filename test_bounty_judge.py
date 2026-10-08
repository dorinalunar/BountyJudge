import unittest
from unittest.mock import patch, MagicMock
import json
import sys

# Mock GenLayer environment and new specific types for v0.3.0
mock_gl = MagicMock()
mock_gl.contract.Contract = object
mock_gl.evm.contract_interface = lambda cls: cls
sys.modules['genlayer'] = mock_gl
sys.modules['genlayer.types'] = MagicMock()

from BountyJudge import ProofBountyJudge

class TestProofBountyJudge(unittest.TestCase):

    def setUp(self):
        self.owner_address = "0xOwner123"
        self.user_address = "0xUser456"
        self.validator_address = "0xValidator789"

        mock_gl.message.sender_address = self.owner_address
        mock_gl.message.value = 0
        
        self.contract = ProofBountyJudge()
        self.contract.balance = "10000"  # Mock contract balance for transfers

    def test_initialization(self):
        self.assertEqual(self.contract.owner, self.owner_address)
        self.assertEqual(self.contract.bounty_counter, "0")
        validators = json.loads(self.contract.validators_json)
        self.assertTrue(validators.get(self.owner_address))

    def test_create_bounty_success(self):
        mock_gl.message.sender_address = self.owner_address
        b_id = self.contract.create_bounty("Task", "Crit", "100")
        self.assertEqual(b_id, "1")
        bounties = json.loads(self.contract.bounties_json)
        self.assertEqual(bounties["1"]["reward_amount"], "100")
        self.assertFalse(bounties["1"]["is_funded"])

    def test_fund_bounty_success(self):
        self.contract.create_bounty("Task", "Crit", "100")
        
        mock_gl.message.value = 100
        result = json.loads(self.contract.fund_bounty("1"))
        
        self.assertEqual(result["escrowed"], "100")
        self.assertEqual(result["credited"], "0")
        self.assertTrue(result["is_funded"])

    def test_fund_bounty_excess_credited(self):
        self.contract.create_bounty("Task", "Crit", "100")
        
        mock_gl.message.value = 150
        result = json.loads(self.contract.fund_bounty("1"))
        
        self.assertEqual(result["escrowed"], "100")
        self.assertEqual(result["credited"], "50")
        
        credits = json.loads(self.contract.credits_json)
        self.assertEqual(credits[self.owner_address], "50")

    @patch('BountyJudge._pay')
    def test_withdraw_credit(self, mock_pay):
        credits = {self.user_address: "50"}
        self.contract.credits_json = json.dumps(credits)
        
        mock_gl.message.sender_address = self.user_address
        self.contract.withdraw_credit()
        
        mock_pay.assert_called_once_with(self.user_address, 50)
        credits_after = json.loads(self.contract.credits_json)
        self.assertNotIn(self.user_address, credits_after)

    @patch('BountyJudge._pay')
    def test_refund_bounty(self, mock_pay):
        self.contract.create_bounty("Task", "Crit", "100")
        mock_gl.message.value = 100
        self.contract.fund_bounty("1")

        self.contract.refund_bounty("1")
        
        mock_pay.assert_called_once_with(self.owner_address, 100)
        bounties = json.loads(self.contract.bounties_json)
        self.assertTrue(bounties["1"]["is_refunded"])
        self.assertFalse(bounties["1"]["is_funded"])

    def test_submit_work_success(self):
        self.contract.create_bounty("Task", "Crit", "50")
        mock_gl.message.value = 50
        self.contract.fund_bounty("1")

        mock_gl.message.sender_address = self.user_address
        sub_id = self.contract.submit_work("1", "https://github.com/dorinalunar/repo")
        self.assertEqual(sub_id, "1")

    def test_submit_work_unfunded_bounty(self):
        self.contract.create_bounty("Task", "Crit", "50")
        mock_gl.message.sender_address = self.user_address
        
        with self.assertRaises(Exception) as context:
            self.contract.submit_work("1", "https://github.com/dorinalunar/repo")
        self.assertTrue("ERR_BOUNTY_NOT_FUNDED" in str(context.exception))

    def test_submit_work_strict_domain_bypass(self):
        self.contract.create_bounty("Task", "Crit", "50")
        mock_gl.message.value = 50
        self.contract.fund_bounty("1")

        mock_gl.message.sender_address = self.user_address
        with self.assertRaises(Exception) as context:
            self.contract.submit_work("1", "https://attacker.com/github.com/my-proof")
        self.assertTrue("ERR_UNAUTHORIZED_EVIDENCE_SOURCE" in str(context.exception))

    @patch('BountyJudge._pay')
    def test_claim_reward_success(self, mock_pay):
        self.contract.create_bounty("Task", "Crit", "100")
        mock_gl.message.value = 100
        self.contract.fund_bounty("1")
        
        mock_gl.message.sender_address = self.user_address
        self.contract.submit_work("1", "https://github.com/test")

        submissions = json.loads(self.contract.submissions_json)
        submissions["1"]["status"] = "APPROVED"
        self.contract.submissions_json = json.dumps(submissions)

        mock_gl.message.sender_address = self.user_address
        result = self.contract.claim_reward("1")
        
        self.assertTrue(self.user_address in result)
        mock_pay.assert_called_once_with(self.user_address, 100)
        
        bounties = json.loads(self.contract.bounties_json)
        self.assertTrue(bounties["1"]["is_paid"])
        self.assertFalse(bounties["1"]["is_funded"])

if __name__ == '__main__':
    unittest.main()