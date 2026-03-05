"use client";

import { useSession } from "next-auth/react";
import { useEffect, useState } from "react";

type Provider = "claude" | "gpt" | "grok" | "gemini";
type Style = "aggressive" | "positional" | "balanced" | "chaotic" | "defensive";

interface ModelOption {
  id: string;
  name: string;
  cost_per_1m_input: number;
  cost_per_1m_output: number;
}

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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

function formatCost(cost: number): string {
  if (cost < 1) return `$${cost.toFixed(2)}`;
  return `$${cost.toFixed(2)}`;
}

export default function RegisterAI() {
  const { data: session, status } = useSession();
  const [displayName, setDisplayName] = useState("");
  const [provider, setProvider] = useState<Provider>("claude");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [style, setStyle] = useState<Style>("balanced");
  const [customInstructions, setCustomInstructions] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [allModels, setAllModels] = useState<Record<string, ModelOption[]>>({});

  // Load available models
  useEffect(() => {
    async function loadModels() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/providers/models`);
        if (res.ok) {
          const data = await res.json();
          setAllModels(data);
          // Set default model for initial provider
          if (data.claude?.length > 0) {
            setModel(data.claude[0].id);
          }
        }
      } catch {
        // ignore
      }
    }
    loadModels();
  }, []);

  // Update model when provider changes
  const providerModels = allModels[provider] ?? [];
  const selectedModel = providerModels.find((m) => m.id === model);

  function handleProviderChange(p: Provider) {
    setProvider(p);
    const models = allModels[p] ?? [];
    setModel(models.length > 0 ? models[0].id : "");
  }

  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.name.endsWith(".md") && !file.name.endsWith(".txt")) {
      setResult({ success: false, message: "Only .md and .txt files are supported" });
      return;
    }
    if (file.size > 50 * 1024) {
      setResult({ success: false, message: "File must be under 50KB" });
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const content = reader.result as string;
      setCustomInstructions((prev) => {
        const combined = prev ? prev + "\n\n" + content : content;
        return combined.slice(0, 15000);
      });
    };
    reader.readAsText(file);
    e.target.value = "";
  }

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
      const tokenRes = await fetch("/api/auth/token");
      if (!tokenRes.ok) {
        setResult({ success: false, message: "Failed to get auth token" });
        return;
      }
      const { token } = await tokenRes.json();

      const idempotencyKey = crypto.randomUUID();
      const res = await fetch(`${API_BASE}/api/v1/ai-profiles`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({
          display_name: displayName,
          provider,
          model,
          api_key: apiKey,
          style,
          custom_instructions: customInstructions || null,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setResult({
          success: true,
          message: `AI "${data.display_name}" registered successfully!`,
        });
        setDisplayName("");
        setApiKey("");
        setCustomInstructions("");
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

      <form onSubmit={handleSubmit} className="mt-8 flex max-w-lg flex-col gap-5">
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
            onChange={(e) => handleProviderChange(e.target.value as Provider)}
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
          <label htmlFor="model" className="text-sm font-medium text-zinc-300">
            Model
          </label>
          <select
            id="model"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white focus:border-zinc-500 focus:outline-none"
          >
            {providerModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
          {selectedModel && (
            <p className="text-xs text-zinc-500">
              Cost: {formatCost(selectedModel.cost_per_1m_input)}/1M input,{" "}
              {formatCost(selectedModel.cost_per_1m_output)}/1M output tokens
            </p>
          )}
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
            Your key is validated on save and encrypted with AES-256-GCM.
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

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center justify-between">
            <label htmlFor="instructions" className="text-sm font-medium text-zinc-300">
              Custom Instructions{" "}
              <span className="font-normal text-zinc-500">(optional)</span>
            </label>
            <span className="text-xs text-zinc-600">
              {customInstructions.length.toLocaleString()} / 15,000
            </span>
          </div>
          <textarea
            id="instructions"
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value.slice(0, 15000))}
            rows={6}
            className="rounded-md border border-zinc-700 bg-zinc-900 px-3 py-2 text-sm text-white placeholder-zinc-500 focus:border-zinc-500 focus:outline-none"
            placeholder="Specific chess strategy instructions for your AI...&#10;&#10;e.g., &quot;Always play the King's Indian Defense as black. Prefer sharp, tactical positions. Castle kingside early.&quot;"
          />
          <div className="flex items-center gap-2">
            <label className="cursor-pointer rounded border border-zinc-700 px-2.5 py-1 text-xs text-zinc-400 transition-colors hover:border-zinc-500 hover:text-white">
              Upload .md file
              <input
                type="file"
                accept=".md,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
            <span className="text-xs text-zinc-600">Max 50KB</span>
          </div>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="mt-2 rounded-md bg-white px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-zinc-200 disabled:opacity-50"
        >
          {submitting ? "Validating & Registering..." : "Register AI"}
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
