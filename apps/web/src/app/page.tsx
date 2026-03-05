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
