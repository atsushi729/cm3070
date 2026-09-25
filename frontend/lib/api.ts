// Thin client for the backend. Requests go through Next.js rewrites
// (/api/* -> http://localhost:8000/*), see next.config.mjs.

export type ReviewStatus = "pending" | "approved" | "edited" | "rejected";
export type BookingStatus = "draft" | "confirmed" | "cancelled";
export type CalendarSyncStatus =
  | "not_synced"
  | "synced"
  | "failed"
  | "disabled";
export type ProcessingStatus =
  | "uploaded"
  | "transcribing"
  | "extracting"
  | "pending_review"
  | "failed";

export interface Reservation {
  id: number;
  recording_id: number | null;
  ai_name: string | null;
  ai_date: string | null;
  ai_time: string | null;
  ai_party_size: number | null;
  ai_confidence: number | null;
  name: string | null;
  reservation_date: string | null;
  reservation_time: string | null;
  party_size: number | null;
  review_status: ReviewStatus;
  has_conflict: boolean;
  created_at: string;
  booking_status: BookingStatus;
  confirmation_ref: string | null;
  confirmed_at: string | null;
  calendar_event_id: string | null;
  calendar_html_link: string | null;
  calendar_sync_status: CalendarSyncStatus;
  calendar_synced_at: string | null;
}

export interface Recording {
  id: number;
  filename: string;
  status: ProcessingStatus;
  transcript: string | null;
  language: string | null;
  duration_sec: number | null;
  asr_latency_sec: number | null;
  error: string | null;
  created_at: string;
}

export interface SettingsStatus {
  db: boolean;
  calendar_sync_enabled: boolean;
}

export type ImageEvaluationStatus =
  | "uploaded"
  | "preprocessing"
  | "scoring"
  | "explaining"
  | "completed"
  | "completed_partial"
  | "failed";

export interface ImageAttributes {
  brightness: number;
  contrast: number;
  saturation: number;
  sharpness: number;
}

export interface ImageSuggestion {
  priority: number;
  title: string;
  reason: string;
}

export interface ImageEvaluation {
  id: number;
  status: ImageEvaluationStatus;
  popularity_score: number | null;
  popularity_score_raw: number | null;
  attributes_json: ImageAttributes | null;
  strengths_json: string[] | null;
  issues_json: string[] | null;
  suggestions_json: ImageSuggestion[] | null;
  vlm_error: string | null;
  error: string | null;
  created_at: string;
  finished_at: string | null;
}

export type SentimentLabel = "positive" | "neutral" | "negative";

export interface ReviewSentiment {
  id: number;
  text: string;
  label: SentimentLabel | null;
  score: number | null;
  latency_sec: number | null;
  feedback_label: SentimentLabel | null;
  feedback_at: string | null;
  created_at: string;
}

export interface ReviewSentimentList {
  items: ReviewSentiment[];
  counts: { positive: number; neutral: number; negative: number };
}

async function request<T>(p: Promise<Response>): Promise<T> {
  const res = await p;
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

function upload<T>(url: string, file: File): Promise<T> {
  const body = new FormData();
  body.append("file", file);
  return request<T>(fetch(url, { method: "POST", body }));
}

export const api = {
  uploadRecording: (file: File) =>
    upload<{ recording_id: number; task_id: string; status: string }>(
      "/api/recordings",
      file,
    ),
  uploadImageEvaluation: (file: File) =>
    upload<ImageEvaluation>("/api/uc2/images/evaluate", file),
  getImageEvaluation: (id: number) =>
    request<ImageEvaluation>(
      fetch(`/api/uc2/images/evaluate/${id}`, { cache: "no-store" }),
    ),
  listReservations: () =>
    request<Reservation[]>(fetch("/api/reservations", { cache: "no-store" })),
  resyncReservation: (id: number) =>
    request<Reservation>(
      fetch(`/api/reservations/${id}/resync`, { method: "POST" }),
    ),
  listRecordings: () =>
    request<Recording[]>(fetch("/api/recordings", { cache: "no-store" })),
  reviewReservation: (
    id: number,
    body: {
      action: ReviewStatus;
      name?: string | null;
      reservation_date?: string | null;
      reservation_time?: string | null;
      party_size?: number | null;
    },
  ) =>
    request<Reservation>(
      fetch(`/api/reservations/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    ),
  audioUrl: (recordingId: number) => `/api/recordings/${recordingId}/audio`,
  getSettingsStatus: () =>
    request<SettingsStatus>(
      fetch("/api/settings/status", { cache: "no-store" }),
    ),
  classifyReview: (text: string) =>
    request<ReviewSentiment>(
      fetch("/api/uc2/reviews", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }),
    ),
  listReviewSentiments: () =>
    request<ReviewSentimentList>(
      fetch("/api/uc2/reviews", { cache: "no-store" }),
    ),
  submitReviewFeedback: (id: number, label: SentimentLabel) =>
    request<ReviewSentiment>(
      fetch(`/api/uc2/reviews/${id}/feedback`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      }),
    ),
};
