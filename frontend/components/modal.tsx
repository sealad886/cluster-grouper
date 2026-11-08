"use client";

import { useEffect, useRef } from "react";

export function Modal({ title, onClose, children, wide = false, error }: { title: string; onClose: () => void; children: React.ReactNode; wide?: boolean; error?: string | null }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  return <dialog ref={dialog} className={`modal ${wide ? "wide" : ""}`} aria-labelledby="modal-title" onCancel={onClose}>
    <div className="modal-heading"><h2 id="modal-title">{title}</h2><button type="button" className="icon-button" aria-label="Close dialog" onClick={onClose}>×</button></div>
    {error && <div className="message error" role="alert"><p>{error}</p></div>}
    {children}
  </dialog>;
}
