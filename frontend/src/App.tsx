import { lazy, Suspense, useEffect } from "react";
import { Route, Routes, useLocation } from "react-router";

import { Footer } from "./components/Footer";
import { MobileNav } from "./components/MobileNav";
import { TopBar } from "./components/TopBar";
import { Skeleton } from "./components/ui";
import { AboutPage, NotFoundPage } from "./pages/AboutPage";
import { AssistantPage } from "./pages/AssistantPage";
import { CropDetailPage, CropsPage } from "./pages/CropsPage";
import { DiseaseDetailPage } from "./pages/DiseaseDetailPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { LibraryPage } from "./pages/LibraryPage";
import { LiveScanPage } from "./pages/LiveScanPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ScannerPage } from "./pages/ScannerPage";
import { TipsPage } from "./pages/TipsPage";

// The two chart pages load their code (and the chart library) only when opened: a smaller first download on
// slow mobile data. Everything a farmer needs first (scan, report, assistant, crops, tips) stays in the main file.
const DashboardPage = lazy(() => import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const FieldIntelPage = lazy(() => import("./pages/FieldIntelPage").then((m) => ({ default: m.FieldIntelPage })));

function PageLoading() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-8" data-testid="page-loading">
      <Skeleton className="h-24 w-full" />
      <Skeleton className="h-72 w-full" />
    </div>
  );
}

function ScrollToTop() {
  const { pathname } = useLocation();
  // braces matter: newer browsers return a Promise from scrollTo, which React would treat as a cleanup
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

export function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <ScrollToTop />
      <TopBar />
      <main className="flex-1" id="main">
        <Suspense fallback={<PageLoading />}>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/scanner" element={<ScannerPage />} />
            <Route path="/live" element={<LiveScanPage />} />
            <Route path="/assistant" element={<AssistantPage />} />
            <Route path="/crops" element={<CropsPage />} />
            <Route path="/crops/:id" element={<CropDetailPage />} />
            <Route path="/tips" element={<TipsPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/library" element={<LibraryPage />} />
            <Route path="/library/:id" element={<DiseaseDetailPage />} />
            <Route path="/field-intelligence" element={<FieldIntelPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/history/:id" element={<ScanDetailPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
      <Footer />
      <MobileNav />
    </div>
  );
}
