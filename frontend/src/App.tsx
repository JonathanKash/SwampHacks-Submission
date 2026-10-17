import { Navigate, Route, Routes } from "react-router-dom";
import EditPage from "./EditPage";
import LandingPage from "./LandingPage";
import TreePage from "./TreePage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/edit" element={<EditPage />} />
      <Route path="/tree" element={<TreePage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
