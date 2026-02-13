import createIntlMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { routing } from "./i18n/routing";

const intlMiddleware = createIntlMiddleware(routing);

export default function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Strip locale prefix for path matching
  const pathnameWithoutLocale = pathname.replace(/^\/(en|ar)/, "");

  // Auth guard: redirect to login if no token for dashboard routes
  if (pathnameWithoutLocale.startsWith("/dashboard")) {
    const token = request.cookies.get("access_token")?.value;
    if (!token) {
      const locale = pathname.match(/^\/(en|ar)/)?.[1] ?? "en";
      return NextResponse.redirect(
        new URL(`/${locale}/login`, request.url),
      );
    }
  }

  return intlMiddleware(request);
}

export const config = {
  matcher: ["/", "/(en|ar)/:path*"],
};
