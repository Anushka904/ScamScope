import { BrowserRouter, Route, Routes } from "react-router-dom";
import { SiteHeader } from "./components/SiteHeader";
import { SiteFooter } from "./components/SiteFooter";
import { LandingPage } from "./pages/LandingPage";
import { SubmitPage } from "./pages/SubmitPage";
import { CasePage } from "./pages/CasePage";
import { AccuracyPage } from "./pages/AccuracyPage";
import { CaseBoardPage } from "./pages/CaseBoardPage";

function NotFound() {
  return <main className="empty-page"><p className="eyebrow">404 / FILE NOT FOUND</p><h1>This page is off the record.</h1><a className="button button-primary" href="/">Return to the lab</a></main>;
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <SiteHeader />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/investigate" element={<SubmitPage />} />
          <Route path="/case" element={<CasePage />} />
          <Route path="/accuracy" element={<AccuracyPage />} />
          <Route path="/cases" element={<CaseBoardPage />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
        <SiteFooter />
      </div>
    </BrowserRouter>
  );
}
