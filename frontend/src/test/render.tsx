import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

import { I18nProvider, type Lang } from "../i18n";
import { DistrictProvider } from "../state/district";

/** Render inside all app providers; `rerender` keeps the providers (they are a wrapper). */
export function renderWithProviders(ui: ReactElement, { lang = "en" as Lang, route = "/" } = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>
      <I18nProvider initialLang={lang}>
        <DistrictProvider>
          <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
        </DistrictProvider>
      </I18nProvider>
    </QueryClientProvider>
  );
  return render(ui, { wrapper: Wrapper });
}

/** Replace fetch with a router: { "/api/stats": body, ... } (unknown URLs → 404). */
export function mockFetch(routes: Record<string, unknown>): void {
  const fn = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : String(input);
    const key = Object.keys(routes).find((path) => url.startsWith(path));
    if (!key) return new Response(JSON.stringify({ detail: "not found" }), { status: 404 });
    return new Response(JSON.stringify(routes[key]), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fn);
}
