# -*- coding: utf-8 -*-
# Author: Dirk Eilander (contact: dirk.eilander@deltares.nl)
# August 2019
"""Core upstream / downstream functionality based on 
parsed indices from core_xxx.py submules"""

from numba import njit, prange
from numba.typed import List
import numpy as np
import math

from pyflwdir import gis_utils

_mv = np.uint32(-1)

#### NETWORK TREE ####
@njit
def _idxs_us(idxs_ds):
    """Return a 2D array with upstream cell indices for each cell 
    
    Parameters
    ----------
    idxs_ds : ndarray of int
        indices of downstream cells
    
    Returns
    -------
    indices of upstream cells : ndarray of int
    """
    n_up = n_upstream(idxs_ds)
    d = np.int64(np.max(n_up))
    n = idxs_ds.size
    # 2D arrays of upstream index
    idxs_us = np.full((n, d), _mv, dtype=np.uint32)
    n_up[:] = np.uint8(0)
    for i in range(n):
        i_ds = idxs_ds[i]
        if i_ds == i:
            continue
        # valid ds cell
        ii = n_up[i_ds]
        idxs_us[i_ds][ii] = i
        n_up[i_ds] += 1
    return idxs_us


@njit
def network_tree(idxs_pits, idxs_us):
    """Return network tree, a list of arrays ordered 
    from down to upstream.
    
    Parameters
    ----------
    idxs_pit, idxs_us : ndarray of int
        indices of pit, upstream cells

    Returns
    -------
    Ordered indices : List of arrays 
    """
    # TODO: test if this works faster with single array per pit
    tree = List()
    tree.append(idxs_pits)
    idxs = idxs_pits
    # move upstream
    while True:
        idxs_us0 = upstream(idxs, idxs_us)
        if idxs_us0.size == 0:  # break if no more upstream
            break
        tree.append(idxs_us0)  # append next leave to tree
        idxs = idxs_us0  # next loop
    return tree  # down- to upstream


#### UPSTREAM / DOWNSTREAM functions ####
@njit
def upstream(idx0, idxs_us):
    """Returns the internal upstream indices.
    
    Parameters
    ----------
    idx0 : array_like of int
        index of local cell(s)
    idxs_us : ndarray of int
        indices of upstream cells

    Returns
    -------
    upstream indices : ndarray of int  
    """
    idxs_us0 = idxs_us[idx0, :].ravel()
    return idxs_us0[idxs_us0 != _mv]


@njit
def _main_upstream(idx0, idxs_us, uparea_sparse, upa_min=0.0):
    """Returns the index of the upstream cell with 
    the largest uparea."""
    idx_us0 = _mv
    upa0 = upa_min
    for idx_us in idxs_us[idx0, :]:
        if idx_us == _mv:
            break
        if uparea_sparse[idx_us] >= upa0:
            idx_us0 = idx_us
            upa0 = uparea_sparse[idx_us]
    return idx_us0


@njit
def main_upstream(idxs, idxs_us, uparea_sparse, upa_min=0.0):
    """Returns the index of the upstream cell with 
    the largest uparea.
    
    Parameters
    ----------
    idxs : ndarray of int
        internal indices of local cells
    idxs_us : ndarray of int
        internal indices of upstream cells
    uparea_sparse : ndarray
        sparse array with upstream area values
    upa_min : float, optional 
        minimum upstream area for cell to be considered
    

    Returns
    -------
    internal upstream indices : ndarray of int  
    """
    if idxs_us.shape[0] != uparea_sparse.size:
        raise ValueError("uparea_sparse has invalid size")
    idxs_us_main = np.ones(idxs.size, dtype=idxs_us.dtype) * _mv
    for i in range(idxs.size):
        idxs_us_main[i] = _main_upstream(
            idxs[i], idxs_us, uparea_sparse, upa_min=upa_min
        )
    return idxs_us_main


