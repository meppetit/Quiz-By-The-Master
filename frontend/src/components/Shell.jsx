export const Shell = ({ children, live = true }) => (
  <div className="min-h-screen relative bg-[#09090b]">
    <div className="mep-grid-bg" />
    <div className="relative z-10 mx-auto w-full max-w-[430px] px-6 py-7">
      <div className="flex items-center justify-between mb-8">
        <span className="font-display text-sm tracking-[0.18em] text-zinc-400">
          MEP <span className="text-white font-extrabold">QUIZ</span>
        </span>
        {live && (
          <span
            data-testid="live-pill"
            className="flex items-center gap-1.5 rounded-full border border-zinc-800 bg-[#121214] px-3 py-1 text-[10px] font-bold tracking-wider text-zinc-300"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#c6f24e]" />
            LIVE
          </span>
        )}
      </div>
      {children}
    </div>
  </div>
);

export const Tag = ({ children, testid }) => (
  <span
    data-testid={testid}
    className="inline-flex items-center gap-1.5 rounded-md border border-[#c6f24e]/40 bg-[#c6f24e]/10 px-2.5 py-1 text-[10px] font-bold tracking-[0.14em] text-[#c6f24e] uppercase"
  >
    <span className="h-1.5 w-1.5 rounded-full bg-[#c6f24e]" />
    {children}
  </span>
);
