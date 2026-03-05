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

  const user = session.user as { github_id?: string; username?: string; name?: string };

  const token = await new SignJWT({
    github_id: user.github_id ?? "",
    username: user.username ?? user.name ?? "",
  })
    .setProtectedHeader({ alg: "HS256" })
    .setExpirationTime("8h")
    .setIssuedAt()
    .sign(new TextEncoder().encode(secret));

  return NextResponse.json({ token });
}
