"use client";

import { useEffect, useId, useRef, useState, type ChangeEvent } from "react";
import {
  api,
  type ImageEvaluation,
  type ImageEvaluationStatus,
} from "@/lib/api";
import Pill from "@/components/Pill";
import PageShell from "@/components/PageShell";

const STATUS_LABEL: Record<ImageEvaluationStatus, string> = {
  uploaded: "Queued",
  preprocessing: "Reading image…",
  scoring: "Scoring popularity…",
  explaining: "Generating evaluation…",
  completed: "Done",
  completed_partial: "Done (partial)",
  failed: "Failed",
};

const IN_PROGRESS = new Set<ImageEvaluationStatus>([
  "uploaded",
  "preprocessing",
  "scoring",
  "explaining",
]);

const STEPS = [
  {
    number: 1,
    title: "Choose a photo",
    detail: "Use the same image you are considering for a post.",
  },
  {
    number: 2,
    title: "Run local analysis",
    detail:
      "The system measures visual attributes and predicts relative popularity.",
  },
  {
    number: 3,
    title: "Start with one action",
    detail:
      "Apply the highest-priority suggestion, then compare another photo.",
  },
] as const;

export default function MarketingPage() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [evaluation, setEvaluation] = useState<ImageEvaluation | null>(null);
  const [uploading, setUploading] = useState(false);
  const [pageError, setPageError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  // Local preview only — there is no server endpoint that serves the image
  // back, so the File the user picked is the only source for the thumbnail.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  // Poll while in progress; stop as soon as a terminal status is reached.
  useEffect(() => {
    if (!evaluation || !IN_PROGRESS.has(evaluation.status)) return;
    const evaluationId = evaluation.id;
    const id = setInterval(async () => {
      try {
        const updated = await api.getImageEvaluation(evaluationId);
        setEvaluation(updated);
      } catch {
        // Transient network error — next tick retries.
      }
    }, 3000);
    return () => clearInterval(id);
  }, [evaluation?.id, evaluation?.status]);

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] ?? null);
    setPageError(null);
  };

  const onUpload = async () => {
    if (!file) return;
    setUploading(true);
    setPageError(null);
    try {
      const ev = await api.uploadImageEvaluation(file);
      setEvaluation(ev);
    } catch (err) {
      setPageError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const resetEvaluation = () => {
    setFile(null);
    setEvaluation(null);
    setPageError(null);
    if (fileRef.current) fileRef.current.value = "";
  };

  const isFinished =
    evaluation?.status === "completed" ||
    evaluation?.status === "completed_partial";
  const currentStep = isFinished ? 3 : file || evaluation || uploading ? 2 : 1;

  return (
    <PageShell
      title="AI Marketing"
      subtitle="Upload a candidate photograph and get a grounded, model-backed evaluation and improvement suggestions."
      error={
        pageError ??
        (evaluation?.status === "failed"
          ? `Evaluation failed: ${evaluation.error}. Please try again with a different photo.`
          : null)
      }
    >
      <section
        className="mb-6 grid gap-3 sm:grid-cols-3"
        aria-label={`Photo evaluation progress: step ${currentStep} of ${STEPS.length}`}
      >
        {STEPS.map(({ number, title, detail }) => {
          const state =
            number < currentStep
              ? "completed"
              : number === currentStep
                ? "current"
                : "upcoming";
          const isCompleted = state === "completed";
          const isCurrent = state === "current";

          return (
            <div
              key={number}
              aria-current={isCurrent ? "step" : undefined}
              className={`relative overflow-hidden rounded-xl border p-4 transition-colors ${
                isCompleted
                  ? "border-emerald-200 bg-emerald-50/70"
                  : isCurrent
                    ? "border-blue-500 bg-white shadow-sm ring-2 ring-blue-100"
                    : "border-slate-200 bg-slate-50/70"
              }`}
            >
              {isCurrent && (
                <span className="absolute inset-x-0 top-0 h-1 bg-blue-600" />
              )}
              <div className="flex items-center justify-between gap-3">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    isCompleted
                      ? "bg-emerald-600 text-white"
                      : isCurrent
                        ? "bg-blue-600 text-white"
                        : "border border-slate-300 bg-white text-slate-400"
                  }`}
                  aria-hidden="true"
                >
                  {isCompleted ? (
                    <svg
                      viewBox="0 0 20 20"
                      fill="none"
                      className="h-4 w-4"
                      stroke="currentColor"
                      strokeWidth="2.25"
                    >
                      <path
                        d="m5 10 3 3 7-7"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    number
                  )}
                </span>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs font-semibold ${
                    isCompleted
                      ? "bg-emerald-100 text-emerald-700"
                      : isCurrent
                        ? "bg-blue-100 text-blue-700"
                        : "bg-slate-200/70 text-slate-500"
                  }`}
                >
                  {isCompleted
                    ? "Completed"
                    : isCurrent
                      ? "In progress"
                      : "Not started"}
                </span>
              </div>
              <span
                className={`mt-4 block text-xs font-bold ${isCurrent ? "text-blue-600" : "text-slate-400"}`}
              >
                STEP {number}
              </span>
              <h2
                className={`mt-1 text-sm font-semibold ${state === "upcoming" ? "text-slate-600" : "text-slate-900"}`}
              >
                {title}
              </h2>
              <p
                className={`mt-1 text-xs leading-5 ${state === "upcoming" ? "text-slate-400" : "text-slate-500"}`}
              >
                {detail}
              </p>
            </div>
          );
        })}
      </section>
      <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
        <div className="flex flex-wrap items-center gap-3">
          <input
            ref={fileRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={onFileChange}
            className="text-sm file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-1.5 file:text-white"
          />
          <button
            onClick={onUpload}
            disabled={uploading || !file}
            className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {uploading ? "Uploading…" : "Evaluate photo"}
          </button>
          {evaluation && (
            <span className="text-sm text-slate-500">
              {STATUS_LABEL[evaluation.status]}
            </span>
          )}
        </div>
        {previewUrl && (
          <img
            src={previewUrl}
            alt="Selected photo preview"
            className="mt-4 max-h-64 rounded-lg border border-slate-100 object-contain"
          />
        )}
      </section>

      {evaluation && (
        <ResultCard evaluation={evaluation} onReset={resetEvaluation} />
      )}
    </PageShell>
  );
}