@njit
def n_upstream(idxs_ds):
    """Returns array with number of upstream cells per cell.
    
    Parameters
    ----------
    idxs_ds : ndarray of int
        indices of downstream cells
    
    Returns
    -------
    number of upstream cells : ndarray of int  
    """
    n = idxs_ds.size
    n_up = np.zeros(n, dtype=np.uint8)
    for i in range(n):
        i_ds = idxs_ds[i]
        if i != i_ds:  # pit
            n_up[i_ds] += 1
    return n_up


@njit
def idxs_no_upstream(idxs_us):
    """Returns indices of cells without upstream neighbors"""
    return np.where(idxs_us[:, 0] == _mv)[0]


@njit
def downstream(idx0, idxs_ds):
    """Returns next downstream indices.
    
    Parameters
    ----------
    idx0 : int
        index of local cell
    idxs_ds : ndarray of int
        indices of downstream cells

    Returns
    -------
    downstream index : ndarray of int  
    """
    return idxs_ds[idx0]


@njit
def downstream_path(idx0, idxs_ds):
    """Returns path of downstream indices
    
    Parameters
    ----------
    idx0 : int
        index of local cell
    idxs_ds : ndarray of int
        indices of downstream cells

    Returns
    -------
    ndarray of int  
        path of downstrewam indices
    """
    idxs = []
    idxs.append(idx0)
    while True:
        idx_ds = idxs_ds[idx0]
        if idx0 == idx_ds:
            break
        idx0 = idx_ds
        idxs.append(np.uint32(idx0))
    return np.array(idxs, dtype=np.uint32)


@njit
def _downstream_mask(idx0, idxs_ds, mask_sparse):
    """Returns index of nearest downstream True cell. For integer index"""
    at_stream = mask_sparse[idx0]
    while not at_stream:
        idx_ds = idxs_ds[idx0]
        if idx_ds == idx0:  # pit
            break
        idx0 = idx_ds
        at_stream = mask_sparse[idx0]
    return idx0


@njit
def downstream_mask(idxs0, idxs_ds, mask_sparse):
    """Returns index the next downstream True cell.
    
    Parameters
    ----------
    idx0 : int
        index of local cell
    idxs_ds : ndarray of int
        indices of downstream cells
    data : ndarray of bool
        True if stream cell

    Returns
    -------
    ndarray of int  
        downstream stream indices 
    """
    idx_out = np.zeros(idxs0.size, dtype=np.uint32)
    for i in range(idxs0.size):
        idx_out[i] = _downstream_mask(np.uint32(idxs0[i]), idxs_ds, mask_sparse)
    return idx_out

@njit
def flwdir_window(idx0, n, idxs_ds, idxs_us, uparea_sparse, upa_min=0.0):
    """Returns the indices of between the nth upstream to nth downstream cell from 
    the current cell. Upstream cells are with based on the  _main_upstream method."""
    idxs = np.full(n * 2 + 1, _mv, idxs_ds.dtype)
    idxs[n] = idx0
    # get n downstream cells
    for i in range(n):
        idx_ds = idxs_ds[idx0]
        if idx_ds == idx0:  # pit
            break
        idx0 = idx_ds
        idxs[n + i + 1] = idx0
    # get n upstreams cells
    idx0 = idxs[n]
    for i in range(n):
        idx_us = _main_upstream(idx0, idxs_us, uparea_sparse, upa_min=upa_min)
        if idx_us == _mv:  # at headwater / no upstream cells
            break
        idx0 = idx_us
        idxs[n - i - 1] = idx0
    return idxs


