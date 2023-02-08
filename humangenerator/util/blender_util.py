import os
import bpy
from humangenerator.util.IO import readOBJ, readPC2, writePC2
import numpy as np
import bmesh
import sys
import pickle as pkl
import shutil
import random

PI = 3.14159

""" Scene """
def init():
    clean()
    # scene
    return scene()

def clean():
    for collection in dir(bpy.data):
        data_structure = getattr(bpy.data, collection)
        # Check that it is a data collection
        if isinstance(data_structure, bpy.types.bpy_prop_collection) and hasattr(data_structure,
                                                                                 "remove") and collection not in [
            "texts"]:
            # Go over all entities in that collection
            for block in data_structure:
                # Remove everything besides the default scene
                if not isinstance(block, bpy.types.Scene) or block.name != "Scene":
                    data_structure.remove(block)

def clean_mesh_and_textures(exclude=[]):
    # ensure everything is lowered
    exclude = [i.lower() for i in exclude]

    for block in bpy.data.objects:
        if block.users == 0 or block.name.lower() not in exclude:
            bpy.data.objects.remove(block)

    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)

    for block in bpy.data.materials:
        if block.users == 0 and block.name.lower() not in exclude:
            bpy.data.materials.remove(block)

    for block in bpy.data.textures:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.images:
        bpy.data.images.remove(block)

    for block in bpy.data.shape_keys:
        if block.users == 0:
            bpy.data.textures.remove(block)

    for block in bpy.data.actions:
        if block.users == 0:
            bpy.data.actions.remove(block)


def scene():
    scene = bpy.data.scenes["Scene"]
    scene.render.engine = "CYCLES"
    # bpy.data.materials['Material'].use_nodes = True
    scene.cycles.shading_system = True
    scene.use_nodes = True
    scene.render.film_transparent = True
    scene.frame_current = 0

    scene.render.fps = 30
    scene.render.resolution_x = 640
    scene.render.resolution_y = 480
    return scene


""" BPY obj manipulation """


def select(ob, only=True):
    if type(ob) is str: ob = bpy.data.objects[ob]
    if only: deselect()
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    return ob


def deselect():
    for obj in bpy.data.objects.values():
        obj.select_set(False)
    bpy.context.view_layer.objects.active = None


def delete(ob):
    select(ob)
    bpy.ops.object.delete()


def createBPYObj(V, F, Vt=None, Ft=None, name='new_obj'):
    # Create obj
    mesh = bpy.data.meshes.new('mesh')
    ob = bpy.data.objects.new(name, mesh)
    # Add to collection
    bpy.context.collection.objects.link(ob)
    select(ob)
    mesh = bpy.context.object.data
    bm = bmesh.new()
    # Vertices
    for v in V:
        bm.verts.new(v)
    bm.verts.ensure_lookup_table()
    # Faces
    for f in F:
        v = [bm.verts[i] for i in f]
        bm.faces.new(v)
    bm.to_mesh(mesh)
    bm.free()
    # UV Map
    if not Vt is None:
        # Create UV layer
        ob.data.uv_layers.new()
        # Assign UV coords
        iloop = 0
        for f in Ft:
            for i in f:
                ob.data.uv_layers['UVMap'].data[iloop].uv = Vt[i]
                iloop += 1
    return ob



def convert_meshcache(ob: bpy.ops.object, offset=0):
    # Converts a MeshCache or Cloth modifiers to ShapeKeys
    bpy.context.scene.frame_current = bpy.context.scene.frame_start
    for frame in range(bpy.context.scene.frame_end + 1):
        bpy.context.scene.frame_current = frame

        # for alembic files converted to PC2 and loaded as MeshCache
        bpy.ops.object.modifier_apply_as_shapekey(keep_modifier=True, modifier="MeshCache")

    # loop through shapekeys and add as keyframe per frame
    # https://blender.stackexchange.com/q/149045/87258
    bpy.context.scene.frame_current = bpy.context.scene.frame_start
    for frame in range(bpy.context.scene.frame_end + 1):
        bpy.context.scene.frame_current = frame

        shapekey = bpy.data.shape_keys[-1]
        for i, keyblock in enumerate(shapekey.key_blocks):
            if keyblock.name != "Basis":
                curr = i - 1
                if curr != frame:
                    keyblock.value = 0
                    keyblock.keyframe_insert("value", frame=frame)
                else:
                    keyblock.value = 1
                    keyblock.keyframe_insert("value", frame=frame)

    bpy.ops.object.modifier_remove(modifier="MeshCache")


