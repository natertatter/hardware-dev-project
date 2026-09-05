import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "EDA Platform — Schematic Editor",
  description: "Visual hardware schematic editor for robotics EDA platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
