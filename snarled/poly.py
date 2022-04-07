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


def intersects(poly_a: ArrayLike, poly_b: ArrayLike) -> bool:
    """
    Check if two polygons overlap and/or touch.

    Args:
        poly_a: List of vertices, implicitly closed: `[[x0, y0], [x1, y1], ...]`
        poly_b: List of vertices, implicitly closed: `[[x0, y0], [x1, y1], ...]`

    Returns:
        `True` if the polygons overlap and/or touch.
    """
    poly_a = numpy.array(poly_a, copy=False)
    poly_b = numpy.array(poly_b, copy=False)

    # Check bounding boxes
    min_a = poly_a.min(axis=0)
    min_b = poly_b.min(axis=0)
    max_a = poly_a.max(axis=0)
    max_b = poly_b.max(axis=0)

    if ((min_a > max_b) | (min_b > max_a)).all():
        return False

    #TODO: Check against sorted coords?

    #Check if edges intersect
    if poly_edges_intersect(poly_a, poly_b):
        return True

    # Check if either polygon contains the other
    if poly_contains_points(poly_b, poly_a).any():
        return True

    if poly_contains_points(poly_a, poly_b).any():
        return True

    return False


def poly_edges_intersect(
        poly_a: NDArray[numpy.float64],
        poly_b: NDArray[numpy.float64],
        ) -> NDArray[numpy.int_]:
    """
    Check if the edges of two polygons intersect.

    Args:
        poly_a: NDArray of vertices, implicitly closed: `[[x0, y0], [x1, y1], ...]`
        poly_b: NDArray of vertices, implicitly closed: `[[x0, y0], [x1, y1], ...]`

    Returns:
        `True` if the polygons' edges intersect.
    """
    a_next = numpy.roll(poly_a, -1, axis=0)
    b_next = numpy.roll(poly_b, -1, axis=0)

    # Lists of initial/final coordinates for polygon segments
    xi1 = poly_a[:, 0, None]
    yi1 = poly_a[:, 1, None]
    xf1 = a_next[:, 0, None]
    yf1 = a_next[:, 1, None]

    xi2 = poly_b[:, 0, None]
    yi2 = poly_b[:, 1, None]
    xf2 = b_next[:, 0, None]
    yf2 = b_next[:, 1, None]

    # Perform calculation
    dxi = xi1 - xi2
    dyi = yi1 - yi2
    dx1 = xf1 - xi1
    dx2 = xf2 - xi2
    dy1 = yf1 - yi1
    dy2 = yf2 - yi2

    numerator_a = dx2 * dyi - dy2 * dxi
    numerator_b = dx1 * dyi - dy1 * dxi
    denominator = dy2 * dx1 - dx2 * dy1

    # Avoid warnings since we may multiply eg. NaN*False
    with numpy.errstate(invalid='ignore', divide='ignore'):
        u_a = numerator_a / denominator
        u_b = numerator_b / denominator

        # Find the adjacency matrix
        adjacency = numpy.logical_and.reduce((u_a >= 0, u_a <= 1, u_b >= 0, u_b <= 1))

    return adjacency.any()
