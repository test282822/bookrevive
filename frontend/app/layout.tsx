import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { DM_Serif_Display, DM_Sans } from "next/font/google";
import "./globals.css";

const dmSerif = DM_Serif_Display({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-serif",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "BookRevive — Digitize Old Books",
  description: "Turn phone photos of old books into polished EPUB files.",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "BookRevive",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#0d0d0d",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <ClerkProvider>
      <html lang="en" className={`${dmSerif.variable} ${dmSans.variable}`}>
        <body className="bg-stone-950 text-stone-100 font-sans antialiased min-h-screen">
          {/* TOP AD SLOT — swap this comment for your AdSense script tag when ready */}
          {/* <AdSlot slot="top-banner" /> */}

          <main className="max-w-2xl mx-auto px-4 pb-24">
            {children}
          </main>

          {/* BOTTOM AD SLOT */}
          {/* <AdSlot slot="bottom-banner" /> */}
        </body>
      </html>
    </ClerkProvider>
  );
}
