"""This module contains functions relevant to the ALARA activation code.
"""
from __future__ import print_function
import numpy as np
import tables as tb

try:
    from itaps import iMesh, iBase, iMeshExtensions
except ImportError:
    warnings.warn("the PyTAPS optional dependency could not be imported. "
         "Some aspects of the alara module may be incomplete.", ImportWarning)

from mesh import Mesh, MeshError

def flux_mesh_to_fluxin(flux_mesh, flux_tag, fluxin="fluxin.out", 
                        reverse=False):
    """This function creates an ALARA fluxin file from fluxes tagged on a PyNE
    Mesh object. Structured meshes are printed in xyz order (z changes fastest)
    and unstructured meshes are printed in the imesh.iterate() order.

    Parameters
    ----------
    flux_mesh : PyNE Mesh object
        Contains the mesh with fluxes tagged on each volume element.
    flux_tag : string
        The name of the tag of the flux mesh. Flux values for different energy
        groups are assumed to be represented as vector tags.
    fluxin : string
        The name of the ALARA fluxin file to be output.
    reverse : bool
        If true, fluxes will be printed in the reverse order as they appear in
        the flux vector tagged on the mesh.
    """
    tag_flux = flux_mesh.mesh.getTagHandle(flux_tag)

    if flux_mesh.structured:
        ves = flux_mesh.structured_iterate_hex("xyz")
    else:
        ves = flux.mesh.mesh.iterate(iBase.Type.region, iMesh.Toplogy.all)

    # find number of e_groups
    e_groups = flux_mesh.mesh.getTagHandle(flux_tag)[list(
                    flux_mesh.mesh.iterate(iBase.Type.region, 
                                           iMesh.Topology.all))[0]]
    e_groups = np.atleast_1d(e_groups)
    num_e_groups = len(e_groups)

    # Establish for loop bounds based on if forward or backward printing
    # is requested
    if not reverse:
        start = 0
        stop = num_e_groups
        direction = 1
    else:
        start = num_e_groups - 1
        stop = -1
        direction = -1

    output = ""
    for ve in ves:
        # print flux data to file
        count = 0
        flux_data = np.atleast_1d(tag_flux[ve])
        for i in range(start, stop, direction):
            output += "{:.6E} ".format(flux_data[i])
            # fluxin formatting: create a new line after every 6th entry
            count += 1
            if count % 6 == 0:
                output += "\n"
    
        output += "\n\n"

    with open(fluxin, "w") as f:
        f.write(output)

def photon_source_to_hdf5(filename, chunkshape=(10000,)):
    """Converts a plaintext photon source file to an HDF5 version for 
    quick later use. 

    Parameters
    ----------
    filename : str
        The path to the file
    chunkshape : tuple of int
        A 1D tuple of the HDF5 chunkshape.

    Output
    ------
    A single HDF5 file named filename.h5 containg the table headings:

    ve_idx : int
        The volume element index assuming the volume elements appear in xyz
        order (z changing fastest).
    nuc : str
        The nuclide name as it appears in the photon source file.
    time : str
        The decay time as it appears in the photon source file.
    phtn_src : 1D array of floats
        Contains the photon source density for each energy group.   
    """
    f = open(filename, 'r')
    header = f.readline().strip().split('\t')
    f.seek(0)
    G = len(header) - 2

    dt = np.dtype([
        ('ve_idx', np.int64),
        ('nuc', 'S6'),
        ('time', 'S20'),
        ('phtn_src', np.float64, G),
        ])

    filters = tb.Filters(complevel=1, complib='zlib')
    h5f = tb.openFile(filename + '.h5', 'w', filters=filters)
    tab = h5f.createTable('/', 'data', dt, chunkshape=chunkshape)

    chunksize = chunkshape[0]
    rows = np.empty(chunksize, dtype=dt)
    ve_idx = 0
    for i, line in enumerate(f, 1):
        ls = line.strip().split('\t')

        # Keep track of the ve_idx by delimiting by the last TOTAL line in a
        # volume element.
        if i != 1:
            if ls[0]  != 'TOTAL' and old == 'TOTAL':
                ve_idx += 1

        j = (i-1)%chunksize
        rows[j] = (ve_idx, ls[0].strip(), ls[1].strip(), np.array(ls[2:], dtype=np.float64))
        # Save the isotope in order to keep track of ve_idx
        old = ls[0].strip()

        if i%chunksize == 0:
            tab.append(rows)
            rows = np.empty(chunksize, dtype=dt)

    if i%chunksize != 0:
        tab.append(rows[:j+1])

    h5f.close()
    f.close()

def photon_source_h5_to_mesh(photon_source_h5, mesh, tags):
    """This function reads in an h5 file produced by photon_source_to_hdf5 and
    tags the requested data to the mesh of a PyNE Mesh object. Any combinations
    of isotopes and decay times are allowed. The photon source file is assumed
    to be in xyz order (z changes fastest) if a stuctured mesh is supplied
    and imesh.iterate() order if an unstructured mesh is supplied.

    Parameters
    ----------
    photon_source_h5 : str
        The path of the hdf5 version of the photon source file.
    mesh : PyNE Mesh
       The object containing the imesh instance to be tagged.
    tags: dict
        A dictionary were the keys are tuples with two values. The first is a
        string denoting an isotope as it appears in the photon source file.
        (e.g. 'h-1', 'u-235', 'TOTAL'). The second is a string denoting the 
        decay time as it appears in the file (e.g. 'shutdown', '1 h' '3 d'. The
        values are the requested tag names for the combination of isotope and
        decay time. For example if one wanted tags for the photon source
        densities from U235 at shutdown and from all isotopes at 1 hour, the
        dictionary would be:

        tags = {('u-235', 'shutdown') : 'tag1', ('TOTAL', '1, h') : 'tag2'}
    """
    
    if mesh.structured:
        ves = list(mesh.structured_iterate_hex("xyz"))
    else:
        ves = list(mesh.imesh.iterate(iBase.Type.region, iMesh.Topology.all))

    with tb.openFile(photon_source_h5) as h5f:
         data = h5f.root.data[:]

    # find number of energy groups
    num_e_groups = len(data[0]) - 3

    # create a dict of tag handles for all keys of the tags dict
    tag_handles ={}
    for tag_name in tags.values():
        tag_handles[tag_name] = mesh.imesh.createTag(tag_name, num_e_groups, float)

    for row in data:
       checklist = tags.keys()
       if (row[0], row[1]) in tags.keys():
           pass 



    
