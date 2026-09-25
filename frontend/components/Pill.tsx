export type Tone = "ai" | "human" | "warn" | "danger" | "muted";

const TONES: Record<Tone, string> = {
  ai: "bg-violet-100 text-violet-700",
  human: "bg-emerald-100 text-emerald-700",
  warn: "bg-amber-100 text-amber-800",
  danger: "bg-rose-100 text-rose-700",
  muted: "bg-slate-100 text-slate-600",
};

export default function Pill({
  tone,
  children,
}: {
  tone: Tone;
  children: React.ReactNode;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}
