import type { DefaultSession } from "next-auth";

declare module "next-auth" {
  interface Session extends DefaultSession {
    apiToken?: string;
    error?: string;
  }
}

declare module "next-auth/jwt" {
  interface JWT {
    apiToken?: string;
    error?: string;
  }
}
