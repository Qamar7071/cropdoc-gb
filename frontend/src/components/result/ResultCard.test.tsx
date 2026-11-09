import { screen } from "@testing-library/react";

import type { PredictResponse } from "../../lib/api";
import { mockFetch, renderWithProviders } from "../../test/render";
import { ResultCard } from "./ResultCard";

const PIXEL = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

function result(overrides: Partial<PredictResponse> = {}): PredictResponse {
  return {
    scan_id: "abc",
    saved: true,
    status: "confident",
    class_id: "Potato___Early_blight",
    crop: "Potato",
    disease: "Early blight",
    healthy: false,
    confidence: 0.912,
    top3: [
      { class_id: "Potato___Early_blight", crop: "Potato", disease: "Early blight", probability: 0.912 },
      { class_id: "Potato___healthy", crop: "Potato", disease: "Healthy", probability: 0.05 },
    ],
    disease_info: { id: "Potato___Early_blight", description: "A fungal disease.", category: "fungal", recommendations: ["Remove infected leaves"], needs_review: true },
    gradcam_png: PIXEL,
    heatmap_png: PIXEL,
    model_view_jpeg: PIXEL,
    scores: { max_softmax: 0.912, energy: -9 },
    thresholds: { min_confidence: 0.64, max_energy: -3.9, provisional: true, source: "test" },
    crop_hint: null,
    district: null,
    model_version: "test",
    disclaimer: "General guidance only, not a diagnosis. Please consult an agriculture expert.",
    ...overrides,
  };
}

beforeEach(() => {
  mockFetch({ "/api/model": { model_loaded: true, classes: [], crops: [], districts: [], model_card: {}, calibration: {} } });
});

test("confident result shows disease, confidence, top-3 and the disclaimer", () => {
  renderWithProviders(<ResultCard result={result()} previewUrl={null} loading={false} error={null} />);
  expect(screen.getByTestId("disease-name")).toHaveTextContent("Early blight");
  expect(screen.getByTestId("confidence-badge")).toHaveTextContent("91.2%");
  expect(screen.getByTestId("top3")).toHaveTextContent("Healthy");
  expect(screen.getByTestId("disclaimer")).toBeInTheDocument();
  expect(screen.queryByTestId("uncertain-warning")).not.toBeInTheDocument();
  expect(screen.getByText("Remove infected leaves")).toBeInTheDocument();
});

test("low confidence shows the 'consult an expert' warning and still the disclaimer", () => {
  renderWithProviders(<ResultCard result={result({ status: "low_confidence", confidence: 0.41 })} previewUrl={null} loading={false} error={null} />);
  expect(screen.getByTestId("uncertain-warning")).toHaveTextContent("Not sure, please consult an agriculture expert");
  expect(screen.getByTestId("disclaimer")).toBeInTheDocument();
});

test("unsupported input hides recommendations", () => {
  renderWithProviders(
    <ResultCard result={result({ status: "not_a_leaf_or_unsupported_crop" })} previewUrl={null} loading={false} error={null} />,
  );
  expect(screen.getByTestId("uncertain-warning")).toHaveTextContent("does not look like a supported leaf");
  expect(screen.queryByText("Remove infected leaves")).not.toBeInTheDocument();
});

test("empty and loading states", () => {
  const { rerender } = renderWithProviders(<ResultCard result={null} previewUrl={null} loading={false} error={null} />);
  expect(screen.getByTestId("result-empty")).toBeInTheDocument();
  rerender(<ResultCard result={null} previewUrl={null} loading error={null} />);
});
