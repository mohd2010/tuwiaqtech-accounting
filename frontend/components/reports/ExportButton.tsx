"use client";

import { useState } from "react";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";
import { downloadBlob } from "@/lib/api";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ExportButtonProps {
  baseUrl: string;
  params?: Record<string, string>;
  locale?: string;
}

export default function ExportButton({ baseUrl, params, locale }: ExportButtonProps) {
  const t = useTranslations("reportExport");
  const [loading, setLoading] = useState(false);

  const handleExport = async (format: "excel" | "pdf") => {
    setLoading(true);
    try {
      await downloadBlob(`${baseUrl}/export/${format}`, { ...params, lang: locale ?? "en" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
          disabled={loading}
        >
          <Download className="h-4 w-4" />
          {loading ? t("exporting") : t("export")}
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent>
        <DropdownMenuItem onClick={() => handleExport("excel")}>
          {t("exportExcel")}
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => handleExport("pdf")}>
          {t("exportPdf")}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
