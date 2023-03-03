# Human animations to USD

## This repository is part of the [GRADE](https://eliabntt.github.io/GRADE-RR/home) project

### This was tested on Windows, using Omniverse suggested Drivers and CUDA version.

The goal of this code is to show how you can convert any SMPL-based animation to a USD-based animation.
The script is capable of managing mesh caches and skeletal animations. It can export point-sequence based animations and skeletal-based animations.

### Installation instructions 

Install blender connector from the Omniverse launcher. This code was tested with versions 3.4.0-usd.101.0 (main branch) and (3.1.0-usd.100.1.10, checkout commit `8b45a952d748c2215c2c61f3adfa5be65828d217`). For the paper we used 3.1.0-usd.100.1.10.

Some limitations of 3.1.0-usd.100.1.10:
- you might need to use the mesh cache modifier instead of the blendshape. There is a _minimal_ difference that arise when loading the animation in Omniverse's products. 
- keep textures with absolute paths. You can replace them whenever you want afterwards with our tool [USD_text_replace](https://github.com/eliabntt/GRADE-RR/tree/main/scripts/process_paths) 

Install the necessary *dependencies*. Locate the blender installation path and run `python.exe -m pip install ipdb pyquaternion scipy torch pyyaml chumpy`.
e.g. In my case `C:\User\ebonetto\AppData\Local\ov\pkg\blender-3.4.0-usd.101.0\Release\3.4\python\bin\python.exe -m pip install ipdb pyquaternion scipy torch pyyaml chumpy`

Additionally, you need to follow [this]() to fill up the installation missing files that we cannot redistribute because of licensing.

### Already Supported datasets and HowTo expand

We are already supporting two datasets. [Cloth3D](https://chalearnlap.cvc.uab.cat/dataset/38/description/) and [AMASS](https://amass.is.tue.mpg.de/).

If you want to add a different dataset for AMASS you need to add it to the `data_folder/taxonomy.json` file

### Run the code 

*From the cloned repository main folder*

`\AppData\Local\ov\pkg\blender-3.4.0-usd.101.0\Release\blender.exe --python-use-system-env --python-exit-code 0 --python start_blend_debug.py -- generate_sequence.py --dataset ... --output_dir ... --samples_dir ... --last_sample ... --parent_path ... --sample_id ...`

The parameters are explained in the code or self-explaining.
`dataset` can be either `[cloth3d, amass]`. With `amass` a necessary configuration file needs to be included (e.g. `--config_file this_repo\humangenerator\amass.json`). We provide a sample config [here](https://github.com/eliabntt/generate_people/blob/main/humangenerator/amass.json).

Note that AMASS will process the folder directly (by querying subfolders) differently than Cloth3D for which you need to give the main parent folder (eg. `cloth3d/train_t1`).

`sample_id` if is an ID it will process that ID otherwise you can set it to all or leave it empty and it will process the whole set of data.

If running multiple loops the code will automatically periodically _clean_ the whole simulation environment including textures and materials to avoid crashing.

- Cloth3D single sample example `--python-use-system-env --python-exit-code 0 --python start_blend_debug.py -- generate_sequence.py --dataset cloth3d --output_dir outdir --samples_dir cloth3d\train --last_sample 01056 --parent_path D:\generate_people\data_folder\ --sample_id 01056`

- AMASS `--python-use-system-env --python-exit-code 0 --python start_blend_debug.py -- generate_sequence.py --dataset amass --output_dir D:\cloth3d\exported_usd --samples_dir D:\AMASS\CMU\ --parent_path D:\Cloth3D_to_usd\data_folder\ --config_file D:\Cloth3D_to_usd\humangenerator\amass.json`

### How does it work

The texture of the person is random. In the Cloth3D case the chosen ones are the ones with underwears, with AMASS the ones with clothes.

You have the possibility of exporting the SMPL information, the vertex info, the USD file, the STL trace of the animation and much more.

You can also suppress the output from the shell. However, the exporter in USD forcibly write directly to stdout. I have found no redirect strategy that works.

The system will replicate the input folder structure in the output folder.

You can also select a single frame.

You are encouraged to extend this and create pull requests.

Cloth3D clothes are loaded and exported as MeshCaches.

For the human animations you can chose.

### How to edit

You can create your own processor by creating a new class [here](https://github.com/eliabntt/generate_people/tree/main/humangenerator), adding your dataset name [here](https://github.com/eliabntt/generate_people/blob/main/humangenerator/avail_datasets.yaml) and write the else [here](https://github.com/eliabntt/generate_people/blob/main/humangenerator/generator.py#L17).

In practice you need to write your own python `dataset_gen.py`.

That file needs to have a `process_sample` method which will be then called by the main script.

Within `process_sample` you want to take care either of the sample (CLOTH3D) or of the whole folder (AMASS). Your choice.

We see the processing from the loading of the animation to writing data.

In the main script then there is a call to `get_processor` that returns `processor, PATH_SAMPLES`, `processor` is the instance of the class you just created.

Few lines below you find `res = processor.process_sample(sample, frame, smpl_body_list)`.

__________
### CITATION
If you find this work useful please cite our work as

```

```
__________

### Acknowledgment
Code based on
- [blenderproc](https://github.com/DLR-RM/BlenderProc/)
- [amass](https://amass.is.tue.mpg.de/)
- [Cloth3D starter kit](http://158.109.8.102/CLOTH3D/StarterKit.zip)
- [surreact](https://github.com/gulvarol/surreact) and [surreal](https://github.com/gulvarol/surreal)
