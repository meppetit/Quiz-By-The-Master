import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { Shell } from "../components/Shell";
import { api, errText, fmtTime } from "../lib/api";

const LETTERS = ["A", "B", "C", "D"];

export default function Quiz() {
  const navigate = useNavigate();
  const token = localStorage.getItem("mep_attempt_token");
  const [q, setQ] = useState(null);
  const [index, setIndex] = useState(1);
  const [total, setTotal] = useState(20);
  const [selected, setSelected] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const loading = useRef(false);

  const load = useCallback(async () => {
    if (loading.current) return;
    loading.current = true;
    try {
      const { data } = await api.get(`/attempt/${token}/question`);
      if (data.completed) {
        navigate("/completion", { replace: true });
        return;
      }
      setQ(data.question);
      setIndex(data.index);
      setTotal(data.total_questions);
      setElapsed(data.elapsed_seconds);
      setSelected(null);
    } catch (e) {
      setError(errText(e));
    } finally {
      loading.current = false;
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!token) {
      navigate("/", { replace: true });
      return;
    }
    load();
  }, [token, navigate, load]);

  useEffect(() => {
    const t = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const next = async () => {
    if (!selected || busy) return;
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post(`/attempt/${token}/answer`, {
        question_id: q.id,
        selected_option: selected,
      });
      if (data.completed) {
        navigate("/completion", { replace: true });
        return;
      }
      await load();
    } catch (e) {
      setError(errText(e));
    } finally {
      setBusy(false);
    }
  };

  const pct = Math.round(((index - 1) / total) * 100);

  return (
    <div className="min-h-screen relative bg-[#09090b]">
      <div className="mep-grid-bg" />
      <div className="relative z-10 mx-auto w-full max-w-[430px] px-6 py-7">
        <div className="mb-6 flex items-center justify-between">
          <span className="font-display text-sm tracking-[0.18em] text-zinc-400">
            MEP <span className="text-white font-extrabold">QUIZ</span>
          </span>
          <span
            data-testid="quiz-timer"
            className="flex items-center gap-1.5 rounded-full border border-zinc-800 bg-[#121214] px-3 py-1 text-xs font-bold tabular-nums text-white"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#c6f24e]" />
            {fmtTime(elapsed)}
          </span>
        </div>

        <div className="mb-2 flex items-end justify-between">
          <span className="mep-label" data-testid="question-counter">
            Question <span className="text-white">{String(index).padStart(2, "0")}</span> of {total}
          </span>
          <span className="text-xs text-zinc-500 tabular-nums">{pct}%</span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-800">
          <div
            data-testid="quiz-progress"
            className="h-full rounded-full bg-[#c6f24e] transition-all duration-300 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>

        {!q ? (
          <div className="mt-24 flex justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-[#c6f24e]" />
          </div>
        ) : (
          <div key={q.id} className="mep-rise">
            <div className="mt-7 rounded-[24px] border border-zinc-800/70 bg-[#121214] p-5">
              {q.category && (
                <span className="inline-flex items-center gap-1.5 rounded-md border border-[#c6f24e]/40 bg-[#c6f24e]/10 px-2.5 py-1 text-[10px] font-bold tracking-[0.14em] text-[#c6f24e] uppercase">
                  <span className="h-1.5 w-1.5 rounded-full bg-[#c6f24e]" />
                  {q.category}
                </span>
              )}
              <h2
                data-testid="question-text"
                className="font-display mt-4 text-2xl font-extrabold leading-snug tracking-tight text-white"
              >
                {q.question_text}
              </h2>
            </div>

            <div className="mt-4 space-y-3">
              {LETTERS.map((l) => {
                const active = selected === l;
                return (
                  <button
                    key={l}
                    type="button"
                    data-testid={`option-${l}`}
                    onClick={() => setSelected(l)}
                    className={`group flex w-full items-center rounded-2xl border p-4 text-left transition-colors duration-200 ${
                      active
                        ? "border-[#c6f24e] bg-[#c6f24e]/10"
                        : "border-zinc-800 bg-[#0d0d0f] hover:border-zinc-600"
                    }`}
                  >
                    <span
                      className={`mr-4 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-bold ${
                        active ? "bg-[#c6f24e] text-black" : "bg-zinc-800 text-zinc-400 group-hover:text-white"
                      }`}
                    >
                      {l}
                    </span>
                    <span className="text-sm text-zinc-100">{q.options?.[l]}</span>
                    <span
                      className={`ml-auto flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 ${
                        active ? "border-[#c6f24e]" : "border-zinc-700"
                      }`}
                    >
                      {active && <span className="h-2.5 w-2.5 rounded-full bg-[#c6f24e]" />}
                    </span>
                  </button>
                );
              })}
            </div>

            {error && (
              <p data-testid="quiz-error" className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                {error}
              </p>
            )}

            <div className="mt-6 flex items-center justify-between gap-4">
              <p className="text-[11px] leading-tight text-zinc-600">Answer locks in on next</p>
              <button
                data-testid="next-btn"
                onClick={next}
                disabled={!selected || busy}
                className="mep-btn !h-12 !w-auto px-7 !text-base"
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <>{index >= total ? "Finish" : "Next"} <ArrowRight className="h-4 w-4" /></>}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
