import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpDown, Download, ListChecks, LogOut, RefreshCw, Trophy, Users, Timer, Target, Percent,
} from "lucide-react";
import { API, api, errText, fmtTime } from "../lib/api";
import QuestionManager from "./QuestionManager";

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "participants", label: "Participants" },
  { key: "leaderboard", label: "Leaderboard" },
  { key: "questions", label: "Questions" },
];

const COLUMNS = [
  { key: "name", label: "Name" },
  { key: "email", label: "Email" },
  { key: "school", label: "School" },
  { key: "set", label: "Set" },
  { key: "score", label: "Score" },
  { key: "time", label: "Time" },
  { key: "completed_at", label: "Completed at" },
];

const StatCard = ({ icon: Icon, label, value, testid }) => (
  <div data-testid={testid} className="rounded-2xl border border-zinc-800 bg-[#121214] p-5">
    <div className="flex items-center gap-2 text-zinc-500">
      <Icon className="h-4 w-4" />
      <span className="mep-label">{label}</span>
    </div>
    <p className="font-display mt-3 text-3xl font-black tracking-tight text-white">{value}</p>
  </div>
);

export default function AdminDashboard() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("overview");
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState([]);
  const [board, setBoard] = useState([]);
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState({ key: "created_at", dir: "desc" });
  const [error, setError] = useState("");

  const logout = useCallback(() => {
    localStorage.removeItem("mep_admin_token");
    navigate("/admin/login", { replace: true });
  }, [navigate]);

  const loadAll = useCallback(async () => {
    try {
      const [s, p, l] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/participants", { params: { search, sort: sort.key, direction: sort.dir } }),
        api.get("/admin/leaderboard"),
      ]);
      setStats(s.data);
      setRows(p.data);
      setBoard(l.data);
      setError("");
    } catch (e) {
      if (e?.response?.status === 401) return logout();
      setError(errText(e));
    }
  }, [search, sort, logout]);

  useEffect(() => {
    if (!localStorage.getItem("mep_admin_token")) {
      navigate("/admin/login", { replace: true });
      return;
    }
    loadAll();
  }, [loadAll, navigate]);

  const toggleSort = (key) =>
    setSort((s) => ({ key, dir: s.key === key && s.dir === "asc" ? "desc" : "asc" }));

  const exportCsv = async () => {
    const token = localStorage.getItem("mep_admin_token");
    const res = await fetch(`${API}/admin/export.csv`, { headers: { Authorization: `Bearer ${token}` } });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "mep-quiz-participants.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const statCards = useMemo(
    () => [
      { icon: Users, label: "Participants", value: stats?.total_participants ?? "—", testid: "stat-participants" },
      { icon: Target, label: "Avg score", value: stats ? `${stats.avg_score}/20` : "—", testid: "stat-avg-score" },
      { icon: Timer, label: "Avg time", value: stats ? fmtTime(stats.avg_time_seconds) : "—", testid: "stat-avg-time" },
      { icon: Percent, label: "Completion rate", value: stats ? `${stats.completion_rate}%` : "—", testid: "stat-completion" },
    ],
    [stats]
  );

  return (
    <div className="relative min-h-screen bg-[#09090b]">
      <div className="mep-grid-bg" />
      <div className="relative z-10 mx-auto max-w-[1400px] px-8 py-8">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-display text-sm tracking-[0.18em] text-zinc-400">
              MEP <span className="font-extrabold text-white">QUIZ</span>
            </span>
            <h1 className="font-display text-3xl font-black tracking-tight text-white">Control room</h1>
          </div>
          <div className="flex items-center gap-3">
            <button data-testid="refresh-btn" onClick={loadAll} className="flex h-10 items-center gap-2 rounded-full border border-zinc-800 bg-[#121214] px-4 text-sm text-zinc-300 transition-colors hover:bg-zinc-800">
              <RefreshCw className="h-4 w-4" /> Refresh
            </button>
            <button data-testid="export-csv-btn" onClick={exportCsv} className="flex h-10 items-center gap-2 rounded-full bg-[#c6f24e] px-5 text-sm font-bold text-black transition-colors hover:bg-[#d4f570]">
              <Download className="h-4 w-4" /> Export CSV
            </button>
            <button data-testid="admin-logout-btn" onClick={logout} className="flex h-10 items-center gap-2 rounded-full border border-zinc-800 px-4 text-sm text-zinc-400 transition-colors hover:text-white">
              <LogOut className="h-4 w-4" /> Log out
            </button>
          </div>
        </div>

        <div className="mt-8 flex gap-2 border-b border-zinc-800">
          {TABS.map((t) => (
            <button
              key={t.key}
              data-testid={`tab-${t.key}`}
              onClick={() => setTab(t.key)}
              className={`-mb-px border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                tab === t.key ? "border-[#c6f24e] text-white" : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {error && <p data-testid="admin-error" className="mt-6 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>}

        {tab === "overview" && (
          <div className="mt-8" data-testid="overview-panel">
            <div className="grid grid-cols-1 gap-5 md:grid-cols-4">
              {statCards.map((c) => <StatCard key={c.label} {...c} />)}
            </div>
            <div className="mt-8 rounded-2xl border border-zinc-800 bg-[#121214] p-6">
              <div className="flex items-center gap-2 text-zinc-500">
                <ListChecks className="h-4 w-4" />
                <span className="mep-label">Latest entries</span>
              </div>
              <div className="mt-4 space-y-2">
                {rows.slice(0, 6).map((r) => (
                  <div key={r.id} className="flex items-center justify-between border-b border-zinc-800/60 py-2 text-sm last:border-0">
                    <span className="text-white">{r.name}</span>
                    <span className="text-zinc-500">{r.set || "—"}</span>
                    <span className="tabular-nums text-zinc-400">{r.score ?? "—"} · {fmtTime(r.time_taken_seconds)}</span>
                  </div>
                ))}
                {!rows.length && <p className="text-sm text-zinc-600">No participants yet.</p>}
              </div>
            </div>
          </div>
        )}

        {tab === "participants" && (
          <div className="mt-8" data-testid="participants-panel">
            <input
              data-testid="participant-search"
              className="mep-input max-w-md"
              placeholder="Search name, email, phone or school…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <div className="mt-5 overflow-x-auto rounded-2xl border border-zinc-800 bg-[#121214]">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800">
                    {COLUMNS.map((c) => (
                      <th key={c.key} className="px-5 py-4 text-left">
                        <button
                          data-testid={`sort-${c.key}`}
                          onClick={() => toggleSort(c.key)}
                          className="mep-label flex items-center gap-1.5 hover:text-zinc-300"
                        >
                          {c.label} <ArrowUpDown className="h-3 w-3" />
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody data-testid="participants-tbody">
                  {rows.map((r) => (
                    <tr key={r.id} className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-900/40">
                      <td className="px-5 py-4 font-medium text-white">{r.name}</td>
                      <td className="px-5 py-4 text-zinc-400">{r.email}</td>
                      <td className="px-5 py-4 text-zinc-400">{r.school || "—"}</td>
                      <td className="px-5 py-4 text-zinc-400">{r.set || "—"}</td>
                      <td className="px-5 py-4 tabular-nums text-white">{r.score ?? "—"}</td>
                      <td className="px-5 py-4 tabular-nums text-zinc-400">{fmtTime(r.time_taken_seconds)}</td>
                      <td className="px-5 py-4 text-zinc-500">{r.completed_at ? new Date(r.completed_at).toLocaleString() : "In progress"}</td>
                    </tr>
                  ))}
                  {!rows.length && (
                    <tr><td colSpan={7} className="px-5 py-10 text-center text-zinc-600">No participants found.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {tab === "leaderboard" && (
          <div className="mt-8 rounded-2xl border border-zinc-800 bg-[#121214] p-6" data-testid="leaderboard-panel">
            <div className="flex items-center gap-2 text-zinc-500">
              <Trophy className="h-4 w-4 text-[#c6f24e]" />
              <span className="mep-label">Top scores · tie-break fastest time</span>
            </div>
            <div className="mt-5 space-y-2">
              {board.map((r) => (
                <div key={r.rank} className="flex items-center gap-4 rounded-xl border border-zinc-800/60 px-4 py-3">
                  <span className={`font-display w-8 text-lg font-black ${r.rank <= 3 ? "text-[#c6f24e]" : "text-zinc-600"}`}>{r.rank}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-white">{r.name}</p>
                    <p className="text-xs text-zinc-500">{r.school || "—"} · {r.set}</p>
                  </div>
                  <span className="font-display text-lg font-black tabular-nums text-white">{r.score}</span>
                  <span className="w-16 text-right text-sm tabular-nums text-zinc-500">{fmtTime(r.time_taken_seconds)}</span>
                </div>
              ))}
              {!board.length && <p className="text-sm text-zinc-600">No completed attempts yet.</p>}
            </div>
          </div>
        )}

        {tab === "questions" && <QuestionManager onUnauthorized={logout} />}
      </div>
    </div>
  );
}
