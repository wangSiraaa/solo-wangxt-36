import { useState } from "react";
import { kg } from "./ui.jsx";

/** 贡献树：合计 → 活动类型 → 具体活动；未核算项以虚线节点单列，不计入总量。 */
export default function ContributionTree({ tree }) {
  if (!tree) return null;
  return (
    <div className="tree">
      <TreeNode node={tree} root />
    </div>
  );
}

function TreeNode({ node, root = false }) {
  const hasChildren = node.children && node.children.length > 0;
  const [open, setOpen] = useState(true);
  const unaccounted = node.code === "unaccounted";

  return (
    <div className={root ? "tree-root-wrap" : "tree-node-wrap"}>
      <div
        className={`tree-node ${root ? "tree-node-root" : ""} ${
          unaccounted ? "tree-node-unaccounted" : ""
        }`}
      >
        {hasChildren ? (
          <button
            className="tree-toggle"
            onClick={() => setOpen((v) => !v)}
            title={open ? "收起" : "展开"}
          >
            {open ? "▾" : "▸"}
          </button>
        ) : (
          <span className="tree-toggle tree-toggle-leaf" />
        )}
        <span className="tree-name" title={node.formula}>
          {node.name}
        </span>
        {node.factor && <span className="tree-factor">{node.factor}</span>}
        {node.share_pct !== null && node.share_pct !== undefined && (
          <span className="tree-share">{Number(node.share_pct).toFixed(1)}%</span>
        )}
        {node.emissions_kg !== null && node.emissions_kg !== undefined ? (
          <span className="tree-amount">{kg(node.emissions_kg)}</span>
        ) : (
          <span className="tree-amount tree-amount-na">未计入总量</span>
        )}
      </div>
      {node.formula && <div className="tree-formula">{node.formula}</div>}
      {hasChildren && open && (
        <div className="tree-children">
          {node.children.map((child, i) => (
            <TreeNode key={i} node={child} />
          ))}
        </div>
      )}
    </div>
  );
}
