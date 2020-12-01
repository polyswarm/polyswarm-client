from polyswarmclient import BidStrategyBase


class BidStrategy(BidStrategyBase):
    def __init__(self):
        super().__init__(1, 1)
