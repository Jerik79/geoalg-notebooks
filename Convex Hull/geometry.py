from enum import Enum, auto
import math
import numpy as np

class Or(Enum):
    LEFT = auto()
    ON_BEFORE = auto()
    ON_BETWEEN = auto()
    ON_BEHIND = auto()
    RIGHT = auto()

class Point:
    def __init__(self,x,y):
        #self.x = x
        #self.y = y
        self.coords = np.array([x, y])

    @property
    def x(self):
        return self.coords[0]
    
    @property
    def y(self):
        return self.coords[1]
        
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"
    
    def distance(self, other: 'Point') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)
    
    def orientation(self, p: 'Point', q: 'Point') -> Or:
        if p == q:
            raise ValueError("Line (segment) needs two different points")
        val = (q.x - p.x) * (self.y - p.y) - (q.y - p.y) * (self.x - p.x)
        if val > 0.0:
            return Or.LEFT
        elif val < 0.0:
            return Or.RIGHT
        else:
            if p.x != q.x:
                param = (self.x - p.x) / (q.x - p.x)
            else:
                param = (self.y - p.y) / (q.y - p.y)
            if param < 0.0:
                return Or.ON_BEFORE
            elif param > 1.0:
                return Or.ON_BEHIND
            else:
                return Or.ON_BETWEEN
            
class PointRef(Point):
    def __init__(self, container: list[Point], pos: int):
        self.container = container
        self.pos = pos
        
    def get_point(self) -> Point:
        return self.container[self.pos]
    
    @property
    def x(self):
        return self.get_point().x
    
    @property
    def y(self):
        return self.get_point().y

    def get_position(self):
        return self.pos
    
    def is_in_container(self, container: list[Point]) -> bool:
        return container is self.container
    