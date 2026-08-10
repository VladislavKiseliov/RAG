import React from 'react';

// Единый визуальный маркер "это демо/мок, без реального бэкенда" — см. openspec/specs/*-mock
// для полного списка, куда он должен быть проставлен.
function MockBadge({ text = 'Демо', title = 'Демо-режим: данные не сохраняются на сервере' }) {
    return (
        <span className="mock-badge" title={title}>
            {text}
        </span>
    );
}

export default MockBadge;
