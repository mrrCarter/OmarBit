"use client";

import Link from "next/link";
import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

interface AIProfile {
  id: string;
  display_name: string;
  provider: string;
  model: string;
  style: string;
  active: boolean;
  created_at: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function MyAIsPage() {
  const { status: authStatus } = useSession();
  const [profiles, setProfiles] = useState<AIProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProfiles = useCallback(async () => {
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
        setProfiles(data.profiles ?? []);
      }
    } catch {
      // API might not be up
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (authStatus === "authenticated") {
      loadProfiles();
    } else if (authStatus === "unauthenticated") {
      setLoading(false);
    }
  }, [authStatus, loadProfiles]);

  async function handleDelete(profileId: string) {
    if (!confirm("Deactivate this AI? It will no longer be available for matches.")) return;
    setDeleting(profileId);
    setError(null);

    try {
      const tokenRes = await fetch("/api/auth/token", {
        signal: AbortSignal.timeout(5000),
      });
      if (!tokenRes.ok) return;
      const { token } = await tokenRes.json();

      const res = await fetch(`${API_BASE}/api/v1/ai-profiles/${profileId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
        signal: AbortSignal.timeout(10000),
      });

      if (res.ok) {
        setProfiles((prev) => prev.filter((p) => p.id !== profileId));
      } else {
        const data = await res.json();
        setError(data?.detail?.error?.message ?? "Failed to delete");
      }
    } catch {
      setError("Network error");
    } finally {
      setDeleting(null);
    }
  }

  async function handleToggleActive(profile: AIProfile) {
    try {
      const tokenRes = await fetch("/api/auth/token", {
        signal: AbortSignal.timeout(5000),
      });
      if (!tokenRes.ok) return;
      const { token } = await tokenRes.json();

      const res = await fetch(`${API_BASE}/api/v1/ai-profiles/${profile.id}`, {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ active: !profile.active }),
        signal: AbortSignal.timeout(10000),
      });

      if (res.ok) {
        const updated = await res.json();
        setProfiles((prev) =>
          prev.map((p) => (p.id === profile.id ? { ...p, active: updated.active } : p))
        );
      }
    } catch {
      // ignore
    }
  }

  if (authStatus === "unauthenticated") {
    return (
      <div className="flex flex-col items-center gap-4 pt-16">
        <h1 className="text-2xl font-bold">My AIs</h1>
        <p className="text-zinc-400">Sign in to manage your AI profiles.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6 pt-8">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">My AIs</h1>
        <Link
          href="/register-ai"
          className="rounded bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200"
        >
          Register New AI
        </Link>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-900/30 px-4 py-2 text-sm text-red-400">
          {error}
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-lg border border-zinc-800 bg-zinc-900/50" />
          ))}
        </div>
      ) : profiles.length === 0 ? (
        <div className="rounded-lg border border-zinc-800 p-8 text-center">
          <p className="text-zinc-400">
            No AI profiles yet.{" "}
            <Link href="/register-ai" className="text-white underline">
              Register your first AI
            </Link>{" "}
            to get started!
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {profiles.map((profile) => (
            <div
              key={profile.id}
              className={`flex items-center justify-between rounded-lg border p-4 transition-colors ${
                profile.active
                  ? "border-zinc-800 bg-zinc-900/30"
                  : "border-zinc-800/50 bg-zinc-900/10 opacity-60"
              }`}
            >
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-white">{profile.display_name}</span>
                  {!profile.active && (
                    <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] font-semibold text-zinc-500">
                      INACTIVE
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-500">
                  <span className="capitalize">{profile.provider}</span>
                  {profile.model && (
                    <>
                      <span className="text-zinc-700">/</span>
                      <span>{profile.model}</span>
                    </>
                  )}
                  <span className="text-zinc-700">|</span>
                  <span className="capitalize">{profile.style}</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  href={`/my-ais/${profile.id}/matches`}
                  className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                >
                  Matches
                </Link>
                <button
                  onClick={() => handleToggleActive(profile)}
                  className="rounded border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:bg-zinc-800 hover:text-white"
                >
                  {profile.active ? "Deactivate" : "Activate"}
                </button>
                <button
                  onClick={() => handleDelete(profile.id)}
                  disabled={deleting === profile.id}
                  className="rounded border border-red-900/50 px-3 py-1.5 text-xs text-red-400 transition-colors hover:bg-red-900/30 disabled:opacity-50"
                >
                  {deleting === profile.id ? "..." : "Delete"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
