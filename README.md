# 产品碳足迹核算工作台（PCF Workbench）

面向制造企业产品经理的**可追溯**产品碳足迹（PCF）核算工作台：对比同一产品在不同
生产方案下的碳排差异，每条结果都能追溯到「活动量 × 哪个排放因子」。

- **前端**：React + Vite —— 活动数据管理、贡献树、结果追溯
- **后端**：Django + Django REST Framework —— 计算引擎与 API
- **数据库**：PostgreSQL（本地无 PG 时自动回退 SQLite）

> ⚠️ **数据声明**：仓库内置的所有排放因子均为 **Acme 虚构示例数据**，
> 仅用于演示软件功能。**不接入任何付费数据库，未经过任何机构认证**，
> 严禁用于真实碳核算、合规申报或对外披露。

## 首版范围与硬性规则

**系统边界（门到门）**：原材料入厂 → 产品出厂。活动类型仅支持：

- 电力（electricity）
- 燃料（fuel）
- 辅料（auxiliary）

核算规则：

1. **可追溯**：每条结果行保存原始活动量、单位、换算倍数、基准单位量、
   因子编码/版本/地区/值、计算式、排放量。
2. **单位不相容 → 拒绝计算**：活动单位量纲（能量/质量/体积/件数）必须与
   因子分母量纲一致，跨量纲折算一律 HTTP 400，不给结果。
3. **因子过期/未生效 → 拒绝计算**：以情景「核算基准日」判断因子有效期。
4. **缺失因子 → 列为未核算项**：活动保留、单列展示，报告 `is_complete=false`，
   合计明确标注为「部分总量」，**绝不悄悄排除后给出完整总量**。
5. **复制情景调整**：已确认情景冻结不可改；复制为新草稿后调整活动，两方案可对比。
6. **确认报告保留原始因子**：确认时把每行因子值与版本写入快照表，因子库改版
   （如电力因子 v2 过期、v3 生效）不影响历史报告。
7. **防重复导入**：批量导入按 `external_ref`（外部单据号）去重，重复单据跳过
   而非累加，避免总量翻倍；量纲错误等导致整批拒绝，不产生部分导入。

## 快速开始

### docker compose（使用 PostgreSQL）

```bash
docker compose up --build
# 前端 http://localhost:5173  后端 http://localhost:8000/api/
```

启动时自动 migrate 并写入虚构演示数据。

### 本地开发（SQLite）

```bash
# 后端
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo          # 写入虚构因子与演示方案
python manage.py runserver 8000

# 前端（另开终端）
cd frontend
npm install
npm run dev                         # http://localhost:5173 ，/api 代理到 8000
```

连接 PostgreSQL：设置环境变量 `PCF_DB=postgres` 及
`POSTGRES_DB/USER/PASSWORD/HOST/PORT`。

## 演示数据（均为虚构）

- 单位：kWh / MWh（×1000）/ MJ（×0.2778）、kg / t、L / m³、pc
- 因子（`Acme 演示因子库（虚构）`）：
  - `EL-CN-GRID` v1（2019–2023，0.5810）、v2（2024–2025，0.5360）、
    v3（2026 起，0.5080）kgCO₂e/kWh
  - `EL-CN-EAST` v1（华东电网，0.5100）
  - `FU-DIESEL`（2.6800 kgCO₂e/L，体积量纲）、`FU-COAL`（质量量纲）
  - `AUX-LUBE`、`AUX-CUTFLUID`（辅料，质量量纲）
  - 故意**不提供**工业清洗剂因子，用于演示未核算项
- 情景：
  1. **A型减速箱-基线方案**：5 条活动，含 1 条缺因子 → 部分总量 8,156 kg
  2. **A型减速箱-节能改造方案**：电量下降、改用华东因子 → 6,705 kg
  3. **演示-因子已过期**：显式钉在 v1，核算时被拒绝
  4. **演示-单位不相容**：柴油以 kg 记账但因子分母为体积，被拒绝
  5. **2025 年历史确认报告**：确认时冻结 v2（现已过期），报告仍保留 0.5360

## 手工验证清单（UI 路径）

1. **kWh/MWh 换算**：打开基线方案试算，热处理 2.4 MWh 与 12,000 kWh
   在电力节点同口径相加。
2. **缺失因子不被吞掉**：结果头部为橙色「部分总量」，工业清洗剂出现在
   「未核算项」表与贡献树虚线节点中。
3. **因子过期**：打开「演示-因子已过期」点试算 → 400 错误条。
4. **单位不相容**：打开「演示-单位不相容」点试算 → 400 错误条。
5. **复制与对比**：复制基线方案，调小用电量后重新核算，两方案合计可对比。
6. **确认保留原始因子**：报告页确认后，因子库中 v2 已显示「已过期」，
   报告详情仍显示 v2 / 0.5360。
7. **重复导入**：在批量导入框对同一 `external_ref` 二次导入，提示「跳过重复」，
   总量不变。

## 主要 API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/scenarios/` `/api/scenarios/{id}/` | 方案列表 / 详情（含活动） |
| POST | `/api/scenarios/` | 新建方案 |
| POST | `/api/scenarios/{id}/copy/` | 复制方案（深拷贝活动） |
| POST | `/api/scenarios/{id}/calculate/` | 试算，返回贡献树+追溯行+未核算项 |
| POST | `/api/scenarios/{id}/import-activities/` | CSV/JSON 批量导入（去重、校验） |
| GET/POST/PATCH/DELETE | `/api/activities/` | 活动增删改（已确认情景拒绝写入） |
| GET | `/api/reports/` `/api/reports/{id}/` | 报告列表 / 详情（快照） |
| POST | `/api/reports/{id}/confirm/` | 确认报告并冻结情景 |
| GET | `/api/factors/` `/api/units/` `/api/regions/` | 因子版本 / 单位 / 地区 |

导入载荷：`{"rows":[{...}]}` 或 `{"csv":"external_ref,activity_type,name,amount,unit_code,factor_code\n..."}`。
因子可省略（未核算），也可用编码 `factor_code` 解析为基准日最新有效版本。

## 测试

```bash
cd backend && python manage.py test
```

覆盖：kWh↔MWh 换算与总量、缺因子部分总量、过期拒绝、量纲拒绝、
编码解析最新版本、确认快照冻结、复制情景、重复导入跳过、导入整批拒绝。
