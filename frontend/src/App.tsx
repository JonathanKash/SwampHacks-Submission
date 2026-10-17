import { Navigate, Route, Routes } from "react-router-dom";
import AuditPage from "./AuditPage";
import EditPage from "./EditPage";
import ErrorBoundary from "./ErrorBoundary";
import LandingPage from "./LandingPage";
import TreePage from "./TreePage";

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/edit" element={<EditPage />} />
        <Route path="/tree" element={<TreePage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
