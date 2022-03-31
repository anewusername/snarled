"""
Utilities for working with polygons
"""
import numpy
from numpy.typing import NDArray, ArrayLike


def poly_contains_points(
        vertices: ArrayLike,
        points: ArrayLike,
        include_boundary: bool = True,
        ) -> NDArray[numpy.int_]:
    """
    Tests whether the provided points are inside the implicitly closed polygon
    described by the provided list of vertices.

    Args:
        vertices: Nx2 Arraylike of form [[x0, y0], [x1, y1], ...], describing an implicitly-
            closed polygon. Note that this should include any offsets.
        points: Nx2 ArrayLike of form [[x0, y0], [x1, y1], ...] containing the points to test.
        include_boundary: True if points on the boundary should be count as inside the shape.
            Default True.

    Returns:
        ndarray of booleans, [point0_is_in_shape, point1_is_in_shape, ...]
    """
    points = numpy.array(points, copy=False)
    vertices = numpy.array(vertices, copy=False)

    if points.size == 0:
        return numpy.zeros(0)

    min_bounds = numpy.min(vertices, axis=0)[None, :]
    max_bounds = numpy.max(vertices, axis=0)[None, :]

    trivially_outside = ((points < min_bounds).any(axis=1)
                       | (points > max_bounds).any(axis=1))

    nontrivial = ~trivially_outside
    if trivially_outside.all():
        inside = numpy.zeros_like(trivially_outside, dtype=bool)
        return inside

    ntpts = points[None, nontrivial, :]     # nontrivial points, along axis 1 of ndarray
    verts = vertices[:, None, :]            # vertices, along axis 0
    xydiff = ntpts - verts      # Expands into (n_vertices, n_ntpts, 2)

    y0_le = xydiff[:, :, 1] >= 0                   # y_point >= y_vertex (axes 0, 1 for all points & vertices)
    y1_le = numpy.roll(y0_le, -1, axis=0)          # same thing for next vertex

    upward = y0_le & ~y1_le         # edge passes point y coord going upwards
    downward = ~y0_le & y1_le       # edge passes point y coord going downwards

    dv = numpy.roll(verts, -1, axis=0) - verts
    is_left = (dv[..., 0] * xydiff[..., 1]        # >0 if left of dv, <0 if right, 0 if on the line
             - dv[..., 1] * xydiff[..., 0])

    winding_number = ((upward & (is_left > 0)).sum(axis=0)
                  - (downward & (is_left < 0)).sum(axis=0))

    nontrivial_inside = winding_number != 0        # filter nontrivial points based on winding number
    if include_boundary:
        nontrivial_inside[(is_left == 0).any(axis=0)] = True        # check if point lies on any edge

    inside = nontrivial.copy()
    inside[nontrivial] = nontrivial_inside
    return inside
