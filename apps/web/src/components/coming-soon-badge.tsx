export function ComingSoonBadge({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 px-4 py-3 opacity-60">
      <span className="text-sm text-zinc-400">{label}</span>
      <span className="rounded bg-amber-900/30 px-2 py-0.5 text-xs font-medium text-amber-500">
        Coming Soon
      </span>
    </div>
  );
}
