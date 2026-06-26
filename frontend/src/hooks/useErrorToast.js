import { useState, useCallback } from 'react';
import { TIMEOUTS } from '../config/constants';

export function useErrorToast() {
    const [error, setError] = useState(null);

    const showError = useCallback((message) => {
        setError(message);
        setTimeout(() => setError(null), TIMEOUTS.ERROR_TOAST);
    }, []);

    return { error, showError };
}