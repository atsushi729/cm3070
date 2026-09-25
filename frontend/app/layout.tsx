import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "SME AI Assistant",
  description: "Locally deployed AI assistant for hospitality SMEs",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden bg-slate-50 text-slate-900">
        <Sidebar />
        <div className="h-screen min-w-0 flex-1 overflow-y-auto">
          {children}
        </div>
      </body>
    </html>
  );
}
