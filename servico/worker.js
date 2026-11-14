// Agenda do Mundo: link pessoal. Guarda as áreas que cada pessoa marcou e entrega um calendário só com elas.
// Roda no Cloudflare Workers (plano gratuito) com um KV chamado AGENDA. Não guarda nome, e-mail nem nada da pessoa:
// só a cidade e a lista de áreas, sob um código aleatório.
const SITE = "https://luisfcblanco.github.io/agenda-do-mundo";
const CORS = { "Access-Control-Allow-Origin": "https://luisfcblanco.github.io", "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS", "Access-Control-Allow-Headers": "Content-Type,Authorization" };
const ID = /^[a-z0-9-]{1,40}$/;
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "Content-Type": "application/json", ...CORS } });
const aleatorio = (n) => [...crypto.getRandomValues(new Uint8Array(n))].map((b) => b.toString(16).padStart(2, "0")).join("");

function valida(b) {
  if (!b || !ID.test(b.cidade || "") || !Array.isArray(b.areas) || b.areas.length > 80 || !b.areas.every((a) => ID.test(a))) return null;
  return { cidade: b.cidade, areas: [...new Set(b.areas)] };
}

async function busca(url, ctx) {
  const cache = caches.default;
  let r = await cache.match(url);
  if (!r) {
    r = await fetch(url, { cf: { cacheTtl: 1800 } });
    if (r.ok) { r = new Response(r.body, r); r.headers.set("Cache-Control", "max-age=1800"); ctx.waitUntil(cache.put(url, r.clone())); }
  }
  return r;
}

async function calendario(sel, grupo, ctx) {
  const cat = await (await busca(`${SITE}/catalogo.json`, ctx)).json();
  const cidade = cat.regioes.find((r) => r.id === sel.cidade);
  if (!cidade) return new Response("cidade desconhecida", { status: 404 });
  const areas = cat.areas.filter((a) => sel.areas.includes(a.id) && (!grupo || cat.grupos_id[a.grupo] === grupo));
  const partes = await Promise.all(areas.map(async (a) => {
    const lugar = a.escopo === "local" ? cidade.id : a.escopo === "regional" ? cidade.macro : "brasil";
    if (!lugar || !(cat.feeds[lugar] || {})[a.id]) return "";
    const r = await busca(`${SITE}/feeds/${lugar}/${a.id}.ics`, ctx);
    if (!r.ok) return "";
    return ((await r.text()).match(/BEGIN:VEVENT[\s\S]*?END:VEVENT\r?\n/g) || []).join("");
  }));
  const nome = grupo ? Object.keys(cat.grupos_id).find((g) => cat.grupos_id[g] === grupo) : "Agenda do Mundo";
  const corpo = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Agenda do Mundo//PT-BR\r\nCALSCALE:GREGORIAN\r\n" +
    `X-WR-CALNAME:${nome} · ${cidade.nome}\r\nX-PUBLISHED-TTL:PT12H\r\n` + partes.join("") + "END:VCALENDAR\r\n";
  return new Response(corpo, { headers: { "Content-Type": "text/calendar; charset=utf-8", "Cache-Control": "max-age=3600" } });
}

export default {
  async fetch(req, env, ctx) {
    const u = new URL(req.url), p = u.pathname;
    if (req.method === "OPTIONS") return new Response(null, { headers: CORS });
    if (req.method === "POST" && p === "/novo") {
      const sel = valida(await req.json().catch(() => null));
      if (!sel) return json({ erro: "pedido inválido" }, 400);
      const id = aleatorio(10), token = aleatorio(16);
      await env.AGENDA.put(id, JSON.stringify({ ...sel, token }));
      return json({ id, token });
    }
    const m = p.match(/^\/c\/([a-f0-9]{20})(?:\/([a-z0-9-]+))?(\.ics)?$/);
    if (!m) return new Response("não encontrado", { status: 404 });
    const salvo = JSON.parse((await env.AGENDA.get(m[1])) || "null");
    if (!salvo) return new Response("não encontrado", { status: 404 });
    if (req.method === "PUT" && !m[3]) {
      if (req.headers.get("Authorization") !== salvo.token) return json({ erro: "sem permissão" }, 403);
      const sel = valida(await req.json().catch(() => null));
      if (!sel) return json({ erro: "pedido inválido" }, 400);
      await env.AGENDA.put(m[1], JSON.stringify({ ...sel, token: salvo.token }));
      return json({ ok: true });
    }
    if (req.method === "GET" && m[3]) return calendario(salvo, m[2], ctx);
    if (req.method === "GET") return json({ cidade: salvo.cidade, areas: salvo.areas });
    return new Response("método não aceito", { status: 405 });
  },
};
