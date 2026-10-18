import type { Metadata } from "next";
import "./globals.css";

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
  metadataBase: new URL("https://mygovt.tn.gov.in"),
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
      </head>
      <body className="min-h-screen bg-slate-50">{children}</body>
    </html>
  );
}
