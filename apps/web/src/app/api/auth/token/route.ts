import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import { auth } from "@/auth";

// Simple in-memory rate limiter: max 10 tokens per user per minute
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 10;
const rateLimitMap = new Map<string, { count: number; resetAt: number }>();

function checkRateLimit(userId: string): boolean {
  const now = Date.now();
  const entry = rateLimitMap.get(userId);
  if (!entry || now >= entry.resetAt) {
    rateLimitMap.set(userId, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  if (entry.count >= RATE_LIMIT_MAX) return false;
  entry.count++;
  return true;
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Not authenticated" } },
      { status: 401 }
    );
  }

  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    return NextResponse.json(
      { error: { code: "SERVER_ERROR", message: "Auth secret not configured" } },
      { status: 500 }
    );
  }

  const user = session.user as {
    id?: string;
    github_id?: string;
    username?: string;
    name?: string;
  };

  const githubId = user.github_id ?? "";
  const username = user.username ?? user.name ?? "";
  const userId = user.id ?? "";

  if (!githubId || !username || !userId) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Session missing required user claims" } },
      { status: 401 }
    );
  }

  if (!checkRateLimit(userId || githubId)) {
    return NextResponse.json(
      { error: { code: "RATE_LIMITED", message: "Too many token requests" } },
      { status: 429 }
    );
  }

  const token = await new SignJWT({
    github_id: githubId,
    username: username,
    user_id: userId,
  })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuer("omarbit-web")
    .setAudience("omarbit-api")
    .setExpirationTime("8h")
    .setIssuedAt()
    .sign(new TextEncoder().encode(secret));

  return NextResponse.json(
    { token },
    {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
        Pragma: "no-cache",
      },
    }
  );
}
