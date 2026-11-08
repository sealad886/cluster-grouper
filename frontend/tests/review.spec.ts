import { expect, test, type Page } from "@playwright/test";
import type { Group, SavedImport, Workspace } from "../lib/api";

const groupId = "11111111-1111-4111-8111-111111111111";
const importId = "22222222-2222-4222-8222-222222222222";

async function fixture(page: Page, offline = false, uncertainFirst = false) {
  let connected = false;
  let exported = offline;
  let submits = 0;
  let lastPatch: Record<string, unknown> | null = null;
  const workspace: Workspace = {
    id: "review-one", name: "Frontdoor review", library_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", base_revision: 7,
    created_at: "2026-11-08T10:00:00Z", appearance_count: 3, export_complete: true, jobs: [], groups: [], imports: [],
    appearances: ["crop-a", "crop-b", "crop-c"].map((id, index) => ({ id, clip_id: `clip-${index}`, source: "Blink", camera: "Frontdoor", date: "2026-05-25", clock: `08:57:4${index}`, seconds: index + 1, confidence: .98, group_ids: [], image_url: `/api/workspaces/review-one/appearances/${id}/image`, embedding_status: "ready", embedding_error: null })),
  };
  if (offline) workspace.groups.push({ id: groupId, name: "Existing review", note: "Keep prior notes", appearance_ids: ["crop-a", "outside-export"], origin: "existing", reviewed: true, dirty: false, similarity: null });
  const status = () => ({ connected, session_active: true, library_id: connected ? workspace.library_id : null, revision: connected ? 7 : null, models_ready: true, model_message: "Checksums verified" });
  await page.route("**/api/**", async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = request.postDataJSON();
    let result: unknown;
    if (method !== "GET" && !request.headers()["content-type"]?.startsWith("application/json")) return route.fulfill({ status: 415, json: { detail: { code: "content_type", message: "Expected application/json for local mutations." } } });
    if (path.endsWith("/image")) return route.fulfill({ contentType: "image/svg+xml", body: '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="220"><rect width="200" height="220" fill="#c8d0bc"/><rect x="35" y="45" width="130" height="130" fill="#99aa87"/></svg>' });
    if (path === "/api/session" || path === "/api/status") result = status();
    else if (path === "/api/connect") { connected = true; result = status(); }
    else if (path === "/api/workspaces") result = exported ? [workspace] : [];
    else if (path === "/api/exports") { exported = true; workspace.name = body.name; result = { workspace_id: workspace.id, job_id: "export-job" }; }
    else if (path === "/api/workspaces/review-one") result = workspace;
    else if (path === "/api/workspaces/review-one/groups" && method === "POST") { const group: Group = { ...body, id: groupId, origin: "manual", dirty: true, similarity: null }; workspace.groups.push(group); result = group; }
    else if (path === `/api/workspaces/review-one/groups/${groupId}` && method === "PATCH") { lastPatch = body; const group = workspace.groups.find(item => item.id === groupId)!; Object.assign(group, body, { dirty: true }); result = group; }
    else if (path === "/api/workspaces/review-one/imports" && method === "POST") { const saved: SavedImport = { id: importId, status: "prepared", payload: { import_id: importId, library_id: workspace.library_id, base_revision: 7, reviewer: body.reviewer, groups: workspace.groups.filter(item => item.reviewed && item.dirty).map(({ id, name, note, appearance_ids }) => ({ id, name, note, appearance_ids })) }, response: null, error: null, created_at: "2026-11-08T11:00:00Z" }; workspace.imports.push(saved); result = saved; }
    else if (path === `/api/workspaces/review-one/imports/${importId}/submit`) { submits++; const saved = workspace.imports[0]; if (uncertainFirst && submits === 1) { saved.status = "uncertain"; saved.error = "Response lost; the save may have succeeded."; } else { saved.status = "submitted"; saved.error = null; saved.response = { import_id: importId, revision: 8, current_revision: 8, group_ids: [groupId], appearance_count: 2, replayed: submits > 1 }; } result = saved; }
    else return route.fulfill({ status: 404, json: { detail: { code: "unexpected_test_request", message: `${method} ${path}` } } });
    await route.fulfill({ json: result });
  });
  return { workspace, submits: () => submits, lastPatch: () => lastPatch };
}

