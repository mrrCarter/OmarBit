import { NextResponse } from "next/server";
import { SignJWT } from "jose";
import { auth } from "@/auth";

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

  if (!githubId || !username) {
    return NextResponse.json(
      { error: { code: "UNAUTHORIZED", message: "Session missing required user claims" } },
      { status: 401 }
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
