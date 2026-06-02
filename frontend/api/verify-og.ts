import type { VercelRequest, VercelResponse } from "@vercel/node";

const BOT_UA_REGEX =
  /Twitterbot|facebookexternalhit|LinkedInBot|Discordbot|Slackbot|WhatsApp|TelegramBot|Googlebot|bingbot/i;

const API_BASE =
  process.env.VITE_API_URL ?? process.env.API_URL ?? "https://verifi-backend.onrender.com";

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const ua = req.headers["user-agent"] ?? "";

  // Only intercept for bots — real users get the SPA
  if (!BOT_UA_REGEX.test(ua)) {
    // Serve the SPA index.html so the React router handles it
    res.setHeader("x-middleware-rewrite", "/index.html");
    res.status(200).end();
    return;
  }

  // Extract ID from the URL path: /verify/claim/:id or /verify/position/:id
  const claimMatch = req.url?.match(/\/verify\/claim\/(\d+)/);
  const positionMatch = req.url?.match(/\/verify\/position\/(\d+)/);
  
  const idStr = claimMatch?.[1] || positionMatch?.[1];
  const isPosition = !!positionMatch;

  const safeId =
    idStr && /^[1-9]\d*$/.test(idStr) ? String(Number.parseInt(idStr, 10)) : null;

  if (!safeId) {
    return serveDefaultOG(res);
  }

  try {
    const endpoint = isPosition
      ? `${API_BASE}/api/posts/positions/${safeId}/og/`
      : `${API_BASE}/api/posts/hard-claims/${safeId}/og/`;
      
    const ogRes = await fetch(endpoint);
    if (!ogRes.ok) {
      return serveDefaultOG(res);
    }

    const data = await ogRes.json();

    const html = buildOGHtml({
      title: data.title || "VeriFi — Verified Proof",
      description: data.description || "Verify this cryptographic proof on VeriFi.",
      url: `https://${req.headers.host}/verify/${isPosition ? 'position' : 'claim'}/${safeId}`,
    });

    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.setHeader("Cache-Control", "public, max-age=3600, s-maxage=3600");
    res.status(200).send(html);
  } catch {
    return serveDefaultOG(res);
  }
}

function serveDefaultOG(res: VercelResponse) {
  const html = buildOGHtml({
    title: "VeriFi — Verifiable finance predictions",
    description:
      "Attach verifiable claims to posts, track market outcomes, and build reputation on-chain.",
    url: "https://verifi.app",
  });
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.status(200).send(html);
}

function buildOGHtml(meta: { title: string; description: string; url: string }): string {
  // Escape HTML entities to prevent XSS
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>${esc(meta.title)}</title>
  <meta name="description" content="${esc(meta.description)}" />
  <meta property="og:type" content="website" />
  <meta property="og:site_name" content="VeriFi" />
  <meta property="og:title" content="${esc(meta.title)}" />
  <meta property="og:description" content="${esc(meta.description)}" />
  <meta property="og:url" content="${esc(meta.url)}" />
  <meta property="og:image" content="/og-image.png" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="${esc(meta.title)}" />
  <meta name="twitter:description" content="${esc(meta.description)}" />
  <meta name="twitter:image" content="/og-image.png" />
  <meta http-equiv="refresh" content="0;url=${esc(meta.url)}" />
</head>
<body>
  <p>Redirecting to <a href="${esc(meta.url)}">${esc(meta.title)}</a>…</p>
</body>
</html>`;
}
