"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { Building2, Shield, ShieldCheck } from "lucide-react";
import api from "@/lib/api";
import { Button } from "@/components/ui/button";

interface OrgData {
  id: string;
  name_en: string;
  name_ar: string;
  vat_number: string;
  additional_id: string | null;
  cr_number: string | null;
  street: string;
  building_number: string;
  city: string;
  district: string;
  postal_code: string;
  province: string | null;
  country_code: string;
  is_production: boolean;
  zatca_api_base_url: string | null;
  has_certificate: boolean;
}

export default function SettingsPage() {
  const t = useTranslations("organization");
  const tc = useTranslations("common");
  const qc = useQueryClient();

  const { data: org, isLoading } = useQuery<OrgData>({
    queryKey: ["organization"],
    queryFn: () => api.get("/api/v1/organization").then((r) => r.data),
    retry: false,
  });

  const [nameEn, setNameEn] = useState("");
  const [nameAr, setNameAr] = useState("");
  const [vatNumber, setVatNumber] = useState("");
  const [crNumber, setCrNumber] = useState("");
  const [street, setStreet] = useState("");
  const [buildingNumber, setBuildingNumber] = useState("");
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [province, setProvince] = useState("");
  const [formLoaded, setFormLoaded] = useState(false);

  // Load org data into form once
  if (org && !formLoaded) {
    setNameEn(org.name_en);
    setNameAr(org.name_ar);
    setVatNumber(org.vat_number);
    setCrNumber(org.cr_number ?? "");
    setStreet(org.street);
    setBuildingNumber(org.building_number);
    setCity(org.city);
    setDistrict(org.district);
    setPostalCode(org.postal_code);
    setProvince(org.province ?? "");
    setFormLoaded(true);
  }

  const saveMutation = useMutation({
    mutationFn: (body: Record<string, string | null>) =>
      api.put("/api/v1/organization", body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organization"] });
    },
  });

  const csrMutation = useMutation({
    mutationFn: () =>
      api.post("/api/v1/zatca/generate-csr", { common_name: nameEn }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["organization"] });
    },
  });

  const handleSave = () => {
    saveMutation.mutate({
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
    });
  };

  const vatValid = /^3\d{13}3$/.test(vatNumber);
  const postalValid = /^\d{5}$/.test(postalCode);
  const buildingValid = /^\d{4}$/.test(buildingNumber);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Building2 className="size-6" />
        <h1 className="text-2xl font-bold">{t("title")}</h1>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">{tc("loading")}</p>
      ) : (
        <div className="space-y-8">
          {/* Company Info */}
          <section className="rounded-lg border p-6 space-y-4">
            <h2 className="text-lg font-semibold">{t("companyInfo")}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium">{t("nameEn")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={nameEn}
                  onChange={(e) => setNameEn(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("nameAr")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  dir="rtl"
                  value={nameAr}
                  onChange={(e) => setNameAr(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("vatNumber")}</label>
                <input
                  className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${vatNumber && !vatValid ? "border-red-500" : ""}`}
                  placeholder="3XXXXXXXXXXXXX3"
                  value={vatNumber}
                  onChange={(e) => setVatNumber(e.target.value)}
                />
                {vatNumber && !vatValid && (
                  <p className="mt-1 text-xs text-red-500">{t("vatHint")}</p>
                )}
              </div>
              <div>
                <label className="text-sm font-medium">{t("crNumber")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={crNumber}
                  onChange={(e) => setCrNumber(e.target.value)}
                />
              </div>
            </div>
          </section>

          {/* Address */}
          <section className="rounded-lg border p-6 space-y-4">
            <h2 className="text-lg font-semibold">{t("address")}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="text-sm font-medium">{t("street")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={street}
                  onChange={(e) => setStreet(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("buildingNumber")}</label>
                <input
                  className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${buildingNumber && !buildingValid ? "border-red-500" : ""}`}
                  placeholder="1234"
                  maxLength={4}
                  value={buildingNumber}
                  onChange={(e) => setBuildingNumber(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("city")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("district")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("postalCode")}</label>
                <input
                  className={`mt-1 w-full rounded-md border px-3 py-2 text-sm ${postalCode && !postalValid ? "border-red-500" : ""}`}
                  placeholder="12345"
                  maxLength={5}
                  value={postalCode}
                  onChange={(e) => setPostalCode(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium">{t("province")}</label>
                <input
                  className="mt-1 w-full rounded-md border px-3 py-2 text-sm"
                  value={province}
                  onChange={(e) => setProvince(e.target.value)}
                />
              </div>
            </div>
          </section>

          <div className="flex gap-3">
            <Button
              onClick={handleSave}
              disabled={saveMutation.isPending || !nameEn || !vatValid || !postalValid || !buildingValid}
            >
              {saveMutation.isPending ? tc("loading") : tc("save")}
            </Button>
            {saveMutation.isSuccess && (
              <span className="self-center text-sm text-green-600">{t("saveSuccess")}</span>
            )}
            {saveMutation.isError && (
              <span className="self-center text-sm text-red-600">{t("saveFailed")}</span>
            )}
          </div>

          {/* ZATCA Certificate */}
          <section className="rounded-lg border p-6 space-y-4">
            <h2 className="text-lg font-semibold">{t("zatcaCertificate")}</h2>
            <div className="flex items-center gap-3">
              {org?.has_certificate ? (
                <>
                  <ShieldCheck className="size-5 text-green-600" />
                  <span className="text-sm font-medium text-green-600">
                    {org.is_production ? t("production") : t("sandbox")}
                  </span>
                </>
              ) : (
                <>
                  <Shield className="size-5 text-yellow-600" />
                  <span className="text-sm text-yellow-600">{t("noCertificate")}</span>
                </>
              )}
            </div>
            <Button
              variant="outline"
              onClick={() => csrMutation.mutate()}
              disabled={csrMutation.isPending || !org}
            >
              {csrMutation.isPending ? tc("loading") : t("generateCsr")}
            </Button>
            {csrMutation.isSuccess && (
              <p className="text-sm text-green-600">{t("csrGenerated")}</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
