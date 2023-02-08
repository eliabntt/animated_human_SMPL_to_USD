from pathlib import Path
from humangenerator.util.blender_util import *
import bpy
from .util.amass_util import loadInfo, bodyCache, _load_parametric_body_model, _get_supported_mocap_datasets, \
    _get_sequence_path
import humangenerator as hgen


class amass:
    def __init__(self, parent_path, with_cache, path_out, path_samples, smpl_models, write_verts, config):
        # temporary usd export path, we cannot directly write in mounted network drives sometimes
        temp_path = os.path.join(parent_path, 'usd_exports')
        # surreal path for textures
        smpl_path = os.path.join(parent_path, "surreal", "datageneration", "smpl_data")

        from humangenerator.generator import generator
        self.generator = generator(smpl_path)
        self.with_cache = with_cache
        self.path_out = path_out
        self.path_samples = path_samples
        self.smpl = smpl_models
        self.sub_dataset_id = config['sub_dataset_id']
        self.num_betas = config['num_betas']
        self.num_dmpls = config['num_dmpls']
        self.subject_ids = config['subject_ids'].split()
        self.write_verts = (write_verts == "True")

        self.temp_path = temp_path
        self.body_model_m, self.faces_m = _load_parametric_body_model(parent_path, "male", self.num_betas,
                                                                      self.num_dmpls)
        self.body_model_f, self.faces_f = _load_parametric_body_model(parent_path, "female", self.num_betas,
                                                                      self.num_dmpls)

        taxonomy_file_path = os.path.join(parent_path, "taxonomy.json")
        self.supported_datasets = _get_supported_mocap_datasets(taxonomy_file_path, path_samples)
        
    def animateSMPL(self, sample, smpl_ob, info, body_model):
        if self.with_cache:
            bodyCache(self.path_cache, sample, info, smpl_ob.ob, body_model, self.num_betas, self.num_dmpls)

        # generate blendshapes + trans
        s = info['betas'][:10]
        smpl_ob.reset_joint_positions(s, bpy.data.scenes["Scene"])

        for i in range(info['poses'].shape[0]):
            p = np.append(info['poses'][i][:66].reshape(-1, 3), [[0, 0, 0], [0, 0, 0]], 0)
            t = info['trans'][i].reshape((3,))
            bpy.data.scenes["Scene"].frame_set(i)
            smpl_ob.apply_trans_pose_shape(t, p, s, i, with_blendshapes=not self.with_cache)

    def generate_SMPLbody_animation(self, sample, info, gender, index, body_model):
        print("Generate Animation..")

        orient = info['poses'][0, :3][2]
        p = np.append(info['poses'][0][:66].reshape(-1, 3), [[0, 0, 0], [0, 0, 0]], 0)
        t = info['trans'][0].reshape((3,))
        s = info['betas'][:10]
        v, j = self.smpl[gender].set_params(pose=p, beta=s, trans=t)
        cloth_img_name = self.generator.pick_skin_texture(gender=gender, clothing_option="all")
        img = bpy.data.materials[f'Material_{index}'].node_tree.nodes["Image Texture"]
        img.image = bpy.data.images.load(cloth_img_name)
        material = bpy.data.materials[f'Material_{index}']

        self.smpl_body_list[index].refine_SMPL(material, j, orient)  # info['zrot']

        self.animateSMPL(sample, self.smpl_body_list[index], info, body_model)

        # Smooth
        bpy.ops.object.shade_smooth()

    def loadAmassSequence(self, sample: str, info: dict, body_model, frame: int = None):
        bpy.context.scene.frame_end = info['poses'].shape[0] - 1

        bpy.ops.object.select_all(action='DESELECT')
        # delete current garments
        for obj in bpy.data.objects.values():
            if 'body' not in obj.name.lower() and 'armature' not in obj.name.lower():
                obj.select_set(True)
                bpy.ops.object.delete()

        for obj in bpy.data.objects.values():
            obj.select_set(False)

        gender = 'm' if info['gender'] == 'male' else 'f'
        index = 0 if info['gender'] == 'male' else 1
        self.generate_SMPLbody_animation(sample, info, gender, index, body_model)

        bpy.context.view_layer.objects.active = bpy.data.objects[f'Armature_{index}']
        arm_obj = bpy.data.objects[f'Armature_{index}']
        bpy.context.scene.frame_current = bpy.context.scene.frame_start

        for obj in bpy.data.objects.values():
            if 'body' not in obj.name.lower() and 'armature' not in obj.name.lower():
                obj.select_set(True)
                obj.parent = arm_obj
                obj.rotation_euler = [0, 0, 0]
                obj.select_set(False)

        for obj in bpy.data.objects.values():
            if 'armature' not in obj.name.lower() and 'body' not in obj.name.lower():
                obj.select_set(True)
            else:
                if str(index) in obj.name:
                    obj.select_set(True)

        if frame != None and frame >= 0 and frame <= bpy.context.scene.frame_end:
            bpy.context.scene.frame_current = frame

    def process_sample(self, sample: str, frame: int, smpl_body_list):
        # load info
        if sample in self.subject_ids:
            for subject_id in os.listdir(os.path.join(self.path_samples, sample)):
                sequence_path, main_path = _get_sequence_path(self.supported_datasets, self.sub_dataset_id, sample,
                                                              subject_id)
                info = loadInfo(sequence_path)

                self.smpl_body_list = smpl_body_list
                subfolder_name = Path(subject_id).stem + ('_with_cache' if self.with_cache else '')
                self.path_cache = hgen.create_outfolder_structure(self.path_out, subfolder_name, self.with_cache)

                if frame is None:
                    self.loadAmassSequence(sample, info, self.body_model_m if info["gender"] == "male" else self.body_model_f)
                else:
                    self.loadAmassSequence(sample, info, self.body_model_m if info["gender"] == "male" else self.body_model_f,
                                           frame)

                bpy.ops.wm.save_as_mainfile(filepath=os.path.join(self.path_out, subfolder_name, subfolder_name + ".blend"))
                my_l = list(info.keys())
                new_info = {}
                for i in my_l:
                    new_info[i] = info[i]
                hgen.export_data(self.temp_path, self.path_out, Path(subject_id).stem, self.with_cache, frame, new_info,
                                 info['poses'][0, :3][2], self.write_verts)

        return True