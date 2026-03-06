import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import Button from '../components/ui/Button';
import { useAuthStore } from '../stores/authStore';

export default function Login() {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const isLoading = useAuthStore((s) => s.isLoading);
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('admin');

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await login(username, password);
      navigate('/dashboard', { replace: true });
      toast.success('Вход выполнен');
    } catch (error) {
      toast.error(error.message || 'Ошибка авторизации');
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <form className="w-full max-w-md rounded-xl border border-slate-200 bg-white p-6 shadow-sm" onSubmit={handleSubmit}>
        <h1 className="mb-1 text-2xl font-semibold text-primary">RAG Admin</h1>
        <p className="mb-6 text-sm text-muted">Вход в административную панель</p>
        <div className="mb-3">
          <label className="mb-1 block text-sm font-medium">Username</label>
          <input className="w-full rounded-md border border-slate-300 px-3 py-2" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div className="mb-4">
          <label className="mb-1 block text-sm font-medium">Password</label>
          <input type="password" className="w-full rounded-md border border-slate-300 px-3 py-2" value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>
        <Button className="w-full justify-center" disabled={isLoading} type="submit">
          {isLoading ? 'Входим...' : 'Войти'}
        </Button>
      </form>
    </div>
  );
}
