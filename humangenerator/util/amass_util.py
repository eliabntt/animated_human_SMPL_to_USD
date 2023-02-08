import numpy as np
import glob
import os
import random
from .IO import readPC2, writePC2
import bpy, sys, torch
from .blender_util import mesh_cache
from typing import Tuple

def bodyCache(path_cache, sample, info, ob, body_model, num_betas, num_dmpls):
    print("Processing Body Cache")

    pc2_path = os.path.join(path_cache, sample + '.pc2')

    V = np.zeros((info['poses'].shape[1], 6890, 3), np.float32)

    bdata = info
    time_length = len(bdata['trans'])
    comp_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    body_params = {
        'root_orient': torch.Tensor(bdata['poses'][:, :3]).to(comp_device),  # controls the global root orientation
        'pose_body': torch.Tensor(bdata['poses'][:, 3:66]).to(comp_device),  # controls the body
        'pose_hand': torch.Tensor(bdata['poses'][:, 66:]).to(comp_device),  # controls the finger articulation
        'trans': torch.Tensor(bdata['trans']).to(comp_device),  # controls the global body position
        'betas': torch.Tensor(np.repeat(bdata['betas'][:num_betas][np.newaxis], repeats=time_length, axis=0)).to(
            comp_device),  # controls the body shape. Body shape is static
        'dmpls': torch.Tensor(bdata['dmpls'][:, :num_dmpls]).to(comp_device)  # controls soft tissue dynamics
    }

    body_trans_root = body_model(
        **{k: v for k, v in body_params.items() if k in ['pose_body', 'betas', 'pose_hand', 'dmpls',
                                                         'trans', 'root_orient']})
    if not os.path.isfile(pc2_path):
        V = body_trans_root.v.data.cpu().numpy()
        print("Writing PC2 file...")
        writePC2(pc2_path, V)
    else:
        V = readPC2(pc2_path)['V']

    if V.shape[1] != len(ob.data.vertices):
        sys.stderr.write("ERROR IN THE VERTEX COUNT FOR THE BODY!!!!!")
        sys.stderr.flush()

    mesh_cache(ob, pc2_path)
    bpy.ops.object.shade_smooth()
    return body_trans_root

def loadInfo(sequence_path):

    if os.path.exists(sequence_path):
        # load AMASS dataset sequence file which contains the coefficients for the whole motion sequence
        sequence_body_data = np.load(sequence_path)
        # get the number of supported frames
        return sequence_body_data
    else:
        raise Exception(
            "Invalid sequence/subject category identifiers, please choose a "
            "valid one. Used path: {}".format(sequence_path))

def _get_sequence_path(supported_mocap_datasets: dict, used_sub_dataset_id: str, used_subject_id: str, used_sequence_id: str) -> [str, str]:
        """ Extract pose and shape parameters corresponding to the requested pose from the database to be processed by the parametric model

        :param supported_mocap_datasets: A dict which maps sub dataset names to their paths.
        :param used_sub_dataset_id: Identifier for the sub dataset, the dataset which the human pose object should be extracted from.
        :param used_subject_id: Type of motion from which the pose should be extracted, this is dataset dependent parameter.
        :param used_sequence_id: Sequence id in the dataset, sequences are the motion recorded to represent certain action.
        :return: tuple of arrays contains the parameters. Type: tuple
        """


        # check if the sub_dataset is supported
        if used_sub_dataset_id in supported_mocap_datasets:
            # get path from dictionary
            sub_dataset_path = supported_mocap_datasets[used_sub_dataset_id]
            # concatenate path to specific
            if not used_subject_id:
                # if none was selected
                possible_subject_ids = glob.glob(os.path.join(sub_dataset_path, "*"))
                possible_subject_ids.sort()
                if len(possible_subject_ids) > 0:
                    used_subject_id_str = os.path.basename(random.choice(possible_subject_ids))
                else:
                    raise Exception("No subjects found in folder: {}".format(sub_dataset_path))
            else:
                try:
                    used_subject_id_str = "{:02d}".format(int(used_subject_id))
                except:
                    used_subject_id_str = used_subject_id

            subject_path = os.path.join(sub_dataset_path, used_subject_id_str)
            sequence_path = os.path.join(subject_path, used_sequence_id)
            return sequence_path, subject_path
        else:
            raise Exception(
                "The requested mocap dataset is not yest supported, please choose anothe one from the following "
                "supported datasets: {}".format([key for key, value in supported_mocap_datasets.items()]))

def _load_parametric_body_model(data_path: str, used_body_model_gender: str, num_betas: int,
                                num_dmpls: int) -> Tuple["BodyModel", np.array]:
    """ loads the parametric model that is used to generate the mesh object

    :return:  parametric model. Type: tuple.
    """
    import torch
    from human_body_prior.body_model.body_model import BodyModel

    bm_path = os.path.join(data_path, 'body_models', 'smplh', used_body_model_gender, 'model.npz')  # body model
    dmpl_path = os.path.join(data_path, 'body_models', 'dmpls', used_body_model_gender, 'model.npz')  # deformation model
    if not os.path.exists(bm_path) or not os.path.exists(dmpl_path):
        raise Exception("Parametric Body model doesn't exist, please follow download instructions section in AMASS Example")
    comp_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    body_model = BodyModel(bm_path=bm_path, num_betas=num_betas, num_dmpls=num_dmpls, path_dmpl=dmpl_path).to(comp_device)
    faces = body_model.f.detach().cpu().numpy()
    return body_model, faces

def _get_supported_mocap_datasets(taxonomy_file_path: str, data_path: str) -> dict:
    """ get latest updated list from taxonomoy json file about the supported mocap datasets supported in the loader module and update.supported_mocap_datasets list

    :param taxonomy_file_path: path to taxomomy.json file which contains the supported datasets and their respective paths. Type: string.
    :param data_path: path to the AMASS dataset root folder. Type: string.
    """
    import json
    # dictionary contains mocap dataset name and path to its sub folder within the main dataset, dictionary will
    # be filled from taxonomy.json file which indicates the supported datastests
    supported_mocap_datasets = {}
    if os.path.exists(taxonomy_file_path):
        with open(taxonomy_file_path, "r") as f:
            loaded_data = json.load(f)
            for block in loaded_data:
                if "sub_data_id" in block:
                    sub_dataset_id = block["sub_data_id"]
                    supported_mocap_datasets[sub_dataset_id] = os.path.join(data_path, block["path"])
    else:
        raise Exception("The taxonomy file could not be found: {}".format(taxonomy_file_path))

    return supported_mocap_datasets