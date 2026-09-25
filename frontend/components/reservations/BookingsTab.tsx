"use client";

import { useState } from "react";
import { api, type CalendarSyncStatus, type Reservation } from "@/lib/api";
import Pill, { type Tone } from "@/components/Pill";

const SYNC_LABEL: Record<CalendarSyncStatus, { tone: Tone; text: string }> = {
  synced: { tone: "human", text: "✓ In calendar" },
  not_synced: { tone: "muted", text: "Not synced" },
  failed: { tone: "danger", text: "⚠ Sync failed" },
  disabled: { tone: "muted", text: "Calendar off" },
};

export default function BookingsTab({
  bookings,
  onChanged,
}: {
  bookings: Reservation[];
  onChanged: () => void;
}) {
  if (bookings.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
        No confirmed bookings yet. Approve a reservation in the Review tab.
      </p>
    );
  }

  const byDate = new Map<string, Reservation[]>();
  for (const booking of bookings) {
    const key = booking.reservation_date ?? "—";
    const group = byDate.get(key);
    if (group) group.push(booking);
    else byDate.set(key, [booking]);
  }

  return (
    <div className="space-y-6">
      {[...byDate.entries()].map(([date, rows]) => (
        <section key={date}>
          <h3 className="mb-2 text-sm font-semibold text-slate-700">
            {date}{" "}
            <span className="font-normal text-slate-400">· {rows.length}</span>
          </h3>
          <div className="space-y-2">
            {rows.map((reservation) => (
              <div
                key={reservation.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-slate-500">
                    {reservation.reservation_time?.slice(0, 5) ?? "--:--"}
                  </span>
                  <span className="font-medium text-slate-800">
                    {reservation.name ?? "—"}
                  </span>
                  <span className="text-slate-500">
                    {reservation.party_size ?? "?"} ppl
                  </span>
                  {reservation.has_conflict && (
                    <Pill tone="warn">⚠ Conflict</Pill>
                  )}
                  {reservation.confirmation_ref && (
                    <span className="text-xs text-slate-400">
                      {reservation.confirmation_ref}
                    </span>
                  )}
                </div>
                <SyncBadge reservation={reservation} onChanged={onChanged} />
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

function SyncBadge({
  reservation,
  onChanged,
}: {
  reservation: Reservation;
  onChanged: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const label = SYNC_LABEL[reservation.calendar_sync_status];
  const badge = <Pill tone={label.tone}>{label.text}</Pill>;

  const resync = async () => {
    setBusy(true);
    try {
      await api.resyncReservation(reservation.id);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {reservation.calendar_html_link ? (
        <a
          href={reservation.calendar_html_link}
          target="_blank"
          rel="noreferrer"
        >
          {badge}
        </a>
      ) : (
        badge
      )}
      {reservation.calendar_sync_status === "failed" && (
        <button
          onClick={resync}
          disabled={busy}
          className="text-xs font-medium text-slate-500 underline disabled:opacity-50"
        >
          {busy ? "…" : "↻ Retry"}
        </button>
      )}
    </div>
  );
}
