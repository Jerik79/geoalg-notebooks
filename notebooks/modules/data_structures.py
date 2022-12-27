from __future__ import annotations
from typing import TypeVar, Generic, Optional, Iterator, Callable, Any
from enum import Enum
from itertools import chain
from abc import ABC, abstractmethod


K = TypeVar("K")
V = TypeVar("V")

Updater = Callable[[Optional[V]], V]

class ComparisonResult(Enum):
    BEFORE = -1
    MATCH = 0
    AFTER = 1

class Comparator(ABC, Generic[K]):
    @abstractmethod
    def compare(self, item: Any, key: K) -> ComparisonResult:
        pass

class DefaultComparator(Generic[K]):
    def compare(self, item: Any, key: K) -> ComparisonResult:
        if item == key:
            return ComparisonResult.MATCH
        elif item < key:
            return ComparisonResult.BEFORE
        elif item > key:
            return ComparisonResult.AFTER
        else:
            raise RuntimeError(f"Default comparator can't determine order for {item} and {key}.")


# TODO: More methods like contains(key) and pop_last() could be implemented.
class BinaryTree(Generic[K]):
    def __init__(self, comparator: Comparator[K] = DefaultComparator[K]()):
        self._root: Node[K, None] = Node()
        self._comparator = comparator

    def is_empty(self) -> bool:
        return self._root.is_empty()

    def insert(self, key: K) -> bool:
        return self._root.insert(key, None, self._comparator)

    def delete(self, key: K) -> bool:
        return self._root.delete(key, self._comparator)[0]

    def pop_first(self) -> Optional[K]:
        if self._root.is_empty():
            return None

        return self._root.pop_first(self._comparator)[0]

    def search_matching(self, item: Any) -> list[K]:
        return list(self._root.search_matching(item, self._comparator))

    def search_predecessor(self, item: Any) -> Optional[K]:
        return self._root.search_predecessor(item, self._comparator)

    def search_successor(self, item: Any) -> Optional[K]:
        return self._root.search_successor(item, self._comparator)

# TODO: The values should be utilised more. There isn't even a get_value(key) method right now.
class BinaryTreeDict(Generic[K, V]):
    def __init__(self, comparator: Comparator[K] = DefaultComparator[K]()):
        self._root: Node[K, V] = Node()
        self._comparator = comparator

    def is_empty(self) -> bool:
        return self._root.is_empty()

    def insert(self, key: K, value: V) -> bool:
        return self._root.insert(key, value, self._comparator)

    def update(self, key: K, value_updater: Updater[V]) -> bool:
        return self._root.update(key, value_updater, self._comparator)

    def delete(self, key: K) -> tuple[bool, Optional[V]]:
        return self._root.delete(key, self._comparator)

    def pop_first(self) -> Optional[tuple[K, V]]:
        if self._root.is_empty():
            return None

        return self._root.pop_first(self._comparator)

    def search_matching(self, item: Any) -> list[K]:
        return list(self._root.search_matching(item, self._comparator))

    def search_predecessor(self, item: Any) -> Optional[K]:
        return self._root.search_predecessor(item, self._comparator)

    def search_predecessor(self, item: Any) -> Optional[K]:
        return self._root.search_successor(item, self._comparator)

