export default function Card({ title, right, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-surface p-4 ${className}`}>
      {(title || right) && (
        <header className="mb-3 flex items-center justify-between">
          <h3 className="text-base font-semibold text-text">{title}</h3>
          {right}
        </header>
      )}
      {children}
    </section>
  );
}
