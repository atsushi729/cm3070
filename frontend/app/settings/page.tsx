"use client";

import { useEffect, useState } from "react";
import { api, type SettingsStatus } from "@/lib/api";
import Pill from "@/components/Pill";
import PageShell from "@/components/PageShell";

function StatusRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-3 text-sm last:border-b-0">
      <span className="text-slate-600">{label}</span>
      <Pill tone={ok ? "human" : "muted"}>{ok ? "Enabled" : "Disabled"}</Pill>
    </div>
  );
}

export default function SettingsPage() {
  const [status, setStatus] = useState<SettingsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getSettingsStatus()
      .then(setStatus)
      .catch(() =>
        setError("Could not reach the backend. Is the API running?"),
      );
  }, []);

  return (
    <PageShell
      title="Setting"
      subtitle="Read-only integration status. On an on-premise, single-tenant deployment, secrets stay in backend/.env (file-permission protected, never exposed to the API or browser) — this screen only reports whether each integration is wired, by design."
      error={error}
    >
      {status && (
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="mb-1 text-sm font-semibold text-slate-900">System</h2>
          <StatusRow label="Database connection" ok={status.db} />

          <h2 className="mb-1 mt-6 text-sm font-semibold text-slate-900">
            Integrations
          </h2>
          <StatusRow
            label="Google Calendar sync"
            ok={status.calendar_sync_enabled}
          />
        </div>
      )}
    </PageShell>
  );
}
