"use client";

import { useState } from "react";
import { api, type Reservation, type ReviewStatus } from "@/lib/api";
import Pill from "@/components/Pill";

export default function ReservationCard({
  reservation: r,
  transcript,
  onReviewed,
}: {
  reservation: Reservation;
  transcript: string | null;
  onReviewed: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [showTranscript, setShowTranscript] = useState(false);
  const [form, setForm] = useState({
    name: r.name ?? "",
    reservation_date: r.reservation_date ?? "",
    reservation_time: (r.reservation_time ?? "").slice(0, 5),
    party_size: r.party_size?.toString() ?? "",
  });

  const act = async (action: ReviewStatus) => {
    setBusy(true);
    setActionError(null);
    try {
      await api.reviewReservation(r.id, {
        action,
        name: form.name || null,
        reservation_date: form.reservation_date || null,
        reservation_time: form.reservation_time || null,
        party_size: form.party_size ? Number(form.party_size) : null,
      });
      onReviewed();
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "Could not update reservation",
      );
    } finally {
      setBusy(false);
    }
  };

  const confidence =
    r.ai_confidence != null ? Math.round(r.ai_confidence * 100) : null;
  const validForm = Boolean(
    form.name.trim() &&
    form.reservation_date &&
    form.reservation_time &&
    Number(form.party_size) > 0,
  );
  const changes = [
    ["Name", r.name ?? "missing", form.name || "missing"],
    [
      "Date",
      r.reservation_date ?? "missing",
      form.reservation_date || "missing",
    ],
    [
      "Time",
      r.reservation_time?.slice(0, 5) ?? "missing",
      form.reservation_time || "missing",
    ],
    [
      "Party",
      r.party_size?.toString() ?? "missing",
      form.party_size || "missing",
    ],
  ].filter(([, before, after]) => before !== after);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-center gap-2">
        <Pill tone="ai">AI draft</Pill>
        {confidence != null && (
          <Pill tone={confidence >= 70 ? "muted" : "warn"}>
            {confidence}% confidence
          </Pill>
        )}
        {r.has_conflict && <Pill tone="danger">⚠ Time conflict</Pill>}
        <span className="ml-auto text-xs text-slate-400">#{r.id}</span>
      </div>

      {!editing ? (
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 sm:grid-cols-4">
          <Field label="Name" value={r.name} />
          <Field label="Date" value={r.reservation_date} />
          <Field label="Time" value={r.reservation_time?.slice(0, 5)} />
          <Field label="Party" value={r.party_size?.toString()} />
        </dl>
      ) : (
        <div>
          <p className="mb-3 text-xs font-medium text-amber-700">
            Editing the AI draft — review your changes before approving.
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <EditField
              label="Name"
              value={form.name}
              onChange={(name) => setForm({ ...form, name })}
            />
            <EditField
              label="Date"
              type="date"
              value={form.reservation_date}
              onChange={(reservation_date) =>
                setForm({ ...form, reservation_date })
              }
            />
            <EditField
              label="Time"
              type="time"
              value={form.reservation_time}
              onChange={(reservation_time) =>
                setForm({ ...form, reservation_time })
              }
            />
            <EditField
              label="Party size"
              type="number"
              value={form.party_size}
              onChange={(party_size) => setForm({ ...form, party_size })}
            />
          </div>
          {changes.length > 0 && (
            <div className="mt-3 rounded-lg bg-amber-50 p-3 text-xs text-amber-900">
              <span className="font-semibold">Changes to approve:</span>{" "}
              {changes
                .map(
                  ([label, before, after]) => `${label}: ${before} → ${after}`,
                )
                .join(" · ")}
            </div>
          )}
          {!validForm && (
            <p className="mt-2 text-xs text-rose-600">
              Complete all fields and use a party size of at least 1.
            </p>
          )}
        </div>
      )}

      <div className="mt-4 border-t border-slate-100 pt-3">
        {r.recording_id != null && (
          <audio
            controls
            preload="none"
            className="h-9 w-full"
            src={api.audioUrl(r.recording_id)}
          />
        )}
        <button
          onClick={() => setShowTranscript((shown) => !shown)}
          className="mt-2 text-xs font-medium text-slate-500 underline"
        >
          {showTranscript ? "Hide" : "Show"} call transcript
        </button>
        {showTranscript && (
          <p className="mt-2 rounded-md bg-slate-50 p-3 text-sm text-slate-600">
            {transcript ?? "(transcript unavailable)"}
          </p>
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {!editing ? (
          <>
            <button
              onClick={() => act("approved")}
              disabled={busy}
              className="rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              ✓ Approve
            </button>
            <button
              onClick={() => setEditing(true)}
              disabled={busy}
              className="rounded-md border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-700"
            >
              Edit reservation details
            </button>
            <button
              onClick={() => act("rejected")}
              disabled={busy}
              className="rounded-md px-4 py-1.5 text-sm font-medium text-rose-600 hover:bg-rose-50"
            >
              Reject
            </button>
          </>
        ) : (
          <>
            <button
              onClick={() => act("edited")}
              disabled={busy || !validForm || changes.length === 0}
              className="rounded-md bg-emerald-600 px-4 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Save changes &amp; approve booking
            </button>
            <button
              onClick={() => setEditing(false)}
              disabled={busy}
              className="rounded-md border border-slate-300 px-4 py-1.5 text-sm font-medium text-slate-700"
            >
              Cancel editing
            </button>
          </>
        )}
      </div>
      {actionError && (
        <p className="mt-3 text-xs text-rose-600">{actionError}</p>
      )}
    </div>
  );
}

function Field({
  label,
  value,
}: {
  label: string;
  value: string | null | undefined;
}) {
  return (
    <div>
      <dt className="text-xs text-slate-400">{label}</dt>
      <dd
        className={`text-sm font-semibold ${value ? "text-slate-900" : "text-rose-500"}`}
      >
        {value || "missing"}
      </dd>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="text-xs text-slate-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-0.5 w-full rounded-md border border-slate-300 px-2 py-1 text-sm"
      />
    </label>
  );
}
