from __future__ import annotations
from typing import TypeVar, Generic, Optional, Iterable, Callable, Any
from enum import Enum
from itertools import chain
from abc import ABC, abstractmethod


K = TypeVar("K")
V = TypeVar("V")

Updater = Callable[[Optional[V]], V]

class ComparisonResult(Enum):
    SMALLER = -1
    EQUAL = 0
    GREATER = 1

class Comparator(ABC, Generic[K]):
    @abstractmethod
    def __call__(self, key: K, item: Any) -> ComparisonResult:
        pass

class DefaultComparator(Generic[K]):
    def __call__(self, key: K, item: Any) -> ComparisonResult:
        if key < item:
            return ComparisonResult.SMALLER
        elif key == item:
            return ComparisonResult.EQUAL
        elif key > item:
            return ComparisonResult.GREATER
        # TODO: raise Error otherwise


class BinaryTree(Generic[K, V]):
    def __init__(self, comparator: Comparator[K] = DefaultComparator[K]()):
        self.root: Node[K, V] = Node.empty_node()
        self.comparator = comparator

    def is_empty(self) -> bool:
        return self.root.is_empty()

    def insert(self, key: K, value: V) -> bool:
        return self.root.insert(key, value, self.comparator)

    def update(self, key: K, updater: Updater[V]) -> bool:
        return self.root.update(key, updater, self.comparator)

    def delete(self, key: K) -> Optional[V]:
        return self.root.delete(key, self.comparator)

    def pop_smallest(self) -> tuple[K, V]:
        return self.root.pop_smallest(self.comparator)

    def smaller_neighbour(self, item: Any) -> Optional[K]:
        return self.root.smaller_neighbour(item, self.comparator)

    def greater_neighbour(self, item: Any) -> Optional[K]:
        return self.root.greater_neighbour(item, self.comparator)

    def range_between_neighbours(self, item: Any) -> list[K]:      # TODO: is list conversion necessary?
        return list(self.root.range_between_neighbours(item, self.comparator))

    def __repr__(self) -> str:
        return self.root.__repr__()


