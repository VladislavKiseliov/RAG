export const formatBytes = (bytes) => {
    if (!bytes) return '—';
    const kb = bytes / 1024;
    return kb >= 1024 ? `${(kb / 1024).toFixed(1)} МБ` : `${Math.round(kb)} КБ`;
};