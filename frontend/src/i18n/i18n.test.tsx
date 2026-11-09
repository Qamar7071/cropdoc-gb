import { fireEvent, screen } from "@testing-library/react";

import { LanguageToggle } from "../components/TopBar";
import { renderWithProviders } from "../test/render";
import en from "./en.json";
import { translate } from "./index";
import ur from "./ur.json";

test("every English key has an Urdu translation", () => {
  const missing = Object.keys(en).filter((key) => !(key in ur));
  expect(missing).toEqual([]);
});

test("Urdu file is marked as needing native review", () => {
  expect(Object.keys(ur).some((key) => key.includes("needs_native_review"))).toBe(true);
});

test("toggle switches to Urdu and right-to-left", () => {
  renderWithProviders(<LanguageToggle />);
  expect(document.documentElement.dir).toBe("ltr");
  fireEvent.click(screen.getByTestId("lang-toggle"));
  expect(document.documentElement.dir).toBe("rtl");
  expect(document.documentElement.lang).toBe("ur");
  expect(screen.getByTestId("lang-toggle")).toHaveTextContent("English");
});

test("missing keys fall back to English, variables are interpolated", () => {
  expect(translate("ur", "no.such.key")).toBe("no.such.key");
  expect(translate("en", "home.cases", { count: 4 })).toBe("4 cases");
});