@njit
def downstream_length(
    idx0, idxs_ds, idxs_dense, ncol, latlon=False, affine=gis_utils.IDENTITY
):
    """Return the next downstream cell index as well 
    as the length in downstream direction assuming a 
    regular raster defined by the affine transform.
    
    Parameters
    ----------
    idx0 : int
        index of local cell
    idxs_ds : ndarray of int
        indices of downstream cells
    idxs_dense : ndarray of int
        linear indices of dense raster
    ncol : int
        number of columns in raster
    latlon : bool, optional
        True if WGS84 coordinates
        (the default is False)
    affine : affine transform
        Two dimensional transform for 2D linear mapping
        (the default is an identity transform which 
        results in an area of 1 for every cell)

    Returns
    -------
    Tuple of int, float
        downstream index, length
    """
    xres, yres, north = (
        np.float64(affine[0]),
        np.float64(affine[4]),
        np.float64(affine[5]),
    )
    idx1 = downstream(idx0, idxs_ds)  # next downstream
    # convert to flattened raster indices
    idx = idxs_dense[idx0]
    idx_ds = idxs_dense[idx1]
    # compute delta row, col
    r = idx_ds // ncol
    dr = (idx // ncol) - r
    dc = (idx % ncol) - (idx_ds % ncol)
    if latlon:  # calculate cell size in metres
        lat = north + (r + 0.5) * yres
        dy = 0.0 if dr == 0 else gis_utils.degree_metres_y(lat) * yres
        dx = 0.0 if dc == 0 else gis_utils.degree_metres_x(lat) * xres
    else:
        dy = xres
        dx = yres
    return idx1, math.hypot(dy * dr, dx * dc)  # length


#### PIT / LOOP INDICES ####
@njit
def pit_indices(idxs_ds):
    """Returns the internal pit indices, i.e. where the 
    downstream cell is equal to the local cell.
    
    Parameters
    ----------
    idxs_ds : ndarray of int
        internal indices of downstream cells

    Returns
    -------
    1D array of internal downstream indices : ndarray of int  
    """
    idx_lst = []
    for idx0 in range(idxs_ds.size):
        if idx0 == idxs_ds[idx0]:
            idx_lst.append(idx0)
    return np.array(idx_lst, dtype=idxs_ds.dtype)


@njit
def loop_indices(idxs_ds, idxs_us):
    """Returns the internal loop indices, i.e. for cells
    which do not have a pit at its most downstream end.
    
    Parameters
    ----------
    idxs_ds, idxs_us : ndarray of int
        internal indices of pit, downstream, upstream cells

    Returns
    -------
    1D array of internal loop indices : array_like  
    """
    # internal lists
    no_loop = idxs_ds == _mv
    idxs_ds0 = pit_indices(idxs_ds)
    if idxs_ds0.size > 0:  # no valid cells!
        no_loop[idxs_ds0] = True
    # loop over pits and mark upstream area
    while True:
        idxs_us0 = upstream(idxs_ds0, idxs_us)
        if idxs_us0.size == 0:
            break
        no_loop[idxs_us0] = ~no_loop[idxs_us0]
        idxs_ds0 = idxs_us0  # next iter
    return np.where(~no_loop)[0]


#### internal data indexing and reordering functions ####
@njit
def _sparse_idx(idxs, idxs_dense, size):
    """Convert linear indices of dense raster to linear indices of sparse 
    array.
    
    Parameters
    ----------
    idxs : ndarray of int
        linear indices of dense raster to be converted
    idxs_dense : ndarray of int
        linear indices of dense raster of valid cells
    size : int
        size of flwdir raster

    Returns
    -------
    linear sparse indices : ndarray of int    
    """
    # NOTE dense idxs in intp data type, sparse idxs in uint32
    # TODO: test if this can be done faster with sorted idxs array
    if np.any(idxs < 0) or np.any(idxs >= size):
        raise ValueError("Index out of bounds")
    idxs_sparse = np.full(size, _mv, np.uint32)
    idxs_sparse[idxs_dense] = np.array(
        [i for i in range(idxs_dense.size)], dtype=np.uint32
    )
    return idxs_sparse[idxs]


@njit
def _densify(data, idxs_dense, shape, nodata=-9999):
    """Densify sparse array.
    
    Parameters
    ----------
    data : ndarray 
        1D data
    idxs_dense : ndarray of int
        linear indices of dense raster
    shape : tuple of int
        shape of output raster

    Returns
    -------
    2D raster data : ndarray    
    """
    if idxs_dense.size != data.size:
        raise ValueError("data has invalid size")
    data_out = np.full(shape[0] * shape[1], nodata, dtype=data.dtype)
    data_out[idxs_dense] = data
    return data_out.reshape(shape)
