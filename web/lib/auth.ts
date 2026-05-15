/**
 * Single-user write-auth: the visitor presents the value of ADMIN_TOKEN in
 * a cookie. The middleware enforces this on `/submit`, `/admin/*`, and the
 * write API routes. Public read paths do not require it.
 */

export const ADMIN_COOKIE = "llm4arxiv_admin";

export function cookieToken(req: Request): string | null {
  const header = req.headers.get("cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const [name, ...rest] = part.trim().split("=");
    if (name === ADMIN_COOKIE) return decodeURIComponent(rest.join("="));
  }
  return null;
}

export function isAdmin(req: Request): boolean {
  const expected = process.env.ADMIN_TOKEN;
  if (!expected) return false; // misconfigured server → deny rather than allow
  const got = cookieToken(req);
  return got !== null && timingSafeEqual(got, expected);
}

// constant-time string comparison; cookies are short so this is fine
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return mismatch === 0;
}