def setMaterial(path_sample, ob, sample, garment, texture):
    mat = bpy.data.materials.new(name=sample + '_' + garment + '_Material')
    mat.use_nodes = True
    ob.data.materials.append(mat)
    if texture['type'] == 'color':
        mat.node_tree.nodes['Principled BSDF'].inputs[0].default_value = texture['data'].tolist() + [1]
    elif texture['type'] == 'pattern':
        # Read pattern
        img_path = os.path.join(path_sample, sample, garment + '.png')
        # Add nodes
        tree = mat.node_tree
        nodes = tree.nodes
        # Principled BSDf
        bsdf = nodes['Principled BSDF']
        # Image
        img = nodes.new('ShaderNodeTexImage')
        try:
            img.image = bpy.data.images.load(img_path)
            # Links
            tree.links.new(img.outputs[0], bsdf.inputs[0])
        except:
            mat.node_tree.nodes['Principled BSDF'].inputs[0].default_value = [random.random(), random.random(),
                                                                              random.random(), 1]


""" Modifiers """
def mesh_cache(ob, cache, scale=1):
    ob = select(ob)
    bpy.ops.object.modifier_add(type='MESH_CACHE')
    ob.modifiers['MeshCache'].cache_format = 'PC2'
    ob.modifiers['MeshCache'].filepath = cache
    ob.modifiers['MeshCache'].frame_scale = scale


def write_usd(temppath, filepath, filename, with_cache, export_animation=True, sf=0, ef=-1, frame_step=1):
    outpath = os.path.join(filepath, filename)
    filepath = os.path.join(filepath, filename, filename + ".usd")
    if ef == -1:
        ef = bpy.context.scene.frame_end

    print(f"\nExporting usd to {filepath}\n")
    bpy.ops.wm.usd_export(filepath=os.path.join(temppath, filename + ".usd"),
                filemode=8, display_type='DEFAULT', sort_method='DEFAULT',
                selected_objects_only=True, visible_objects_only=True, export_animation=export_animation,
                export_hair=True, export_vertices=True, export_vertex_colors=True,
                export_vertex_groups=True, export_face_maps=True, export_uvmaps=True, export_normals=True,
                export_transforms=True, export_materials=True, export_meshes=True, export_lights=True,
                export_cameras=False, export_blendshapes=with_cache,
                export_curves=True, export_particles=True, export_armatures=True, use_instancing=False,
                evaluation_mode='VIEWPORT', default_prim_path=f"/body_{filename}",
                root_prim_path=f"/body_{filename}", material_prim_path=f"/body_{filename}/materials",
                generate_cycles_shaders=False, generate_preview_surface=True, generate_mdl=True,
                convert_uv_to_st=True, convert_orientation=True,
                convert_to_cm=True, export_global_forward_selection='Y', export_global_up_selection='Z',
                export_child_particles=False,
                export_as_overs=False, merge_transform_and_shape=False, export_custom_properties=True,
                add_properties_namespace=False, export_identity_transforms=False,
                apply_subdiv=True, author_blender_name=True, vertex_data_as_face_varying=False,
                frame_step=frame_step, start=sf, end=ef, override_shutter=False,
                init_scene_frame_range=True, export_textures=True, relative_paths=True,
                light_intensity_scale=1,
                convert_light_to_nits=True, scale_light_radius=True, convert_world_material=True,
                fix_skel_root=True, xform_op_mode='SRT')
    shutil.move(os.path.join(temppath, filename + ".usd"), filepath)
    shutil.move(os.path.join(temppath, "textures"), os.path.join(outpath, "textures"))


