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

function errorResponse(code: string, message: string, status: number) {
  return NextResponse.json(
    {
      error: { code, message },
      requestId: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
    },
    { status }
  );
}

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return errorResponse("UNAUTHORIZED", "Not authenticated", 401);
  }

  const secret = process.env.NEXTAUTH_SECRET;
  if (!secret) {
    return errorResponse("SERVER_ERROR", "Auth secret not configured", 500);
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
    return errorResponse("UNAUTHORIZED", "Session missing required user claims", 401);
  }

  if (!checkRateLimit(userId || githubId)) {
    return errorResponse("RATE_LIMITED", "Too many token requests", 429);
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
