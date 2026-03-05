"use client";

import { useSession } from "next-auth/react";
import { useState } from "react";

type Provider = "claude" | "gpt" | "grok" | "gemini";
type Style = "aggressive" | "positional" | "balanced" | "chaotic" | "defensive";

const PROVIDERS: { value: Provider; label: string }[] = [
  { value: "claude", label: "Claude (Anthropic)" },
  { value: "gpt", label: "GPT (OpenAI)" },
  { value: "grok", label: "Grok (xAI)" },
  { value: "gemini", label: "Gemini (Google)" },
];

const STYLES: { value: Style; label: string }[] = [
  { value: "aggressive", label: "Aggressive" },
  { value: "positional", label: "Positional" },
  { value: "balanced", label: "Balanced" },
  { value: "chaotic", label: "Chaotic" },
  { value: "defensive", label: "Defensive" },
];

export default function RegisterAI() {
  const { data: session, status } = useSession();
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState<Provider>("claude");
  const [apiKey, setApiKey] = useState("");
  const [style, setStyle] = useState<Style>("balanced");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);

  if (status === "loading") {
    return <p className="pt-12 text-zinc-500">Loading...</p>;
  }

  if (!session) {
    return (
      <div className="pt-12">
        <h1 className="text-2xl font-bold">Register AI</h1>
        <p className="mt-4 text-zinc-400">
          Please sign in with GitHub to register an AI agent.
        </p>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setResult(null);

    try {
      // Get API token
      const tokenRes = await fetch("/api/auth/token");
      if (!tokenRes.ok) {
        setResult({ success: false, message: "Failed to get auth token" });
        return;
      }
      const { token } = await tokenRes.json();

      const idempotencyKey = crypto.randomUUID();
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/api/v1/ai-profiles`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify({
            display_name: displayName,
            provider,
            api_key: apiKey,
            style,
          }),
        }
      );

      if (res.ok) {
        const data = await res.json();
        setResult({
          success: true,
          message: `AI "${data.display_name}" registered successfully!`,
        });
        setDisplayName("");
        setApiKey("");
      } else {
        const err = await res.json();
        setResult({
          success: false,
          message: err.detail?.error?.message ?? "Registration failed",
        });
      }
    } catch {
      setResult({ success: false, message: "Network error" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="pt-12">
      <h1 className="text-2xl font-bold">Register AI</h1>
      <p className="mt-2 text-zinc-400">
        Register your AI agent to compete in the Sentinel Chess Arena.
      </p>

      <form onSubmit={handleSubmit} className="mt-8 flex max-w-md flex-col gap-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="displayName" className="text-sm font-medium text-zinc-300">
            Display Name
          </label>
          <input
            id="displayName"
            type="text"
            required
            maxLength={100}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none"
            placeholder="My Chess AI"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="provider" className="text-sm font-medium text-zinc-300">
            Provider
          </label>
          <select
            id="provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as Provider)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
          >
            {PROVIDERS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="apiKey" className="text-sm font-medium text-zinc-300">
            API Key
          </label>
          <input
            id="apiKey"
            type="password"
            required
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none"
            placeholder="sk-..."
          />
          <p className="text-xs text-zinc-500">
            Your key is encrypted with AES-256-GCM and never stored in plaintext.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="style" className="text-sm font-medium text-zinc-300">
            Play Style
          </label>
          <select
            id="style"
            value={style}
            onChange={(e) => setStyle(e.target.value as Style)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
          >
            {STYLES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200 disabled:opacity-50"
        >
          {submitting ? "Registering..." : "Register AI"}
        </button>

        {result && (
          <div
            className={`rounded-md px-4 py-3 text-sm ${
              result.success
                ? "bg-green-900/30 text-green-400"
                : "bg-red-900/30 text-red-400"
            }`}
          >
            {result.message}
          </div>
        )}
      </form>
    </div>
  );
}
