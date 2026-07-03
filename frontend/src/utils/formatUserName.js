export function formatUserName(user, fallback = '') {
    if (!user) return fallback;
    const { first_name, last_name, login, friend_first_name, friend_last_name, friend_login } = user;
    const fn = first_name ?? friend_first_name;
    const ln = last_name ?? friend_last_name;
    const lg = login ?? friend_login;
    if (fn || ln) return [fn, ln].filter(Boolean).join(' ');
    return lg ?? fallback;
}

export function formatUserInitial(user) {
    if (!user) return '?';
    const { first_name, last_name, login, friend_first_name, friend_login } = user;
    const fn = first_name || friend_first_name;
    const lg = login || friend_login;
    return ((fn || lg || '?')[0]).toUpperCase();
}