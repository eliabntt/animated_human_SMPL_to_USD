import os
import sys

# check the python version, only python 3.X is allowed:
if sys.version_info.major < 3:
    raise Exception("HumanGenerator requires at least python 3.X to run.")

sys.path.remove(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from .util.blender_util import *
from data_folder.smpl.smpl_np import SMPLModel
from .generator import *
