# E2E fixtures

- `field-low-confidence.jpg`: a real-world photo from the PlantDoc test set
  (`test/Apple rust leaf/2011-011.jpg`, https://github.com/pratikkayal/PlantDoc-Dataset, CC BY 4.0),
  resized to ≤1200 px. The real quick model is NOT confident on it (it is used to screenshot the
  "Not sure, please consult an agriculture expert" state with a genuine model output, not a mock).
- The upload test uses `public/examples/early-blight.jpg` (PlantVillage test split, CC BY-SA 3.0).
