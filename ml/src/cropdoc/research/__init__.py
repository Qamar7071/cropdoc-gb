"""Research experiments that run on CPU (Milestone 2). Each module writes one results/*.json file.

leakage       naive vs group-aware split (frozen features + classical/MLP/1-NN baselines)
background    background uniformity and background-only probes (shortcut risk)
shift_eval    lab vs PlantDoc (public real-world photos) and vs GB field photos (PENDING until collected)
fewshot       accuracy vs k real-world photos per class (k = 0, 5, 10, 20; 3 seeds)
ood_eval      unseen diseases and non-leaf photos: AUROC of max-softmax and energy scores
calibrate     ECE, reliability, temperature scaling, selective prediction (lab and real-world)
explain_eval  Grad-CAM mass outside the leaf, leaf-removed test, galleries, confusion matrix
"""
