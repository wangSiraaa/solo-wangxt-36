import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api.js";
import { Spinner, Banner } from "../components/ui.jsx";
import ReportView from "../components/ReportView.jsx";

export default function ReportDetailPage() {
  const { id } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getReport(id).then(setReport).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <Banner kind="error">{error}</Banner>;
  if (!report) return <Spinner />;

  const confirm = async () => {
    setBusy(true);
    try {
      setReport(await api.confirmReport(id));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="back-link">
        <Link to="/reports">← 全部报告</Link>
      </div>
      <header className="page-head">
        <div>
          <h1>报告 #{report.id} · {report.scenario_name}</h1>
          <p className="muted">
            产品：{report.product}　|　边界：{report.boundary}
          </p>
        </div>
      </header>
      <ReportView report={report} confirming={busy} onConfirm={report.confirmed ? undefined : confirm} />
    </div>
  );
}
