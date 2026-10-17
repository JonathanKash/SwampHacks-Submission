import { Navigate, Route, Routes } from "react-router-dom";
import AuditPage from "./AuditPage";
import ComparePage from "./ComparePage";
import EditPage from "./EditPage";
import ErrorBoundary from "./ErrorBoundary";
import IdentifyPage from "./IdentifyPage";
import LandingPage from "./LandingPage";
import MethodPage from "./MethodPage";
import TextPage from "./TextPage";
import TreePage from "./TreePage";

export default function App() {
  return (
    <ErrorBoundary>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/edit" element={<EditPage />} />
        <Route path="/identify" element={<IdentifyPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/tree" element={<TreePage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/text" element={<TextPage />} />
        <Route path="/method" element={<MethodPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ErrorBoundary>
  );
}
