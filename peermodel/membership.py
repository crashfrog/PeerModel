"""Membership proposal and voting structures for cohort lifecycle."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, List
import uuid


@dataclass
class MembershipVote:
    """A cryptographically signed vote on a membership proposal."""

    voter_identity_id: str
    proposal_id: str
    approve: bool
    signature: bytes
    voted_at: datetime = field(default_factory=datetime.now)


@dataclass
class MembershipProposal:
    """Proposal to add or expel a cohort member."""

    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cohort_id: str = ""
    action: Literal["add", "expel"] = "add"
    subject_member_id: str = ""
    subject_credential: dict | None = None
    proposed_by: str = ""
    proposed_at: datetime = field(default_factory=datetime.now)
    votes: List[MembershipVote] = field(default_factory=list)

    def add_vote(self, vote: MembershipVote):
        """Add a vote if voter hasn't already voted."""
        if any(v.voter_identity_id == vote.voter_identity_id for v in self.votes):
            raise ValueError(f"Voter {vote.voter_identity_id} already voted on proposal {self.proposal_id}")
        self.votes.append(vote)

    def check_outcome(self, total_members: int) -> Literal["approved", "rejected", "pending"]:
        """Check if proposal is approved, rejected, or still pending.

        Majority approval required: >50% of members must vote approve.
        """
        if not self.votes:
            return "pending"

        approvals = sum(1 for v in self.votes if v.approve)
        rejections = sum(1 for v in self.votes if not v.approve)

        threshold = (total_members // 2) + 1

        if approvals >= threshold:
            return "approved"
        elif rejections >= threshold:
            return "rejected"
        else:
            return "pending"
