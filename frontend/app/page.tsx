"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api, Appearance, downloadJson, errorText, GroupUpdate, SavedImport, Status, Workspace, WorkspaceSummary } from "@/lib/api";
import { Modal } from "@/components/modal";
import { Jobs } from "@/components/jobs";
import { GroupEditor } from "@/components/group-editor";

type View = "all" | "ungrouped" | "unusable";
const activeStates = ["queued", "running", "paused"];

export default function Home() {
  const [status, setStatus] = useState<Status | null>(null);
  const [workspaces, setWorkspaces] = useState<WorkspaceSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [groupId, setGroupId] = useState<string | null>(null);
  const [view, setView] = useState<View>("all");
  const [selection, setSelection] = useState<Set<string>>(new Set());
  const [targetGroup, setTargetGroup] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [exportOpen, setExportOpen] = useState(false);
  const [clusterOpen, setClusterOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [zoom, setZoom] = useState<Appearance | null>(null);
  const [endpoint, setEndpoint] = useState("http://127.0.0.1:8765");
  const [token, setToken] = useState("");
  const [exportName, setExportName] = useState("");
  const [date, setDate] = useState("");
  const [source, setSource] = useState("");
  const [camera, setCamera] = useState("");
  const [threshold, setThreshold] = useState(0.55);
  const [minSize, setMinSize] = useState(2);
  const [newName, setNewName] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [savedImport, setSavedImport] = useState<SavedImport | null>(null);

  const refreshList = useCallback(async () => {
    const list = await api.workspaces(); setWorkspaces(list); return list;
  }, []);
  const refreshWorkspace = useCallback(async () => {
    if (activeId) { const next = await api.workspace(activeId); setWorkspace(next); }
    await refreshList();
  }, [activeId, refreshList]);

  useEffect(() => {
    let live = true;
    async function initialize() {
      try {
        const nextStatus = await api.session();
        const list = await api.workspaces();
        if (live) { setStatus(nextStatus); setWorkspaces(list); if (list.length) setActiveId(list[0].id); }
      } catch (caught) { if (live) setError(errorText(caught)); }
    }
    void initialize();
    return () => { live = false; };
  }, []);

  useEffect(() => {
    if (!activeId) return;
    let live = true;
    async function load() {
      try { const next = await api.workspace(activeId!); if (live) setWorkspace(next); }
      catch (caught) { if (live) setError(errorText(caught)); }
    }
    void load();
    const interval = setInterval(() => void load(), 2000);
    return () => { live = false; clearInterval(interval); };
  }, [activeId]);

  useEffect(() => {
    const interval = setInterval(() => void api.status().then(setStatus).catch(() => undefined), 10000);
    return () => clearInterval(interval);
  }, []);

  async function act(operation: () => Promise<void>) {
    setBusy(true); setError(null); setNotice(null);
    try { await operation(); }
    catch (caught) { setError(errorText(caught)); }
    finally { setBusy(false); }
  }

  function chooseWorkspace(id: string) {
    setActiveId(id); setWorkspace(null); setGroupId(null); setSelection(new Set()); setView("all"); setSearch(""); setSavedImport(null);
  }
  const group = workspace?.groups.find(item => item.id === groupId);
  const groupedIds = useMemo(() => new Set(workspace?.groups.flatMap(item => item.appearance_ids) ?? []), [workspace?.groups]);
  const visible = useMemo(() => (workspace?.appearances ?? []).filter(appearance => {
    if (group && !group.appearance_ids.includes(appearance.id)) return false;
    if (!group && view === "ungrouped" && groupedIds.has(appearance.id)) return false;
    if (!group && view === "unusable" && appearance.embedding_status !== "unusable") return false;
    return `${appearance.id} ${appearance.camera} ${appearance.source} ${appearance.date} ${appearance.clock}`.toLowerCase().includes(search.toLowerCase());
  }), [workspace?.appearances, group, view, groupedIds, search]);
  const reviewedCount = workspace?.groups.filter(item => item.reviewed && item.dirty).length ?? 0;
  const running = workspace?.jobs.some(job => activeStates.includes(job.status)) ?? false;
  const unusableCount = workspace?.appearances.filter(item => item.embedding_status === "unusable").length ?? 0;

  function toggleSelection(id: string) { setSelection(previous => { const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next; }); }
  async function updateGroup(body: GroupUpdate) {
    if (!workspace || !group) return;
    await act(async () => { await api.updateGroup(workspace.id, group.id, body); await refreshWorkspace(); setNotice(body.reviewed ? "Group approved locally. Prepare an import when your review is ready." : "Group changes saved. Review it again before import."); });
  }

  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to review workspace</a>
    <aside className="sidebar">
      <Link className="brand" href="/" aria-label="Cluster Grouper home"><span className="brand-mark" aria-hidden="true"><i/><i/><i/><i/></span><span>cluster<br/><b>grouper.</b></span></Link>
      <div className="sidebar-kicker">A FOOTAGE REVIEW COMPANION</div>
      <button className="connection" onClick={() => setConnectOpen(true)}><span className={`status-dot ${status?.connected ? "online" : ""}`}/><span>{status?.connected ? "Footage Review connected" : "Connect Footage Review"}<small>{status?.connected ? "Local connection · API v1" : "Your library stays on this Mac"}</small></span><span aria-hidden="true">↗</span></button>
      <div className="sidebar-heading"><h2>WORKSPACES</h2><button className="icon-button" aria-label="Export a new workspace" title="Export a new workspace" onClick={() => status?.connected ? setExportOpen(true) : setConnectOpen(true)}>+</button></div>
      <nav className="workspace-list" aria-label="Workspaces">{workspaces.map(item => <button key={item.id} className={activeId === item.id ? "active" : ""} onClick={() => chooseWorkspace(item.id)}><span className="folder-icon" aria-hidden="true">▤</span><span>{item.name}<small>{(workspace?.id === item.id ? workspace.appearances.length : item.appearance_count).toLocaleString()} appearances · rev {item.base_revision}</small></span></button>)}{workspaces.length === 0 && <p className="sidebar-empty">Your exports and review progress will appear here.</p>}</nav>
      {workspace && <><div className="sidebar-heading group-heading"><h2>GROUPS</h2><span>{workspace.groups.length}</span></div><nav className="group-list" aria-label="Review groups"><button className={!groupId ? "active all-groups" : "all-groups"} onClick={() => { setGroupId(null); setSelection(new Set()); }}><span>▦</span> All appearances<span>{workspace.appearances.length}</span></button>{workspace.groups.map(item => <button className={groupId === item.id ? "active" : ""} key={item.id} onClick={() => { setGroupId(item.id); setSelection(new Set()); }}><span className={`group-dot ${item.reviewed ? "reviewed" : ""}`}/><span className="group-label">{item.name}<small>{item.reviewed ? "Reviewed" : item.origin === "suggested" ? "Suggested" : "Needs review"}</small></span><span>{item.appearance_ids.length}</span></button>)}</nav></>}
      <div className="sidebar-footer"><span className="local-icon" aria-hidden="true">⌁</span><div>Local by design.<small>Face processing happens on this Mac.</small></div></div>
    </aside>

    <div className="main-shell">
      <header className="topbar"><div><span className="breadcrumb">YOUR REVIEW DESK</span><span className="topbar-separator">/</span><span>{workspace?.name ?? "Getting started"}</span></div><div className="topbar-actions"><span className="local-badge"><span/> ON THIS MAC</span>{workspace && <button className="secondary small" onClick={() => status?.connected ? setExportOpen(true) : setConnectOpen(true)}>+ New export</button>}</div></header>
      <div className="messages" aria-live="polite">{error && <div className="message error" role="alert"><div><strong>Action needs attention</strong><p>{error}</p></div><button aria-label="Dismiss error" className="icon-button" onClick={() => setError(null)}>×</button></div>}{notice && <div className="message success"><p>{notice}</p><button aria-label="Dismiss notice" className="icon-button" onClick={() => setNotice(null)}>×</button></div>}</div>
      <main id="main-content">
        {!activeId ? <div className="welcome">
          <div className="welcome-copy"><div className="eyebrow"><span/> LESS SORTING. MORE SEEING.</div><h1>Find the familiar.<br/><em>You make the call.</em></h1><p>Bring your detected appearances together. Find similar faces, review the details, and send considered groups back to Footage Review.</p><button className="primary large" disabled={busy || !status} onClick={() => status?.connected ? setExportOpen(true) : setConnectOpen(true)}>{status ? status.connected ? "Export your first workspace" : "Connect your library" : "Starting local workspace…"}<span aria-hidden="true">↗</span></button><span className="welcome-caption">Local face processing · Human-reviewed groups</span></div>
          <div className="welcome-art" aria-hidden="true"><div className="art-label">THE REVIEW PROCESS</div><div className="film-frame frame-one"><span>01 / COLLECT</span><div className="abstract-crop"><i/><i/><i/><i/></div><p>Every appearance.<br/>Its original context.</p></div><div className="film-frame frame-two"><span>02 / COMPARE</span><div className="compare-art"><i/><i/></div><p>Similarity opens<br/>the conversation.</p></div><div className="film-frame frame-three"><span>03 / REVIEW</span><div className="art-check">✓</div><p>Your judgment<br/>makes the group.</p></div><div className="art-footnote">A WORKSPACE FOR CAREFUL LOOKING.</div></div>
          <div className="workflow-guide"><article><span>01</span><div><h2>Bring in appearances</h2><p>Connect to the API in Footage Review, then export the dates and cameras you need.</p></div></article><article><span>02</span><div><h2>Find & review similarities</h2><p>Run local clustering. Inspect crops, adjust membership, name groups, and approve.</p></div></article><article><span>03</span><div><h2>Return reviewed groups</h2><p>Preview the saved import and submit it. Original IDs keep everything connected.</p></div></article></div>
        </div> : !workspace ? <output className="loading-state">Opening your review workspace…</output> : <>
          <section className="workspace-heading"><div><div className="eyebrow">{workspace.export_complete ? "READY FOR YOUR EYE" : "COLLECTING APPEARANCES"} <span className="revision">REV {workspace.base_revision}</span></div><h1>{group?.name ?? workspace.name}</h1><p>{workspace.appearances.length.toLocaleString()} exported appearances <span>·</span> {workspace.groups.length} groups <span>·</span> {reviewedCount} reviewed changes</p></div><div className="workspace-heading-actions"><button className="secondary" disabled={busy || running || !workspace.export_complete || workspace.appearances.length === 0} onClick={() => setClusterOpen(true)}><span aria-hidden="true">✳</span> Find similar faces</button><button className="primary" disabled={busy || (!reviewedCount && !workspace.imports.length)} onClick={() => { setSavedImport(null); setImportOpen(true); }}>Prepare import <span>{reviewedCount}</span></button></div></section>
          <Jobs jobs={workspace.jobs} busy={busy} onControl={(id, action) => void act(async () => { await api.control(id, action); await refreshWorkspace(); })}/>
          {!workspace.export_complete && !running && <div className="message warning"><p>This export is incomplete. Start a fresh export if its snapshot expired; partial data cannot be imported.</p><button className="secondary small" onClick={() => status?.connected ? setExportOpen(true) : setConnectOpen(true)}>New export</button></div>}
          <div className={`review-layout ${group ? "with-inspector" : ""}`}>
            <section className="contact-sheet" aria-label="Appearance review">
              <div className="sheet-toolbar"><div className="view-tabs" aria-label="Appearance filters">{([["all", "All appearances"], ["ungrouped", "Ungrouped"], ["unusable", `Unusable (${unusableCount})`]] as const).map(([id, label]) => <button key={id} className={!group && view === id ? "active" : ""} aria-pressed={!group && view === id} onClick={() => { setView(id); setGroupId(null); setSelection(new Set()); }}>{label}</button>)}</div><label className="search"><span aria-hidden="true">⌕</span><input type="search" aria-label="Search appearances" placeholder="Camera, date, or ID…" value={search} onChange={event => setSearch(event.target.value)}/></label></div>
              <div className="sheet-caption"><span>{visible.length} appearance{visible.length === 1 ? "" : "s"}{group ? " in this export" : " shown"}</span><button className="text-button" disabled={visible.length === 0} onClick={() => setSelection(selection.size ? new Set() : new Set(visible.map(item => item.id)))}>{selection.size ? "Clear selection" : "Select shown"}</button></div>
              {selection.size > 0 && <div className="selection-bar"><strong>{selection.size} selected</strong><button className="secondary small" disabled={busy || !workspace.export_complete} onClick={() => setCreateOpen(true)}>+ New group</button><label className="sr-only" htmlFor="add-to-group">Add selected appearances to group</label><select id="add-to-group" value={targetGroup} onChange={event => setTargetGroup(event.target.value)}><option value="">Choose group…</option>{workspace.groups.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button className="primary small" disabled={busy || !targetGroup || !workspace.export_complete} onClick={() => void act(async () => { const target = workspace.groups.find(item => item.id === targetGroup); if (!target) return; await api.updateGroup(workspace.id, target.id, { appearance_ids: [...new Set([...target.appearance_ids, ...selection])], reviewed: false }); setSelection(new Set()); await refreshWorkspace(); setNotice("Appearances added. Review the updated group before importing."); })}>Add to group</button></div>}
              {visible.length ? <div className="crop-grid">{visible.map((appearance, index) => <article className={`crop-card ${selection.has(appearance.id) ? "selected" : ""}`} key={appearance.id} style={{ animationDelay: `${Math.min(index, 16) * 15}ms` }}>
                <div className="crop-image"><button className="crop-open" aria-label={`Inspect appearance ${appearance.id}`} onClick={() => setZoom(appearance)}><img src={appearance.image_url} alt={`Detected appearance from ${appearance.camera || "unknown camera"}`} loading="lazy" decoding="async" width={240} height={260}/></button><label className="crop-select"><input type="checkbox" checked={selection.has(appearance.id)} onChange={() => toggleSelection(appearance.id)} aria-label={`Select appearance ${appearance.id}`}/><span/></label><span className="crop-offset">+{appearance.seconds.toFixed(1)}s</span>{appearance.embedding_status === "unusable" && <span className="unusable-badge" title={appearance.embedding_error ?? "Crop cannot be embedded"}>Unusable</span>}</div>
                <div className="crop-meta"><strong>{appearance.camera || "Unknown camera"}</strong><span>{appearance.date || "Date unknown"} <i>·</i> {appearance.clock || "Time unknown"}</span><div><span>{appearance.source || "Unknown source"}</span><span title="Detection confidence, not identity confidence">Detection {Math.round(appearance.confidence * 100)}%</span></div></div>
              </article>)}</div> : <div className="empty-sheet"><span aria-hidden="true">▧</span><h2>{search ? "No appearances match" : view === "unusable" ? "No unusable crops" : group ? "No exported crops in this group" : "Nothing here yet"}</h2><p>{search ? "Try another camera, date, or appearance ID." : group ? "Membership outside this export is preserved. Select appearances from the full view to add them." : "Exported appearances will appear here as your job progresses."}</p></div>}
              <div className="sheet-footer"><span>APPEARANCES, NOT UNIQUE PEOPLE</span><p>Dates and times come from clip metadata. Detection confidence describes the detector.</p></div>
            </section>
            {group && <GroupEditor key={group.id} group={group} appearances={workspace.appearances} busy={busy} onSave={updateGroup} onRemove={id => void updateGroup({ appearance_ids: group.appearance_ids.filter(member => member !== id), reviewed: false })} onDiscard={() => void act(async () => { await api.discardGroup(workspace.id, group.id); setGroupId(null); await refreshWorkspace(); })}/>}
          </div>
          {workspace.imports.length > 0 && <section className="import-history"><h2>Saved imports</h2><div>{workspace.imports.map(item => <button key={item.id} className="import-record" onClick={() => { setSavedImport(item); setImportOpen(true); }}><span className={`import-status ${item.status}`}>{item.status}</span><code>{item.id.slice(0, 8)}…</code><span>{new Date(item.created_at).toLocaleString()}</span><span aria-hidden="true">↗</span></button>)}</div></section>}
        </>}
      </main>
    </div>

    {connectOpen && <Modal error={error} title={status?.connected ? "Library connection" : "Connect Footage Review"} onClose={() => { setConnectOpen(false); setToken(""); }}><p className="modal-intro">In Footage Review, open <strong>Integrations</strong>, start the API, then copy its endpoint and current access token. Keep Footage Review open.</p><div className="note-box">This app connects through its local server. You can leave Footage Review’s Browser origin blank.</div><form onSubmit={event => { event.preventDefault(); void act(async () => { const next = await api.connect(endpoint.trim(), token); setStatus(next); setToken(""); setConnectOpen(false); await refreshList(); setNotice("Connected to Footage Review. Export a workspace to begin."); }); }}><label htmlFor="endpoint">Local API endpoint</label><input id="endpoint" type="url" value={endpoint} onChange={event => setEndpoint(event.target.value)} required spellCheck={false}/><label htmlFor="token">Access token</label><input id="token" type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} required placeholder="Paste the active token"/><p className="footnote">Token stays in server memory. Restarting Footage Review’s API creates a fresh token; reconnect with it.</p><div className="modal-actions">{status?.connected && <button className="text-button danger" type="button" disabled={busy} onClick={() => void act(async () => { await api.disconnect(); setStatus(await api.status()); setConnectOpen(false); setNotice("Disconnected. Your local review work remains available."); })}>Disconnect</button>}<button className="primary" disabled={busy || !token}>{busy ? "Connecting…" : status?.connected ? "Reconnect" : "Connect library"}</button></div></form></Modal>}
    {exportOpen && <Modal error={error} title="Export a review workspace" onClose={() => setExportOpen(false)}><p className="modal-intro">Bring in detected appearances and the complete current group state. Filters match Footage Review metadata exactly.</p><form onSubmit={event => { event.preventDefault(); void act(async () => { const next = await api.export({ name: exportName.trim(), ...(date ? { date } : {}), ...(source.trim() ? { source: source.trim() } : {}), ...(camera.trim() ? { camera: camera.trim() } : {}) }); chooseWorkspace(next.workspace_id); setExportOpen(false); setExportName(""); await refreshList(); }); }}><label htmlFor="export-name">Workspace name</label><input id="export-name" required maxLength={120} placeholder="e.g. Frontdoor · May review" value={exportName} onChange={event => setExportName(event.target.value)}/><div className="form-columns"><div><label htmlFor="date">Date <span className="optional">optional</span></label><input id="date" type="date" value={date} onChange={event => setDate(event.target.value)}/></div><div><label htmlFor="source">Source <span className="optional">optional</span></label><input id="source" placeholder="e.g. Blink" value={source} onChange={event => setSource(event.target.value)}/></div></div><label htmlFor="camera">Camera <span className="optional">optional</span></label><input id="camera" placeholder="Exact displayed camera name" value={camera} onChange={event => setCamera(event.target.value)}/><div className="note-box">Original appearance and group IDs are preserved. Existing memberships outside these filters stay intact.</div><div className="modal-actions"><button type="button" className="secondary" onClick={() => setExportOpen(false)}>Cancel</button><button className="primary" disabled={busy || !exportName.trim() || !status?.connected}>{busy ? "Starting export…" : "Export appearances"}</button></div></form></Modal>}
    {clusterOpen && workspace && <Modal error={error} title="Find similar faces" onClose={() => setClusterOpen(false)}><p className="modal-intro">Compare ungrouped appearances locally and suggest groups for your review. Every pair in a suggested group must meet your similarity threshold.</p><div className={`model-status ${status?.models_ready ? "ready" : ""}`}><strong>{status?.models_ready ? "Local models ready" : "Models need setup"}</strong><p>{status?.model_message || "Checking local model files…"}</p>{!status?.models_ready && <code>make models</code>}</div><form onSubmit={event => { event.preventDefault(); void act(async () => { await api.cluster(workspace.id, threshold, minSize); setClusterOpen(false); await refreshWorkspace(); }); }}><label htmlFor="threshold">Minimum cosine similarity <strong className="range-value">{threshold.toFixed(2)}</strong></label><input id="threshold" type="range" min="0.1" max="0.99" step="0.01" value={threshold} onChange={event => setThreshold(Number(event.target.value))}/><div className="range-labels"><span>More suggestions</span><span>Stricter matches</span></div><label htmlFor="min-size">Minimum appearances per suggestion</label><input id="min-size" type="number" min={2} max={100} required value={minSize} onChange={event => setMinSize(Number(event.target.value))}/><p className="footnote">Similarity is a comparison score, not an identity probability. Existing, manual, and reviewed groups are excluded. Running again replaces all unapproved suggestions, including local edits to them; approve work you want to preserve first. Unusable crops remain available for manual review.</p><div className="modal-actions"><button className="secondary" type="button" onClick={() => setClusterOpen(false)}>Cancel</button><button className="primary" disabled={busy || !status?.models_ready || running}>Find suggestions</button></div></form></Modal>}
    {createOpen && workspace && <Modal error={error} title="Create a review group" onClose={() => setCreateOpen(false)}><p className="modal-intro">Start a local group with your {selection.size} selected appearance{selection.size === 1 ? "" : "s"}. You can refine its membership before approving.</p><form onSubmit={event => { event.preventDefault(); void act(async () => { const next = await api.createGroup(workspace.id, { name: newName.trim(), note: "", appearance_ids: [...selection], reviewed: false }); setGroupId(next.id); setSelection(new Set()); setNewName(""); setCreateOpen(false); await refreshWorkspace(); }); }}><label htmlFor="new-name">Group name</label><input id="new-name" required maxLength={120} value={newName} onChange={event => setNewName(event.target.value)} placeholder="Give this group a useful name"/><div className="modal-actions"><button className="secondary" type="button" onClick={() => setCreateOpen(false)}>Cancel</button><button className="primary" disabled={busy || !newName.trim()}>Create group</button></div></form></Modal>}
    {importOpen && workspace && <Modal error={error} title={savedImport ? "Review saved import" : "Prepare reviewed groups"} wide onClose={() => setImportOpen(false)}>{!savedImport ? <><p className="modal-intro">Prepare an immutable request containing only reviewed groups with local changes. Nothing is sent to Footage Review yet.</p><div className="import-summary"><span><b>{reviewedCount}</b> reviewed groups</span><span><b>{workspace.base_revision}</b> base revision</span></div>{workspace.groups.some(item => item.dirty && !item.reviewed) && <div className="note-box">Unreviewed changes are excluded from this import.</div>}<form onSubmit={event => { event.preventDefault(); void act(async () => { setSavedImport(await api.prepareImport(workspace.id, reviewer.trim())); await refreshWorkspace(); }); }}><label htmlFor="reviewer">Reviewer name <span className="optional">optional</span></label><input id="reviewer" maxLength={200} value={reviewer} onChange={event => setReviewer(event.target.value)}/><div className="modal-actions"><button className="secondary" type="button" onClick={() => setImportOpen(false)}>Back to review</button><button className="primary" disabled={busy || !reviewedCount || !status?.connected}>Save import for review</button></div>{!status?.connected && <p className="inline-error">Connect to the same Footage Review library to prepare an import.</p>}</form></> : <><div className="saved-import-heading"><span className={`import-status ${savedImport.status}`}>{savedImport.status}</span><code>{savedImport.id}</code></div><p className="modal-intro">Each supplied group replaces its complete membership. Groups absent from this request are preserved. Inspect the original IDs and names before submitting.</p><pre className="payload" tabIndex={0} aria-label="Saved import payload">{JSON.stringify(savedImport.payload, null, 2)}</pre>{savedImport.error && <div className="message error"><p>{savedImport.error}{savedImport.status === "rejected" && " Keep this request for reference. Reconcile against a fresh export; do not change its base revision to bypass a conflict."}</p></div>}{savedImport.response && <div className="message success"><p>Footage Review accepted this import. {savedImport.response.replayed === true && "This was a safe replay of an earlier import. "}Open its Groups sidebar and inspect the source clips.</p></div>}{savedImport.status === "uncertain" && <div className="note-box">The save outcome is uncertain. Retry this unchanged saved request with its original import ID.</div>}<div className="modal-actions"><button className="secondary" onClick={() => downloadJson(savedImport.payload, `reviewed-groups-${savedImport.id}.json`)}>Download JSON</button><button className="primary" disabled={busy || !status?.connected || savedImport.status === "submitted" || savedImport.status === "rejected"} onClick={() => void act(async () => { const next = await api.submitImport(workspace.id, savedImport.id); setSavedImport(next); await refreshWorkspace(); setStatus(await api.status()); })}>{busy ? "Submitting…" : savedImport.status === "uncertain" ? "Retry saved request" : savedImport.status === "submitted" ? "Imported successfully" : savedImport.status === "rejected" ? "Reconciliation required" : "Submit to Footage Review"}</button></div></>}</Modal>}
    {zoom && <Modal error={error} title="Appearance details" onClose={() => setZoom(null)}><div className="zoom-image"><img src={zoom.image_url} alt={`Detected appearance from ${zoom.camera || "unknown camera"}`} width={400} height={400}/></div><dl className="appearance-details"><dt>Appearance ID</dt><dd><code>{zoom.id}</code></dd><dt>Clip ID</dt><dd><code>{zoom.clip_id}</code></dd><dt>Source / camera</dt><dd>{zoom.source || "Unknown"} / {zoom.camera || "Unknown"}</dd><dt>Metadata date & time</dt><dd>{zoom.date || "Unknown"} {zoom.clock}</dd><dt>Clip offset</dt><dd>+{zoom.seconds.toFixed(2)} seconds</dd><dt>Detector confidence</dt><dd>{(zoom.confidence * 100).toFixed(1)}%</dd><dt>Face embedding</dt><dd>{zoom.embedding_status}{zoom.embedding_error && ` — ${zoom.embedding_error}`}</dd></dl><p className="footnote">Detector confidence is not confidence in a person’s identity. Check the source clip in Footage Review for more context.</p></Modal>}
  </div>;
}
