#!/usr/bin/env python3
"""Regression tests for find_sequential_awaits.py. Run: python3 test_find_sequential_awaits.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import find_sequential_awaits as f  # noqa: E402

CASES = {
    "independent reads": ("""
export async function load(id: string) {
  const user = await getUser(id);
  const posts = await getPosts(id);
  return { user, posts };
}""", ["SEQ"]),
    "dependent reads": ("""
export async function load(id: string) {
  const user = await getUser(id);
  const posts = await getPosts(user.orgId);
  return { user, posts };
}""", []),
    "dependency through derived value": ("""
export async function load(id: string) {
  const user = await getUser(id);
  const org = user.orgId;
  const posts = await getPosts(org);
  return posts;
}""", []),
    "multi-line sql templates, existence gate": ("""
export async function renderZip(sql: Sql, zip: string): Promise<string | null> {
  const sites = await sql`
    SELECT folio FROM sites
    WHERE zip = ${zip}
    LIMIT 120`;
  if (!sites.length) return null;
  const [done] = await sql`SELECT count(*) FROM sites WHERE zip = ${zip}`;
  return render(sites, done);
}""", ["GATED"]),
    "auth gate stays hidden": ("""
export async function GET(req: Request) {
  const session = await getSession(req);
  if (!session) return new Response(null, { status: 401 });
  const rows = await listThings();
  return Response.json(rows);
}""", []),
    "write then refresh is ordered": ("""
async function onSave() {
  await runApiMutation("items:update", { id });
  await refresh();
}""", []),
    "free awaits ignored": ("""
export default async function Page({ params, searchParams }: Props) {
  const { slug } = await params;
  const sp = await searchParams;
  return <div>{slug}{sp.q}</div>;
}""", []),
    "await in loop": ("""
export async function tagAll(ids: string[]) {
  for (const id of ids) {
    await tag(id);
  }
}""", ["LOOP"]),
    "map inside Promise.all is fine": ("""
export async function tagAll(ids: string[]) {
  return Promise.all(ids.map(async (id) => {
    await tag(id);
  }));
}""", []),
    "jsx apostrophe keeps line numbers": ("""
export async function load(id: string) {
  const a = <p>Don't stop</p>;
  const user = await getUser(id);
  const posts = await getPosts(id);
  return { a, user, posts };
}""", ["SEQ@3"]),
}


def run() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as d:
        for name, (src, want) in CASES.items():
            p = Path(d) / "app" / "api" / "x" / "route.tsx"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(src.lstrip("\n"))
            hits = f.scan_file(p, "app/api/x/route.tsx")
            got = [h["kind"] for h in hits]
            exp_kinds = [w.split("@")[0] for w in want]
            ok = got == exp_kinds
            for w in want:
                if "@" in w and ok:
                    ok = any(h["line"] == int(w.split("@")[1]) for h in hits)
            print(("ok   " if ok else "FAIL ") + name + ("" if ok else f": want {want}, got {[(h['kind'], h['line']) for h in hits]}"))
            failed += not ok
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
