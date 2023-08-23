"""
Object detection in world space.
"""

import numpy as np


# Basically a struct
# pylint: disable=too-few-public-methods
class DetectionInWorld:
    """
    Typically on the ground.
    """
    __create_key = object()

    @classmethod
    def create(cls,
               vertices: np.ndarray,
               centre: np.ndarray,
               label: int,
               confidence: float) -> "tuple[bool, DetectionInWorld | None]":
        """
        vertices is a quadrilateral of 4 points.
        centre is a point.
        A point is an xy coordinate (index 0 and 1 respectively).
        """
        if vertices.shape != (4, 2):
            return False, None

        if centre.shape != (2,):
            return False, None

        if label < 0:
            return False, None

        if confidence < 0.0 or confidence > 1.0:
            return False, None

        return True, DetectionInWorld(cls.__create_key, vertices, centre, label, confidence)

    def __init__(self,
                 class_private_create_key,
                 vertices: np.ndarray,
                 centre: np.ndarray,
                 label: int,
                 confidence: float):
        """
        Private constructor, use create() method.
        """
        assert class_private_create_key is DetectionInWorld.__create_key, "Use create() method"

        self.vertices = vertices
        self.centre = centre
        self.label = label
        self.confidence = confidence

# pylint: enable=too-few-public-methods
