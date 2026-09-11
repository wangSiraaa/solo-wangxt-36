import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Badge, Spinner, kg } from "../components/ui.jsx";

export default function ReportListPage() {
  const [reports, setReports] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listReports().then(setReports).catch((e) => setError(e.message));
  }, []);

  if (!reports) return <Spinner />;

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>核算报告</h1>
          <p className="muted">
            报告在试算时生成；确认后因子值与版本被快照冻结，可长期追溯。
          </p>
        </div>
      </header>

      {error && <div className="banner banner-error">{error}</div>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>方案</th>
                <th>产品</th>
                <th>已核算合计</th>
                <th>完整性</th>
                <th>状态</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/reports/${r.id}`}>#{r.id}</Link>
                  </td>
                  <td>
                    <Link to={`/scenarios/${r.scenario}`}>{r.scenario_name}</Link>
                  </td>
                  <td>{r.product}</td>
                  <td className="num">{kg(r.accounted_kg)}</td>
                  <td>
                    {r.is_complete ? (
                      <Badge kind="ok">完整</Badge>
                    ) : (
                      <Badge kind="warn">部分总量（{r.unaccounted_count} 条未核算）</Badge>
                    )}
                  </td>
                  <td>
                    {r.confirmed ? (
                      <Badge kind="locked">已确认冻结</Badge>
                    ) : (
                      <Badge kind="draft">试算稿</Badge>
                    )}
                  </td>
                  <td className="muted small">{r.created_at?.replace("T", " ").slice(0, 16)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
