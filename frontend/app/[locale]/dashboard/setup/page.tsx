"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useRouter } from "@/i18n/navigation";
import {
  Building2,
  MapPin,
  CheckCircle2,
  ChevronRight,
  ChevronLeft,
} from "lucide-react";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const STEPS = [
  { icon: Building2, key: "companyInfo" as const },
  { icon: MapPin, key: "address" as const },
  { icon: CheckCircle2, key: "review" as const },
];

export default function SetupPage() {
  const t = useTranslations("setup");
  const to = useTranslations("organization");
  const router = useRouter();
  const { user, refreshUser } = useAuth();

  const [step, setStep] = useState(0);

  // Company info fields
  const [nameEn, setNameEn] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [crNumber, setCrNumber] = useState("");

  // Address fields
  const [street, setStreet] = useState("");
  const [buildingNumber, setBuildingNumber] = useState("");
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [province, setProvince] = useState("");

  const [error, setError] = useState("");

  const userPerms = user?.permissions ?? [];
  const canWrite = userPerms.includes("organization:write");

  // If org is already configured, redirect to dashboard
  if (user?.orgConfigured) {
    router.replace("/dashboard");
    return null;
  }

  // Non-admin users without permission see a message
  if (user && !canWrite) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Card className="max-w-md">
          <CardHeader className="text-center">
            <Building2 className="mx-auto size-12 text-muted-foreground" />
            <CardTitle className="mt-4">{t("waitingSetup")}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-center text-muted-foreground">
              {t("noPermission")}
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const vatValid = /^3\d{13}3$/.test(vatNumber);
  const postalValid = /^\d{5}$/.test(postalCode);
  const buildingValid = /^\d{4}$/.test(buildingNumber);

  const step1Valid = nameEn.trim() !== "" && nameAr.trim() !== "" && vatValid;
  const step2Valid =
    street.trim() !== "" &&
    buildingValid &&
    city.trim() !== "" &&
    district.trim() !== "" &&
    postalValid;

  const saveMutation = useMutation({
    mutationFn: () =>
      api.put("/api/v1/organization", {
        name_en: nameEn,
        name_ar: nameAr,
        vat_number: vatNumber,
        cr_number: crNumber || null,
        street,
        building_number: buildingNumber,
        city,
        district,
        postal_code: postalCode,
        province: province || null,
        country_code: "SA",
      }),
    onSuccess: async () => {
      setError("");
      await refreshUser();
      router.push("/dashboard");
    },
    onError: () => {
      setError(t("setupFailed"));
    },
  });

  return (
    <div className="mx-auto max-w-2xl space-y-6 py-8">
      {/* Header */}
      <div className="text-center">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("subtitle")}</p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center justify-center gap-2">
        {STEPS.map((s, i) => {
          const Icon = s.icon;
          const isActive = i === step;
          const isDone = i < step;
          return (
            <div key={s.key} className="flex items-center gap-2">
              {i > 0 && (
                <div
                  className={`h-px w-8 ${isDone ? "bg-primary" : "bg-border"}`}
                />
              )}
              <div
                className={`flex size-10 items-center justify-center rounded-full border-2 transition-colors ${
                  isActive
                    ? "border-primary bg-primary text-primary-foreground"
                    : isDone
                      ? "border-primary bg-primary/10 text-primary"
                      : "border-border text-muted-foreground"
                }`}
              >
                <Icon className="size-5" />
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-center text-sm text-muted-foreground">
        {t("step", { current: step + 1, total: STEPS.length })}
      </p>

      {/* Step content */}
      <Card>
        {step === 0 && (
          <>
            <CardHeader>
              <CardTitle>{t("companyInfo")}</CardTitle>
              <CardDescription>{t("companyInfoDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium">
                    {to("nameEn")} *
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={nameEn}
                    onChange={(e) => setNameEn(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("nameAr")} *
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    dir="rtl"
                    value={nameAr}
                    onChange={(e) => setNameAr(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("vatNumber")} *
                  </label>
                  <input
                    className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${vatNumber && !vatValid ? "border-red-500" : ""}`}
                    placeholder="3XXXXXXXXXXXXX3"
                    value={vatNumber}
                    onChange={(e) => setVatNumber(e.target.value)}
                  />
                  {vatNumber && !vatValid && (
                    <p className="mt-1 text-xs text-red-500">
                      {to("vatHint")}
                    </p>
                  )}
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("crNumber")}
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={crNumber}
                    onChange={(e) => setCrNumber(e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </>
        )}

        {step === 1 && (
          <>
            <CardHeader>
              <CardTitle>{t("address")}</CardTitle>
              <CardDescription>{t("addressDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="text-sm font-medium">
                    {to("street")} *
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={street}
                    onChange={(e) => setStreet(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("buildingNumber")} *
                  </label>
                  <input
                    className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${buildingNumber && !buildingValid ? "border-red-500" : ""}`}
                    placeholder="1234"
                    maxLength={4}
                    value={buildingNumber}
                    onChange={(e) => setBuildingNumber(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("city")} *
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={city}
                    onChange={(e) => setCity(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("district")} *
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={district}
                    onChange={(e) => setDistrict(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("postalCode")} *
                  </label>
                  <input
                    className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${postalCode && !postalValid ? "border-red-500" : ""}`}
                    placeholder="12345"
                    maxLength={5}
                    value={postalCode}
                    onChange={(e) => setPostalCode(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">
                    {to("province")}
                  </label>
                  <input
                    className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                    value={province}
                    onChange={(e) => setProvince(e.target.value)}
                  />
                </div>
              </div>
            </CardContent>
          </>
        )}

        {step === 2 && (
          <>
            <CardHeader>
              <CardTitle>{t("review")}</CardTitle>
              <CardDescription>{t("reviewDesc")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Company Info Summary */}
              <div className="rounded-md border p-4 space-y-2">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Building2 className="size-4" />
                  {t("companyInfo")}
                </h3>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <dt className="text-muted-foreground">{to("nameEn")}</dt>
                  <dd>{nameEn}</dd>
                  <dt className="text-muted-foreground">{to("nameAr")}</dt>
                  <dd dir="rtl">{nameAr}</dd>
                  <dt className="text-muted-foreground">{to("vatNumber")}</dt>
                  <dd className="font-mono">{vatNumber}</dd>
                  {crNumber && (
                    <>
                      <dt className="text-muted-foreground">
                        {to("crNumber")}
                      </dt>
                      <dd>{crNumber}</dd>
                    </>
                  )}
                </dl>
              </div>

              {/* Address Summary */}
              <div className="rounded-md border p-4 space-y-2">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <MapPin className="size-4" />
                  {t("address")}
                </h3>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                  <dt className="text-muted-foreground">{to("street")}</dt>
                  <dd>{street}</dd>
                  <dt className="text-muted-foreground">
                    {to("buildingNumber")}
                  </dt>
                  <dd className="font-mono">{buildingNumber}</dd>
                  <dt className="text-muted-foreground">{to("city")}</dt>
                  <dd>{city}</dd>
                  <dt className="text-muted-foreground">{to("district")}</dt>
                  <dd>{district}</dd>
                  <dt className="text-muted-foreground">{to("postalCode")}</dt>
                  <dd className="font-mono">{postalCode}</dd>
                  {province && (
                    <>
                      <dt className="text-muted-foreground">
                        {to("province")}
                      </dt>
                      <dd>{province}</dd>
                    </>
                  )}
                </dl>
              </div>

              {error && (
                <p className="text-sm text-red-600">{error}</p>
              )}
            </CardContent>
          </>
        )}
      </Card>

      {/* Navigation buttons */}
      <div className="flex justify-between">
        <Button
          variant="outline"
          onClick={() => setStep((s) => s - 1)}
          disabled={step === 0}
        >
          <ChevronLeft className="mr-1 size-4" />
          {t("back")}
        </Button>

        {step < STEPS.length - 1 ? (
          <Button
            onClick={() => setStep((s) => s + 1)}
            disabled={step === 0 ? !step1Valid : !step2Valid}
          >
            {t("next")}
            <ChevronRight className="ml-1 size-4" />
          </Button>
        ) : (
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending}
          >
            {saveMutation.isPending ? t("saving") : t("completeSetup")}
          </Button>
        )}
      </div>
    </div>
  );
}
