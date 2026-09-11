import { Link, NavLink, Route, Routes } from "react-router-dom";
import ScenarioListPage from "./pages/ScenarioListPage.jsx";
import ScenarioDetailPage from "./pages/ScenarioDetailPage.jsx";
import ReportListPage from "./pages/ReportListPage.jsx";
import ReportDetailPage from "./pages/ReportDetailPage.jsx";
import FactorLibraryPage from "./pages/FactorLibraryPage.jsx";

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-leaf">🌿</span>
          <div>
            <div className="brand-title">产品碳足迹工作台</div>
            <div className="brand-sub">门到门 · 原材料入厂 → 产品出厂</div>
          </div>
        </div>
        <nav>
          <NavLink to="/" end>生产方案</NavLink>
          <NavLink to="/reports">核算报告</NavLink>
          <NavLink to="/factors">排放因子库</NavLink>
        </nav>
        <div className="sidebar-note">
          示例因子均为 <b>Acme 虚构数据</b>，仅用于演示，
          不来自付费数据库，<b>未获得任何认证</b>。
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<ScenarioListPage />} />
          <Route path="/scenarios/:id" element={<ScenarioDetailPage />} />
          <Route path="/reports" element={<ReportListPage />} />
          <Route path="/reports/:id" element={<ReportDetailPage />} />
          <Route path="/factors" element={<FactorLibraryPage />} />
        </Routes>
      </main>
    </div>
  );
}
