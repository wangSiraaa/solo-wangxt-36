async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const msg =
      data && data.non_field_errors
        ? data.non_field_errors.join("；")
        : data && data.detail
        ? data.detail
        : `请求失败（${res.status}）`;
    const err = new Error(msg);
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  listScenarios: () => request("/scenarios/"),
  getScenario: (id) => request(`/scenarios/${id}/`),
  createScenario: (body) =>
    request("/scenarios/", { method: "POST", body: JSON.stringify(body) }),
  copyScenario: (id) =>
    request(`/scenarios/${id}/copy/`, { method: "POST" }),
  calculate: (id) =>
    request(`/scenarios/${id}/calculate/`, { method: "POST" }),
  importActivities: (id, payload) =>
    request(`/scenarios/${id}/import-activities/`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  createActivity: (body) =>
    request("/activities/", { method: "POST", body: JSON.stringify(body) }),
  updateActivity: (id, body) =>
    request(`/activities/${id}/`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteActivity: (id) =>
    request(`/activities/${id}/`, { method: "DELETE" }),
  listReports: () => request("/reports/"),
  getReport: (id) => request(`/reports/${id}/`),
  confirmReport: (id) =>
    request(`/reports/${id}/confirm/`, { method: "POST" }),
  listFactors: () => request("/factors/"),
  listUnits: () => request("/units/"),
  listRegions: () => request("/regions/"),
};
