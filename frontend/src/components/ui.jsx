export function Banner({ kind = "info", children }) {
  if (!children) return null;
  return <div className={`banner banner-${kind}`}>{children}</div>;
}

export function Badge({ kind = "neutral", children }) {
  return <span className={`badge badge-${kind}`}>{children}</span>;
}

export function Spinner() {
  return <div className="spinner">加载中…</div>;
}

export function kg(value) {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  return `${n.toLocaleString("zh-CN", { maximumFractionDigits: 3 })} kgCO₂e`;
}

export function tonnes(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 6 })} tCO₂e`;
}

export const TYPE_BADGE = {
  electricity: "elec",
  fuel: "fuel",
  auxiliary: "aux",
};

export const TYPE_LABEL = {
  electricity: "电力",
  fuel: "燃料",
  auxiliary: "辅料",
};
