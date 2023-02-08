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
parser.add_argument("--dataset", help="Dataset from which you want to generate data")
parser.add_argument("--output_dir", help="Path to where the data should be saved")
parser.add_argument("--samples_dir", help="Paths where the data is stored")
parser.add_argument("--last_sample",
                    help="Last sample processed, this must be the FULL name of the folder (e.g. 00001). This WILL be processed",
                    default="")
parser.add_argument("--parent_path", help="Path containing the subfolders for the datasets (with the pkl models)",
                    default="")
parser.add_argument("--sample_id", help="ID of the sample, if emtpy process all", default="all")
parser.add_argument("--with_cache", help="Write \"False\" if generating blendshapes", default="True")
parser.add_argument("--suppress_out", help="Write \"False\" if output in console", default="False")
parser.add_argument("--write_verts", help="Write \"True\" if you want to write verts info in the pkl", default="False")
parser.add_argument("--frame", help="The n-th frame to generate. Default all", default="all")
parser.add_argument("--config_file", help="json file containing the configuration", default="")
parser.add_argument("--exp_name",
                    help="The name of the \"experiment\" of the dataset. By default the name of the samples_dir folder",
                    default="")


# structure should be `parent_path/[surreal/datageneration/smpl_data,body_models/{smplh,dmpls}]`
args = parser.parse_args()
with open(os.path.join("humangenerator", "avail_datasets.yaml"), 'r') as stream:
    data_loaded = yaml.safe_load(stream)
    avail_datasets = data_loaded["datasets"]

processor = None
if avail_datasets == [] or args.dataset not in avail_datasets:
    if not avail_datasets:
        print("No avail dataset. Check file")
    else:
        print(f"Sought dataset is not yet avail. The avail ones are {avail_datasets}")
    exit(-1)
else:
    print(f"Processing {args.dataset} data")

found = (args.last_sample == "")

try:
    WITH_CACHE = (False if args.with_cache == "False" else True)
    parent_path = args.parent_path

    smpl_body_list = []
    # Init SMPL models
    smpl_path = os.path.join(parent_path, "surreal", "datageneration", "smpl_data")
    smpl_models = {
        'f': hgen.SMPLModel(os.path.join(smpl_path, 'smpl', 'models', 'basicModel_f_lbs_10_207_0_v1.0.0.pkl')),
        'm': hgen.SMPLModel(os.path.join(smpl_path, 'smpl', 'models', 'basicModel_m_lbs_10_207_0_v1.0.0.pkl')),
    }

    if args.frame != "all":
        try:
            frame = int(args.frame)
        except:
            print("Error converting frame to int, considering the WHOLE sequence")
            frame = None
    else:
        frame = None
        print("Whole sequence considered")
        print("This will export only the whole sequence")

    hgen.init()

    # Parse args
    PATH_SAMPLES = args.samples_dir

    if args.exp_name == "":
        exp_name = os.path.split(PATH_SAMPLES)[-1]
    else:
        exp_name = args.exp_name

    PATH_OUT = os.path.join(args.output_dir, exp_name)
    if not os.path.exists(PATH_OUT):
        os.makedirs(PATH_OUT)

    if args.config_file == "":
        config = {}
    else:
        if os.path.exists(args.config_file):
            with open(args.config_file, "r") as f:
                config = json.load(f)
        else:
            raise Exception("The taxonomy file could not be found: {}".format(args.config_file))

    processor, PATH_SAMPLES = hgen.get_processor(args.dataset, parent_path, WITH_CACHE, PATH_OUT, PATH_SAMPLES,
                                                 smpl_models, args.write_verts.lower() == "false", config)
    sample_id = args.sample_id
    if sample_id != "all":
        print("Processing single sample")
        # Check if sample exists
        if not os.path.isdir(os.path.join(PATH_SAMPLES, sample_id)):
            print("Specified sample does not exist")
            exit(-1)
        else:
            sample_id = [sample_id]
    else:
        print("Processing all samples")
        sample_id = os.listdir(PATH_SAMPLES)
        if not sample_id:
            print("No subfolder found")
            exit(-1)

    if len(smpl_body_list) == 0:
        smpl_body_list = processor.generator.load_SMPLs_objects()

    found = (args.last_sample == "")

    sample_id.sort()

    clean_cnt = 1
    for sample in sample_id:
        if not found:
            if sample == args.last_sample:
                found = True
            else:
                continue
        if clean_cnt % 100 == 0:
            clean_cnt = 0
            hgen.init()
            smpl_body_list = processor.generator.load_SMPLs_objects()

        clean_cnt += 1
        print("------------------------------")
        print(f"Processing {sample}")
        isdone = False
        count = 0
        while (not isdone and count <= 5):
            hgen.deselect()
            if len(sample_id) > 1:
                hgen.clean_mesh_and_textures(
                    exclude=['Material_0', 'Material_1', 'Armature_0', 'Armature_1', 'body_0', 'body_1'])
                print("Scene cleaned!\n\n")

            count += 1
            path_sample = os.path.join(PATH_OUT, sample + ('_with_cache' if WITH_CACHE else ''))
            if not os.path.exists(path_sample):
                os.makedirs(path_sample)
            with open(os.path.join(path_sample, f"out_{count}.txt"), "w") as file_out, open(
                    os.path.join(path_sample, f"err_{count}.txt"), "w") as file_err:
                # file logging
                try:
                    if args.suppress_out == "True":
                        sys.stdout = file_out
                        sys.stderr = file_err

                    res = processor.process_sample(sample, frame, smpl_body_list)
                    if res:
                        print("Exported!")
                    else:
                        raise Exception("Unknown error")

                    isdone = True
                except:
                    import traceback

                    sys.stderr.write('error\n')
                    sys.stderr.write(traceback.format_exc())
                    print(f"Failed -- going with try {count}\n\n")
                finally:
                    sys.stderr.flush()
                    sys.stdout.flush()
                    sys.stdout = sys.__stdout__
                    sys.stderr = sys.__stderr__
except:

    import traceback

    sys.stderr.write('error\n')
    sys.stderr.write(traceback.format_exc())

    sys.stdout.flush()
    sys.stderr.flush()

    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    print('error')
    print(traceback.format_exc())
    extype, value, tb = sys.exc_info()
    ipdb.post_mortem(tb)
