import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Loader2 } from "lucide-react";
import { Shell, Tag } from "../components/Shell";
import { api, errText } from "../lib/api";

const FIELDS = [
  { key: "name", label: "Full name", placeholder: "e.g. Arjun Mehta", type: "text" },
  { key: "email", label: "Email", placeholder: "you@example.com", type: "email" },
  { key: "phone", label: "Phone number", placeholder: "+91 98765 43210", type: "tel" },
  { key: "school", label: "School", placeholder: "Where do you study?", type: "text", optional: true },
];

export default function Registration() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", phone: "", school: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    if (!form.name.trim() || !form.email.trim() || !form.phone.trim()) {
      setError("Name, email and phone number are required.");
      return;
    }
    setBusy(true);
    try {
      const { data } = await api.post("/register", {
        name: form.name.trim(),
        email: form.email.trim(),
        phone: form.phone.trim(),
        school: form.school.trim() || null,
      });
      localStorage.setItem("mep_attempt_token", data.attempt_token);
      navigate("/quiz", { replace: true });
    } catch (err) {
      setError(errText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Shell>
      <div className="mep-rise" data-testid="registration-screen">
        <Tag testid="quiz-ready-tag">Quiz ready</Tag>
        <h1 className="font-display mt-5 text-4xl font-black leading-[1.05] tracking-tight text-white">
          You’re in. Let’s get you set up.
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">
          20 questions, one shot each, no going back. Fill this in to start your run.
        </p>

        <form onSubmit={submit} className="mt-7 rounded-[24px] border border-zinc-800/70 bg-[#121214] p-5 shadow-xl">
          {FIELDS.map((f) => (
            <div key={f.key} className="mb-5 last:mb-0">
              <div className="mb-2 flex items-center justify-between">
                <label className="mep-label" htmlFor={f.key}>{f.label}</label>
                {f.optional && <span className="text-[10px] text-zinc-600">Optional</span>}
              </div>
              <input
                id={f.key}
                data-testid={`input-${f.key}`}
                className="mep-input"
                type={f.type}
                value={form[f.key]}
                onChange={set(f.key)}
                placeholder={f.placeholder}
                autoComplete="off"
              />
            </div>
          ))}
        </form>

        {error && (
          <p data-testid="registration-error" className="mt-4 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </p>
        )}

        <button
          data-testid="start-quiz-btn"
          className="mep-btn mt-6"
          onClick={submit}
          disabled={busy}
        >
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <>Start quiz <ArrowRight className="h-5 w-5" /></>}
        </button>

        <p className="mt-4 text-center text-[11px] text-zinc-600">
          One entry per person. Timer starts the moment you begin.
        </p>
      </div>
    </Shell>
  );
}
