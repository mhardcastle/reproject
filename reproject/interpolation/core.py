# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import numpy as np
from astropy.coordinates import UnitSphericalRepresentation
from astropy import units as u
from astropy.wcs import WCSSUB_CELESTIAL
from ..wcs_utils import wcs_to_celestial_frame
from ..array_utils import iterate_over_celestial_slices

__all__ = ['interpolate_2d', 'interpolate_celestial_slices']


def get_input_pixels_celestial(wcs_in, wcs_out, shape_out):
    """
    Get the pixel coordinates of the pixels in an array of shape ``shape_out``
    in the input WCS.
    """

    # TODO: for now assuming that coordinates are spherical, not
    # necessarily the case. Also assuming something about the order of the
    # arguments.

    # Find input/output frames
    frame_in = wcs_to_celestial_frame(wcs_in)
    frame_out = wcs_to_celestial_frame(wcs_out)

    # Generate pixel coordinates of output image
    xp_out_ax = np.arange(shape_out[1])
    yp_out_ax = np.arange(shape_out[0])
    xp_out, yp_out = np.meshgrid(xp_out_ax, yp_out_ax)

    # Convert output pixel coordinates to pixel coordinates in original image
    # (using pixel centers).
    xw_out, yw_out = wcs_out.wcs_pix2world(xp_out, yp_out, 0)

    xw_out_unit = u.Unit(wcs_out.wcs.cunit[0])
    yw_out_unit = u.Unit(wcs_out.wcs.cunit[1])

    data = UnitSphericalRepresentation(xw_out * xw_out_unit,
                                       yw_out * yw_out_unit)

    coords_out = frame_out.realize_frame(data)
    coords_in = coords_out.transform_to(frame_in)

    xw_unit_in = u.Unit(wcs_in.wcs.cunit[0])
    yw_unit_in = u.Unit(wcs_in.wcs.cunit[1])

    xw_in = coords_in.spherical.lon.to(xw_unit_in).value
    yw_in = coords_in.spherical.lat.to(yw_unit_in).value

    xp_in, yp_in = wcs_in.wcs_world2pix(xw_in, yw_in, 0)

    return xp_in, yp_in


def interpolate_2d(array, wcs_in, wcs_out, shape_out, order=1):
    """
    Reproject a 2D array from one WCS to another using interpolation.

    Parameters
    ----------
    array : :class:`~numpy.ndarray`
        The array to reproject
    wcs_in : :class:`~astropy.wcs.WCS`
        The input WCS
    wcs_out : :class:`~astropy.wcs.WCS`
        The output WCS
    shape_out : tuple
        The shape of the output array
    order : int
        The order of the interpolation (if ``mode`` is set to
        ``'interpolation'``). A value of ``0`` indicates nearest neighbor
        interpolation (the default).

    Returns
    -------
    array_new : :class:`~numpy.ndarray`
        The reprojected array
    """

    # Get position of output pixel centers in input image
    xp_in, yp_in = get_input_pixels_celestial(wcs_in, wcs_out, shape_out)
    coordinates = [yp_in.ravel(), xp_in.ravel()]

    # Interpolate values to new grid
    from scipy.ndimage import map_coordinates
    array_new = map_coordinates(array, coordinates,
                                order=order, cval=np.nan,
                                mode='constant').reshape(shape_out)

    return array_new


def interpolate_celestial_slices(array, wcs_in, wcs_out, shape_out, order=1):
    """
    Reproject celestial slices from an n-d array from one WCS to another using
    interpolation, and assuming all other dimensions are independent.

    Parameters
    ----------
    array : :class:`~numpy.ndarray`
        The array to reproject
    wcs_in : :class:`~astropy.wcs.WCS`
        The input WCS
    wcs_out : :class:`~astropy.wcs.WCS`
        The output WCS
    shape_out : tuple
        The shape of the output array
    order : int
        The order of the interpolation (if ``mode`` is set to
        ``'interpolation'``). A value of ``0`` indicates nearest neighbor
        interpolation (the default).

    Returns
    -------
    array_new : :class:`~numpy.ndarray`
        The reprojected array
    """

    # For now, assume axes are independent in this routine

    # Check that WCSs are equivalent
    if wcs_in.naxis == wcs_out.naxis and np.any(wcs_in.wcs.axis_types != wcs_out.wcs.axis_types):
        raise ValueError("The input and output WCS are not equivalent")

    # Extract celestial part of WCS in lon/lat order
    wcs_in_celestial = wcs_in.sub([WCSSUB_CELESTIAL])
    wcs_out_celestial = wcs_out.sub([WCSSUB_CELESTIAL])

    # We create an output array with the required shape, then create an array
    # that is in order of [rest, lat, lon] where rest is the flattened
    # remainder of the array. We then operate on the view, but this will change
    # the original array with the correct shape.

    array_new = np.zeros(shape_out)

    xp_in = yp_in = None

    # Loop over slices and interpolate
    for slice_in, slice_out in iterate_over_celestial_slices(array, array_new, wcs_in):

        if xp_in is None:  # Get position of output pixel centers in input image
            xp_in, yp_in = get_input_pixels_celestial(wcs_in_celestial, wcs_out_celestial, slice_out.shape)
            coordinates = [yp_in.ravel(), xp_in.ravel()]

        from scipy.ndimage import map_coordinates
        slice_out[:,:] = map_coordinates(slice_in,
                                         coordinates,
                                         order=order, cval=np.nan,
                                         mode='constant'
                                         ).reshape(slice_out.shape)

    return array_new