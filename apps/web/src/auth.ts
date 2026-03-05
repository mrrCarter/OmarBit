import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID!,
      clientSecret: process.env.GITHUB_CLIENT_SECRET!,
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    jwt({ token, profile }) {
      if (profile) {
        token.github_id = String(profile.id);
        token.username = (profile as { login?: string }).login ?? profile.name;
      }
      return token;
    },
    session({ session, token }) {
      return {
        ...session,
        user: {
          ...session.user,
          github_id: token.github_id as string,
          username: token.username as string,
        },
      };
    },
  },
});
