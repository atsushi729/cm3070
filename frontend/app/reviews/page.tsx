"use client";

import { useEffect, useState } from "react";
import { api, type ReviewSentimentList, type SentimentLabel } from "@/lib/api";
import Pill, { type Tone } from "@/components/Pill";
import PageShell from "@/components/PageShell";

const LABEL_TONE: Record<SentimentLabel, Tone> = {
  positive: "human",
  neutral: "muted",
  negative: "warn",
};

const LABEL_TEXT: Record<SentimentLabel, string> = {
  positive: "Positive",
  neutral: "Neutral",
  negative: "Negative",
};

const EMPTY: ReviewSentimentList = {
  items: [],
  counts: { positive: 0, neutral: 0, negative: 0 },
};

export default function ReviewsPage() {
  const [text, setText] = useState("");
  const [data, setData] = useState<ReviewSentimentList>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [choosingCorrection, setChoosingCorrection] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listReviewSentiments()
      .then(setData)
      .catch(() =>
        setError("Could not reach the backend. Is the API running?"),
      );
  }, []);

  const latest = data.items[0] ?? null;

  const onClassify = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setError(null);
    try {
      // The POST returns the full row, so prepend it and bump the tally
      // locally instead of re-fetching the whole list.
      const row = await api.classifyReview(text.trim());
      setText("");
      setData((prev) => ({
        items: [row, ...prev.items],
        counts: row.label
          ? { ...prev.counts, [row.label]: prev.counts[row.label] + 1 }
          : prev.counts,
      }));
      setChoosingCorrection(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Classification failed");
    } finally {
      setBusy(false);
    }
  };

  const onFeedback = async (label: SentimentLabel) => {
    if (!latest) return;
    setFeedbackBusy(true);
    setError(null);
    try {
      const updated = await api.submitReviewFeedback(latest.id, label);
      // Move one count from the previous effective label to the new one.
      const before = latest.feedback_label ?? latest.label;
      setData((prev) => {
        const counts = { ...prev.counts };
        if (before) counts[before] -= 1;
        counts[label] += 1;
        return {
          items: prev.items.map((item) =>
            item.id === updated.id ? updated : item,
          ),
          counts,
        };
      });
      setChoosingCorrection(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save feedback");
    } finally {
      setFeedbackBusy(false);
    }
  };

  return (
    <PageShell
      title="Review Sentiment"
      subtitle="Paste one customer review (Google, Tabelog, Instagram…) to classify its overall sentiment with the locally fine-tuned multilingual model. Nothing leaves this machine."
      error={error}
    >
      <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          placeholder="Paste a customer review here…"
          className="w-full resize-y rounded-md border border-slate-200 p-3 text-sm focus:border-slate-400 focus:outline-none"
        />
        <div className="mt-3">
          <button
            onClick={onClassify}
            disabled={busy || !text.trim()}
            className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? "Classifying…" : "Classify"}
          </button>
        </div>
      </section>

      {latest && latest.label && (
        <section className="mb-8 rounded-xl border border-slate-200 bg-white p-5">
          <p className="mb-3 text-xs text-slate-500">
            This is the overall tone predicted by the local model. A review that
            praises one aspect and criticises another may need human correction.
          </p>
          <div className="mb-2 flex items-center gap-3">
            <Pill tone={LABEL_TONE[latest.label]}>
              {LABEL_TEXT[latest.label]}
            </Pill>
            {latest.score !== null && (
              <span className="text-sm text-slate-500">
                {Math.round(latest.score * 100)}% confidence
              </span>
            )}
          </div>
          <p className="text-sm text-slate-600">{latest.text}</p>
          <div className="mt-4 border-t border-slate-100 pt-3">
            {latest.feedback_label ? (
              <p className="text-sm text-emerald-700">
                ✓ Human checked: {LABEL_TEXT[latest.feedback_label]}
                {latest.feedback_label !== latest.label && " (corrected)"}
              </p>
            ) : (
              <>
                <p className="mb-2 text-xs font-medium text-slate-600">
                  Is this classification correct?
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => onFeedback(latest.label!)}
                    disabled={feedbackBusy}
                    className="rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-800 disabled:opacity-50"
                  >
                    ✓ Correct
                  </button>
                  <button
                    onClick={() => setChoosingCorrection((value) => !value)}
                    disabled={feedbackBusy}
                    className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 disabled:opacity-50"
                  >
                    Choose a different label
                  </button>
                </div>
                {choosingCorrection && (
                  <div className="mt-3 rounded-lg bg-slate-50 p-3">
                    <p className="mb-2 text-xs text-slate-500">
                      What should the overall label be?
                    </p>
                    <div className="flex gap-2">
                      {(["positive", "neutral", "negative"] as SentimentLabel[])
                        .filter((label) => label !== latest.label)
                        .map((label) => (
                          <button
                            key={label}
                            onClick={() => onFeedback(label)}
                            disabled={feedbackBusy}
                            className="rounded-md bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm ring-1 ring-slate-200 disabled:opacity-50"
                          >
                            {LABEL_TEXT[label]}
                          </button>
                        ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      )}

      <section className="rounded-xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center gap-4 text-sm">
          <span className="text-slate-400">All time</span>
          <span className="text-emerald-700">
            Positive {data.counts.positive}
          </span>
          <span className="text-slate-500">Neutral {data.counts.neutral}</span>
          <span className="text-amber-800">
            Negative {data.counts.negative}
          </span>
        </div>
        <ul className="divide-y divide-slate-100">
          {data.items.map((it) => (
            <li
              key={it.id}
              className="flex items-start justify-between gap-4 py-3"
            >
              <p className="line-clamp-2 text-sm text-slate-600">{it.text}</p>
              <div className="flex flex-shrink-0 items-center gap-2">
                {(it.feedback_label ?? it.label) && (
                  <Pill tone={LABEL_TONE[it.feedback_label ?? it.label!]}>
                    {LABEL_TEXT[it.feedback_label ?? it.label!]}
                  </Pill>
                )}
                {it.feedback_label && it.feedback_label !== it.label && (
                  <span
                    className="text-xs text-slate-400"
                    title={`AI predicted ${it.label}`}
                  >
                    corrected
                  </span>
                )}
                <span className="whitespace-nowrap text-xs text-slate-400">
                  {new Date(it.created_at).toLocaleString()}
                </span>
              </div>
            </li>
          ))}
          {data.items.length === 0 && (
            <li className="py-3 text-sm text-slate-400">
              No reviews classified yet.
            </li>
          )}
        </ul>
      </section>
    </PageShell>
  );
}
