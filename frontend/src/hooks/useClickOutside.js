import { useEffect } from 'react';

export function useClickOutside(enabled, selectors, onClose) {
    useEffect(() => {
        if (!enabled) return;
        const handler = (event) => {
            const clickedInside = selectors.some((sel) => event.target.closest(sel));
            if (!clickedInside) onClose();
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [enabled, selectors, onClose]);
}