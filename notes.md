Installation instructions

From the `generate_people` folder

```
mkdir data_folder
cd data_folder
git clone https://github.com/gulvarol/surreact surreal
```

- Download the following two fbx files for SMPL for Maya from https://smpl.is.tue.mpg.de/ using your credentials. Please comply with their license. The files are `basicModel_f_lbs_10_207_0_v1.0.2.fbx` and `basicModel_m_lbs_10_207_0_v1.0.2.fbx` and can be downloaded with this [link](https://download.is.tue.mpg.de/download.php?domain=smpl&sfile=SMPL_maya.zip). Place them in `.../surreal/datageneration/smpl_data`.

- download this [pkl](https://raw.githubusercontent.com/gulvarol/surreal/master/datageneration/pkl/segm_per_v_overlap.pkl) and place it in `.../surreal/datageneration/smpl_data`

- get [SMPL_python_v.1.0.0](https://download.is.tue.mpg.de/download.php?domain=smpl&sfile=SMPL_python_v.1.0.0.zip). Extract the basicModel\_[m,f]\_lbs\_10\_207\_0\_v1.0.0.pkl. Place those two files in `.../surreal/datageneration/smpl_data/smpl/models/basicModel_{f,m}_lbs_10_207_0_v1.0.0.pkl`. Run `mv basicmodel_m_lbs_10_207_0_v1.0.0.pkl basicModel_m_lbs_10_207_0_v1.0.0.pkl`

- `cp .../surreal/datageneration/misc/prepare_smpl_data/extract_J_regressors.py .../surreal/datageneration/smpl_data/smpl/`
- run `python3 extract_J_regressor.py`

## Surreal Textures
- Accept surreal terms and get an account (you will need username and password to download textures)

- get the download script https://github.com/gulvarol/surreal/blob/master/download/download_smpl_data.sh and place it somewhere you like
let's call this location "loc"

- download this file https://github.com/gulvarol/surreal/blob/master/download/files/files_smpl_data.txt 
and place it "loc/files/files_smpl_data.txt"(alongside the fbx models)

essentially you have ./loc/{script,files/files_smpl_data.txt}

- call the download script with  `./download_smpl_data.sh /yourpath/surreal/datageneration/smpl_data username_surreal pw_surreal`
_____

At this point you should have 
smpl_data/basicModel_{f,m}_lbs_10_207_0_v1.0.2.fbx
smpl_data/smpl/models/basicModel_{f,m}_lbs_10_207_0_v1.0.0.pkl
smpl_data/segm_per_v_overlap.pkl
smpl_data/joint_regressors.pkl
_____

## For AMASS

- create a `body_models` folder in `data_folder`
- create inside `smplh` and `dmpls` folders
- download [dmpls](https://download.is.tue.mpg.de/download.php?domain=smpl&sfile=dmpls.tar.xz) (DMPLs compatibile with SMPL) and [smplh](https://mano.is.tue.mpg.de/download.php) and get `Extended SMPLH model for AMASS` (accepting the respective licenses) there.

NOTE:
If exporting WITH cache, the hand movement will be complete, if exporting WITHOUT cache it will not as the basic model for blendshapes is the SMPL model WITHOUT hand. It shouldn't be too difficult to adapt the code to your needs eventually.
TESTED ONLY WITH CMU DATA