import Link from "next/link";

const CARDS = [
  { href: "/upload", title: "Upload Agreement", body: "Drop a vendor PDF — the pipeline extracts, classifies, and normalizes pricing." },
  { href: "/search", title: "Ask Anything", body: "“Rate from Meerut to Bangalore?”, “penalty clause?”, “cheapest to Kolkata?”." },
  { href: "/compare", title: "Compare Vendors", body: "Best and average rates per vendor for any lane." },
];

export default function Home() {
  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">Freight Agreement Intelligence</h1>
        <p className="mt-2 max-w-2xl text-slate-600">
          Turn inconsistent vendor freight agreements into a normalized, searchable,
          auditable rate book. Deterministic extraction first, AI only on exception,
          human review before any export.
        </p>
      </section>
      <section className="grid gap-4 sm:grid-cols-3">
        {CARDS.map((c) => (
          <Link
            key={c.href}
            href={c.href}
            className="rounded-lg border bg-white p-5 transition hover:border-brand hover:shadow-sm"
          >
            <h2 className="font-medium text-brand">{c.title}</h2>
            <p className="mt-1 text-sm text-slate-600">{c.body}</p>
          </Link>
        ))}
      </section>
    </div>
  );
}
