"use client";

import { useState } from "react";
import { Appearance, Group, GroupUpdate } from "@/lib/api";

export function GroupEditor({ group, appearances, busy, onSave, onRemove, onDiscard }: { group: Group; appearances: Appearance[]; busy: boolean; onSave: (body: GroupUpdate) => Promise<void>; onRemove: (id: string) => void; onDiscard: () => void }) {
  const [name, setName] = useState(group.name);
  const [note, setNote] = useState(group.note);
  const visible = appearances.filter(appearance => group.appearance_ids.includes(appearance.id));
  const offFilter = group.appearance_ids.length - visible.length;
  const unsaved = name !== group.name || note !== group.note;
  return <aside className="inspector" aria-label="Group review">
    <div className="section-eyebrow">GROUP REVIEW <span>{group.origin}</span></div>
    <h2>Look closely.<br/>Make the call.</h2>
    <p className="muted">Similarity suggests a starting point. Review each crop before approving this group.</p>
    <div className={`review-state ${group.reviewed && !unsaved ? "approved" : ""}`}>{group.reviewed && !unsaved ? "✓ Reviewed" : "○ Needs human review"}{group.dirty && <span>Local changes</span>}</div>
    {group.similarity !== null && <div className="similarity"><span>Minimum pair similarity</span><strong>{group.similarity.toFixed(3)}</strong></div>}
    <form onSubmit={async event => { event.preventDefault(); await onSave({ name: name.trim(), note, reviewed: false }); }}>
      <label htmlFor="group-name">Group name</label><input id="group-name" value={name} onChange={event => setName(event.target.value)} maxLength={120} required/>
      <label htmlFor="group-note">Review notes <span className="optional">optional</span></label><textarea id="group-note" value={note} onChange={event => setNote(event.target.value)} maxLength={4000} rows={4} placeholder="What should the next reviewer know?"/>
      <div className="editor-actions"><button className="secondary" type="submit" disabled={busy || !name.trim() || !unsaved}>Save changes</button><button className="primary" type="button" disabled={busy || !name.trim() || (group.reviewed && !unsaved)} onClick={() => void onSave({ name: name.trim(), note, reviewed: true })}>Approve group</button></div>
    </form>
    <div className="membership-heading"><h3>Membership</h3><span>{group.appearance_ids.length} appearances</span></div>
    {offFilter > 0 && <p className="preserved-note">{offFilter} appearance{offFilter === 1 ? " is" : "s are"} outside this export. Their membership is preserved.</p>}
    <ul className="member-list">{visible.map(appearance => <li key={appearance.id}><img src={appearance.image_url} alt="" loading="lazy" width={42} height={46}/><div><strong>{appearance.camera || "Unknown camera"}</strong><span>{appearance.clock || appearance.id.slice(0, 12)} · +{appearance.seconds.toFixed(1)}s</span></div><button className="icon-button" title="Remove appearance from group" aria-label={`Remove ${appearance.id} from group`} disabled={busy} onClick={() => onRemove(appearance.id)}>×</button></li>)}</ul>
    {group.origin !== "existing" && <button className="danger text-button discard" disabled={busy} onClick={onDiscard}>Discard local group</button>}
    <p className="footnote">Approval stays local until you prepare and submit an import. A crop can belong to several groups.</p>
  </aside>;
}
