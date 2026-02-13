"use client";

import { useLocale } from "next-intl";
import { Link, usePathname } from "@/i18n/navigation";

export default function LanguageSwitcher() {
  const locale = useLocale();
  const pathname = usePathname();
  const next = locale === "ar" ? "en" : "ar";

  return (
    <Link
      href={pathname}
      locale={next}
      className="flex w-full items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-sidebar-accent/50"
    >
      {locale === "ar" ? "English" : "العربية"}
    </Link>
  );
}