class Node(Generic[K, V]):
    def __init__(self, key: K, value: V, level: int, left: Node[K, V], right: Node[K, V]):
        self.key = key
        self.value = value
        self.level = level
        self.left = left
        self.right = right

    @classmethod
    def empty_node(cls) -> 'Node':
        return cls(None, None, 0, None, None)

    def make_empty(self):
        self.key = None
        self.value = None
        self.level = 0
        self.left = None
        self.right = None

    def is_empty(self) -> bool:
        return self.level == 0      # TODO: maybe use "left is None and right is None" instead...

    def make_leaf(self, key: K, value: V):
        self.key = key
        self.value = value
        self.level = 1
        self.left = Node.empty_node()
        self.right = Node.empty_node()

    def is_leaf(self) -> bool:
        #return self.level == 1     # THIS IS WRONG
        return not self.is_empty() and self.left.is_empty() and self.right.is_empty()

    def get_successor(self) -> Node[K,V]:     # fails if self or self.right is empty... TODO: Add checks?
        successor = self.right
        while not successor.left.is_empty():
            successor = successor.left
        return successor

    def get_predecessor(self) -> Node[K,V]:   # fails if self or self.left is empty... TODO: Add checks?
        predecessor = self.left
        while not predecessor.right.is_empty():
            predecessor = predecessor.right
        return predecessor

    def replace_with_successor(self, comparator: Comparator[K]):
        successor = self.get_successor()
        self.key = successor.key
        self.value = successor.value
        self.right.delete(successor.key, comparator)

    def replace_with_predecessor(self, comparator: Comparator[K]):
        predecessor = self.get_predecessor()
        self.key = predecessor.key
        self.value = predecessor.value
        self.left.delete(predecessor.key, comparator)

    def skew(self):
        if self.is_empty() or self.left.is_empty():
            return
        
        if self.left.level == self.level:
            self.right = Node(self.key, self.value, self.level, self.left.right, self.right)   # TODO: remove allocation?
            self.key = self.left.key
            self.value = self.left.value
            self.left = self.left.left

    def split(self):
        if self.is_empty() or self.right.is_empty() or self.right.right.is_empty():
            return

        if self.right.right.level == self.level:
            self.left = Node(self.key, self.value, self.level, self.left, self.right.left)     # TODO: remove allocation?
            self.key = self.right.key
            self.value = self.right.value
            self.level = self.right.level + 1
            self.right = self.right.right

    def adjust_after_deletion(self):
        if self.is_empty():
            return

        level = min(self.left.level, self.right.level) + 1
        if level < self.level:
            self.level = level
            if level < self.right.level:
                self.right.level = level
        
        self.skew()
        self.right.skew()
        if not self.right.is_empty():
            self.right.right.skew()
        self.split()
        self.right.split()

    def insert(self, key: K, value: V, comparator: Comparator[K]) -> bool:     # TODO: another method for overwriting insertions returning the old value?
        if self.is_empty():
            self.make_leaf(key, value)
            return False
        
        cr = comparator(self.key, key)
        if cr is ComparisonResult.GREATER:
            was_key_present = self.left.insert(key, value, comparator)
        elif cr is ComparisonResult.SMALLER:
            was_key_present = self.right.insert(key, value, comparator)
        else:
            was_key_present = True

        if not was_key_present:
            self.skew()
            self.split()
        return was_key_present

    def update(self, key: K, updater: Updater[V], comparator: Comparator[K]) -> bool:
        if self.is_empty():
            self.make_leaf(key, updater(None))
            return False
        
        cr = comparator(self.key, key)
        if cr is ComparisonResult.GREATER:
            was_key_present = self.left.update(key, updater, comparator)
        elif cr is ComparisonResult.SMALLER:
            was_key_present = self.right.update(key, updater, comparator)
        else:
            self.value = updater(self.value)
            was_key_present = True

        if not was_key_present:
            self.skew()
            self.split()
        return was_key_present

    def delete(self, key: K, comparator: Comparator[K]) -> Optional[V]:
        if self.is_empty():
            return None
        
        cr = comparator(self.key, key)
        if cr is ComparisonResult.GREATER:
            value = self.left.delete(key, comparator)
        elif cr is ComparisonResult.SMALLER:
            value = self.right.delete(key, comparator)
        else:
            value = self.value
            if self.is_leaf():
                self.make_empty()
            elif self.left.is_empty():
                self.replace_with_successor(comparator)
            else:
                self.replace_with_predecessor(comparator)

        self.adjust_after_deletion()        # TODO: this is only necessary if a deletion occured...
        return value

    def pop_smallest(self, comparator: Comparator[K]) -> tuple[K, V]:
        if self.is_empty():
            return None      # TODO: maybe throw assertion instead...

        if not self.left.is_empty():
            key, value = self.left.pop_smallest(comparator)
        else:
            key = self.key
            value = self.value
            if self.is_leaf():
                self.make_empty()
            else:
                self.replace_with_successor(comparator)
        
        self.adjust_after_deletion()
        return key, value

    def smaller_neighbour(self, item: Any, comparator: Comparator[K], previous_key: Optional[K] = None) -> Optional[K]:   # TODO: Also return value?
        if self.is_empty():
            return previous_key

        if comparator(self.key, item) is ComparisonResult.SMALLER:
            return self.right.smaller_neighbour(item, comparator, self.key)
        else:
            return self.left.smaller_neighbour(item, comparator, previous_key)

    def greater_neighbour(self, item: Any, comparator: Comparator[K], previous_key: Optional[K] = None) -> Optional[K]:   # TODO: Also return value?
        if self.is_empty():
            return previous_key

        if comparator(self.key, item) is ComparisonResult.GREATER:
            return self.left.greater_neighbour(item, comparator, self.key)
        else:
            return self.right.greater_neighbour(item, comparator, previous_key)

    def range_between_neighbours(self, item: Any, comparator: Comparator[K]) -> Iterable[K]:      # running time is in O(log(n) * |output|)
        if self.is_empty():
            return ()

        cr = comparator(self.key, item)
        if cr is ComparisonResult.GREATER:
            return self.left.range_between_neighbours(item, comparator)
        elif cr is ComparisonResult.SMALLER:
            return self.right.range_between_neighbours(item, comparator)
        else:
            return chain(
                self.left.range_between_neighbours(item, comparator),
                (self.key,),
                self.right.range_between_neighbours(item, comparator)
            )

    def __repr__(self) -> str:
        if self.is_empty():
            return ", "
        if self.value:
            return f"{self.key}/{self.value} <{self.left.__repr__()}> <{self.right.__repr__()}>"
            #return f"{self.left.__repr__()}{self.key}:{self.value}{self.right.__repr__()}"
        else:
            return f"{self.key} <{self.left.__repr__()}> <{self.right.__repr__()}>"
            #return f"{self.left.__repr__()}{self.key}{self.right.__repr__()}"
