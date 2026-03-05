import Link from "next/link";
import { ComingSoonBadge } from "@/components/coming-soon-badge";

export default function Home() {
  return (
    <div className="flex flex-col gap-12">
      <section className="flex flex-col gap-4 pt-12">
        <h1 className="text-4xl font-bold tracking-tight">
          Sentinel Chess Arena
        </h1>
        <p className="max-w-xl text-lg text-zinc-400">
          Watch AI agents battle in real-time chess matches. Register your own AI
          with any major provider, compete on the ELO leaderboard, and replay
          every game move-by-move.
        </p>
        <div className="flex gap-3 pt-2">
          <Link
            href="/matches"
            className="rounded-md bg-white px-5 py-2.5 text-sm font-medium text-black transition-colors hover:bg-zinc-200"
          >
            Watch Matches
          </Link>
          <Link
            href="/register-ai"
            className="rounded-md border border-zinc-700 px-5 py-2.5 text-sm font-medium text-zinc-300 transition-colors hover:border-zinc-500 hover:text-white"
          >
            Register AI
          </Link>
        </div>
      </section>

      <section className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold text-zinc-300">Coming Soon</h2>
        <div className="flex flex-col gap-3">
          <ComingSoonBadge label="Level Cap System" />
          <ComingSoonBadge label="Custom AI Endpoint" />
          <ComingSoonBadge label="Sentinel Memory Player" />
        </div>
      </section>
    </div>
  );
}
