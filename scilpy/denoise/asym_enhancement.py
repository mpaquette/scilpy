# -*- coding: utf-8 -*-

import numpy as np
from dipy.reconst.shm import sh_to_sf_matrix
from dipy.data import get_sphere
from dipy.core.sphere import Sphere
from scipy.ndimage import correlate


def local_asym_gaussian_filtering(in_sh, sh_order=8, sh_basis='descoteaux07',
                                  out_full_basis=True, dot_sharpness=1.0,
                                  sphere_str='repulsion724', sigma=1.0,
                                  mask=None):
    """Average the SH projected on a sphere using a first-neighbor gaussian
    blur and a dot product weight between sphere directions and the direction
    to neighborhood voxels, forcing to 0 negative values and thus performing
    asymmetric hemisphere-aware filtering.

    Parameters
    ----------
    in_sh: ndarray (x, y, z, n_coeffs)
        Input SH coefficients array
    sh_order: int, optional
        Maximum order of the SH series.
    sh_basis: {'descoteaux07', 'tournier07'}, optional
        SH basis of the input signal.
    out_full_basis: bool, optional
        If True, save output SH using full SH basis.
    dot_sharpness: float, optional
        Exponent of the dot product. When set to 0.0, directions
        are not weighted by the dot product.
    sphere_str: str, optional
        Name of the sphere used to project SH coefficients to SF.
    sigma: float, optional
        Sigma for the Gaussian.
    mask: ndarray (x, y, z), optional
        Mask identifying voxels to average. If None,
        then all voxels are averaged.

    Returns
    -------
    out_sh: ndarray (x, y, z, n_coeffs)
        Filtered signal as SH coefficients.
    """
    # Load the sphere used for projection of SH
    sphere = get_sphere(sphere_str)

    # Normalized filter for each sf direction
    weights = _get_weights(sphere, dot_sharpness, sigma)

    # Detect if the basis is full based on its order
    # and the number of coefficients of the SH
    in_full_basis = in_sh.shape[-1] == (sh_order + 1)**2

    nb_dir = len(sphere.vertices)
    mean_sf = np.zeros(np.append(in_sh.shape[:-1], nb_dir))
    B = sh_to_sf_matrix(sphere, sh_order=sh_order, basis_type=sh_basis,
                        return_inv=False, full_basis=in_full_basis)

    # We want a B matrix to project on an inverse sphere to have the sf on
    # the opposite hemisphere for a given vertice
    neg_B = sh_to_sf_matrix(Sphere(xyz=-sphere.vertices), sh_order=sh_order,
                            basis_type=sh_basis, return_inv=False,
                            full_basis=in_full_basis)

    # Apply filter to each sphere vertice
    for dir_i in range(nb_dir):
        w_filter = weights[..., dir_i]
        curr_dir_eval = np.dot(in_sh, B[:, dir_i])
        opposite_dir_eval = np.dot(in_sh, neg_B[:, dir_i])
        if mask is None:
            # Calculate contribution of center voxel
            mean_sf[..., dir_i] = w_filter[1, 1, 1] * curr_dir_eval

            # Add contributions of neighbors using opposite hemispheres
            w_filter[1, 1, 1] = 0.0
            mean_sf[..., dir_i] += correlate(opposite_dir_eval, w_filter,
                                             mode='constant')
        else:
            mean_sf[..., dir_i] = _apply_naive_correlation(curr_dir_eval,
                                                           opposite_dir_eval,
                                                           w_filter, mask)

    # Convert back to SH coefficients
    _, B_inv = sh_to_sf_matrix(sphere, sh_order=sh_order, basis_type=sh_basis,
                               full_basis=out_full_basis)

    out_sh = np.array([np.dot(i, B_inv) for i in mean_sf], dtype=in_sh.dtype)
    return out_sh


def _get_weights(sphere, dot_sharpness, sigma):
    """
    Get neighbors weight in respect to the direction to a voxel.

    Parameters
    ----------
    sphere: Sphere
        Sphere used for SF reconstruction.
    dot_sharpness: float
        Dot product exponent.
    sigma: float
        Variance of the gaussian used for weighting neighbors.

    Returns
    -------
    weights: dictionary
        Vertices weights with respect to voxel directions.
    """
    directions = np.zeros((3, 3, 3, 3))
    for x in range(3):
        for y in range(3):
            for z in range(3):
                directions[x, y, z, 0] = x - 1
                directions[x, y, z, 1] = y - 1
                directions[x, y, z, 2] = z - 1

    non_zero_dir = np.ones((3, 3, 3), dtype=bool)
    non_zero_dir[1, 1, 1] = False

    # normalize dir
    dir_norm = np.linalg.norm(directions, axis=-1, keepdims=True)
    directions[non_zero_dir] /= dir_norm[non_zero_dir]

    g_weights = np.exp(-dir_norm**2 / (2 * sigma**2))
    d_weights = np.dot(directions, sphere.vertices.T)

    d_weights = np.where(d_weights > 0.0, d_weights**dot_sharpness, 0.0)
    weights = d_weights * g_weights
    weights[1, 1, 1, :] = 1.0

    # Normalize filters so that all sphere directions weights sum to 1
    weights /= weights.reshape((-1, weights.shape[-1])).sum(axis=0)

    return weights


def _apply_naive_correlation(curr_dir, opposite_dir, w_filter, mask):
    shape = curr_dir.shape
    out = np.zeros_like(curr_dir)
    curr_dir = np.pad(curr_dir, ((1, 1), (1, 1), (1, 1)))
    opposite_dir = np.pad(opposite_dir, ((1, 1), (1, 1), (1, 1)))
    mask = np.pad(mask, ((1, 1), (1, 1), (1, 1)))
    for ii in range(shape[0]):
        for jj in range(shape[1]):
            for kk in range(shape[2]):
                win_arr = opposite_dir[ii:ii+3, jj:jj+3, kk:kk+3]
                win_arr[1, 1, 1] = curr_dir[ii+1, jj+1, kk+1]
                win_mask = mask[ii:ii+3, jj:jj+3, kk:kk+3]

                curr_w = w_filter * win_mask
                if curr_w.any():
                    curr_w /= curr_w.sum()  # such that curr_w sums to 1

                if win_mask[1, 1, 1] > 0.:  # only update non-zero fODF
                    out[ii, jj, kk] = \
                        (win_arr.flatten() * curr_w.flatten()).sum()
    return out