function ResultCard({
  evaluation,
  onReset,
}: {
  evaluation: ImageEvaluation;
  onReset: () => void;
}) {
  // The card only renders finished-with-results states; in-progress polls on,
  // and "failed" is reported via PageShell's error banner.
  if (
    evaluation.status !== "completed" &&
    evaluation.status !== "completed_partial"
  )
    return null;

  const attrs = evaluation.attributes_json;
  const score = evaluation.popularity_score;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Photo evaluation
          </h2>
          <p className="mt-1 max-w-2xl text-xs text-slate-500">
            The popularity score is a model estimate for comparing candidate
            images—not a guarantee of engagement, sales or customer preference.
          </p>
        </div>
        <button
          onClick={onReset}
          className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700"
        >
          Evaluate another photo
        </button>
      </div>
      {score === null ? (
        <p className="mb-5 text-sm text-slate-400">
          Popularity score unavailable (model not calibrated) — showing pixel
          attributes and the model-backed evaluation only.
        </p>
      ) : (
        <div className="mb-5">
          <div className="mb-1 flex items-baseline gap-2">
            <span className="text-3xl font-bold text-slate-900">
              {Math.round(score)}
            </span>
            <span className="text-sm text-slate-400">
              / 100 popularity score
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-slate-100">
            <div
              className="h-2 rounded-full bg-slate-900"
              style={{ width: `${Math.max(0, Math.min(100, score))}%` }}
            />
          </div>
        </div>
      )}

      {attrs && (
        <div className="mb-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          <Bar
            label="Brightness"
            help="How light or dark the image is overall."
            value={attrs.brightness}
          />
          <Bar
            label="Contrast"
            help="The separation between light and dark areas."
            value={attrs.contrast}
          />
          <Bar
            label="Saturation"
            help="The overall intensity of colours."
            value={attrs.saturation}
          />
          <Bar
            label="Sharpness"
            help="An edge-based estimate of visible detail, not a guarantee of focus."
            value={attrs.sharpness}
          />
        </div>
      )}

      {evaluation.status === "completed_partial" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <Pill tone="warn">Partial result</Pill>
          <p className="mt-2 text-sm text-amber-800">
            Could not generate the written evaluation. The score and image
            attributes are still available.
          </p>
        </div>
      )}

      {evaluation.status === "completed" && (
        <div className="space-y-5">
          {evaluation.strengths_json &&
            evaluation.strengths_json.length > 0 && (
              <div>
                <h3 className="mb-1 text-sm font-semibold text-emerald-700">
                  Strengths
                </h3>
                <ul className="list-inside list-disc text-sm text-slate-600">
                  {evaluation.strengths_json.map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </div>
            )}

          {evaluation.issues_json && evaluation.issues_json.length > 0 && (
            <div>
              <h3 className="mb-1 text-sm font-semibold text-amber-800">
                Issues
              </h3>
              <ul className="list-inside list-disc text-sm text-slate-600">
                {evaluation.issues_json.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            </div>
          )}

          {evaluation.suggestions_json &&
            evaluation.suggestions_json.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-900">
                  Prioritised suggestions
                </h3>
                <ol className="space-y-2 text-sm">
                  {[...evaluation.suggestions_json]
                    .sort((a, b) => a.priority - b.priority)
                    .map((s, i) => (
                      <li
                        key={i}
                        className={
                          i === 0
                            ? "rounded-lg border border-emerald-200 bg-emerald-50 p-3"
                            : "px-3 py-1"
                        }
                      >
                        {i === 0 && (
                          <span className="mb-1 block text-xs font-bold uppercase tracking-wide text-emerald-700">
                            Start here
                          </span>
                        )}
                        <span className="font-medium text-slate-800">
                          {s.title}
                        </span>
                        <p className="text-xs text-slate-500">{s.reason}</p>
                      </li>
                    ))}
                </ol>
              </div>
            )}
        </div>
      )}
    </section>
  );
}

function Bar({
  label,
  help,
  value,
}: {
  label: string;
  help: string;
  value: number;
}) {
  const pct = Math.round(value * 100);
  const tooltipId = useId();

  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span className="group relative inline-flex">
          <button
            type="button"
            aria-describedby={tooltipId}
            className="cursor-help border-b border-dotted border-slate-400"
          >
            {label} ⓘ
          </button>
          <span
            id={tooltipId}
            role="tooltip"
            className="pointer-events-none absolute bottom-full left-0 z-20 mb-2 hidden w-52 rounded-md bg-slate-900 px-3 py-2 text-left text-xs font-normal leading-4 text-white shadow-lg group-hover:block group-focus-within:block"
          >
            {help}
          </span>
        </span>
        <span>{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-100">
        <div
          className="h-1.5 rounded-full bg-slate-900"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
