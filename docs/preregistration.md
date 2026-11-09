# Pre-registered comparisons (written before the Colab sweep)

These headline comparisons, and how they are tested, were fixed **before** any sweep run, so they cannot
be chosen after seeing the results. They are implemented in `ml/src/cropdoc/evaluate.py` (`COMPARISONS`).

| ID | Question | A vs B | Evaluation set | Metric |
|---|---|---|---|---|
| H1-r18, H1-mbv3, H1-cnn | How much does a naive split inflate accuracy? | `*_std_naive` vs `*_std` | each split's own test set | accuracy |
| H3-r18, H3-mbv3 | Does background randomization improve real-world accuracy? | `*_bgrand` vs `*_std` | PlantDoc | accuracy |
| H4-r18 | Does strong augmentation improve real-world accuracy? | `r18_strong` vs `r18_std` | PlantDoc | accuracy |
| H5 | Does ImageNet pretraining help on real-world photos? | `mbv3_std` vs `cnn_std` | PlantDoc | accuracy |

**Statistics.**
- **Seeds:** every configuration runs with 3 seeds; tables report mean ± std across seeds.
- **Per-photo correctness:** a photo's correctness is averaged over the seeds, giving a value in {0, ⅓, ⅔, 1}.
- **Confidence interval:** a bootstrap over photos (2,000 resamples) gives a 95% CI for A − B. It is paired when both
  arms are scored on the same photos (all comparisons except H1, whose test sets differ).
- **Reading a CI:** a CI that excludes 0 is reported as a difference; otherwise "no clear difference".
- **Multiple comparisons:** there are 7, so CIs near 0 should be read cautiously.

**Model selection** uses validation data only (PlantVillage validation; background-swapped validation for
robustness choices). PlantDoc and GB field photos are never used to choose models or thresholds.

**Already measured on CPU (frozen-feature model, before the sweep):** the leakage, PlantDoc gap, few-shot,
OOD, calibration and Grad-CAM studies in `results/`. These are reported as they came out, with no reruns
to improve them.
