"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface AIProfile {
  id: string;
  display_name: string;
  provider: string;
  style: string;
  active: boolean;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function NewMatchPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [profiles, setProfiles] = useState<AIProfile[]>([]);
  const [whiteId, setWhiteId] = useState("");
  const [blackId, setBlackId] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (status !== "authenticated") return;

    async function loadProfiles() {
      try {
        const tokenRes = await fetch("/api/auth/token", {
          signal: AbortSignal.timeout(5000),
        });
        if (!tokenRes.ok) return;
        const { token } = await tokenRes.json();

        const res = await fetch(`${API_BASE}/api/v1/ai-profiles/me`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: AbortSignal.timeout(10000),
        });
        if (res.ok) {
          const data = await res.json();
          const list = data.profiles ?? [];
          setProfiles(list);
          if (list.length >= 2) {
            setWhiteId(list[0].id);
            setBlackId(list[1].id);
          } else if (list.length === 1) {
            setWhiteId(list[0].id);
          }
        }
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    loadProfiles();
  }, [status]);

  if (status === "loading") {
    return <p className="pt-12 text-zinc-500">Loading...</p>;
  }

  if (!session) {
    return (
      <div className="pt-12">
        <h1 className="text-2xl font-bold">New Match</h1>
        <p className="mt-4 text-zinc-400">Please sign in to create a match.</p>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!whiteId || !blackId) {
      setError("Select both white and black AIs");
      return;
    }
    if (whiteId === blackId) {
      setError("White and black must be different AIs");
      return;
    }

    setSubmitting(true);
    setError("");

    try {
      const tokenRes = await fetch("/api/auth/token", {
        signal: AbortSignal.timeout(5000),
      });
      if (!tokenRes.ok) {
        setError("Failed to get auth token");
        return;
      }
      const { token } = await tokenRes.json();

      const res = await fetch(`${API_BASE}/api/v1/matches`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "Idempotency-Key": crypto.randomUUID(),
        },
        body: JSON.stringify({
          white_ai_id: whiteId,
          black_ai_id: blackId,
          time_control: "5+0",
        }),
        signal: AbortSignal.timeout(15000),
      });

      if (res.ok) {
        const data = await res.json();
        router.push(`/matches/${data.id}`);
      } else {
        const err = await res.json();
        setError(err.detail?.error?.message ?? "Failed to create match");
      }
    } catch {
      setError("Network error");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="pt-12">
      <h1 className="text-2xl font-bold">New Match</h1>
      <p className="mt-2 text-zinc-400">
        Select two AI players for a 5+0 blitz match.
      </p>

      {loading ? (
        <p className="mt-8 text-zinc-500">Loading your AIs...</p>
      ) : profiles.length < 2 ? (
        <div className="mt-8 rounded-lg border border-zinc-800 p-6">
          <p className="text-zinc-400">
            You need at least 2 registered AIs to start a match.
          </p>
          <p className="mt-2 text-sm text-zinc-500">
            You have {profiles.length} AI{profiles.length !== 1 ? "s" : ""} registered.{" "}
            <a href="/register-ai" className="text-white underline">
              Register another
            </a>
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-8 flex max-w-md flex-col gap-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="white" className="text-sm font-medium text-zinc-300">
              White
            </label>
            <select
              id="white"
              value={whiteId}
              onChange={(e) => setWhiteId(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name} ({p.provider} / {p.style})
                </option>
              ))}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="black" className="text-sm font-medium text-zinc-300">
              Black
            </label>
            <select
              id="black"
              value={blackId}
              onChange={(e) => setBlackId(e.target.value)}
              className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name} ({p.provider} / {p.style})
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-md border border-zinc-800 px-4 py-3 text-sm text-zinc-400">
            Time control: <strong className="text-white">5+0 blitz</strong>
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="mt-2 rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200 disabled:opacity-50"
          >
            {submitting ? "Creating..." : "Start Match"}
          </button>

          {error && (
            <div className="rounded-md bg-red-900/30 px-4 py-3 text-sm text-red-400">
              {error}
            </div>
          )}
        </form>
      )}
    </div>
  );
}
