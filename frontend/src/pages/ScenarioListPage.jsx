import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { Badge, Banner, Spinner } from "../components/ui.jsx";

export default function ScenarioListPage() {
  const [scenarios, setScenarios] = useState(null);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: "",
    product: "",
    as_of: new Date().toISOString().slice(0, 10),
  });

  const load = () =>
    api.listScenarios().then(setScenarios).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      await api.createScenario(form);
      setCreating(false);
      setForm({ ...form, name: "", product: "" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  if (!scenarios) return <Spinner />;

  return (
    <div>
      <header className="page-head">
        <div>
          <h1>生产方案（情景）</h1>
          <p className="muted">
            同一产品可建立多个生产方案对比碳排；已确认方案冻结，调整请复制为新方案。
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating((v) => !v)}>
          {creating ? "取消" : "+ 新建方案"}
        </button>
      </header>

      {error && <Banner kind="error">{error}</Banner>}

      {creating && (
        <form className="card form-grid" onSubmit={submit}>
          <label>
            方案名称
            <input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="如：A型减速箱-基线方案"
            />
          </label>
          <label>
            产品名称
            <input
              required
              value={form.product}
              onChange={(e) => setForm({ ...form, product: e.target.value })}
            />
          </label>
          <label>
            核算基准日（按该日判断因子有效性）
            <input
              type="date"
              required
              value={form.as_of}
              onChange={(e) => setForm({ ...form, as_of: e.target.value })}
            />
          </label>
          <div className="form-actions">
            <button className="btn btn-primary" type="submit">创建</button>
          </div>
        </form>
      )}

      <div className="card-list">
        {scenarios.map((s) => (
          <Link key={s.id} to={`/scenarios/${s.id}`} className="card scenario-card">
            <div className="scenario-card-head">
              <strong>{s.name}</strong>
              {s.status === "confirmed" ? (
                <Badge kind="locked">已确认 · 冻结</Badge>
              ) : (
                <Badge kind="draft">草稿</Badge>
              )}
            </div>
            <div className="muted">
              产品：{s.product}　|　功能单位：{s.functional_unit}
            </div>
            <div className="muted">基准日：{s.as_of}</div>
            {s.source_scenario && <div className="muted small">由其他方案复制而来</div>}
          </Link>
        ))}
      </div>

      <Banner>
        系统边界为首版限定：<b>原材料入厂 → 产品出厂（门到门）</b>，
        支持电力、燃料、辅料三类活动；不含上游原料开采与下游分销使用阶段。
      </Banner>
    </div>
  );
}
