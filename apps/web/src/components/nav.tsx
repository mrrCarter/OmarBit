"use client";

import Link from "next/link";
import { useSession, signIn, signOut } from "next-auth/react";

export function Nav() {
  const { data: session, status } = useSession();

  return (
    <nav className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
      <Link href="/" className="text-xl font-bold tracking-tight text-white">
        OmarBit
      </Link>
      <div className="flex items-center gap-4">
        <Link
          href="/register-ai"
          className="text-sm text-zinc-400 transition-colors hover:text-white"
        >
          Register AI
        </Link>
        <span className="text-sm text-zinc-600">|</span>
        <span className="cursor-not-allowed text-sm text-zinc-600">
          Leaderboard
          <span className="ml-1 rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500">
            Soon
          </span>
        </span>
        <span className="text-sm text-zinc-600">|</span>
        <span className="cursor-not-allowed text-sm text-zinc-600">
          Matches
          <span className="ml-1 rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500">
            Soon
          </span>
        </span>
        {status === "loading" ? (
          <span className="text-sm text-zinc-500">...</span>
        ) : session ? (
          <div className="flex items-center gap-3">
            <span className="text-sm text-zinc-300">
              {session.user?.name}
            </span>
            <button
              onClick={() => signOut()}
              className="rounded-md bg-zinc-800 px-3 py-1.5 text-sm text-zinc-300 transition-colors hover:bg-zinc-700"
            >
              Sign out
            </button>
          </div>
        ) : (
          <button
            onClick={() => signIn("github")}
            className="rounded-md bg-white px-3 py-1.5 text-sm font-medium text-black transition-colors hover:bg-zinc-200"
          >
            Sign in with GitHub
          </button>
        )}
      </div>
    </nav>
  );
}
