import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function lint(source) {
  const directory = mkdtempSync(join(tmpdir(), "cluster-grouper-lint-probe-"));
  try {
    const target = join(directory, "probe.tsx");
    writeFileSync(target, source);
    const result = spawnSync(
      process.execPath,
      [join(frontend, "node_modules/oxlint/bin/oxlint"), "--config", join(frontend, ".oxlintrc.json"), "--deny-warnings", "--format=json", target],
      { cwd: frontend, encoding: "utf8", timeout: 30000 },
    );
    assert.ifError(result.error);
    return { status: result.status, output: `${result.stdout}\n${result.stderr}` };
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
}

const invalidCases = [
  ["conditional React hooks", "react/rules-of-hooks", `import { useState } from "react";
export function Example({ enabled }: { enabled: boolean }) {
  if (enabled) useState(0);
  return null;
}`],
  ["missing effect dependencies", "react/exhaustive-deps", `import { useEffect } from "react";
export function Example({ message }: { message: string }) {
  useEffect(() => { console.log(message); }, []);
  return null;
}`],
  ["missing image alternatives", "jsx-a11y/alt-text", `export function Example() { return <img src="/crop.jpg" />; }`],
  ["async client components", "nextjs/no-async-client-component", `"use client";
export default async function Example() { return <p>Client component</p>; }`],
  ["synchronous scripts", "nextjs/no-sync-scripts", `export function Example() { return <script src="/blocking.js" />; }`],
  ["unrestricted TypeScript any", "typescript/no-explicit-any", `export function example(value: any) { return value; }`],
  ["unused TypeScript values", "no-unused-vars", `export function example() { const unused = 123; return null; }`],
];

for (const [requirement, rule, source] of invalidCases) {
  test(`lint rejects ${requirement}`, () => {
    const result = lint(source);
    assert.notEqual(result.status, 0, result.output);
    assert.ok(result.output.includes(rule.split("/").at(-1)), result.output);
  });
}

test("review crops may use ordinary images with accessible alternatives", () => {
  const result = lint(`export function Example() { return <img src="/crop.jpg" alt="Detected appearance" />; }`);
  assert.equal(result.status, 0, result.output);
});