test("exports, reviews, and explicitly retries the same immutable grouping request", async ({ page }) => {
  const state = await fixture(page, false, true);
  await page.goto("/");
  await page.getByRole("button", { name: "Connect your library" }).click();
  await page.getByLabel("Access token", { exact: true }).fill("synthetic-test-token");
  await page.getByRole("button", { name: "Connect library", exact: true }).click();
  await page.getByRole("button", { name: "Export your first workspace" }).click();
  await page.getByLabel("Workspace name").fill("Frontdoor review");
  await page.getByRole("button", { name: "Export appearances", exact: true }).click();
  await expect(page.getByRole("checkbox")).toHaveCount(3);
  await page.getByRole("checkbox", { name: "Select appearance crop-a", exact: true }).check();
  await page.getByRole("checkbox", { name: "Select appearance crop-b", exact: true }).check();
  await page.getByRole("button", { name: "+ New group", exact: true }).click();
  await page.getByLabel("Group name", { exact: true }).fill("Reviewed frontdoor appearances");
  await page.getByRole("button", { name: "Create group", exact: true }).click();
  await page.getByLabel("Review notes").fill("Checked both appearances.");
  await page.getByRole("button", { name: "Approve group", exact: true }).click();
  await page.getByRole("button", { name: /Prepare import/ }).click();
  await page.getByLabel("Reviewer name").fill("Local reviewer");
  await page.getByRole("button", { name: "Save import for review" }).click();
  await expect(page.getByLabel("Saved import payload")).toContainText('"base_revision": 7');
  await expect(page.getByLabel("Saved import payload")).toContainText('"crop-a"');
  await expect(page.getByLabel("Saved import payload")).toContainText('"crop-b"');
  expect(state.submits()).toBe(0);
  const payloadBefore = structuredClone(state.workspace.imports[0].payload);
  await page.getByRole("button", { name: "Submit to Footage Review", exact: true }).click();
  await expect(page.getByRole("button", { name: "Retry saved request" })).toBeEnabled();
  expect(state.submits()).toBe(1);
  expect(state.workspace.imports[0].payload).toEqual(payloadBefore);
  await page.getByRole("button", { name: "Retry saved request", exact: true }).click();
  await expect(page.getByRole("button", { name: "Imported successfully" })).toBeDisabled();
  expect(state.submits()).toBe(2);
  expect(state.workspace.imports).toHaveLength(1);
  expect(state.workspace.imports[0].payload).toEqual(payloadBefore);
});

test("offline review retains existing membership outside the filtered export", async ({ page }) => {
  const state = await fixture(page, true);
  await page.goto("/");
  await page.getByRole("button", { name: /Existing review Reviewed/ }).click();
  await expect(page.getByText(/outside this export\. Their membership is preserved/)).toBeVisible();
  await page.getByLabel("Group name", { exact: true }).fill("Renamed existing review");
  await page.getByRole("button", { name: "Save changes", exact: true }).click();
  expect(state.workspace.groups[0].appearance_ids).toEqual(["crop-a", "outside-export"]);
  expect(state.lastPatch()).toMatchObject({ reviewed: false });
  await page.getByRole("button", { name: "Approve group", exact: true }).click();
  await page.getByRole("button", { name: /Prepare import/ }).click();
  await expect(page.getByRole("button", { name: "Save import for review" })).toBeDisabled();
  expect(state.submits()).toBe(0);
});

test("completed and cancelled jobs retain their latest outcome without an active progress bar", async ({ page }) => {
  const state = await fixture(page, true);
  state.workspace.jobs = [
    { id: "export-first", workspace_id: "review-one", kind: "export", status: "completed", phase: "Export complete", completed: 3, total: 3, error: null },
    { id: "cluster-first", workspace_id: "review-one", kind: "cluster", status: "completed", phase: "Created 0 groups for review", completed: 3, total: 3, error: null },
    { id: "cluster-second", workspace_id: "review-one", kind: "cluster", status: "cancelled", phase: "Cancelled by operator", completed: 1, total: 3, error: null },
  ];
  await page.goto("/");
  await expect(page.getByRole("region", { name: "export job" })).toContainText("Export completed");
  await expect(page.getByRole("region", { name: "cluster job" })).toContainText("Clustering cancelled");
  await expect(page.getByRole("region", { name: "cluster job" })).toHaveCount(1);
  await expect(page.getByRole("progressbar")).toHaveCount(0);
});
