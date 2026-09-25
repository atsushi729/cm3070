"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type Recording, type Reservation } from "@/lib/api";
import Pill from "@/components/Pill";
import PageShell from "@/components/PageShell";
import BookingsTab from "@/components/reservations/BookingsTab";
import ReservationCard from "@/components/reservations/ReservationCard";

const STATUS_LABEL: Record<string, string> = {
  uploaded: "Queued",
  transcribing: "Transcribing…",
  extracting: "Reading reservation…",
  pending_review: "Ready for review",
  failed: "Failed",
};

type Tab = "review" | "bookings";

export default function ReservationsPage() {
  const [reservations, setReservations] = useState<Reservation[]>([]);
  const [recordings, setRecordings] = useState<Recording[]>([]);
  const [tab, setTab] = useState<Tab>("review");
  const [uploading, setUploading] = useState(false);
  const [hasFile, setHasFile] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    const [nextReservations, nextRecordings] = await Promise.all([
      api.listReservations(),
      api.listRecordings(),
    ]);
    setReservations(nextReservations);
    setRecordings(nextRecordings);
  }, []);

  const bookings = useMemo(
    () =>
      reservations
        .filter((reservation) => reservation.booking_status === "confirmed")
        .sort((a, b) =>
          `${a.reservation_date}T${a.reservation_time}`.localeCompare(
            `${b.reservation_date}T${b.reservation_time}`,
          ),
        ),
    [reservations],
  );

  const processing = recordings.filter(
    (recording) =>
      recording.status !== "pending_review" && recording.status !== "failed",
  );
  const hasProcessing = processing.length > 0;

  const failed = recordings
    .filter((recording) => recording.status === "failed")
    .sort((a, b) => b.created_at.localeCompare(a.created_at));

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const interval = hasProcessing ? 3000 : 15000;
    const id = setInterval(() => {
      if (!document.hidden) refresh();
    }, interval);
    return () => clearInterval(id);
  }, [hasProcessing, refresh]);

  const onUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadRecording(file);
      if (fileRef.current) fileRef.current.value = "";
      setHasFile(false);
      await refresh();
    } finally {
      setUploading(false);
    }
  };

  const pending = reservations.filter(
    (reservation) => reservation.review_status === "pending",
  );
  const reviewed = reservations.filter(
    (reservation) => reservation.review_status !== "pending",
  );

  return (
    <PageShell
      title="Voice Reservation System"
      subtitle="AI drafts each reservation from the call recording. Nothing is booked until you approve it."
    >
      <nav className="mb-8 flex gap-1 border-b border-slate-200">
        <TabButton active={tab === "review"} onClick={() => setTab("review")}>
          Review {pending.length > 0 && `(${pending.length})`}
        </TabButton>
        <TabButton
          active={tab === "bookings"}
          onClick={() => setTab("bookings")}
        >
          Bookings {bookings.length > 0 && `(${bookings.length})`}
        </TabButton>
      </nav>

      {tab === "review" && (
        <>
          <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileRef}
                type="file"
                accept="audio/*"
                onChange={(event) => setHasFile(!!event.target.files?.length)}
                className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-white"
              />
              <button
                onClick={onUpload}
                disabled={uploading || !hasFile}
                className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {uploading ? "Uploading…" : "Process call recording"}
              </button>
              {processing.length > 0 && (
                <span className="text-sm text-slate-500">
                  {processing.length} call(s) processing —{" "}
                  {processing
                    .map((item) => STATUS_LABEL[item.status])
                    .join(", ")}
                </span>
              )}
            </div>
          </section>

          {failed.length > 0 && (
            <div className="mb-8 space-y-2">
              {failed.map((recording) => (
                <div
                  key={recording.id}
                  className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm"
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium text-red-800">
                      Processing failed — {recording.filename}
                    </span>
                    <Pill tone="danger">Failed</Pill>
                  </div>
                  {recording.error && (
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words text-xs text-red-700">
                      {recording.error}
                    </pre>
                  )}
                  <p className="mt-2 text-xs text-red-600">
                    Re-upload the recording to try again.
                  </p>
                </div>
              ))}
            </div>
          )}

          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
            Awaiting your approval ({pending.length})
          </h2>
          <div className="space-y-4">
            {pending.length === 0 && (
              <p className="rounded-lg border border-dashed border-slate-200 p-6 text-center text-sm text-slate-400">
                No reservations waiting. Upload a call recording above.
              </p>
            )}
            {pending.map((reservation) => (
              <ReservationCard
                key={reservation.id}
                reservation={reservation}
                transcript={
                  recordings.find(
                    (recording) => recording.id === reservation.recording_id,
                  )?.transcript ?? null
                }
                onReviewed={refresh}
              />
            ))}
          </div>

          {reviewed.length > 0 && (
            <>
              <h2 className="mb-3 mt-10 text-sm font-semibold uppercase tracking-wide text-slate-500">
                Reviewed ({reviewed.length})
              </h2>
              <div className="space-y-2">
                {reviewed.map((reservation) => (
                  <div
                    key={reservation.id}
                    className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm"
                  >
                    <span className="font-medium text-slate-700">
                      {reservation.name ?? "—"} ·{" "}
                      {reservation.reservation_date ?? "?"}{" "}
                      {reservation.reservation_time?.slice(0, 5) ?? ""} ·{" "}
                      {reservation.party_size ?? "?"} ppl
                    </span>
                    <Pill
                      tone={
                        reservation.review_status === "rejected"
                          ? "danger"
                          : "human"
                      }
                    >
                      {reservation.review_status}
                    </Pill>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}

      {tab === "bookings" && (
        <BookingsTab bookings={bookings} onChanged={refresh} />
      )}
    </PageShell>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
        active
          ? "border-slate-900 text-slate-900"
          : "border-transparent text-slate-500 hover:text-slate-700"
      }`}
    >
      {children}
    </button>
  );
}
