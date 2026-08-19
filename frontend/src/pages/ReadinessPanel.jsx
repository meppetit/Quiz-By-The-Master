import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, RefreshCw } from "lucide-react";
import { api, errText } from "../lib/api";

export default function ReadinessPanel({ onUnauthorized }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const res = await api.get("/admin/health-check");
      setData(res.data);
      setError("");
    } catch (e) {
      if (e?.response?.status === 401) return onUnauthorized?.();
      setError(errText(e));
    }
  }, [onUnauthorized]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="mt-8" data-testid="readiness-panel">
      <div className="flex items-center justify-between">
        <div>
          <p className="mep-label">Pre-event checklist</p>
          <h2 className="font-display mt-1 text-2xl font-black tracking-tight text-white">
            {data
              ? data.event_ready
                ? "All sets ready for the event"
                : `${data.blocked_sets} set(s) need attention`
              : "Checking sets…"}
          </h2>
        </div>
        <button data-testid="readiness-refresh" onClick={load} className="flex h-10 items-center gap-2 rounded-full border border-zinc-800 bg-[#121214] px-4 text-sm text-zinc-300 hover:bg-zinc-800">
          <RefreshCw className="h-4 w-4" /> Re-check
        </button>
      </div>

      {error && <p className="mt-5 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>}

      {data && (
        <div className="mt-6 grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.sets.map((s) => (
            <div
              key={s.set_id}
              data-testid={`readiness-set-${s.set_id}`}
              className={`rounded-2xl border p-5 ${s.ready ? "border-zinc-800 bg-[#121214]" : "border-amber-500/40 bg-amber-500/[0.06]"}`}
            >
              <div className="flex items-center justify-between">
                <p className="font-display text-lg font-extrabold text-white">{s.name}</p>
                {s.ready ? (
                  <span className="flex items-center gap-1.5 text-xs font-bold text-[#c6f24e]"><CheckCircle2 className="h-4 w-4" /> READY</span>
                ) : (
                  <span className="flex items-center gap-1.5 text-xs font-bold text-amber-400"><AlertTriangle className="h-4 w-4" /> CHECK</span>
                )}
              </div>
              <p className="mt-2 text-xs text-zinc-500">{s.question_count} questions · {s.attempt_count} attempts</p>
              {!!s.issues.length && (
                <ul className="mt-3 space-y-1">
                  {s.issues.slice(0, 6).map((i, k) => (
                    <li key={k} className="text-xs text-amber-300/90">• {i}</li>
                  ))}
                  {s.issues.length > 6 && <li className="text-xs text-zinc-500">+{s.issues.length - 6} more</li>}
                </ul>
              )}
              {!!(s.warnings || []).length && (
                <ul className="mt-3 space-y-1">
                  {s.warnings.map((w, k) => (
                    <li key={k} className="text-xs text-zinc-500">• {w}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
