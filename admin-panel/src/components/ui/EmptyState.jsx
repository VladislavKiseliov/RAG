export default function EmptyState({ title, description }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center">
      <p className="mb-1 text-base font-semibold text-text">{title}</p>
      <p className="text-sm text-muted">{description}</p>
    </div>
  );
}
