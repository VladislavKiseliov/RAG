import { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';

const EMPTY_USER = { initials: '..', name: '', login: '', role: '', isAdmin: false };

// Единственное место, которое дёргает GET /api/profile — раньше это делали
// независимо Sidebar, UserMenu и useUserRole, по 2-3 одинаковых запроса на маунт.
export function useCurrentUser(api) {
    const [user, setUser] = useState(EMPTY_USER);

    useEffect(() => {
        let cancelled = false;
        api.get(ENDPOINTS.PROFILE).then((data) => {
            if (cancelled) return;
            const name = [data.first_name, data.last_name].filter(Boolean).join(' ') || data.login || '';
            const initials = name
                ? name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
                : (data.login || '?').slice(0, 2).toUpperCase();
            setUser({
                initials,
                name,
                login: data.login || '',
                role: data.role || '',
                isAdmin: data.role === 'admin',
            });
        }).catch(() => {});
        return () => { cancelled = true; };
    }, [api]);

    return user;
}