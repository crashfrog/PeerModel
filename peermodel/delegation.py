from peermodel.capabilities import IdentityManager, Keysystem, SoftwareKeysystem
from peermodel import primitives
from typing import Union, Iterator, List, Optional
from abc import ABC, abstractmethod
from collections import defaultdict
from itertools import chain
from cryptography.fernet import Fernet
import json

"""
A cohort model of delegation where the cohort is the group of people who have access to a peermodel database.

A cohort is a group of people who have access to a peermodel database. Each cohort has a unique name, and each person in the cohort has a unique identity. The cohort is the group of people who have access to the database, and the identity is the unique identifier for each person in the cohort.

A peermodel database includes a default 'public' cohort to which every user of the database belongs.

A cohort member can extend 'guest' access to other users. Guest access allows the guest to read the database, but not to write to it.

A cohort member can invite a guest to join the cohort. A majority of cohort members must approve the invitation before the guest is added to the cohort.

"""

class Cohort(ABC):

    KeyExchange = defaultdict(lambda: defaultdict(Keysystem))
    
    # CLI api

    def create(self):
        pass
    

    def invite(self):
        pass
    

    def review(self):
        pass
    

    def approve(self):
        pass
    

    def revoke(self):
        pass


    def regenerate(self):
        pass

    # public API
    @classmethod
    @abstractmethod
    def lookupCohort(cls, identity, db):
        return

    @property
    @abstractmethod
    def keysystem(self) -> Keysystem:
        pass

    @property
    @abstractmethod
    def guests(self) -> Iterator[Keysystem]:
        pass

    @property
    @abstractmethod
    def members(self) -> Iterator[Keysystem]:
        pass

    @property
    def readers(self) -> Iterator[Keysystem]:
        return chain(self.members, self.guests)

    @abstractmethod
    def generateRecordKey(self):
        pass

    @property
    @abstractmethod
    def signature(self):
        pass
    
    

