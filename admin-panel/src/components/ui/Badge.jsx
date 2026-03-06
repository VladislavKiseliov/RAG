const styles = {
  completed: 'bg-green-50 text-success border-green-200',
  processing: 'bg-amber-50 text-amber-700 border-amber-200',
  error: 'bg-rose-50 text-danger border-rose-200',
  active: 'bg-green-50 text-success border-green-200',
  blocked: 'bg-slate-100 text-slate-600 border-slate-200',
  ACTIVE: 'bg-amber-50 text-amber-700 border-amber-200',
  SUCCESS: 'bg-green-50 text-success border-green-200',
  FAILURE: 'bg-rose-50 text-danger border-rose-200',
  online: 'bg-green-50 text-success border-green-200',
  offline: 'bg-rose-50 text-danger border-rose-200',
  degraded: 'bg-amber-50 text-amber-700 border-amber-200',
};

export default function Badge({ value }) {
  return (
    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-medium ${styles[value] || 'bg-slate-50 text-slate-700 border-slate-200'}`}>
      {value}
    </span>
  );
}
