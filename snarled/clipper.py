"""
Wrappers to simplify some pyclipper functions
"""
from typing import Sequence, Optional, List

from numpy.typing import ArrayLike
from pyclipper import (
    Pyclipper, PT_CLIP, PT_SUBJECT, CT_UNION, CT_INTERSECTION, PFT_NONZERO, PFT_EVENODD,
    PyPolyNode, CT_DIFFERENCE,
    )

from .types import contour_t


def union_nonzero(shapes: Sequence[ArrayLike]) -> Optional[PyPolyNode]:
    if not shapes:
        return None
    pc = Pyclipper()
    pc.AddPaths(shapes, PT_CLIP, closed=True)
    result = pc.Execute2(CT_UNION, PFT_NONZERO, PFT_NONZERO)
    return result


def union_evenodd(shapes: Sequence[ArrayLike]) -> List[contour_t]:
    if not shapes:
        return []
    pc = Pyclipper()
    pc.AddPaths(shapes, PT_CLIP, closed=True)
    return pc.Execute(CT_UNION, PFT_EVENODD, PFT_EVENODD)


def intersection_evenodd(
        subject_shapes: Sequence[ArrayLike],
        clip_shapes: Sequence[ArrayLike],
        ) -> List[contour_t]:
    if not subject_shapes or not clip_shapes:
        return []
    pc = Pyclipper()
    pc.AddPaths(subject_shapes, PT_SUBJECT, closed=True)
    pc.AddPaths(clip_shapes, PT_CLIP, closed=True)
    return pc.Execute(CT_INTERSECTION, PFT_EVENODD, PFT_EVENODD)


def difference_evenodd(
        subject_shapes: Sequence[ArrayLike],
        clip_shapes: Sequence[ArrayLike],
        ) -> List[contour_t]:
    if not subject_shapes:
        return []
    if not clip_shapes:
        return subject_shapes
    pc = Pyclipper()
    pc.AddPaths(subject_shapes, PT_SUBJECT, closed=True)
    pc.AddPaths(clip_shapes, PT_CLIP, closed=True)
    return pc.Execute(CT_DIFFERENCE, PFT_EVENODD, PFT_EVENODD)


def hier2oriented(polys: Sequence[PyPolyNode]) -> List[ArrayLike]:
    contours = []
    for poly in polys:
        contours.append(poly.Contour)
        contours += [hole.Contour for hole in poly.Childs]

    return contours
