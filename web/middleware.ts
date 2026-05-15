import { NextRequest, NextResponse } from "next/server";

/**
 * Gate write paths behind the ADMIN_TOKEN cookie. Read paths are public.
 *
 * We can't `import` the auth helper here because Edge middleware runs in a
 * separate, leaner runtime; we inline the cookie check instead.
 */

const ADMIN_COOKIE = "llm4arxiv_admin";

// Paths that require an authenticated admin cookie. Use prefix matches.
const PROTECTED_PREFIXES = ["/submit"];
// API routes that require auth at the request level. The cron route uses its
// own CRON_SECRET check inside the handler.
const PROTECTED_API_PREFIXES = [
  "/api/papers/ingest",
  "/api/stars",
  "/api/hide",
];

export function middleware(req: NextRequest) {
  const path = req.nextUrl.pathname;
  const needsAuth =
    PROTECTED_PREFIXES.some((p) => path.startsWith(p)) ||
    PROTECTED_API_PREFIXES.some((p) => path.startsWith(p));
  if (!needsAuth) return NextResponse.next();

  const expected = process.env.ADMIN_TOKEN;
  const got = req.cookies.get(ADMIN_COOKIE)?.value;
  if (expected && got && got === expected) {
    return NextResponse.next();
  }

  // For API requests, return JSON 401. For page requests, redirect to login.
  if (path.startsWith("/api/")) {
    return new NextResponse(
      JSON.stringify({ error: "unauthenticated" }),
      { status: 401, headers: { "content-type": "application/json" } },
    );
  }
  const login = req.nextUrl.clone();
  login.pathname = "/login";
  login.searchParams.set("redirect", path);
  return NextResponse.redirect(login);
}

export const config = {
  // Run only on the paths we actually want to guard. The catch-all home page
  // and public paper views stay zero-overhead.
  matcher: [
    "/submit/:path*",
    "/api/papers/ingest",
    "/api/stars/:path*",
    "/api/hide/:path*",
  ],
};
