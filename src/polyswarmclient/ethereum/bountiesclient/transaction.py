from polyswarmclient.ethereum.verifiers import NctApproveVerifier, \
    PostBountyVerifier, PostAssertionVerifier, RevealAssertionVerifier, \
    PostVoteVerifier, SettleBountyVerifier
from polyswarmclient.ethereum.transaction import EthereumTransaction


class PostBountyTransaction(EthereumTransaction):
    def __init__(self, client, artifact_type, amount, bounty_fee, artifact_uri, num_artifacts, duration, bloom_,
                 metadata):
        self.amount = amount
        self.artifact_type = artifact_type
        self.artifact_uri = artifact_uri
        self.duration = duration
        if metadata is not None:
            self.metadata = metadata
        else:
            self.metadata = ''

        approve = NctApproveVerifier(amount + bounty_fee)
        bounty = PostBountyVerifier(artifact_type, amount, artifact_uri, num_artifacts, duration, bloom_, self.metadata)

        super().__init__(client, [approve, bounty])

    def get_path(self):
        return '/bounties'

    def get_body(self):
        body = {
            'amount': str(self.amount),
            'artifact_type': self. artifact_type,
            'uri': self.artifact_uri,
            'duration': self.duration
        }
        if self.metadata:
            body['metadata'] = self.metadata

        return body

    def has_required_event(self, transaction_events):
        bounties = transaction_events.get('bounties', [])
        for bounty in bounties:
            if (bounty.get('amount', '') == str(self.amount) and
                    bounty.get('uri', '') == self.artifact_uri):
                return True

        return False


class PostAssertionTransaction(EthereumTransaction):
    def __init__(self, client, bounty_guid, bid, assertion_fee, mask, commitment):
        self.bounty_guid = bounty_guid
        self.bid = bid
        self.assertion_fee = assertion_fee
        self.mask = mask
        self.commitment = commitment

        approve = NctApproveVerifier(sum(bid) + assertion_fee)
        assertion = PostAssertionVerifier(bounty_guid, bid, mask, commitment)

        super().__init__(client, [approve, assertion])

    def get_body(self):
        return {
            'bid': [str(b) for b in self.bid],
            'mask': self.mask,
            'commitment': str(self.commitment),
        }

    def get_path(self):
        return '/bounties/{0}/assertions'.format(self.bounty_guid)

    def has_required_event(self, transaction_events):
        assertions = transaction_events.get('assertions', [])
        for assertion in assertions:
            if (assertion.get('bid', []) == [str(b) for b in self.bid] and
                    assertion.get('mask', []) == self.mask and
                    assertion.get('commitment', '') == str(self.commitment) and
                    assertion.get('bounty_guid', '') == self.bounty_guid):
                return True

        return False


class RevealAssertionTransaction(EthereumTransaction):
    def __init__(self, client, bounty_guid, index, nonce, verdicts, metadata):
        self.verdicts = verdicts
        self.metadata = metadata
        self.nonce = nonce
        self.guid = bounty_guid
        self.index = index
        reveal = RevealAssertionVerifier(bounty_guid, index, nonce, verdicts, metadata)
        super().__init__(client, [reveal])

    def get_path(self):
        return '/bounties/{0}/assertions/{1}/reveal'.format(self.guid, self.index)

    def get_body(self):
        return {
            'nonce': str(self.nonce),
            'verdicts': self.verdicts,
            'metadata': self.metadata,
        }

    def has_required_event(self, transaction_events):
        reveals = transaction_events.get('reveals', [])
        for reveal in reveals:
            if (reveal.get('verdicts', []) == self.verdicts and
                    reveal.get('metadata', '') == self.metadata and
                    reveal.get('bounty_guid', '') == self.guid):
                return True

        return False


class PostVoteTransaction(EthereumTransaction):
    def __init__(self, client, bounty_guid, votes, valid_bloom):
        self.votes = votes
        self.valid_bloom = valid_bloom
        self.guid = bounty_guid
        vote = PostVoteVerifier(bounty_guid, votes, valid_bloom)
        super().__init__(client, [vote])

    def get_path(self):
        return '/bounties/{0}/vote'.format(self.guid)

    def get_body(self):
        return {
            'votes': self.votes,
            'valid_bloom': self.valid_bloom,
        }

    def has_required_event(self, transaction_events):
        votes = transaction_events.get('votes', [])
        for vote in votes:
            if (vote.get('votes', []) == self.votes and
                    vote.get('bounty_guid', '') == self.guid):
                return True

        return False


class SettleBountyTransaction(EthereumTransaction):
    def __init__(self, client, bounty_guid):
        self.guid = bounty_guid
        settle = SettleBountyVerifier(bounty_guid)
        super().__init__(client, [settle])

    def get_path(self):
        return '/bounties/{0}/settle'.format(self.guid)

    def get_body(self):
        return None

    def has_required_event(self, transaction_events):
        # Settle events are not reported by polyswarmd, transfers are but are not guaranteed
        return True