class SimpleCohort(Cohort):
    """Concrete implementation of Cohort using software keysystem."""

    def __init__(self, cohort_id, founder_identity, members=None, guests=None, signing_key_der=None):
        """Initialize a cohort.

        Args:
            cohort_id: Unique identifier for this cohort
            founder_identity: Identity of the founder
            members: List of member identities (default: [founder_identity])
            guests: List of guest identities (default: [])
            signing_key_der: Ed25519 private key for cohort signatures (default: generate new)
        """
        self.cohort_id = cohort_id
        self.founder_identity = founder_identity
        self._members = members or [founder_identity]
        self._guests = guests or []
        self._proposals = {}
        self._sequence_number = 0

        # Generate cohort keypair (X25519 for encryption, Ed25519 for signing)
        cohort_x25519_priv, cohort_x25519_pub, cohort_ed25519_priv, cohort_ed25519_pub = primitives.generate_keypair()
        self.cohort_x25519_private = cohort_x25519_priv
        self.cohort_x25519_public = cohort_x25519_pub
        self.cohort_ed25519_private = cohort_ed25519_priv
        self.cohort_ed25519_public = cohort_ed25519_pub

        # Use provided signing_key_der if given, otherwise use generated cohort Ed25519 key
        if signing_key_der is None:
            signing_key_der = cohort_ed25519_priv
        self.signing_key_der = signing_key_der

        self._keysystem = SoftwareKeysystem(
            founder_identity['x25519_private'],
            founder_identity['x25519_public'],
            founder_identity['ed25519_private'],
            founder_identity['ed25519_public']
        )
        self._record_key = Fernet.generate_key()

    @classmethod
    def lookupCohort(cls, identity, db):
        """Look up a cohort by identity (stub for Phase 2)."""
        return None

    @property
    def keysystem(self) -> Keysystem:
        """Return the keysystem for this cohort."""
        return self._keysystem

    @property
    def guests(self) -> Iterator:
        """Return iterator over guest identities."""
        return iter(self._guests)

    @property
    def members(self) -> Iterator:
        """Return iterator over member identities."""
        return iter(self._members)

    def generateRecordKey(self):
        """Generate a new Fernet key for record encryption."""
        return Fernet.generate_key()

    def get_cohort_public_keys(self):
        """Get cohort public keys for distribution to members.

        Returns:
            dict: Dictionary with 'x25519_public' and 'ed25519_public' keys
        """
        return {
            'x25519_public': self.cohort_x25519_public,
            'ed25519_public': self.cohort_ed25519_public
        }

    def sign_cohort_message(self, message):
        """Sign a message using cohort's Ed25519 key.

        Args:
            message: bytes to sign

        Returns:
            bytes: Ed25519 signature (64 bytes)
        """
        return primitives.sign_bytes(message, self.cohort_ed25519_private, algorithm='ed25519')

    def encrypt_for_member(self, plaintext, member_x25519_public_key_der):
        """Encrypt data for a member using cohort encryption key.

        Args:
            plaintext: bytes to encrypt
            member_x25519_public_key_der: DER-encoded X25519 public key of member

        Returns:
            tuple: (ciphertext, salt, tag, ephemeral_public_key) - result of encrypt_to_recipient
        """
        return primitives.encrypt_to_recipient(plaintext, member_x25519_public_key_der)

    def regenerate_cohort_keypair(self):
        """Regenerate cohort keypair for forward secrecy.

        Generates new X25519 and Ed25519 keypairs for the cohort.
        This invalidates all previously encrypted material and signatures.
        """
        cohort_x25519_priv, cohort_x25519_pub, cohort_ed25519_priv, cohort_ed25519_pub = primitives.generate_keypair()
        self.cohort_x25519_private = cohort_x25519_priv
        self.cohort_x25519_public = cohort_x25519_pub
        self.cohort_ed25519_private = cohort_ed25519_priv
        self.cohort_ed25519_public = cohort_ed25519_pub
        # Update signing_key_der to use new cohort key
        self.signing_key_der = cohort_ed25519_priv

    @property
    def signature(self):
        """Compute signature over cohort metadata.

        Returns:
            bytes: Ed25519 signature of cohort_id
        """
        message = json.dumps({
            'cohort_id': self.cohort_id,
            'members': len(self._members),
            'guests': len(self._guests)
        }).encode('utf-8')
        return primitives.sign_bytes(message, self.signing_key_der)

    def addMember(self, member_identity):
        """Add a member to the cohort."""
        if member_identity not in self._members:
            self._members.append(member_identity)

    def removeMember(self, member_identity):
        """Remove a member from the cohort."""
        if member_identity in self._members:
            self._members.remove(member_identity)

    def create_add_member_proposal(self, subject_identity, proposer_identity):
        """Create a proposal to add a new member."""
        from peermodel.membership import MembershipProposal

        # Check subject not already member
        member_ids = [m['identity_id'] for m in self._members]
        if subject_identity['identity_id'] in member_ids:
            raise ValueError(f"{subject_identity['identity_id']} is already a member")

        proposal = MembershipProposal(
            cohort_id=self.cohort_id,
            action="add",
            subject_member_id=subject_identity['identity_id'],
            subject_credential={
                'x25519_public': subject_identity['x25519_public'],
                'ed25519_public': subject_identity['ed25519_public']
            },
            proposed_by=proposer_identity['identity_id']
        )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def create_expel_member_proposal(self, subject_identity, proposer_identity):
        """Create a proposal to expel a member."""
        from peermodel.membership import MembershipProposal

        # Cannot expel founder
        if subject_identity['identity_id'] == self.founder_identity['identity_id']:
            raise ValueError("Cannot expel founder")

        proposal = MembershipProposal(
            cohort_id=self.cohort_id,
            action="expel",
            subject_member_id=subject_identity['identity_id'],
            proposed_by=proposer_identity['identity_id']
        )
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def vote_on_proposal(self, proposal_id, voter_identity, approve):
        """Vote on a membership proposal."""
        from peermodel.membership import MembershipVote

        # Check voter is member
        voter_ids = [m['identity_id'] for m in self._members]
        if voter_identity['identity_id'] not in voter_ids:
            raise ValueError(f"{voter_identity['identity_id']} is not a member")

        proposal = self._proposals[proposal_id]

        # Create signed vote
        message = json.dumps({
            'proposal_id': proposal_id,
            'approve': approve
        }).encode('utf-8')
        signature = primitives.sign_bytes(message, voter_identity['ed25519_private'])

        vote = MembershipVote(
            voter_identity_id=voter_identity['identity_id'],
            proposal_id=proposal_id,
            approve=approve,
            signature=signature
        )
        proposal.add_vote(vote)
        return proposal

    def execute_proposal(self, proposal):
        """Execute an approved proposal (add or expel member)."""
        outcome = proposal.check_outcome(len(self._members))
        if outcome != "approved":
            raise ValueError(f"Cannot execute proposal with status: {outcome}")

        if proposal.action == "add":
            # Add member
            new_member = {
                'identity_id': proposal.subject_member_id,
                'x25519_public': proposal.subject_credential['x25519_public'],
                'ed25519_public': proposal.subject_credential['ed25519_public']
            }
            self.addMember(new_member)
        elif proposal.action == "expel":
            # Remove member
            member_to_remove = next(
                (m for m in self._members if m['identity_id'] == proposal.subject_member_id),
                None
            )
            if member_to_remove:
                self.removeMember(member_to_remove)

    def create_operation(self, op_type, record_type, record_id, payload, previous_head_cid, initiator):
        """Create and sign an operation record.

        Args:
            op_type: Type of operation (insert, update, tombstone)
            record_type: Type of document being operated on
            record_id: ID of the record being operated on
            payload: The operation data (None for tombstone operations)
            previous_head_cid: CID of the previous operation (None for first)
            initiator: Identity of the member initiating the operation

        Returns:
            OperationRecord: Signed operation record

        Raises:
            ValueError: If op_type is invalid
        """
        from peermodel.operations import OperationRecord, canonical_op_bytes
        from datetime import datetime, timezone
        from uuid import uuid4

        # Validate required parameters
        if initiator is None:
            raise TypeError("initiator cannot be None")
        if record_type is None:
            raise ValueError("record_type cannot be None")
        if record_id is None:
            raise ValueError("record_id cannot be None")

        # Validate op_type
        valid_op_types = ["insert", "update", "tombstone"]
        if op_type not in valid_op_types:
            raise ValueError(f"Invalid op_type: {op_type}. Must be one of {valid_op_types}")

        # Increment sequence number
        self._sequence_number += 1

        # Generate operation record with datetime timestamp
        timestamp = datetime.now(timezone.utc)

        op = OperationRecord(
            op_id=str(uuid4()),
            op_type=op_type,
            cohort_id=self.cohort_id,
            record_type=record_type,
            record_id=record_id,
            sequence_number=self._sequence_number,
            payload=payload,
            previous_head_cid=previous_head_cid,
            timestamp=timestamp,
            schema_version="1.0",
            signature=b"",  # Placeholder, will be replaced
            signing_algorithm="Ed25519"
        )

        # Sign the operation using canonical CBOR encoding
        canonical_bytes = canonical_op_bytes(op)
        signature = primitives.sign_bytes(canonical_bytes, self.signing_key_der)

        # Create final operation with signature
        op.signature = signature

        return op



    def regenerate(self):
        """Regenerate cohort signing/encryption keys."""
        self.regenerate_cohort_keypair()


class Guest(ABC):

    def invite(self):
        pass

    def review(self):
        pass

    def approve(self):
        pass

    def revoke(self):
        pass
