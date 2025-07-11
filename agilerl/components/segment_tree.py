import operator
from typing import Callable


class SegmentTree:
    """Create SegmentTree.

    Taken from OpenAI baselines github repository:
    https://github.com/openai/baselines/blob/master/baselines/common/segment_tree.py

    :param capacity: Capacity of segment tree
    :type capacity: int
    :param operation: Operation to apply
    :type operation: Callable
    :param init_value: Initial value
    :type init_value: float
    """

    def __init__(self, capacity: int, operation: Callable, init_value: float):
        assert (
            capacity > 0 and capacity & (capacity - 1) == 0
        ), "capacity must be positive and a power of 2."
        self.capacity = capacity
        self.tree = [init_value for _ in range(2 * capacity)]
        self.operation = operation

    def _operate_helper(
        self, start: int, end: int, node: int, node_start: int, node_end: int
    ) -> float:
        """Returns result of operation in segment.

        :param start: Start index of segment
        :type start: int
        :param end: End index of segment
        :type end: int
        :param node: Current node index
        :type node: int
        :param node_start: Start index of current node
        :type node_start: int
        :param node_end: End index of current node
        :type node_end: int

        :return: Result of operation in segment
        :rtype: float
        """
        if start == node_start and end == node_end:
            return self.tree[node]
        mid = (node_start + node_end) // 2
        if end <= mid:
            return self._operate_helper(start, end, 2 * node, node_start, mid)
        else:
            if mid + 1 <= start:
                return self._operate_helper(start, end, 2 * node + 1, mid + 1, node_end)
            else:
                return self.operation(
                    self._operate_helper(start, mid, 2 * node, node_start, mid),
                    self._operate_helper(mid + 1, end, 2 * node + 1, mid + 1, node_end),
                )

    def operate(self, start: int = 0, end: int = 0) -> float:
        """Returns result of applying `self.operation`.

        :param start: Start index of segment
        :type start: int
        :param end: End index of segment
        :type end: int

        :return: Result of applying `self.operation`
        :rtype: float
        """
        if end <= 0:
            end += self.capacity
        end -= 1

        return self._operate_helper(start, end, 1, 0, self.capacity - 1)

    def __setitem__(self, idx: int, val: float):
        """Set value in tree.

        :param idx: Index to set value at
        :type idx: int
        :param val: Value to set
        :type val: float
        """
        idx += self.capacity
        self.tree[idx] = val

        idx //= 2
        while idx >= 1:
            self.tree[idx] = self.operation(self.tree[2 * idx], self.tree[2 * idx + 1])
            idx //= 2

    def __getitem__(self, idx: int) -> float:
        """Get real value in leaf node of tree.

        :param idx: Index to get value at
        :type idx: int

        :return: Value at index
        :rtype: float
        """
        assert 0 <= idx < self.capacity

        return self.tree[self.capacity + idx]


class SumSegmentTree(SegmentTree):
    """Create SumSegmentTree.

    Taken from OpenAI baselines github repository:
    https://github.com/openai/baselines/blob/master/baselines/common/segment_tree.py

    :param capacity: Capacity of segment tree
    :type capacity: int
    """

    def __init__(self, capacity: int):
        super().__init__(capacity=capacity, operation=operator.add, init_value=0.0)

    def sum(self, start: int = 0, end: int = 0) -> float:
        """Returns sum of elements from start to end index.

        :param start: Start index of range, defaults to 0
        :type start: int, optional
        :param end: End index of range, defaults to 0 (meaning capacity)
        :type end: int, optional
        :return: Sum of elements in range [start, end)
        :rtype: float
        """
        return super().operate(start, end)

    def retrieve(self, upperbound: float) -> int:
        """Find the highest index `i` about `upperbound` in the tree

        :param upperbound: Upper bound for cumulative sum
        :type upperbound: float
        :return: Index where cumulative sum is <= upperbound
        :rtype: int
        """
        # TODO: Check assert case and fix bug
        assert 0 <= upperbound <= self.sum() + 1e-5, f"upperbound: {upperbound}"

        idx = 1
        while idx < self.capacity:  # while non-leaf
            left = 2 * idx
            right = left + 1
            if self.tree[left] > upperbound:
                idx = 2 * idx
            else:
                upperbound -= self.tree[left]
                idx = right
        return idx - self.capacity


class MinSegmentTree(SegmentTree):
    """Create SegmentTree.

    Taken from OpenAI baselines github repository:
    https://github.com/openai/baselines/blob/master/baselines/common/segment_tree.py

    :param capacity: Capacity of segment tree
    :type capacity: int
    """

    def __init__(self, capacity: int):
        super().__init__(capacity=capacity, operation=min, init_value=float("inf"))

    def min(self, start: int = 0, end: int = 0) -> float:
        """Returns minimum element from start to end index.

        :param start: Start index of range, defaults to 0
        :type start: int, optional
        :param end: End index of range, defaults to 0 (meaning capacity)
        :type end: int, optional
        :return: Minimum element in range [start, end)
        :rtype: float
        """
        return super().operate(start, end)
