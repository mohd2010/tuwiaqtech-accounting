"use client";

import { useState } from "react";
import { format, startOfMonth, endOfMonth, subMonths, startOfYear } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";

interface DateRangePickerProps {
  fromDate: Date;
  toDate: Date;
  onChange: (from: Date, to: Date) => void;
}

export default function DateRangePicker({
  fromDate,
  toDate,
  onChange,
}: DateRangePickerProps) {
  const t = useTranslations("reportFilters");
  const [fromOpen, setFromOpen] = useState(false);
  const [toOpen, setToOpen] = useState(false);

  const presets = [
    {
      label: t("currentMonth"),
      from: startOfMonth(new Date()),
      to: new Date(),
    },
    {
      label: t("lastMonth"),
      from: startOfMonth(subMonths(new Date(), 1)),
      to: endOfMonth(subMonths(new Date(), 1)),
    },
    {
      label: t("lastQuarter"),
      from: startOfMonth(subMonths(new Date(), 3)),
      to: endOfMonth(subMonths(new Date(), 1)),
    },
    {
      label: t("yearToDate"),
      from: startOfYear(new Date()),
      to: new Date(),
    },
  ];

  return (
    <div className="mb-6 flex flex-wrap items-center gap-3">
      {/* From date */}
      <Popover open={fromOpen} onOpenChange={setFromOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className={cn(
              "w-[160px] justify-start text-left font-normal",
              !fromDate && "text-muted-foreground",
            )}
          >
            <CalendarIcon className="ltr:mr-2 rtl:ml-2 size-4" />
            {format(fromDate, "yyyy-MM-dd")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={fromDate}
            onSelect={(d) => {
              if (d) {
                onChange(d, toDate);
                setFromOpen(false);
              }
            }}
            initialFocus
          />
        </PopoverContent>
      </Popover>

      <span className="text-sm text-muted-foreground">{t("to")}</span>

      {/* To date */}
      <Popover open={toOpen} onOpenChange={setToOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className={cn(
              "w-[160px] justify-start text-left font-normal",
              !toDate && "text-muted-foreground",
            )}
          >
            <CalendarIcon className="ltr:mr-2 rtl:ml-2 size-4" />
            {format(toDate, "yyyy-MM-dd")}
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <Calendar
            mode="single"
            selected={toDate}
            onSelect={(d) => {
              if (d) {
                onChange(fromDate, d);
                setToOpen(false);
              }
            }}
            initialFocus
          />
        </PopoverContent>
      </Popover>

      {/* Presets */}
      <div className="flex gap-1">
        {presets.map((p) => (
          <Button
            key={p.label}
            variant="ghost"
            size="sm"
            className="text-xs"
            onClick={() => onChange(p.from, p.to)}
          >
            {p.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
