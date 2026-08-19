import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Lock } from "lucide-react";
import { api, errText } from "../lib/api";

export default function AdminLogin() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { data } = await api.post("/admin/login", { username, password });
      localStorage.setItem("mep_admin_token", data.access_token);
      navigate("/admin", { replace: true });
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-[#09090b] px-6">
      <div className="mep-grid-bg" />
      <form
        onSubmit={submit}
        data-testid="admin-login-form"
        className="relative z-10 w-full max-w-sm rounded-[24px] border border-zinc-800/70 bg-[#121214] p-7 mep-rise"
      >
        <Lock className="h-8 w-8 text-[#c6f24e]" />
        <h1 className="font-display mt-5 text-3xl font-black tracking-tight text-white">Admin access</h1>
        <p className="mt-2 text-sm text-zinc-500">MEP Quiz control room.</p>

        <label className="mep-label mt-7 block">Username</label>
        <input data-testid="admin-username" name="username" className="mep-input mt-2" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        <label className="mep-label mt-5 block">Password</label>
        <input data-testid="admin-password" name="password" type="password" className="mep-input mt-2" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />

        {error && <p data-testid="admin-login-error" className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>}

        <button data-testid="admin-login-btn" type="submit" className="mep-btn mt-6" disabled={busy}>
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : "Sign in"}
        </button>
      </form>
    </div>
  );
}
