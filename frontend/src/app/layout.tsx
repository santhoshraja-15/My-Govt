import type { Metadata } from "next";
import "./globals.css";
import { Inter, Noto_Sans_Tamil } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import { LangProvider } from "@/lib/i18n";
import { SiteHeader } from "@/components/layout/SiteHeader";
import { ToastProvider } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: {
    default: "MyGovt — Your Government. Your Services. Your Voice.",
    template: "%s | MyGovt Tamil Nadu",
  },
  description:
    "AI-powered citizen intelligence platform for Tamil Nadu government schemes, services, complaints and information — in English and Tamil.",
  keywords: ["Tamil Nadu", "government schemes", "e-Sevai", "citizen services", "AI assistant", "complaints"],
  authors: [{ name: "MyGovt Tamil Nadu" }],
  openGraph: {
    title: "MyGovt — Tamil Nadu Citizen Intelligence Platform",
    description: "Find government schemes, track complaints, and get AI-powered answers about Tamil Nadu government services.",
    type: "website",
    locale: "en_IN",
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"),
};

// Self-hosted at build time (no request to Google when a citizen loads a page).
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const notoTamil = Noto_Sans_Tamil({ subsets: ["tamil"], variable: "--font-tamil", display: "swap" });

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${notoTamil.variable}`}>
      <body className="min-h-screen bg-slate-50">
        <LangProvider>
          <AuthProvider>
            <ToastProvider>
              <SiteHeader />
              {children}
            </ToastProvider>
          </AuthProvider>
        </LangProvider>
      </body>
    </html>
  );
}
