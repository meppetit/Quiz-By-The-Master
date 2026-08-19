import { useEffect } from "react";
import { CheckCircle2 } from "lucide-react";
import { Shell, Tag } from "../components/Shell";

export default function Completion() {
  useEffect(() => {
    localStorage.removeItem("mep_attempt_token");
  }, []);

  return (
    <Shell>
      <div className="mep-rise pt-10" data-testid="completion-screen">
        <Tag testid="completion-tag">Run complete</Tag>
        <div className="mt-7 rounded-[24px] border border-zinc-800/70 bg-[#121214] p-7">
          <CheckCircle2 className="h-11 w-11 text-[#c6f24e]" />
          <h1 className="font-display mt-6 text-4xl font-black leading-[1.05] tracking-tight text-white">
            Thanks for participating.
          </h1>
          <p className="mt-4 text-sm leading-relaxed text-zinc-400">
            Your answers are locked in. Results are with the organisers — keep an eye on the main screen.
          </p>
        </div>
        <p className="mt-6 text-center text-[11px] text-zinc-600">You can close this window now.</p>
      </div>
    </Shell>
  );
}
