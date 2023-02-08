import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Quaternion
import numpy as np
import pickle as pkl
import os
import math
from pyquaternion import Quaternion

# computes rotation matrix through Rodrigues formula as in cv2.Rodrigues
def Rodrigues(rotvec):
    theta = np.linalg.norm(rotvec)
    r = (rotvec / theta).reshape(3, 1) if theta > 0.0 else rotvec
    cost = np.cos(theta)
    mat = np.asarray([[0, -r[2], r[1]], [r[2], 0, -r[0]], [-r[1], r[0], 0]])
    return cost * np.eye(3) + (1 - cost) * r.dot(r.T) + np.sin(theta) * mat

# transformation between pose and blendshapes
def rodrigues2bshapes(pose):
    rod_rots = np.asarray(pose).reshape(24, 3)
    mat_rots = [Rodrigues(rod_rot) for rod_rot in rod_rots]
    bshapes = np.concatenate(
        [(mat_rot - np.eye(3)).ravel() for mat_rot in mat_rots[1:]]
    )
    return mat_rots, bshapes

def rotate_vector(vector, axis, angle):
    """
    Rotate a vector around an axis by an angle.
    """
    q = Quaternion(axis=axis, angle=angle)
    return q.rotate(vector)

class SMPL_Body:
    def __init__(self, smpl_data_folder, material, j, gender="female", person_no=0, zrot=0):
        # load fbx model
        bpy.ops.import_scene.fbx(
            filepath=os.path.join(
                smpl_data_folder,
                "basicModel_{}_lbs_10_207_0_v1.0.2.fbx".format(gender[0]),
            ),
            axis_forward="Y",
            axis_up="Z",
            global_scale=100,
        )
        J_regressors = pkl.load(
            open(os.path.join(smpl_data_folder, "joint_regressors.pkl"), "rb")
        )
        # 24 x 6890 regressor from vertices to joints
        self.joint_regressor = J_regressors["J_regressor_{}".format(gender)]
        self.j = j

        armature_name = "Armature_{}".format(person_no)
        bpy.context.active_object.name = armature_name

        self.gender_name = "{}_avg".format(gender[0])

        self.obj_name = "body_{:d}".format(person_no)
        bpy.data.objects[armature_name].children[0].name = self.obj_name
        # not the default self.gender_name because each time fbx is loaded it adds some suffix
        self.ob = bpy.data.objects[self.obj_name]

        # Rename the armature
        self.ob.data.use_auto_smooth = False  # autosmooth creates artifacts
        # assign the existing spherical harmonics material
        self.ob.active_material = bpy.data.materials["Material_{}".format(person_no)]
        bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN', center='MEDIAN')

        # clear existing animation data
        # self.ob.shape_key_clear()
        self.ob.data.shape_keys.animation_data_clear()

        self.arm_ob = bpy.data.objects[armature_name]
        self.arm_ob.animation_data_clear()

        self.setState0()
        # self.ob.select = True  # blender < 2.8x
        self.ob.select_set(True)
        # bpy.context.scene.objects.active = self.ob  # blender < 2.8x
        bpy.context.view_layer.objects.active = self.ob
        self.smpl_data_folder = smpl_data_folder
        self.materials = self.create_segmentation(material, smpl_data_folder)

        # unblocking both the pose and the blendshape limits
        for k in self.ob.data.shape_keys.key_blocks.keys():
            self.ob.data.shape_keys.key_blocks[k].slider_min = -100
            self.ob.data.shape_keys.key_blocks[k].slider_max = 100
        # bpy.context.scene.objects.active = self.arm_ob  # blender < 2.8x
        bpy.context.view_layer.objects.active = self.arm_ob

        # order
        self.part_match = {
            "root": "root",
            "bone_00": "Pelvis",
            "bone_01": "L_Hip",
            "bone_02": "R_Hip",
            "bone_03": "Spine1",
            "bone_04": "L_Knee",
            "bone_05": "R_Knee",
            "bone_06": "Spine2",
            "bone_07": "L_Ankle",
            "bone_08": "R_Ankle",
            "bone_09": "Spine3",
            "bone_10": "L_Foot",
            "bone_11": "R_Foot",
            "bone_12": "Neck",
            "bone_13": "L_Collar",
            "bone_14": "R_Collar",
            "bone_15": "Head",
            "bone_16": "L_Shoulder",
            "bone_17": "R_Shoulder",
            "bone_18": "L_Elbow",
            "bone_19": "R_Elbow",
            "bone_20": "L_Wrist",
            "bone_21": "R_Wrist",
            "bone_22": "L_Hand",
            "bone_23": "R_Hand",
        }

    def refine_SMPL(self, material, j, zrot):
        self.j = j
        self.arm_ob.rotation_euler = [0, 0, zrot]
        self.ob.data.shape_keys.animation_data_clear()
        self.arm_ob.animation_data_clear()
        
        self.ob.select_set(True)
        bpy.ops.object.origin_set(type='GEOMETRY_ORIGIN', center='MEDIAN')

        # bpy.context.scene.objects.active = self.ob  # blender < 2.8x
        bpy.context.view_layer.objects.active = self.ob
        self.materials = self.create_segmentation(material, self.smpl_data_folder)
        for k in self.ob.data.shape_keys.key_blocks.keys():
            self.ob.data.shape_keys.key_blocks[k].slider_min = -10
            self.ob.data.shape_keys.key_blocks[k].slider_max = 10
        
        # bpy.context.scene.objects.active = self.arm_ob  # blender < 2.8x
        bpy.context.view_layer.objects.active = self.arm_ob


    def setState0(self):
        for ob in bpy.data.objects.values():
            # ob.select = False  # blender < 2.8x
            ob.select_set(False)
        # bpy.context.scene.objects.active = None  # blender < 2.8x
        bpy.context.view_layer.objects.active = None

    # create one material per part as defined in a pickle with the segmentation
    # this is useful to render the segmentation in a material pass
    def create_segmentation(self, material, smpl_path):
        print("Creating materials segmentation")
        sorted_parts = [
            "hips",
            "leftUpLeg",
            "rightUpLeg",
            "spine",
            "leftLeg",
            "rightLeg",
            "spine1",
            "leftFoot",
            "rightFoot",
            "spine2",
            "leftToeBase",
            "rightToeBase",
            "neck",
            "leftShoulder",
            "rightShoulder",
            "head",
            "leftArm",
            "rightArm",
            "leftForeArm",
            "rightForeArm",
            "leftHand",
            "rightHand",
            "leftHandIndex1",
            "rightHandIndex1",
        ]
        part2num = {part: (ipart + 1) for ipart, part in enumerate(sorted_parts)}
        materials = {}
        vgroups = {}
        with open(os.path.join(smpl_path,"segm_per_v_overlap.pkl"), "rb") as f:
            vsegm = pkl.load(f)

        if len(self.ob.material_slots) <= 1:
            bpy.ops.object.material_slot_remove()

        parts = sorted(vsegm.keys())
        existing = False
        cnt = 0
        for part in parts:
            vs = vsegm[part]
            # vgroups[part] = self.ob.vertex_groups.new(part)  # blender < 2.8x
            if part not in self.ob.vertex_groups:
                vgroups[part] = self.ob.vertex_groups.new(name=part)
                vgroups[part].add(vs, 1.0, "ADD")
            else:
                existing = True

            bpy.ops.object.vertex_group_set_active(group=part)
            materials[part] = material.copy()
            materials[part].pass_index = part2num[part]
            if not existing:
                bpy.ops.object.material_slot_add()    
                self.ob.material_slots[-1].material = materials[part]

                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="DESELECT")
                bpy.ops.object.vertex_group_select()
                bpy.ops.object.material_slot_assign()
                bpy.ops.object.mode_set(mode="OBJECT")
            else:
                self.ob.material_slots[cnt].material = materials[part]
                cnt += 1
        for scene_material in bpy.data.materials:
            if not scene_material.users and len(scene_material.name) != len(material.name):
                bpy.data.materials.remove(scene_material)
        return materials

    def quaternion_multiply(self, quaternion1, quaternion0):
        w0, x0, y0, z0 = quaternion0
        w1, x1, y1, z1 = quaternion1
        return np.array([-x1 * x0 - y1 * y0 - z1 * z0 + w1 * w0,
                         x1 * w0 + y1 * z0 - z1 * y0 + w1 * x0,
                         -x1 * z0 + y1 * w0 + z1 * x0 + w1 * y0,
                         x1 * y0 - y1 * x0 + z1 * w0 + w1 * z0], dtype=np.float64)


    def euler_from_quaternion(self, quat):
        """
        Convert a quaternion into euler angles (roll, pitch, yaw)
        roll is rotation around x in radians (counterclockwise)
        pitch is rotation around y in radians (counterclockwise)
        yaw is rotation around z in radians (counterclockwise)
        """
        w,x,y,z = quat
        t0 = +2.0 * (w * x + y * z)
        t1 = +1.0 - 2.0 * (x * x + y * y)
        roll_x = math.atan2(t0, t1)

        t2 = +2.0 * (w * y - z * x)
        t2 = +1.0 if t2 > +1.0 else t2
        t2 = -1.0 if t2 < -1.0 else t2
        pitch_y = math.asin(t2)

        t3 = +2.0 * (w * z + x * y)
        t4 = +1.0 - 2.0 * (y * y + z * z)
        yaw_z = math.atan2(t3, t4)

        return roll_x*180/3.1415, pitch_y*180/3.1415, yaw_z*180/3.1415  # in radians

    def apply_trans_pose_shape(self, trans, pose, shape, frame=None, with_blendshapes = True):
        """
        Apply trans pose and shape to character
        """
        # transform pose into rotation matrices (for pose) and pose blendshapes
        mrots, bsh = rodrigues2bshapes(pose)

        # set the location of the first bone to the translation parameter
        mytrans = [0,0,0]
        mytrans[2] = trans[2]
        mytrans[1] = trans[1]
        mytrans[0] = trans[0]

        self.arm_ob.pose.bones[self.gender_name + "_Pelvis"].location = mytrans
        if frame is not None:
            self.arm_ob.pose.bones[self.gender_name + "_root"].keyframe_insert(
                "location", frame=frame
            )
            self.arm_ob.pose.bones[self.gender_name + "_root"].keyframe_insert(
                "rotation_quaternion", frame=frame
            )

        # set the pose of each bone to the quaternion specified by pose
        for ibone, mrot in enumerate(mrots):
            bone = self.arm_ob.pose.bones[
                self.gender_name + "_" + self.part_match["bone_{:02d}".format(ibone)]
                ]
            bone.rotation_quaternion = Matrix(mrot).to_quaternion()

            if frame is not None:
                bone.keyframe_insert("rotation_quaternion", frame=frame)
                bone.keyframe_insert("location", frame=frame)

        # apply pose blendshapes
        if with_blendshapes:
            for ibshape, bshape in enumerate(bsh):
                self.ob.data.shape_keys.key_blocks[
                    "Pose{:03d}".format(ibshape)
                ].value = bshape
                if frame is not None:
                    self.ob.data.shape_keys.key_blocks[
                        "Pose{:03d}".format(ibshape)
                    ].keyframe_insert("value", index=-1, frame=frame)

            # apply shape blendshapes
            for ibshape, shape_elem in enumerate(shape):
                self.ob.data.shape_keys.key_blocks[
                    "Shape{:03d}".format(ibshape)
                ].value = shape_elem 
                if frame is not None:
                    self.ob.data.shape_keys.key_blocks[
                        "Shape{:03d}".format(ibshape)
                    ].keyframe_insert("value", index=-1, frame=frame)
        else:
            mod = self.ob.modifiers.get('Armature')
            if mod is not None: self.ob.modifiers.remove(mod)

    def reset_joint_positions(self, shape, scene):   
        orig_trans = np.asarray(
            self.arm_ob.pose.bones[self.gender_name + "_Pelvis"].location
        ).copy()
        # zero the pose and trans to obtain joint positions in zero pose
        self.apply_trans_pose_shape(orig_trans, np.zeros(72), shape)

        bpy.ops.wm.memory_statistics()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        me = self.ob.evaluated_get(depsgraph).to_mesh()

        num_vertices = len(me.vertices)  # 6890
        reg_vs = np.empty((num_vertices, 3))
        for iiv in range(num_vertices):
            reg_vs[iiv] = me.vertices[iiv].co
        # bpy.data.meshes.remove(me)  # blender < 2.8x
        self.ob.evaluated_get(depsgraph).to_mesh_clear()

        # regress joint positions in rest pose
        joint_xyz = self.j

        # adapt joint positions in rest pose
        # self.arm_ob.hide = False
        # Added this line
        # bpy.context.scene.objects.active = self.arm_ob  # blender < 2.8x
        bpy.context.view_layer.objects.active = self.arm_ob
        bpy.ops.object.mode_set(mode="EDIT")
        # self.arm_ob.hide = True
        for ibone in range(24):
            bb = self.arm_ob.data.edit_bones[
                self.gender_name + "_" + self.part_match["bone_{:02d}".format(ibone)]
            ]
            bboffset = bb.tail - bb.head
            bb.head = joint_xyz[ibone]
            bb.tail = bb.head + bboffset
        bpy.ops.object.mode_set(mode="OBJECT")