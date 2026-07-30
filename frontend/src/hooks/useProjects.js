import { useCallback, useState } from 'react';

// Проекты — чисто на моках (клиентское состояние, как Главная/Задачи), пока нет
// реального бэкенда под документооборот (Subfolder/Changeset). Модель:
// Проект → Раздел (7 фиксированных шаблонов) → Подраздел (создаётся вручную) →
// Документ (шифр + версии) → Пакет изменений (changeset, утверждение/отклонение).

export const SECTION_DEFS = [
    { id: 'inLetters', name: 'Письма входящие' },
    { id: 'outLetters', name: 'Письма исходящие' },
    { id: 'input', name: 'Исходные данные' },
    { id: 'design', name: 'Проектные чертежи' },
    { id: 'raw', name: 'Рабочие чертежи' },
    { id: 'equipment', name: 'Оборудование' },
    { id: 'tkp', name: 'ТКП' },
];

const PROJECT_TYPE_OPTIONS = [
    { id: 'new-equip', label: 'Новое оборудование' },
    { id: 'upgrade', label: 'Модернизация' },
    { id: 'bpg', label: 'БПГ' },
];

function seedProjects() {
    return [
        {
            id: 'bpg', name: 'БПГ-101', type: 'Промышленный объект', glyph: 'БГ', kind: 'active',
            status: 'В работе', lead: 'Иван Петров',
            members: [{ init: 'ИП', name: 'Иван Петров', role: 'Инженер' }, { init: 'СК', name: 'Соня Кравец', role: 'Эксперт' }],
            updated: '2 ч назад',
            desc: 'Проектная документация промышленного объекта БПГ-101: архитектурные решения, отопление и вентиляция, технологическая часть.',
            activity: [
                { who: 'ИП', text: 'Иван загрузил пакет изменений по разделу «Отопление»', when: '2 часа назад' },
                { who: 'СК', text: 'Соня отклонила пакет по разделу «Технология» — нужны правки', when: 'вчера' },
            ],
            subfolders: { raw: [{ id: 'sf-heat', name: 'Отопление' }, { id: 'sf-vent', name: 'Вентиляция' }, { id: 'sf-tech', name: 'Технология' }] },
        },
        {
            id: 'grs', name: 'ГРС-14', type: 'Промышленный объект', glyph: 'ГР', kind: 'plan',
            status: 'Планирование', lead: 'Артём Рыжов',
            members: [{ init: 'АР', name: 'Артём Рыжов', role: 'Инженер' }],
            updated: '3 дня назад',
            desc: 'Газораспределительная станция ГРС-14 — на этапе сбора исходных данных.',
            activity: [{ who: 'АР', text: 'Артём создал проект', when: '3 дня назад' }],
            subfolders: {},
        },
    ];
}

