import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Maximize2, Trophy, Users, X } from "lucide-react";
import { api, errText, fmtTime } from "../lib/api";

export default function LiveLeaderboard() {
  const navigate = useNavigate();
  const [board, setBoard] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [l, s] = await Promise.all([
        api.get("/admin/leaderboard", { params: { limit: 12 } }),
        api.get("/admin/stats"),
      ]);
      setBoard(l.data);
      setStats(s.data);
      setError("");
    } catch (e) {
      if (e?.response?.status === 401) {
        navigate("/admin/login", { replace: true });
        return;
      }
      setError(errText(e));
    }
  }, [navigate]);

  useEffect(() => {
    if (!localStorage.getItem("mep_admin_token")) {
      navigate("/admin/login", { replace: true });
      return;
    }
    load();
    const t = setInterval(() => {
      if (document.visibilityState === "visible") load();
    }, 5000);
    return () => clearInterval(t);
  }, [load, navigate]);

  const goFullscreen = () => {
    const el = document.documentElement;
    if (document.fullscreenElement) document.exitFullscreen();
    else el.requestFullscreen?.();
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[#09090b]" data-testid="live-leaderboard">
      <div className="mep-grid-bg" />
      <div className="relative z-10 mx-auto max-w-[1500px] px-10 py-8">
        <div className="flex items-start justify-between">
          <div>
            <span className="font-display text-sm tracking-[0.2em] text-zinc-400">
              MEP <span className="font-extrabold text-white">QUIZ</span>
            </span>
            <h1 className="font-display text-6xl font-black leading-none tracking-tighter text-white">
              Live leaderboard
            </h1>
            <p className="mt-3 flex items-center gap-2 text-sm text-zinc-500">
              <span className="h-2 w-2 animate-pulse rounded-full bg-[#c6f24e]" />
              Updating every 5 seconds
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-zinc-800 bg-[#121214] px-6 py-4 text-right">
              <p className="mep-label flex items-center justify-end gap-2"><Users className="h-3.5 w-3.5" /> Players</p>
              <p className="font-display text-3xl font-black text-white" data-testid="live-total">
                {stats?.total_participants ?? "—"}
              </p>
            </div>
            <div className="rounded-2xl border border-zinc-800 bg-[#121214] px-6 py-4 text-right">
              <p className="mep-label">Avg score</p>
              <p className="font-display text-3xl font-black text-[#c6f24e]">{stats ? stats.avg_score : "—"}</p>
            </div>
            <button data-testid="fullscreen-btn" onClick={goFullscreen} className="flex h-11 items-center gap-2 rounded-full border border-zinc-800 bg-[#121214] px-4 text-sm text-zinc-300 transition-colors hover:bg-zinc-800">
              <Maximize2 className="h-4 w-4" /> Fullscreen
            </button>
            <button data-testid="exit-live-btn" onClick={() => navigate("/admin")} className="flex h-11 items-center gap-2 rounded-full border border-zinc-800 px-4 text-sm text-zinc-400 transition-colors hover:text-white">
              <X className="h-4 w-4" /> Exit
            </button>
          </div>
        </div>

        {error && <p className="mt-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-red-300">{error}</p>}

        <div className="mt-9 grid grid-cols-2 gap-4" data-testid="live-rows">
          {board.map((r) => {
            const top = r.rank <= 3;
            return (
              <div
                key={r.rank}
                className={`mep-rise flex items-center gap-6 rounded-2xl border px-7 py-5 ${
                  top ? "border-[#c6f24e]/50 bg-[#c6f24e]/[0.07]" : "border-zinc-800 bg-[#121214]"
                }`}
                style={{ animationDelay: `${r.rank * 40}ms` }}
              >
                <span className={`font-display w-14 text-4xl font-black tabular-nums ${top ? "text-[#c6f24e]" : "text-zinc-700"}`}>
                  {String(r.rank).padStart(2, "0")}
                </span>
                {top && <Trophy className="h-6 w-6 shrink-0 text-[#c6f24e]" />}
                <div className="min-w-0 flex-1">
                  <p className="font-display truncate text-2xl font-extrabold tracking-tight text-white">{r.name}</p>
                  <p className="truncate text-sm text-zinc-500">{r.school || "—"} · {r.set}</p>
                </div>
                <div className="text-right">
                  <p className="font-display text-4xl font-black tabular-nums text-white">{r.score}</p>
                  <p className="text-xs tabular-nums text-zinc-500">{fmtTime(r.time_taken_seconds)}</p>
                </div>
              </div>
            );
          })}
          {!board.length && (
            <p className="col-span-2 py-24 text-center text-xl text-zinc-600">
              Waiting for the first completed run…
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
