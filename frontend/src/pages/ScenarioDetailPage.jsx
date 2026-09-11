import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api } from "../api.js";
import { Badge, Banner, Spinner, TYPE_BADGE, TYPE_LABEL } from "../components/ui.jsx";
import ReportView from "../components/ReportView.jsx";

const EMPTY_FORM = {
  activity_type: "electricity",
  name: "",
  amount: "",
  unit: "",
  factor: "",
  factor_code: "",
  external_ref: "",
};

export default function ScenarioDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [scenario, setScenario] = useState(null);
  const [units, setUnits] = useState([]);
  const [factors, setFactors] = useState([]);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [csvText, setCsvText] = useState(
    "external_ref,activity_type,name,amount,unit_code,factor_code\n" +
      "DOC-201,fuel,示例燃料,100,L,FU-DIESEL"
  );

  const locked = scenario?.status === "confirmed";

  const load = async () => {
    const [s, u, f] = await Promise.all([
      api.getScenario(id),
      api.listUnits(),
      api.listFactors(),
    ]);
    setScenario(s);
    setUnits(u);
    setFactors(f);
  };

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);

  const filteredFactors = useMemo(() => {
    const unit = units.find((u) => String(u.id) === String(form.unit));
    return factors.filter(
      (f) =>
        f.activity_type === form.activity_type &&
        (!unit || f.denominator_dimension === unit.dimension)
    );
  }, [factors, form.activity_type, form.unit, units]);

  if (!scenario) return <Spinner />;

  const wrap = async (fn, success) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const r = await fn();
      if (success) success(r);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const doCalculate = () =>
    wrap(() => api.calculate(id), (r) => {
      setResult(r);
      if (r.is_complete) setNotice("核算完成，总量完整。");
    });

  const doCopy = () =>
    wrap(() => api.copyScenario(id), (clone) =>
      navigate(`/scenarios/${clone.id}`)
    );

  const addActivity = (e) => {
    e.preventDefault();
    wrap(
      () =>
        api.createActivity({
          scenario: Number(id),
          ...form,
          amount: form.amount,
          factor: form.factor ? Number(form.factor) : null,
        }),
      async () => {
        setShowForm(false);
        setForm(EMPTY_FORM);
        await load();
      }
    );
  };

  const doImport = (useCsv) =>
    wrap(
      () =>
        api.importActivities(
          id,
          useCsv ? { csv: csvText } : { rows: safeParseRows() }
        ),
      async (r) => {
        setNotice(r.message + (r.skipped.length ? `（跳过 ${r.skipped.length} 条重复）` : ""));
        setShowImport(false);
        await load();
      }
    );

  const safeParseRows = () => {
    try {
      const parsed = JSON.parse(csvText);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      setError("JSON 解析失败，请检查格式");
      return [];
    }
  };

  const removeActivity = (aid) =>
    wrap(() => api.deleteActivity(aid), load);

  const confirmReport = (reportId) =>
    wrap(() => api.confirmReport(reportId), async (r) => {
      setResult(r);
      await load();
      setNotice("报告已确认：因子快照冻结，情景已锁定。");
    });

  return (
    <div className="detail">
      <div className="back-link">
        <Link to="/">← 全部方案</Link>
      </div>

      <header className="page-head">
        <div>
          <h1>
            {scenario.name}{" "}
            {locked ? (
              <Badge kind="locked">已确认 · 冻结</Badge>
            ) : (
              <Badge kind="draft">草稿</Badge>
            )}
          </h1>
          <p className="muted">
            产品：{scenario.product}　|　功能单位：{scenario.functional_unit}
            <br />
            边界：{scenario.boundary_note}　|　基准日：{scenario.as_of}
          </p>
        </div>
        <div className="head-actions">
          <button className="btn" onClick={doCopy} disabled={busy}>
            复制为新方案
          </button>
          {!locked && (
            <button className="btn btn-primary" onClick={doCalculate} disabled={busy}>
              试算 / 重新核算
            </button>
          )}
        </div>
      </header>

      {error && <Banner kind="error">{error}</Banner>}
      {notice && <Banner kind="ok">{notice}</Banner>}
      {locked && (
        <Banner>
          该方案已确认并冻结，活动数据不可修改；如需调整，请点「复制为新方案」。
          已确认报告继续保留确认时的原始因子，不受因子库改版影响。
        </Banner>
      )}

      <section className="card">
        <div className="card-head">
          <h3>活动数据（{scenario.activities.length} 条）</h3>
          {!locked && (
            <div className="head-actions">
              <button className="btn btn-small" onClick={() => setShowImport((v) => !v)}>
                批量导入
              </button>
              <button className="btn btn-small" onClick={() => setShowForm((v) => !v)}>
                + 添加活动
              </button>
            </div>
          )}
        </div>

        {showForm && (
          <form className="form-grid add-form" onSubmit={addActivity}>
            <label>
              活动类型
              <select
                value={form.activity_type}
                onChange={(e) => setForm({ ...form, activity_type: e.target.value, factor: "" })}
              >
                {Object.entries(TYPE_LABEL).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </label>
            <label>
              活动名称
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              活动量
              <input
                required
                type="number"
                step="any"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </label>
            <label>
              计量单位
              <select
                required
                value={form.unit}
                onChange={(e) => setForm({ ...form, unit: e.target.value, factor: "" })}
              >
                <option value="">请选择</option>
                {units.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.code}（{u.dimension_display}）
                  </option>
                ))}
              </select>
            </label>
            <label>
              排放因子（仅显示同类型同量纲，留空=未核算）
              <select
                value={form.factor}
                onChange={(e) =>
                  setForm({
                    ...form,
                    factor: e.target.value,
                    factor_code: e.target.selectedOptions[0]?.dataset.code || "",
                  })
                }
              >
                <option value="">— 不指定（列为未核算）—</option>
                {filteredFactors.map((f) => (
                  <option key={f.id} value={f.id} data-code={f.code}>
                    {f.code} v{f.version}（{f.region_code}）{f.valid_to ? ` 至 ${f.valid_to}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label>
              外部单据号（防重复，可空）
              <input
                value={form.external_ref}
                onChange={(e) => setForm({ ...form, external_ref: e.target.value })}
              />
            </label>
            <div className="form-actions">
              <button className="btn btn-primary" type="submit" disabled={busy}>保存活动</button>
            </div>
          </form>
        )}

        {showImport && (
          <div className="import-box">
            <p className="muted small">
              粘贴 CSV（表头：external_ref,activity_type,name,amount,unit_code,factor_code）
              或 JSON 数组。同一 external_ref 重复导入将被<b>跳过而非累加</b>；
              量纲不相容或因子过期将整批拒绝。
            </p>
            <textarea
              rows="6"
              value={csvText}
              onChange={(e) => setCsvText(e.target.value)}
            />
            <div className="head-actions">
              <button className="btn btn-small" onClick={() => doImport(true)}>按 CSV 导入</button>
              <button className="btn btn-small" onClick={() => doImport(false)}>按 JSON 导入</button>
            </div>
          </div>
        )}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>活动</th>
                <th>类型</th>
                <th>活动量</th>
                <th>因子</th>
                <th>外部单据</th>
                {!locked && <th></th>}
              </tr>
            </thead>
            <tbody>
              {scenario.activities.map((a) => (
                <tr key={a.id}>
                  <td>{a.name}</td>
                  <td>
                    <Badge kind={TYPE_BADGE[a.activity_type]}>
                      {TYPE_LABEL[a.activity_type]}
                    </Badge>
                  </td>
                  <td>
                    {a.amount} {a.unit_code}
                    <span className="muted small">（{a.unit_dimension}）</span>
                  </td>
                  <td>
                    {a.factor_label ? (
                      <>
                        {a.factor_label}
                        {a.factor_resolution_note && (
                          <div className="muted small">{a.factor_resolution_note}</div>
                        )}
                      </>
                    ) : (
                      <Badge kind="warn">缺因子 → 未核算</Badge>
                    )}
                  </td>
                  <td className="muted small">{a.external_ref || "—"}</td>
                  {!locked && (
                    <td>
                      <button
                        className="btn btn-link btn-danger"
                        onClick={() => removeActivity(a.id)}
                      >
                        删除
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {result && (
        <ReportView
          report={result}
          confirming={busy}
          onConfirm={
            locked || result.confirmed
              ? undefined
              : () => confirmReport(result.id)
          }
        />
      )}
    </div>
  );
}
