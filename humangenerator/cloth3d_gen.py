from humangenerator.util.blender_util import *
import bpy
from .util.cloth3d_util import loadInfo, bodyCache, loadGarment
import humangenerator as hgen
from pathlib import Path

class cloth3d:
    def __init__(self, parent_path, with_cache, path_out, path_samples, smpl_models, write_verts):
        from humangenerator.generator import generator
        # temporary usd export path, we cannot directly write in mounted network drives sometimes
        temp_path = os.path.join(parent_path, 'usd_exports')
        # surreal path for textures
        smpl_path = os.path.join(parent_path, "surreal", "datageneration", "smpl_data")

        self.generator = generator(smpl_path)
        self.with_cache = with_cache
        self.path_out = path_out
        self.path_samples = path_samples
        self.smpl = smpl_models
        self.temp_path = temp_path
        self.write_verts = (write_verts == "True")

    def animateSMPL(self, sample, smpl_ob, info, j):
        if self.with_cache:
            bodyCache(self.path_cache, sample, info, smpl_ob.ob, self.smpl)

        # generate blendshapes + trans
        s = info['shape']
        smpl_ob.reset_joint_positions(s, bpy.data.scenes["Scene"])
        if len(info['poses'].shape) > 1:
            N = info['poses'].shape[1]
        else:
            sys.stderr.write('Error animation is ONLY ONE FRAME \n')
            N = 1
        for i in range(N):
            if N > 1:
                p = info['poses'][:, i]
                t = info['trans'][:, i].reshape((3,)) - j[0]
            else:
                p = info['poses'][:]
                t = info['trans'][:].reshape((3,)) - j[0]
            bpy.data.scenes["Scene"].frame_set(i)
            smpl_ob.apply_trans_pose_shape(t, p, s, i, with_blendshapes=not self.with_cache)

    def generate_SMPLbody_animation(self, sample, info, gender, index):
        print("Generate Animation..")
        if len(info['poses'].shape) > 1:
            p = info['poses'][:, 0].reshape((24, 3))
            t = info['trans'][:, 0].reshape((3,))
        else:
            p = info['poses'][:].reshape((24, 3))
            t = info['trans'][:].reshape((3,))
        
        s = info['shape']
        v, j = self.smpl[gender].set_params(pose=p, beta=s, trans=t)

        cloth_img_name = self.generator.pick_skin_texture(gender=gender, clothing_option="grey")
        img = bpy.data.materials[f'Material_{index}'].node_tree.nodes["Image Texture"]
        img.image = bpy.data.images.load(cloth_img_name)
        material = bpy.data.materials[f'Material_{index}']

        self.smpl_body_list[index].refine_SMPL(material, j, info['zrot'])
        self.animateSMPL(sample, self.smpl_body_list[index], info, j)

        # Smooth
        bpy.ops.object.shade_smooth()

    def loadCloth3DSequence(self, sample: str, info: dict, frame: int = None):
        if len(info['poses'].shape) > 1:
            bpy.context.scene.frame_end = info['poses'].shape[-1] - 1
        else:
            bpy.context.scene.frame_end = 1
        bpy.ops.object.select_all(action='DESELECT')
        # delete current garments
        for obj in bpy.data.objects.values():
            if 'body' not in obj.name.lower() and 'armature' not in obj.name.lower():
                obj.select_set(True)
                bpy.ops.object.delete()

        # Load new garments
        for garment in info['outfit']:
            loadGarment(self.path_samples, self.path_cache, sample, garment, info)

        for obj in bpy.data.objects.values():
            obj.select_set(False)

        gender = 'm' if info['gender'] else 'f'
        index = 0 if info['gender'] else 1
        self.generate_SMPLbody_animation(sample, info, gender, index)

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
        info = loadInfo(os.path.join(self.path_samples, sample, 'info.mat'))

        self.smpl_body_list = smpl_body_list
        subfolder_name = Path(sample).stem + ('_with_cache' if self.with_cache else '')
        self.path_cache = hgen.create_outfolder_structure(self.path_out, subfolder_name, self.with_cache)

        if frame is None:
            self.loadCloth3DSequence(sample, info)
        else:
            self.loadCloth3DSequence(sample, info, frame)

        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(self.path_out, subfolder_name, subfolder_name + ".blend"))
        return hgen.export_data(self.temp_path, self.path_out, Path(sample).stem, self.with_cache, frame, info, info['zrot'], self.write_verts)