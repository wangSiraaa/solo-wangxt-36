import ContributionTree from "./ContributionTree.jsx";
import { Badge, Banner, kg, tonnes, TYPE_BADGE, TYPE_LABEL } from "./ui.jsx";

/** 试算结果与确认报告共用的只读视图：总量、完整性、贡献树、追溯行、未核算项。 */
export default function ReportView({ report, onConfirm, confirming = false }) {
  const complete = report.is_complete;
  return (
    <div>
      <div className={`result-head ${complete ? "" : "result-head-partial"}`}>
        <div>
          <div className="result-total">
            {complete ? "产品碳足迹合计" : "已核算合计（部分总量）"}
          </div>
          <div className="result-value">
            {kg(report.accounted_kg)}
            <span className="result-tonne">≈ {tonnes(report.accounted_t)}</span>
          </div>
          <div className="muted small">
            {report.accounted_count}/{report.activity_count} 条活动已核算
            ｜基准日 {report.as_of}
          </div>
        </div>
        <div className="result-head-side">
          {complete ? (
            <Badge kind="ok">总量完整</Badge>
          ) : (
            <Badge kind="warn">不完整 · {report.unaccounted_count} 条未核算</Badge>
          )}
          {report.confirmed ? (
            <Badge kind="locked">报告已确认冻结 #{report.id}</Badge>
          ) : (
            onConfirm && (
              <button
                className="btn btn-primary"
                disabled={confirming}
                onClick={onConfirm}
                title={
                  complete
                    ? "确认后快照因子并冻结情景"
                    : "可确认，但报告将明确标注为部分总量"
                }
              >
                {complete ? "确认报告并冻结情景" : "确认部分总量报告（仍标注不完整）"}
              </button>
            )
          )}
        </div>
      </div>

      {report.completeness_notice && (
        <Banner kind="warn">⚠️ {report.completeness_notice}</Banner>
      )}

      <section className="card">
        <h3>贡献树</h3>
        <ContributionTree tree={report.tree} />
      </section>

      <section className="card">
        <h3>可追溯结果行（活动量 × 排放因子）</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>活动</th>
                <th>类型</th>
                <th>活动量</th>
                <th>基准单位量</th>
                <th>因子（版本 / 地区）</th>
                <th>因子值</th>
                <th>排放量</th>
              </tr>
            </thead>
            <tbody>
              {report.lines.map((ln, i) => (
                <tr key={i}>
                  <td>{ln.activity_name}</td>
                  <td>
                    <Badge kind={TYPE_BADGE[ln.activity_type]}>
                      {TYPE_LABEL[ln.activity_type]}
                    </Badge>
                  </td>
                  <td>
                    {ln.raw_amount} {ln.raw_unit_code}
                  </td>
                  <td title={ln.unit_factor_to_base ? `× ${ln.unit_factor_to_base}` : ""}>
                    {ln.amount_in_base}
                  </td>
                  <td>
                    <div>
                      {ln.factor_code} <b>v{ln.factor_version}</b>
                    </div>
                    <div className="muted small">
                      {ln.factor_name}（{ln.factor_region_code}）
                    </div>
                    <div className="small">因子ID #{ln.factor_id}</div>
                  </td>
                  <td>{ln.factor_value}</td>
                  <td className="num strong">{ln.emissions_kg}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {report.lines[0] && (
          <p className="muted small">
            计算式示例：{report.lines[0].formula}
          </p>
        )}
      </section>

      {(report.unaccounted_lines?.length > 0 ||
        report.unaccounted?.length > 0) && (
        <section className="card card-unaccounted">
          <h3>未核算项（单列展示，未计入上方总量）</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>活动</th>
                  <th>类型</th>
                  <th>活动量</th>
                  <th>请求因子</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                {(report.unaccounted_lines || report.unaccounted || []).map(
                  (u, i) => (
                    <tr key={i}>
                      <td>{u.activity_name}</td>
                      <td>{TYPE_LABEL[u.activity_type]}</td>
                      <td>
                        {u.raw_amount} {u.raw_unit_code}
                      </td>
                      <td>{u.requested_factor_code || "未指定"}</td>
                      <td className="reason">
                        <Badge kind="warn">{u.reason_code}</Badge>{" "}
                        {u.reason_detail}
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
