import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router";

import { Footer } from "./components/Footer";
import { MobileNav } from "./components/MobileNav";
import { TopBar } from "./components/TopBar";
import { AboutPage, NotFoundPage } from "./pages/AboutPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DiseaseDetailPage } from "./pages/DiseaseDetailPage";
import { FieldIntelPage } from "./pages/FieldIntelPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { LibraryPage } from "./pages/LibraryPage";
import { ScanDetailPage } from "./pages/ScanDetailPage";
import { ScannerPage } from "./pages/ScannerPage";

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
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/scanner" element={<ScannerPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/library/:id" element={<DiseaseDetailPage />} />
          <Route path="/field-intelligence" element={<FieldIntelPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/history/:id" element={<ScanDetailPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
      <MobileNav />
    </div>
  );
}
