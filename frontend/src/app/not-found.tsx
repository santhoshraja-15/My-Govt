import Link from "next/link";
import { Compass } from "lucide-react";

export default function NotFound() {
  return (
    <main className="max-w-xl mx-auto px-4 py-24 text-center space-y-4" data-testid="not-found">
      <Compass size={48} className="mx-auto text-slate-500" aria-hidden />
      <h1 className="text-3xl font-black text-slate-900">Page not found</h1>
      <p className="text-slate-600">The page you are looking for does not exist or has moved.</p>
      <div className="flex justify-center gap-3">
        <Link href="/" className="btn-primary">Go to the home page</Link>
        <Link href="/schemes" className="btn-secondary">Browse schemes</Link>
      </div>
    </main>
  );
}
