import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Registration from "@/pages/Registration";
import Quiz from "@/pages/Quiz";
import Completion from "@/pages/Completion";
import AdminLogin from "@/pages/AdminLogin";
import AdminDashboard from "@/pages/AdminDashboard";
import LiveLeaderboard from "@/pages/LiveLeaderboard";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Registration />} />
        <Route path="/quiz" element={<Quiz />} />
        <Route path="/completion" element={<Completion />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/live" element={<LiveLeaderboard />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
