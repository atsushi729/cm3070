"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/reservations", label: "Voice Reservation" },
  { href: "/marketing", label: "AI Marketing" },
  { href: "/reviews", label: "Review Sentiment" },
] as const;

const SETTINGS_LINK = { href: "/settings", label: "Setting" } as const;

export default function Sidebar() {
  const pathname = usePathname();

  const renderLink = (link: { href: string; label: string }) => {
    const active = pathname?.startsWith(link.href) ?? false;
    return (
      <li key={link.href}>
        <Link
          href={link.href}
          className={`block rounded-md px-3 py-2 text-sm font-medium ${
            active
              ? "bg-slate-900 text-white"
              : "text-slate-600 hover:bg-slate-100"
          }`}
        >
          {link.label}
        </Link>
      </li>
    );
  };

  return (
    <nav className="flex h-screen w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-white px-3 py-6">
      <div className="mb-6 px-2 text-sm font-bold text-slate-900">
        SME AI Assistant
      </div>
      <ul className="space-y-1">{LINKS.map(renderLink)}</ul>
      <ul className="mt-auto space-y-1 border-t border-slate-200 pt-3">
        {renderLink(SETTINGS_LINK)}
      </ul>
    </nav>
  );
}