class Node(Generic[K, V]):
    def __init__(self):
        self._make_empty()

    def _make_empty(self):
        self._key: Optional[K] = None
        self._value: Optional[V] = None
        self._level: int = 0
        self._left: Optional[Node] = None
        self._right: Optional[Node] = None

    def is_empty(self) -> bool:
        return self._level == 0

    def _make_leaf(self, key: K, value: V):
        self._key = key
        self._value = value
        self._level = 1
        self._left = Node()
        self._right = Node()

    def _is_leaf(self) -> bool:
        return self._level == 1 and self._right.is_empty()

    def _skew(self):
        if not self.is_empty() and self._left._level == self._level:
            self._key, self._left._key = self._left._key, self._key
            self._value, self._left._value = self._left._value, self._value

            self._left, self._right = self._right, self._left
            self._left, self._right._left = self._right._left, self._left
            self._right._left, self._right._right = self._right._right, self._right._left

    def _split(self):
        if not self.is_empty() and not self._right.is_empty() and self._right._right._level == self._level:
            self._key, self._right._key = self._right._key, self._key
            self._value, self._right._value = self._right._value, self._value
            self._level += 1

            self._left, self._right = self._right, self._left
            self._right, self._left._right = self._left._right, self._right
            self._left._left, self._left._right = self._left._right, self._left._left

    def _adjust_after_deletion(self):
        if not self.is_empty():
            level = min(self._left._level, self._right._level) + 1
            if level < self._level:
                self._level = level
                if level < self._right._level:
                    self._right._level = level

            self._skew()
            self._right._skew()
            if not self._right.is_empty():
                self._right._right._skew()
            self._split()
            self._right._split()

    def _replace_with_predecessor(self, comparator: Comparator[K]):
        predecessor = self._left
        while not predecessor._right.is_empty():
            predecessor = predecessor._right
        self._key = predecessor._key
        self._value = predecessor._value
        self._left.delete(predecessor._key, comparator)

    def _replace_with_successor(self, comparator: Comparator[K]):
        successor = self._right
        while not successor._left.is_empty():
            successor = successor._left
        self._key = successor._key
        self._value = successor._value
        self._right.delete(successor._key, comparator)

    def insert(self, key: K, value: V, comparator: Comparator[K]) -> bool:
        if self.is_empty():
            self._make_leaf(key, value)
            return False

        cr = comparator.compare(key, self._key)
        if cr is ComparisonResult.BEFORE:
            was_key_present = self._left.insert(key, value, comparator)
        elif cr is ComparisonResult.AFTER:
            was_key_present = self._right.insert(key, value, comparator)
        else:
            was_key_present = True

        if not was_key_present:
            self._skew()
            self._split()

        return was_key_present

    def update(self, key: K, value_updater: Updater[V], comparator: Comparator[K]) -> bool:
        if self.is_empty():
            self._make_leaf(key, value_updater(None))
            return False

        cr = comparator.compare(key, self._key)
        if cr is ComparisonResult.BEFORE:
            was_key_present = self._left.update(key, value_updater, comparator)
        elif cr is ComparisonResult.AFTER:
            was_key_present = self._right.update(key, value_updater, comparator)
        else:
            self._value = value_updater(self._value)
            was_key_present = True

        if not was_key_present:
            self._skew()
            self._split()

        return was_key_present

    def delete(self, key: K, comparator: Comparator[K]) -> tuple[bool, Optional[V]]:
        if self.is_empty():
            return False, None

        cr = comparator.compare(key, self._key)
        if cr is ComparisonResult.BEFORE:
            was_key_present, value = self._left.delete(key, comparator)
        elif cr is ComparisonResult.AFTER:
            was_key_present, value = self._right.delete(key, comparator)
        else:
            was_key_present, value = True, self._value
            if not self._left.is_empty():
                self._replace_with_predecessor(comparator)
            elif not self._right.is_empty():
                self._replace_with_successor(comparator)
            else:
                self._make_empty()

        if was_key_present:
            self._adjust_after_deletion()

        return was_key_present, value

    def pop_first(self, comparator: Comparator[K]) -> tuple[K, V]:
        if not self._left.is_empty():
            key, value = self._left.pop_first(comparator)
        else:
            key, value = self._key, self._value
            if not self._right.is_empty():
                self._replace_with_successor(comparator)
            else:
                self._make_empty()

        self._adjust_after_deletion()

        return key, value

    def search_matching(self, item: Any, comparator: Comparator[K]) -> Iterator[K]:
        if self.is_empty():
            return ()

        cr = comparator.compare(item, self._key)
        if cr is ComparisonResult.BEFORE:
            return self._left.search_matching(item, comparator)
        elif cr is ComparisonResult.AFTER:
            return self._right.search_matching(item, comparator)
        else:
            return chain(
                self._left.search_matching(item, comparator),
                (self._key,),
                self._right.search_matching(item, comparator)
            )

    def search_predecessor(self, item: Any, comparator: Comparator[K], candidate: Optional[K] = None) -> Optional[K]:
        if self.is_empty():
            return candidate

        if comparator.compare(item, self._key) is ComparisonResult.AFTER:
            return self._right.search_predecessor(item, comparator, self._key)
        else:
            return self._left.search_predecessor(item, comparator, candidate)

    def search_successor(self, item: Any, comparator: Comparator[K], candidate: Optional[K] = None) -> Optional[K]:
        if self.is_empty():
            return candidate

        if comparator.compare(item, self._key) is ComparisonResult.BEFORE:
            return self._left.search_successor(item, comparator, self._key)
        else:
            return self._right.search_successor(item, comparator, candidate)
