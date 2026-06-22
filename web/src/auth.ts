import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

const API_INTERNAL =
  process.env.API_BASE_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "https://minhacarteira.duckdns.org/api/v1";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID ?? "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET ?? "",
    }),
  ],

  callbacks: {
    async jwt({ token, account }) {
      if (account?.id_token) {
        try {
          const res = await fetch(`${API_INTERNAL}/auth/google`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id_token: account.id_token }),
          });
          if (res.ok) {
            const data = (await res.json()) as { access_token: string };
            token.apiToken = data.access_token;
          } else {
            const err = await res.json().catch(() => ({}));
            token.error = (err as { detail?: string }).detail ?? "auth_failed";
          }
        } catch (e) {
          token.error = String(e);
        }
      }
      return token;
    },

    async session({ session, token }) {
      return {
        ...session,
        apiToken: token.apiToken as string | undefined,
        error: token.error as string | undefined,
      };
    },
  },

  pages: {
    signIn: "/login",
    error: "/login",
  },
});
