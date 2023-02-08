import json
import os
import humangenerator
import bpy
import humangenerator as hgen
import argparse
import ipdb
import sys
import yaml

parser = argparse.ArgumentParser()
parser.add_argument("--fbx", help="Path to the fbx file")
parser.add_argument("--output_dir", help="Path to where the data should be saved")
parser.add_argument("--temp_dir", help="Path to where the data should be temporary saved")
parser.add_argument("--usd", help="True if export usd is necessary, default to false", default="False")
args = parser.parse_args()


out_dir = args.output_dir
if not os.path.exists(out_dir):
    os.makedirs(out_dir)
fbx = args.fbx
for o in bpy.context.scene.objects:
    o.select_set(True)
    
# Call the operator only once
bpy.ops.object.delete()

with open(os.path.join(out_dir, f"out.txt"), "w") as file_out, open(
    os.path.join(out_dir, f"err.txt"), "w") as file_err:
    try:
        sys.stdout = file_out
        sys.stderr = file_err
        bpy.ops.import_scene.fbx(filepath=fbx)

        filepath=os.path.join(out_dir,os.path.basename(fbx[:-4])+".usd")
        temp_filepath = os.path.join(args.temp_dir,os.path.basename(fbx[:-4])+".usd")

        hgen.export_data(temp_path, out_dir, os.path.basename(fbx[:-4]), False, None, {}, {}, False, args.usd.lower() == "true")

        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()
        succeed = True
    except:
        import traceback
        sys.stderr.write('error\n')
        sys.stderr.write(traceback.format_exc())
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__