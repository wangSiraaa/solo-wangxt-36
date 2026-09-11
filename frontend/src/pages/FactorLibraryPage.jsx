import { useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { Badge, Banner, Spinner } from "../components/ui.jsx";

export default function FactorLibraryPage() {
  const [factors, setFactors] = useState(null);
  const [units, setUnits] = useState([]);
  const [error, setError] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const today = new Date().toISOString().slice(0, 10);

  useEffect(() => {
    Promise.all([api.listFactors(), api.listUnits()])
      .then(([f, u]) => {
        setFactors(f);
        setUnits(u);
      })
      .catch((e) => setError(e.message));
  }, []);

  const dimName = useMemo(() => {
    const map = {};
    units.forEach((u) => (map[u.dimension] = u.dimension_display));
    return map;
  }, [units]);

  if (!factors) return <Spinner />;

  const statusOf = (f) => {
    if (today < f.valid_from) return { kind: "future", text: `未生效（${f.valid_from} 起）` };
    if (f.valid_to && today > f.valid_to)
      return { kind: "expired", text: `已过期（至 ${f.valid_to}）` };
    return { kind: "ok", text: "有效" };
  };

  const shown = factors.filter((f) => !typeFilter || f.activity_type === typeFilter);

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>排放因子库（版本管理）</h1>
          <p className="muted">
            同编码多版本，按核算基准日判断有效性；活动只可选择同量纲因子。
          </p>
        </div>
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="">全部类型</option>
          <option value="electricity">电力</option>
          <option value="fuel">燃料</option>
          <option value="auxiliary">辅料</option>
        </select>
      </header>

      <Banner kind="warn">
        本库所有因子均为 <b>Acme 虚构示例数据</b>，仅用于演示软件的版本、
        单位与适用地区管理；<b>不接入任何付费数据库，未经过认证</b>，
        严禁用于真实碳核算或合规披露。
      </Banner>
      {error && <Banner kind="error">{error}</Banner>}

      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>编码 / 版本</th>
                <th>名称</th>
                <th>类型</th>
                <th>地区</th>
                <th>分母量纲</th>
                <th>值 kgCO₂e/基准单位</th>
                <th>有效期</th>
                <th>状态（今日 {today}）</th>
              </tr>
            </thead>
            <tbody>
              {shown.map((f) => {
                const st = statusOf(f);
                return (
                  <tr key={f.id} className={st.kind === "expired" ? "row-expired" : ""}>
                    <td>
                      <b>{f.code}</b>
                      <div className="muted small">v{f.version} #{f.id}</div>
                    </td>
                    <td>{f.name}</td>
                    <td>{f.activity_type_display}</td>
                    <td>
                      {f.region_code}
                      <div className="muted small">{f.region_name}</div>
                    </td>
                    <td>{dimName[f.denominator_dimension] || f.denominator_dimension}</td>
                    <td className="num">{f.value}</td>
                    <td className="small">
                      {f.valid_from} ~ {f.valid_to || "长期有效"}
                    </td>
                    <td>
                      <Badge
                        kind={
                          st.kind === "ok" ? "ok" : st.kind === "expired" ? "expired" : "future"
                        }
                      >
                        {st.text}
                      </Badge>
                      <div className="muted small">{f.source}</div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
