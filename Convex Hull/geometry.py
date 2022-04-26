from enum import Enum, auto
import math
import numpy as np

class Orientation(Enum):
    LEFT = auto()
    RIGHT = auto()
    BEHIND_SOURCE = auto()
    BETWEEN = auto()
    BEHIND_TARGET = auto()

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
    
    def orientation(self, source: 'Point', target: 'Point') -> Orientation:
        if source == target:
            raise ValueError("Line (segment) needs two different points")
        val = (target.x - source.x) * (self.y - source.y) - (target.y - source.y) * (self.x - source.x)
        if val > 0.0:
            return Orientation.LEFT
        elif val < 0.0:
            return Orientation.RIGHT
        else:
            if source.x != target.x:
                param = (self.x - source.x) / (target.x - source.x)
            else:
                param = (self.y - source.y) / (target.y - source.y)
            if param < 0.0:
                return Orientation.BEHIND_SOURCE
            elif param > 1.0:
                return Orientation.BEHIND_TARGET
            else:
                return Orientation.BETWEEN
            
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
    