import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24 text-center">
      <div className="flex items-center gap-2 font-mono-data text-sm font-bold uppercase tracking-[0.28em] text-white">
        <span className="h-1.5 w-1.5 rounded-full bg-red" />
        ARIS
      </div>
      <p className="mt-10 font-mono-data text-[11px] uppercase tracking-[0.32em] text-red">404</p>
      <h1 className="mt-3 text-3xl font-extrabold tracking-tight text-white sm:text-4xl">
        Page not found
      </h1>
      <p className="mt-3 max-w-md font-sans text-sm leading-relaxed text-muted">
        This route is not on the grid. Head back to the pit wall.
      </p>
      <Link
        href="/"
        className="mt-8 rounded bg-red px-4 py-2 font-mono-data text-[11px] uppercase tracking-widest text-white hover:brightness-110"
      >
        Back to home
      </Link>
    </main>
  );
}
