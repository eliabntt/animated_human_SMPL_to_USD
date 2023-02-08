import numpy as np
import scipy.io as sio
from math import cos, sin
from .blender_util import readOBJ, createBPYObj, setMaterial, mesh_cache, convert_meshcache
import os, sys
from .IO import readPC2, writePC2
import bpy

def loadInfo(path: str):
    '''
    this function should be called instead of direct sio.loadmat
    as it cures the problem of not properly recovering python dictionaries
    from mat files. It calls the function check keys to cure all entries
    which are still mat-objects
    '''
    data = sio.loadmat(path, struct_as_record=False, squeeze_me=True)
    del data['__globals__']
    del data['__header__']
    del data['__version__']
    return _check_keys(data)

def _check_keys(dict):
    '''
    checks if entries in dictionary are mat-objects. If yes
    todict is called to change them to nested dictionaries
    '''
    for key in dict:
        if isinstance(dict[key], sio.matlab.mio5_params.mat_struct):
            dict[key] = _todict(dict[key])
    return dict

def _todict(matobj):
    '''
    A recursive function which constructs from matobjects nested dictionaries
    '''
    dict = {}
    for strg in matobj._fieldnames:
        elem = matobj.__dict__[strg]
        if isinstance(elem, sio.matlab.mio5_params.mat_struct):
            dict[strg] = _todict(elem)
        elif isinstance(elem, np.ndarray) and np.any([isinstance(item, sio.matlab.mio5_params.mat_struct) for item in elem]):
            dict[strg] = [None] * len(elem)
            for i,item in enumerate(elem):
                if isinstance(item, sio.matlab.mio5_params.mat_struct):
                    dict[strg][i] = _todict(item)
                else:
                    dict[strg][i] = item
        else:
            dict[strg] = elem
    return dict

# Computes matrix of rotation around z-axis for 'zrot' radians
def zRotMatrix(zrot):
    c, s = cos(zrot), sin(zrot)
    return np.array([[c, -s, 0],
                     [s,  c, 0],
                     [0,  0, 1]], np.float32)
""" CAMERA """
def intrinsic():
    RES_X = 640
    RES_Y = 480
    f_mm             = 50 # blender default
    sensor_w_mm      = 36 # blender default
    sensor_h_mm = sensor_w_mm * RES_Y / RES_X

    fx_px = f_mm * RES_X / sensor_w_mm;
    fy_px = f_mm * RES_Y / sensor_h_mm;

    u = RES_X / 2;
    v = RES_Y / 2;

    return np.array([[fx_px, 0,     u],
                     [0,     fy_px, v],
                     [0,     0,     1]], np.float32)

def extrinsic(camLoc):
    R_w2bc = np.array([[0, 1, 0],
                       [0, 0, 1],
                       [1, 0, 0]], np.float32)

    T_w2bc = -1 * R_w2bc.dot(camLoc)

    R_bc2cv = np.array([[1,  0,  0],
                        [0, -1,  0],
                        [0,  0, -1]], np.float32)

    R_w2cv = R_bc2cv.dot(R_w2bc)
    T_w2cv = R_bc2cv.dot(T_w2bc)

    return np.concatenate((R_w2cv, T_w2cv[:,None]), axis=1)

def proj(camLoc):
    return intrinsic().dot(extrinsic(camLoc))

""" 
Mesh to UV map
Computes correspondences between 3D mesh and UV map
NOTE: 3D mesh vertices can have multiple correspondences with UV vertices
"""
def mesh2UV(F, Ft):
    m2uv = {v: set() for f in F for v in f}
    for f, ft in zip(F, Ft):
        for v, vt in zip(f, ft):
            m2uv[v].add(vt)
    # m2uv = {k:list(v) for k,v in m2uv.items()}
    return m2uv

# Maps UV coordinates to texture space (pixel)
IMG_SIZE = 2048 # all image textures have this squared size
def uv_to_pixel(vt):
    px = vt * IMG_SIZE # scale to image plane
    px %= IMG_SIZE # wrap to [0, IMG_SIZE]
    # Note that Blender graphic engines invert vertical axis
    return int(px[0]), int(IMG_SIZE - px[1]) # texel X, texel Y


def loadGarment(path_sample, path_cache, sample, garment, info):
    print("Processing Garment Cache")
    print(f"Loading {garment}")
    texture = info['outfit'][garment]['texture']
    # Read OBJ file and create BPY object
    V, F, Vt, Ft = readOBJ(os.path.join(path_sample, sample, garment + '.obj'))
    ob = createBPYObj(V, F, Vt, Ft, name=sample + '_' + garment)
    # z-rot
    ob.rotation_euler[2] = info['zrot']
    # Convert cache PC16 to PC2

    pc2_path = os.path.join(path_cache,
                            sample + '_' + garment + '.pc2'
                            )
    if not os.path.isfile(pc2_path):
        # Convert PC16 to PC2 (and move to view_cache folder)
        # Add trans to vertex locations
        pc16_path = os.path.join(path_sample, sample, garment + '.pc16')
        V = readPC2(pc16_path, True)['V']
        for i in range(V.shape[0]):
            sys.stdout.write('\r' + str(i + 1) + '/' + str(V.shape[0]))
            sys.stdout.flush()
            if V.shape[0] > 1:
                V[i] += info['trans'][:, i][None]
            else:
                V[i] += info['trans'][:][None]
        writePC2(pc2_path, V)
    else:
        V = readPC2(pc2_path)['V']

    if V.shape[1] != len(ob.data.vertices):
        sys.stderr.write("ERROR IN THE VERTEX COUNT!!!!!")
        sys.stderr.flush()

    mesh_cache(ob, pc2_path)
    # necessary to have this in the old version of the code with the old omni-blender
    # convert_meshcache(bpy.ops.object)

    # Set material
    setMaterial(path_sample, ob, sample, garment, texture)
    # Smooth
    bpy.ops.object.shade_smooth()
    print(f"\nLoaded {garment}.\n")


def bodyCache(path_cache, sample, info, ob, smpl):
    print("Processing Body Cache")
    pc2_path = os.path.join(path_cache, sample + '.pc2')
    if not os.path.isfile(pc2_path):
        # Compute body sequence
        print("Computing body sequence...")
        print("")
        gender = 'm' if info['gender'] else 'f'
        if len(info['poses'].shape)>1:
            N = info['poses'].shape[1]
        else:
            N = 1
        V = np.zeros((N, 6890, 3), np.float32)
        for i in range(N):
            sys.stdout.write('\r' + str(i + 1) + '/' + str(N))
            sys.stdout.flush()
            s = info['shape']
            if N == 1:
                p = info['poses'][:].reshape((24, 3))
                t = info['trans'][:].reshape((3,))
            else:
                p = info['poses'][:, i].reshape((24, 3))
                t = info['trans'][:, i].reshape((3,))
            v, j = smpl[gender].set_params(pose=p, beta=s, trans=t)
            V[i] = v - j[0:1]
        print("")
        print("Writing PC2 file...")
        writePC2(pc2_path, V)
    else:
        V = readPC2(pc2_path)['V']

    if V.shape[1] != len(ob.data.vertices):
        sys.stderr.write("ERROR IN THE VERTEX COUNT FOR THE BODY!!!!!")
        sys.stderr.flush()

    mesh_cache(ob, pc2_path)
    bpy.ops.object.shade_smooth()