# Gilgit-Baltistan field photos (evaluation only)

Place your own photos here, one folder per class, using the model's class ids:

    data/field_test/Potato___Late_blight/<district>_<plant>_<leaf>_<yyyymmdd>_<n>.jpg

Example: `Skardu_P012_L03_20270614_2.jpg` = district Skardu, plant 12, leaf 3, 14 June 2027, photo 2.
Photos of the same leaf share plant + leaf ids, so the code can keep them together and never
put one in the few-shot pool and another in the test split.

Read docs/field_collection_guide.md before collecting. Labels must be confirmed by an
agriculture expert. While this folder is empty, every GB field result is shown as PENDING.
