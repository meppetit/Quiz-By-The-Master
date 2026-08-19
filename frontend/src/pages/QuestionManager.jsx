import { useCallback, useEffect, useState } from "react";
import { Check, Plus, Trash2, Upload, X } from "lucide-react";
import { api, errText } from "../lib/api";

const LETTERS = ["A", "B", "C", "D"];
const EMPTY = { question_text: "", options: { A: "", B: "", C: "", D: "" }, correct_option: "A", category: "" };

const SAMPLE = `1. Which data structure gives O(1) average-time lookup by key?
A) Hash map
B) Linked list
C) Binary search tree
D) Array (unsorted)
Category: Data Structures
Answer: A`;

export default function QuestionManager({ onUnauthorized }) {
  const [sets, setSets] = useState([]);
  const [setId, setSetId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [draft, setDraft] = useState(EMPTY);
  const [editingId, setEditingId] = useState(null);
  const [raw, setRaw] = useState("");
  const [replace, setReplace] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const fail = (e) => {
    if (e?.response?.status === 401) return onUnauthorized?.();
    setError(errText(e));
  };

  const loadSets = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/sets");
      setSets(data);
      setSetId((cur) => cur ?? data[0]?.id ?? null);
    } catch (e) { fail(e); }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadQuestions = useCallback(async () => {
    if (!setId) return;
    try {
      const { data } = await api.get(`/admin/sets/${setId}/questions`);
      setQuestions(data);
    } catch (e) { fail(e); }
  }, [setId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { loadSets(); }, [loadSets]);
  useEffect(() => { loadQuestions(); }, [loadQuestions]);

  const save = async () => {
    setError(""); setMsg("");
    try {
      const body = { ...draft, category: draft.category || null };
      if (editingId) await api.put(`/admin/questions/${editingId}`, body);
      else await api.post(`/admin/sets/${setId}/questions`, body);
      setDraft(EMPTY); setEditingId(null);
      setMsg(editingId ? "Question updated." : "Question added.");
      await loadQuestions(); await loadSets();
    } catch (e) { fail(e); }
  };

  const remove = async (id) => {
    try {
      await api.delete(`/admin/questions/${id}`);
      await loadQuestions(); await loadSets();
    } catch (e) { fail(e); }
  };

  const doImport = async () => {
    setError(""); setMsg("");
    try {
      const { data } = await api.post(`/admin/sets/${setId}/import`, { raw_text: raw, replace });
      setMsg(`Imported ${data.imported} question(s).`);
      setError((data.errors || []).join(" | "));
      setRaw("");
      await loadQuestions(); await loadSets();
    } catch (e) { fail(e); }
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (file) setRaw(await file.text());
  };

  return (
    <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-[220px_1fr]" data-testid="questions-panel">
      <div className="rounded-2xl border border-zinc-800 bg-[#121214] p-3">
        <p className="mep-label px-2 py-2">Question sets</p>
        <div className="max-h-[560px] space-y-1 overflow-y-auto">
          {sets.map((s) => (
            <button
              key={s.id}
              data-testid={`set-${s.id}`}
              onClick={() => setSetId(s.id)}
              className={`flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm transition-colors ${
                setId === s.id ? "bg-[#c6f24e]/10 text-[#c6f24e]" : "text-zinc-400 hover:bg-zinc-800/60"
              }`}
            >
              <span>{s.name}</span>
              <span className="text-xs text-zinc-600">{s.question_count}q · {s.attempt_count}a</span>
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-6">
        <div className="rounded-2xl border border-zinc-800 bg-[#121214] p-6">
          <p className="mep-label">Bulk paste / upload</p>
          <p className="mt-2 text-xs text-zinc-500">
            Blank line between questions. Format: question, then A) B) C) D) options, optional <code>Category:</code>, then <code>Answer: B</code>.
          </p>
          <textarea
            data-testid="import-textarea"
            className="mep-input mt-4 h-44 font-mono text-xs"
            placeholder={SAMPLE}
            value={raw}
            onChange={(e) => setRaw(e.target.value)}
          />
          <div className="mt-4 flex flex-wrap items-center gap-4">
            <input data-testid="import-file" type="file" accept=".txt,.md,.csv" onChange={onFile} className="text-xs text-zinc-500" />
            <label className="flex items-center gap-2 text-xs text-zinc-400">
              <input data-testid="import-replace" type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
              Replace existing questions in this set
            </label>
            <button data-testid="import-btn" onClick={doImport} disabled={!raw.trim()} className="ml-auto flex h-10 items-center gap-2 rounded-full bg-[#c6f24e] px-5 text-sm font-bold text-black disabled:opacity-40">
              <Upload className="h-4 w-4" /> Import
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-[#121214] p-6">
          <p className="mep-label">{editingId ? "Edit question" : "Add question manually"}</p>
          <input data-testid="q-text" className="mep-input mt-4" placeholder="Question text" value={draft.question_text} onChange={(e) => setDraft({ ...draft, question_text: e.target.value })} />
          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            {LETTERS.map((l) => (
              <div key={l} className="flex items-center gap-3">
                <button
                  data-testid={`q-correct-${l}`}
                  onClick={() => setDraft({ ...draft, correct_option: l })}
                  className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-sm font-bold ${
                    draft.correct_option === l ? "bg-[#c6f24e] text-black" : "bg-zinc-800 text-zinc-400"
                  }`}
                  title="Mark as correct answer"
                >
                  {draft.correct_option === l ? <Check className="h-4 w-4" /> : l}
                </button>
                <input
                  data-testid={`q-option-${l}`}
                  className="mep-input"
                  placeholder={`Option ${l}`}
                  value={draft.options[l]}
                  onChange={(e) => setDraft({ ...draft, options: { ...draft.options, [l]: e.target.value } })}
                />
              </div>
            ))}
          </div>
          <input data-testid="q-category" className="mep-input mt-4 max-w-xs" placeholder="Category (optional)" value={draft.category || ""} onChange={(e) => setDraft({ ...draft, category: e.target.value })} />
          <div className="mt-5 flex items-center gap-3">
            <button data-testid="q-save-btn" onClick={save} className="flex h-10 items-center gap-2 rounded-full bg-[#c6f24e] px-5 text-sm font-bold text-black">
              <Plus className="h-4 w-4" /> {editingId ? "Save changes" : "Add question"}
            </button>
            {editingId && (
              <button data-testid="q-cancel-btn" onClick={() => { setEditingId(null); setDraft(EMPTY); }} className="flex h-10 items-center gap-2 rounded-full border border-zinc-800 px-4 text-sm text-zinc-400">
                <X className="h-4 w-4" /> Cancel
              </button>
            )}
          </div>
          {msg && <p data-testid="q-msg" className="mt-4 text-sm text-[#c6f24e]">{msg}</p>}
          {error && <p data-testid="q-error" className="mt-3 rounded-xl border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300">{error}</p>}
        </div>

        <div className="rounded-2xl border border-zinc-800 bg-[#121214] p-6">
          <p className="mep-label">Questions in this set ({questions.length})</p>
          <div className="mt-4 space-y-2" data-testid="question-list">
            {questions.map((q, i) => (
              <div key={q.id} className="rounded-xl border border-zinc-800/60 px-4 py-3">
                <div className="flex items-start gap-3">
                  <span className="mt-0.5 text-xs tabular-nums text-zinc-600">{i + 1}</span>
                  <div className="flex-1">
                    <p className="text-sm text-white">{q.question_text}</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      Answer <span className="text-[#c6f24e]">{q.correct_option}</span>
                      {q.category ? ` · ${q.category}` : ""}
                    </p>
                  </div>
                  <button data-testid={`q-edit-${q.id}`} onClick={() => { setEditingId(q.id); setDraft({ ...q, category: q.category || "" }); }} className="text-xs text-zinc-400 hover:text-white">Edit</button>
                  <button data-testid={`q-delete-${q.id}`} onClick={() => remove(q.id)} className="text-zinc-500 hover:text-red-400"><Trash2 className="h-4 w-4" /></button>
                </div>
              </div>
            ))}
            {!questions.length && <p className="text-sm text-zinc-600">No questions in this set yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
