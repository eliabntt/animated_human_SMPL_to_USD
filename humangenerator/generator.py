import os
from random import choice
import bpy
from .util.smplutils import SMPL_Body, rotate_vector
from .cloth3d_gen import *
from .amass_gen import *
from .util.blender_util import export_stl_data, write_pkl_data, write_usd


# import amass_gen

def get_processor(dataset, parent_path, with_cache, path_out, path_samples, smpl_models, write_verts, config={}):
    if dataset == "cloth3d":
        return cloth3d(parent_path, with_cache, path_out, path_samples, smpl_models, write_verts), path_samples
    if dataset == "amass":  # todo fixme
        tmp_obj = amass(parent_path, with_cache, path_out, path_samples, smpl_models, write_verts, config)
        return tmp_obj, path_samples
    raise Exception("NOT A VALID DATASET")


def export_data(temp_path, path_out, sample, with_cache, frame, info, orient, write_verts, usd=True):
    try:
        if usd:
            write_usd(temp_path, path_out, sample + ('_with_cache' if with_cache else ''), with_cache,
                      True if frame == None else False, 0 if frame == None else frame)
        for obj in bpy.data.objects.values():
            if "body" in obj.name.lower() and obj.select_get():
                ob = obj
            elif "armature" in obj.name.lower() and obj.select_get():
                arm_ob = obj

        export_stl_data(path_out, sample + ('_with_cache' if with_cache else ''),
                        [ob for ob in bpy.data.objects if ob.select_get()], orient)
        write_pkl_data(path_out, sample + ('_with_cache' if with_cache else ''), arm_ob, ob, info, write_verts=write_verts)
    except:
        return False
    return True


def create_outfolder_structure(path_out, subfolder_name, with_cache):
    if (with_cache):
        path_cache = os.path.join(path_out, subfolder_name, 'view_cache')
        if not os.path.exists(path_cache):
            os.makedirs(path_cache)
    else:
        path_cache = os.path.join(path_out, subfolder_name, 'view_cache')
        if not os.path.exists(path_cache):
            os.makedirs(path_cache)
    return path_cache


class generator:
    def __init__(self, smpl_path, write_verts=False):
        self.SMPL_PATH = smpl_path

    def pick_skin_texture(self, split_name='all', clothing_option="grey", gender="m"):
        if gender == "f":
            with open(
                    os.path.join(self.SMPL_PATH, "textures", "female_{}.txt".format(split_name))
            ) as f:
                txt_paths = f.read().splitlines()
        else:
            with open(
                    os.path.join(self.SMPL_PATH, "textures", "male_{}.txt".format(split_name))
            ) as f:
                txt_paths = f.read().splitlines()

        # if using only one source of clothing
        if clothing_option == "nongrey":
            txt_paths = [k for k in txt_paths if "nongrey" in k]
        elif clothing_option == "grey":
            txt_paths = [k for k in txt_paths if "nongrey" not in k]
        elif clothing_option == "same":
            # Orig
            txt_paths = ["textures/male/nongrey_male_0244.jpg"]
        elif clothing_option == "all":
            txt_paths = [k for k in txt_paths]

        # random clothing texture
        cloth_img_name = choice(txt_paths)
        cloth_img_name = os.path.join(self.SMPL_PATH, cloth_img_name)
        print("Picked skin texture: {}".format(cloth_img_name))
        return cloth_img_name

    def create_material_SMPL(self, gender="m", person_no=0, clothing_option="grey", split_name="all"):
        print("Creating SMPL texture material")
        cloth_img_name = self.pick_skin_texture(split_name, clothing_option, gender)
        material = bpy.data.materials.new(name=f"Material_{person_no}")
        material.use_nodes = True

        # Add nodes
        tree = material.node_tree
        nodes = tree.nodes
        # Principled BSDf
        bsdf = nodes['Principled BSDF']
        # Image
        img = nodes.new('ShaderNodeTexImage')
        img.image = bpy.data.images.load(cloth_img_name)
        # Links
        tree.links.new(img.outputs[0], bsdf.inputs[0])
        return material

    def load_SMPLs_objects(self):
        # create the material for SMPL
        material = self.create_material_SMPL("m", 0)
        print("Male Material Created")
        smpl_body_list = []
        # create the SMPL_Body object
        smpl_body_list.append(
            SMPL_Body(self.SMPL_PATH, material, 0, "male", person_no=0)
        )
        print("Male created")

        material = self.create_material_SMPL("f", 1)
        print("Female material created")
        smpl_body_list.append(
            SMPL_Body(self.SMPL_PATH, material, 0, "female", person_no=1)
        )
        print("Female created")
        return smpl_body_list
