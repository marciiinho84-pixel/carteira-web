import type { Metadata } from "next";
import { Geist, Geist_Mono, Source_Serif_4, IBM_Plex_Mono } from "next/font/google";
import { Providers } from "./providers";
import PaperTexture from "@/components/PaperTexture";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Papel & Tinta — títulos e valores-hero
const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin"],
  weight: ["400", "600", "700"],
});

// Papel & Tinta — todo número (preços, %, tabelas)
const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "App Minha Carteira",
  description: "Gestão de investimentos pessoais",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="pt-BR"
      className={`${geistSans.variable} ${geistMono.variable} ${sourceSerif.variable} ${plexMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col relative">
        <PaperTexture />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
