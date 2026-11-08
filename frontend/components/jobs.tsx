"use client";

import { Job } from "@/lib/api";

export function Jobs({ jobs, onControl, busy }: { jobs: Job[]; onControl: (id: string, action: "pause" | "resume" | "cancel") => void; busy: boolean }) {
  // The backend returns insertion order. Keep the latest terminal result per kind.
  const latestTerminal = new Map<string, string>();
  for (const job of jobs) if (["completed", "cancelled"].includes(job.status)) latestTerminal.set(job.kind, job.id);
  const displayed = jobs.filter(job => !["completed", "cancelled"].includes(job.status) || latestTerminal.get(job.kind) === job.id);
  return <div className="jobs" aria-label="Processing jobs">{displayed.map(job => <section className={`job ${job.status}`} key={job.id} aria-label={`${job.kind} job`}>
    <div className="job-main"><span className="job-symbol">{job.status === "completed" ? "✓" : job.status === "cancelled" ? "○" : job.kind === "export" ? "↓" : "✳"}</span><div><strong>{job.status === "completed" ? job.kind === "export" ? "Export completed" : "Clustering completed" : job.status === "cancelled" ? job.kind === "export" ? "Export cancelled" : "Clustering cancelled" : job.kind === "export" ? "Exporting appearances" : "Finding similar appearances"}</strong><p>{job.phase} · {job.completed.toLocaleString()} / {job.total.toLocaleString()} · {job.status}</p></div></div>
    <div className="job-actions">{["running", "queued"].includes(job.status) && <button className="small secondary" disabled={busy} onClick={() => onControl(job.id, "pause")}>Pause</button>}{job.status === "paused" && <button className="small secondary" disabled={busy} onClick={() => onControl(job.id, "resume")}>Resume</button>}{["running", "queued", "paused"].includes(job.status) && <button className="small text-button" disabled={busy} onClick={() => onControl(job.id, "cancel")}>Cancel</button>}</div>
    {job.total > 0 && ["queued", "running", "paused"].includes(job.status) && <progress value={job.completed} max={job.total} aria-label={`${job.kind} progress`}/>} {job.error && <p className="inline-error" role="alert">{job.error}</p>}
  </section>)}</div>;
}
