import { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';

export function useUserRole(api) {
    const [role, setRole] = useState(null);

    useEffect(() => {
        let cancelled = false;
        api.get(ENDPOINTS.PROFILE)
            .then((data) => { if (!cancelled) setRole(data.role); })
            .catch(() => {});
        return () => { cancelled = true; };
    }, [api]);

    return role;
}