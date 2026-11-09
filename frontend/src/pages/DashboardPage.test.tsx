import { screen } from "@testing-library/react";

import { mockFetch, renderWithProviders } from "../test/render";
import { DashboardPage } from "./DashboardPage";

const EMPTY = {
  total_scans: 0,
  healthy_scans: 0,
  diseased_scans: 0,
  by_disease: [],
  by_week: [],
  by_district: [],
  feedback: { total: 0, correct: 0, incorrect: 0 },
  source: "Computed only from scans saved on this device.",
};

test("empty database shows an empty state and no numbers", async () => {
  mockFetch({ "/api/stats": EMPTY });
  renderWithProviders(<DashboardPage />);
  expect(await screen.findByTestId("empty-state")).toHaveTextContent("No scans yet");
  expect(screen.queryByTestId("stat-tiles")).not.toBeInTheDocument();
});

test("real counts are shown as tiles", async () => {
  mockFetch({
    "/api/stats": {
      ...EMPTY,
      total_scans: 3,
      diseased_scans: 3,
      by_disease: [{ key: "Potato___Early_blight", label: "Early blight (Potato)", count: 3 }],
      by_week: [{ key: "2026-W45", label: "2026-W45", count: 3 }],
      by_district: [{ key: "Skardu", label: "Skardu", count: 3 }],
    },
  });
  renderWithProviders(<DashboardPage />);
  expect(await screen.findByTestId("stat-tiles")).toHaveTextContent("3");
});
