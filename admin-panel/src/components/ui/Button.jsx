export default function Button({ variant = 'primary', className = '', ...props }) {
  const base = 'inline-flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors';
  const variants = {
    primary: 'bg-accent text-white hover:bg-[#3a6886]',
    secondary: 'bg-white text-text border border-slate-200 hover:bg-slate-50',
    danger: 'bg-danger text-white hover:brightness-95',
    ghost: 'text-muted hover:bg-slate-100',
  };
  return <button className={`${base} ${variants[variant]} ${className}`} {...props} />;
}
