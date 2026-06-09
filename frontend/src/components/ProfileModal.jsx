import React, { useState, useEffect } from 'react';
import { ENDPOINTS } from '../config/api';

function ProfileModal({ api, onClose }) {
    const [form, setForm] = useState({
        first_name: '',
        last_name: '',
        patronymic: '',
        job_title: '',
    });
    const [login, setLogin] = useState('');
    const [role, setRole] = useState('');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(false);

    useEffect(() => {
        api.get(ENDPOINTS.PROFILE)
            .then((data) => {
                setLogin(data.login || '');
                setRole(data.role || '');
                setForm({
                    first_name: data.first_name || '',
                    last_name: data.last_name || '',
                    patronymic: data.patronymic || '',
                    job_title: data.job_title || '',
                });
            })
            .catch((e) => setError(e.message))
            .finally(() => setLoading(false));
    }, []);

    const handleSave = async () => {
        setSaving(true);
        setError(null);
        setSuccess(false);
        try {
            await api.patch(ENDPOINTS.PROFILE, form);
            setSuccess(true);
            setTimeout(() => setSuccess(false), 3000);
        } catch (e) {
            setError(e.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="modal-overlay" onClick={onClose} onKeyDown={(e) => e.key === 'Escape' && onClose()}>
            <div className="modal-box" onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <span className="modal-title">Профиль</span>
                    <button className="modal-close" onClick={onClose}>✕</button>
                </div>

                {loading ? (
                    <div className="modal-loading">Загрузка...</div>
                ) : (
                    <div className="modal-body">
                        <div className="profile-readonly">
                            <div className="profile-field">
                                <span className="profile-label">Логин</span>
                                <span className="profile-value">{login}</span>
                            </div>
                            <div className="profile-field">
                                <span className="profile-label">Роль</span>
                                <span className="profile-value">{role}</span>
                            </div>
                        </div>

                        <div className="modal-divider" />

                        {[
                            { key: 'last_name', label: 'Фамилия' },
                            { key: 'first_name', label: 'Имя' },
                            { key: 'patronymic', label: 'Отчество' },
                            { key: 'job_title', label: 'Должность' },
                        ].map(({ key, label }) => (
                            <div key={key} className="modal-field">
                                <label className="modal-label">{label}</label>
                                <input
                                    className="modal-input"
                                    type="text"
                                    value={form[key]}
                                    onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                                    placeholder={label}
                                />
                            </div>
                        ))}

                        {error && <div className="modal-error">{error}</div>}
                        {success && <div className="modal-success">Сохранено</div>}

                        <div className="modal-actions">
                            <button className="modal-btn-cancel" onClick={onClose}>Отмена</button>
                            <button className="modal-btn-save" onClick={handleSave} disabled={saving}>
                                {saving ? 'Сохранение...' : 'Сохранить'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default ProfileModal;