def export_stl_data(filepath, filename, lobs, zrot):
    context = bpy.context

    dg = context.evaluated_depsgraph_get()
    scene = context.scene
    coll = context.collection

    step = 5
    for ob in lobs:
        if ob.type != 'MESH':
            print(ob.name)
            print(ob.type)
            ob.select_set(False)
            continue
        bpy.context.view_layer.objects.active = ob
        rings = []
        me = ob.data
        nverts = len(me.vertices)
        nedges = len(me.edges)
        bm = bmesh.new()
        f = scene.frame_start
        while f <= scene.frame_end:
            scene.frame_set(f)
            bm.from_object(ob, dg, cage=True)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.02)
            #    bmesh.ops.transform(bm, verts=bm.verts[:], matrix=ob.matrix_world)
            f += step
        rings.append(bm.edges[:])
        print("Frames processeds, going to do rings")
        # build from rings
        next = rings.pop()
        while rings:
            ring = rings.pop()
            bmesh.ops.bridge_loops(bm, edges=ring + next)
            next = ring

        rme = bpy.data.meshes.new("Rib")
        bm.to_mesh(rme)
        copy = bpy.data.objects.new("Rib", rme)
        coll.objects.link(copy)
        print("DONE" + ob.name)

    for ob in bpy.data.objects:
        if 'Rib' in ob.name:
            ob.select_set(True)
            bpy.context.view_layer.objects.active = ob
        else:
            ob.select_set(False)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.select_set(True)
    ob.rotation_euler = [0, 0, zrot]
    bpy.ops.export_mesh.stl(filepath=os.path.join(filepath, filename, filename + ".stl"), check_existing=True,
                            use_selection=True, global_scale=1, ascii=False, use_mesh_modifiers=False, batch_mode='OFF',
                            axis_forward='Y', axis_up='Z')
    bpy.ops.object.delete()


def write_pkl_data(filepath, filename, arm_ob, ob, info, frame_step=1, write_verts=False):
    bpy.context.scene.frame_current = bpy.context.scene.frame_start
    N = int((bpy.context.scene.frame_end - bpy.context.scene.frame_start + 1) / frame_step)
    n_bones = len(arm_ob.pose.bones) - 1
    n_verts = len(ob.data.vertices)
    if write_verts:
        d = {
            'frame': [],
            'bones': np.zeros((N, n_bones, 3), np.float32),
            'info': info,
            'verts': np.zeros((N, n_verts, 3), np.float32),
            'sf': bpy.context.scene.frame_start,
            'ef': bpy.context.scene.frame_end + 1,
            'nframes': frame_step
        }
    else:
        d = {
            'frame': [],
            'bones': np.zeros((N, n_bones, 3), np.float32),
            'info': info,
            'sf': bpy.context.scene.frame_start,
            'ef': bpy.context.scene.frame_end + 1,
            'nframes': frame_step
        }
    select(ob)
    dg = bpy.context.evaluated_depsgraph_get()

    cnt = 0
    for f in range(bpy.context.scene.frame_start, bpy.context.scene.frame_end + 1):
        sys.stdout.write('\r' + str(f) + '/' + str(N * frame_step))
        sys.stdout.flush()
        bpy.context.scene.frame_current = f
        bpy.context.view_layer.update()

        d['frame'].append(f)

        select(ob)
        tmp = ob.evaluated_get(dg)
        me = tmp.to_mesh()
        if write_verts:
            d['verts'][cnt] = np.reshape([ob.matrix_world @ v.co for v in me.vertices], (n_verts, 3))

        select(arm_ob)
        d['bones'][cnt] = np.reshape([arm_ob.matrix_world @ bone.head for bone in arm_ob.pose.bones[1:]], (n_bones, 3))
        cnt += 1

    if not os.path.exists(os.path.join(filepath, filename)):
        os.makedirs(os.path.join(filepath, filename))
    filepath = os.path.join(filepath, filename, filename + ".pkl")

    out = open(filepath, 'wb')
    pkl.dump(d, out)
    out.close()