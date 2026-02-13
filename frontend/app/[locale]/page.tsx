"use client";

import { useEffect } from "react";
import { useRouter } from "@/i18n/navigation";
import { useTranslations } from "next-intl";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/button";

export default function Home() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const tc = useTranslations("common");
  const th = useTranslations("home");

  useEffect(() => {
    if (!loading && user) {
      router.push("/dashboard");
    }
  }, [user, loading, router]);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center">
      <div className="text-center space-y-6">
        <h1 className="text-4xl font-bold tracking-tight">
          {tc("appName")}
        </h1>
        <p className="text-muted-foreground">
          {tc("appVersion")}
        </p>
        <Button onClick={() => router.push("/login")}>
          {th("signIn")}
        </Button>
      </div>
    </main>
  );
}