function seedDocs() {
    return [
        {
            id: 'docA', code: 'БПГ-101-АР-01', name: 'Архитектурные решения', sectionId: 'design', subfolderId: null,
            projectId: 'bpg', approvedVersion: 2, pendingChangesetId: null, lastRejectedChangesetId: null,
            versions: [
                { v: 1, fileName: 'AR-01_v1.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '10 июня', comment: 'Первая версия' },
                { v: 2, fileName: 'AR-01_v2.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '18 июня', comment: 'Правки по замечаниям экспертизы' },
            ],
            notes: [{ id: 'n1', author: 'Влад Логинов', text: 'Проверить соответствие СП 1.13130 в части эвакуационных путей.', isAI: false, date: '18 июня' }],
        },
        {
            id: 'docB', code: 'БПГ-101-ОВ-03', name: 'Отопление и вентиляция', sectionId: 'raw', subfolderId: 'sf-heat',
            projectId: 'bpg', approvedVersion: 3, pendingChangesetId: 'cs1', lastRejectedChangesetId: null,
            versions: [
                { v: 1, fileName: 'OV-03_v1.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '1 июня', comment: 'Первая версия' },
                { v: 2, fileName: 'OV-03_v2.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '10 июня', comment: 'Уточнён расход воздуха' },
                { v: 3, fileName: 'OV-03_v3.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: 'вчера', comment: 'Актуализация по факту монтажа' },
            ],
            notes: [],
        },
        {
            id: 'docC', code: 'БПГ-101-ТХ-02', name: 'Технологическая часть', sectionId: 'raw', subfolderId: 'sf-tech',
            projectId: 'bpg', approvedVersion: 1, pendingChangesetId: null, lastRejectedChangesetId: 'cs4',
            versions: [{ v: 1, fileName: 'TH-02_v1.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '5 июня', comment: 'Первая версия' }],
            notes: [],
        },
        {
            id: 'docD', code: 'НОВ-014', name: 'Схема вентиляции склада', sectionId: 'raw', subfolderId: 'sf-vent',
            projectId: 'bpg', approvedVersion: null, pendingChangesetId: 'cs3', lastRejectedChangesetId: null,
            versions: [], notes: [],
        },
        {
            id: 'docE', code: 'БПГ-101-ПС-01', name: 'Письмо согласования с заказчиком', sectionId: 'outLetters', subfolderId: null,
            projectId: 'bpg', approvedVersion: 1, pendingChangesetId: null, lastRejectedChangesetId: null,
            versions: [{ v: 1, fileName: 'PS-01.pdf', uploadedBy: 'Иван Петров', approvedBy: 'Влад Логинов', date: '2 июня', comment: 'Отправлено заказчику' }],
            notes: [],
        },
    ];
}

function seedChangesets() {
    return [
        {
            id: 'cs1', projectId: 'bpg', author: 'Иван Петров', authorInit: 'ИП', date: 'вчера', status: 'pending',
            comment: 'Обновление по замечаниям экспертизы', rejectionComment: null,
            items: [{ docId: 'docB', code: 'БПГ-101-ОВ-03', name: 'Отопление и вентиляция', action: 'replace', fromVersion: 2, fileName: 'OV-03_v3.pdf' }],
        },
        {
            id: 'cs2', projectId: 'bpg', author: 'Иван Петров', authorInit: 'ИП', date: '18 июня', status: 'approved',
            comment: 'Правки по замечаниям экспертизы', rejectionComment: null,
            items: [{ docId: 'docA', code: 'БПГ-101-АР-01', name: 'Архитектурные решения', action: 'replace', fromVersion: 1, fileName: 'AR-01_v2.pdf' }],
        },
        {
            id: 'cs3', projectId: 'bpg', author: 'Соня Кравец', authorInit: 'СК', date: 'сегодня', status: 'pending',
            comment: 'Новая схема вентиляции склада, разработана по запросу заказчика', rejectionComment: null,
            items: [{ docId: 'docD', code: 'НОВ-014', name: 'Схема вентиляции склада', action: 'new', toVersion: 1, fileName: 'НОВ-014_v1.pdf' }],
        },
        {
            id: 'cs4', projectId: 'bpg', author: 'Иван Петров', authorInit: 'ИП', date: 'вчера', status: 'rejected',
            comment: 'Обновление технологической схемы', rejectionComment: 'Не соответствует ГОСТ Р 59548-2022 — переделать раздел 4, согласовать заново.',
            items: [{ docId: 'docC', code: 'БПГ-101-ТХ-02', name: 'Технологическая часть', action: 'replace', fromVersion: 1, fileName: 'TH-02_v2.pdf' }],
        },
    ];
}

export function useProjects() {
    const [role, setRole] = useState('manager'); // 'manager' | 'engineer' — демо-переключатель, убрать при реальной ролевой модели (роль из сессии)
    const [view, setView] = useState('list');
    const [projects, setProjects] = useState(seedProjects);
    const [docs, setDocs] = useState(seedDocs);
    const [changesets, setChangesets] = useState(seedChangesets);

    const [selectedProjectId, setSelectedProjectId] = useState(null);
    const [selectedSectionId, setSelectedSectionId] = useState('all');
    const [selectedSubfolderId, setSelectedSubfolderId] = useState('all');
    const [selectedDocId, setSelectedDocId] = useState(null);
    const [filesQuery, setFilesQuery] = useState('');
    const [archiveSection, setArchiveSection] = useState('all');
    const [expandedSections, setExpandedSections] = useState(['raw']);
    const [addingSubfolderSectionId, setAddingSubfolderSectionId] = useState(null);
    const [subfolderDraft, setSubfolderDraft] = useState('');

    const [uploadModalOpen, setUploadModalOpen] = useState(false);
    const [uploadItems, setUploadItems] = useState([]);
    const [uploadComment, setUploadComment] = useState('');

    const [rejectModalOpen, setRejectModalOpen] = useState(false);
    const [rejectTargetId, setRejectTargetId] = useState(null);
    const [rejectComment, setRejectComment] = useState('');

    const [newProjectModalOpen, setNewProjectModalOpen] = useState(false);
    const [newProjectName, setNewProjectName] = useState('');
    const [newProjectType, setNewProjectType] = useState('new-equip');

    const [pdfOverlayOpen, setPdfOverlayOpen] = useState(false);
    const [pdfTitle, setPdfTitle] = useState('');

    // ---------- helpers (не мутируют state сами, читают его как аргумент) ----------
    const currentUser = () => (role === 'manager' ? 'Влад Логинов' : 'Иван Петров');

    const projectDocs = useCallback((pid) => docs.filter((d) => d.projectId === pid), [docs]);
    const projectChangesets = useCallback((pid) => changesets.filter((c) => c.projectId === pid), [changesets]);
    const pendingCount = useCallback((pid) => projectChangesets(pid).filter((c) => c.status === 'pending').length, [projectChangesets]);

    const docBadge = (d) => {
        if (d.pendingChangesetId && d.approvedVersion != null) return { label: 'На утверждении', color: 'var(--accent)' };
        if (d.pendingChangesetId && d.approvedVersion == null) return { label: 'Новый · на утверждении', color: 'var(--accent)' };
        if (d.lastRejectedChangesetId && !d.pendingChangesetId) return { label: 'Отклонён', color: '#d65f5f' };
        if (d.approvedVersion != null) return { label: 'Утверждён', color: 'var(--ok)' };
        return { label: 'Черновик', color: 'var(--muted)' };
    };

    const changesetConflict = (cs) => cs.items.some((it) => {
        if (it.action !== 'replace' || !it.docId) return false;
        const d = docs.find((x) => x.id === it.docId);
        return d && d.approvedVersion !== it.fromVersion;
    });

    // ---------- навигация ----------
    const openProject = useCallback((id) => { setSelectedProjectId(id); setView('overview'); }, []);
    const back = useCallback(() => { setSelectedProjectId(null); setView('list'); }, []);
    const backToOverview = useCallback(() => setView('overview'), []);
    const goFiles = useCallback(() => {
        setSelectedSectionId('all'); setSelectedSubfolderId('all'); setFilesQuery(''); setView('files');
    }, []);
    const goQueue = useCallback(() => setView('queue'), []);
    const goArchive = useCallback(() => { setArchiveSection('all'); setView('archive'); }, []);
    const openDoc = useCallback((id) => { setSelectedDocId(id); setView('document'); }, []);
    const backToFiles = useCallback(() => setView('files'), []);

    const selectSection = useCallback((id) => { setSelectedSectionId(id); setSelectedSubfolderId('all'); }, []);
    const selectSubfolder = useCallback((id) => setSelectedSubfolderId(id), []);
    const toggleExpandSection = useCallback((id) => {
        setExpandedSections((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
    }, []);

    // ---------- подразделы ----------
    const startAddSubfolder = useCallback((sectionId) => {
        setAddingSubfolderSectionId(sectionId);
        setSubfolderDraft('');
        setExpandedSections((prev) => (prev.includes(sectionId) ? prev : [...prev, sectionId]));
    }, []);
    const cancelAddSubfolder = useCallback(() => { setAddingSubfolderSectionId(null); setSubfolderDraft(''); }, []);
    const confirmAddSubfolder = useCallback(() => {
        const name = subfolderDraft.trim();
        const sectionId = addingSubfolderSectionId;
        if (!name || !sectionId) return;
        setProjects((prev) => prev.map((p) => {
            if (p.id !== selectedProjectId) return p;
            const existing = p.subfolders[sectionId] || [];
            return { ...p, subfolders: { ...p.subfolders, [sectionId]: [...existing, { id: 'sf' + Date.now(), name }] } };
        }));
        setAddingSubfolderSectionId(null);
        setSubfolderDraft('');
    }, [subfolderDraft, addingSubfolderSectionId, selectedProjectId]);

    // ---------- заметки документа ----------
    const addNote = useCallback((docId, text) => {
        const trimmed = text.trim();
        if (!trimmed) return;
        setDocs((prev) => prev.map((d) => (d.id !== docId ? d : {
            ...d, notes: [...d.notes, { id: 'note' + Date.now(), author: currentUser(), text: trimmed, isAI: false, date: 'только что' }],
        })));
    }, [role]);
    const deleteNote = useCallback((docId, noteId) => {
        setDocs((prev) => prev.map((d) => (d.id !== docId ? d : { ...d, notes: d.notes.filter((n) => n.id !== noteId) })));
    }, []);

    // ---------- загрузка пакета изменений ----------
    const openUpload = useCallback(() => { setUploadItems([]); setUploadComment(''); setUploadModalOpen(true); }, []);
    const closeUpload = useCallback(() => setUploadModalOpen(false), []);
    const addUploadFile = useCallback(() => {
        const n = uploadItems.length + 1;
        setUploadItems((prev) => [...prev, { id: 'up' + Date.now() + n, fileName: `скан_${String(n).padStart(3, '0')}.pdf`, mode: 'new', docId: '', newCode: '' }]);
    }, [uploadItems.length]);
    const removeUploadItem = useCallback((id) => setUploadItems((prev) => prev.filter((it) => it.id !== id)), []);
    const setUploadItemMode = useCallback((id, mode) => setUploadItems((prev) => prev.map((it) => (it.id === id ? { ...it, mode } : it))), []);
    const setUploadItemDoc = useCallback((id, docId) => setUploadItems((prev) => prev.map((it) => (it.id === id ? { ...it, docId } : it))), []);
    const setUploadItemCode = useCallback((id, code) => setUploadItems((prev) => prev.map((it) => (it.id === id ? { ...it, newCode: code } : it))), []);

    const submitUpload = useCallback(() => {
        if (uploadItems.length === 0 || !uploadComment.trim()) return;
        const csId = 'cs' + Date.now();
        const items = uploadItems.map((it) => {
            if (it.mode === 'replace') {
                const d = docs.find((x) => x.id === it.docId);
                return { docId: it.docId, code: d?.code || '', name: d?.name || '', action: 'replace', fromVersion: d?.approvedVersion || 0, fileName: it.fileName };
            }
            const code = it.newCode.trim() || ('НОВ-' + Math.floor(100 + Math.random() * 900));
            return { code, name: it.fileName, action: 'new', toVersion: 1, fileName: it.fileName };
        });

        setDocs((prev) => {
            let next = prev;
            for (const it of uploadItems) {
                if (it.mode === 'replace' && it.docId) {
                    next = next.map((d) => (d.id === it.docId ? { ...d, pendingChangesetId: csId } : d));
                } else if (it.mode === 'new') {
                    const code = it.newCode.trim() || ('НОВ-' + Math.floor(100 + Math.random() * 900));
                    next = [...next, {
                        id: 'doc' + Date.now() + Math.random().toString(36).slice(2, 6),
                        code, name: it.fileName, sectionId: selectedSectionId !== 'all' ? selectedSectionId : SECTION_DEFS[0].id,
                        subfolderId: selectedSubfolderId !== 'all' ? selectedSubfolderId : null,
                        projectId: selectedProjectId, approvedVersion: null, pendingChangesetId: csId, lastRejectedChangesetId: null,
                        versions: [], notes: [],
                    }];
                }
            }
            return next;
        });

        setChangesets((prev) => [...prev, {
            id: csId, projectId: selectedProjectId, author: currentUser(), authorInit: currentUser().split(' ').map((w) => w[0]).join(''),
            date: 'только что', status: 'pending', comment: uploadComment.trim(), rejectionComment: null, items,
        }]);
        setUploadModalOpen(false);
    }, [uploadItems, uploadComment, docs, selectedProjectId, selectedSectionId, selectedSubfolderId, role]);

    // ---------- переотправка отклонённого документа ----------
    const resubmitDoc = useCallback((docId) => {
        const doc = docs.find((d) => d.id === docId);
        if (!doc) return;
        const csId = 'cs' + Date.now();
        setChangesets((prev) => [...prev, {
            id: csId, projectId: doc.projectId, author: currentUser(), authorInit: currentUser().split(' ').map((w) => w[0]).join(''),
            date: 'только что', status: 'pending', comment: 'Исправленный пакет (взамен отклонённого)', rejectionComment: null,
            items: [{ docId: doc.id, code: doc.code, name: doc.name, action: 'replace', fromVersion: doc.approvedVersion || 0, fileName: doc.code + '_new.pdf' }],
        }]);
        setDocs((prev) => prev.map((d) => (d.id === docId ? { ...d, pendingChangesetId: csId, lastRejectedChangesetId: null } : d)));
    }, [docs, role]);

    // ---------- очередь утверждения ----------
    const approveChangeset = useCallback((csId) => {
        const cs = changesets.find((c) => c.id === csId);
        if (!cs) return;
        setDocs((prev) => prev.map((d) => {
            const item = cs.items.find((it) => it.docId === d.id);
            if (!item) return d;
            const newVersion = (d.approvedVersion || 0) + 1;
            return {
                ...d,
                approvedVersion: newVersion,
                pendingChangesetId: null,
                lastRejectedChangesetId: null,
                versions: [...d.versions, { v: newVersion, fileName: item.fileName, uploadedBy: cs.author, approvedBy: currentUser(), date: 'сегодня', comment: cs.comment }],
            };
        }));
        setChangesets((prev) => prev.map((c) => (c.id === csId ? { ...c, status: 'approved' } : c)));
    }, [changesets, role]);

    const openReject = useCallback((csId) => { setRejectTargetId(csId); setRejectComment(''); setRejectModalOpen(true); }, []);
    const closeReject = useCallback(() => setRejectModalOpen(false), []);
    const confirmReject = useCallback(() => {
        if (!rejectComment.trim() || !rejectTargetId) return;
        const cs = changesets.find((c) => c.id === rejectTargetId);
        if (cs) {
            setDocs((prev) => prev.map((d) => {
                const item = cs.items.find((it) => it.docId === d.id);
                if (!item) return d;
                return { ...d, pendingChangesetId: null, lastRejectedChangesetId: rejectTargetId };
            }));
        }
        setChangesets((prev) => prev.map((c) => (c.id === rejectTargetId ? { ...c, status: 'rejected', rejectionComment: rejectComment.trim() } : c)));
        setRejectModalOpen(false);
    }, [rejectComment, rejectTargetId, changesets]);

    // ---------- PDF-превью (мок) ----------
    const openPdf = useCallback((title) => { setPdfTitle(title); setPdfOverlayOpen(true); }, []);
    const closePdf = useCallback(() => setPdfOverlayOpen(false), []);

    // ---------- новый проект ----------
    const openNewProject = useCallback(() => { setNewProjectName(''); setNewProjectType('new-equip'); setNewProjectModalOpen(true); }, []);
    const closeNewProject = useCallback(() => setNewProjectModalOpen(false), []);
    const submitNewProject = useCallback(() => {
        const name = newProjectName.trim();
        if (!name) return;
        const typeLabel = (PROJECT_TYPE_OPTIONS.find((t) => t.id === newProjectType) || {}).label || '';
        setProjects((prev) => [...prev, {
            id: 'p' + Date.now(), name, type: typeLabel, glyph: name.slice(0, 2).toUpperCase(), kind: 'plan',
            status: 'Планирование', lead: currentUser(), members: [{ init: currentUser().split(' ').map((w) => w[0]).join(''), name: currentUser(), role: 'Инженер' }],
            updated: 'только что', desc: `Новый проект (${typeLabel}).`, activity: [], subfolders: {},
        }]);
        setNewProjectModalOpen(false);
    }, [newProjectName, newProjectType, role]);

    return {
        role, setRole,
        view, projects, docs, changesets,
        selectedProjectId, selectedSectionId, selectedSubfolderId, selectedDocId, filesQuery, setFilesQuery,
        archiveSection, setArchiveSection,
        expandedSections, addingSubfolderSectionId, subfolderDraft, setSubfolderDraft,
        uploadModalOpen, uploadItems, uploadComment, setUploadComment,
        rejectModalOpen, rejectComment, setRejectComment,
        newProjectModalOpen, newProjectName, setNewProjectName, newProjectType, setNewProjectType,
        pdfOverlayOpen, pdfTitle,
        projectTypeOptions: PROJECT_TYPE_OPTIONS,

        currentUser, projectDocs, projectChangesets, pendingCount, docBadge, changesetConflict,

        openProject, back, backToOverview, goFiles, backToFiles, goQueue, goArchive, openDoc,
        selectSection, selectSubfolder, toggleExpandSection,
        startAddSubfolder, cancelAddSubfolder, confirmAddSubfolder,
        addNote, deleteNote,
        openUpload, closeUpload, addUploadFile, removeUploadItem, setUploadItemMode, setUploadItemDoc, setUploadItemCode, submitUpload,
        resubmitDoc,
        approveChangeset, openReject, closeReject, confirmReject,
        openPdf, closePdf,
        openNewProject, closeNewProject, submitNewProject,
    };
}
