import { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';
import { useApi, useShowError } from '../context/ApiContext';

export function useKnowledgeBase() {
    const api = useApi();
    const showError = useShowError();
    const [documents, setDocuments] = useState([]);
    const [collections, setCollections] = useState([]);
    const [selectedCollection, setSelectedCollection] = useState('all');
    const [query, setQuery] = useState('');
    const [selectedDocId, setSelectedDocId] = useState(null);
    const [chapterIdx, setChapterIdx] = useState(null);
    const [contentMode, setContentModeState] = useState('summary');
    const [chapterContent, setChapterContent] = useState(null);
    const [chapterContentLoading, setChapterContentLoading] = useState(false);
    const [sourceViewerOpen, setSourceViewerOpen] = useState(false);

    // Список отдаёт только summary — главы (sections) для оглавления читалки грузятся лениво
    // здесь, только для реально открытого документа, а не для всей библиотеки сразу.
    const openDoc = useCallback((id) => {
        setSelectedDocId(id);
        setChapterIdx(null);
        setContentModeState('summary');
        setSourceViewerOpen(false);
        api.get(ENDPOINTS.KNOWLEDGE_DOCUMENT_STATUS(id))
            .then((detail) => {
                setDocuments((prev) => prev.map((d) => (d.id === id ? { ...d, ...detail } : d)));
            })
            .catch((e) => showError(e.message));
    }, [api, showError]);

    const closeDoc = useCallback(() => {
        setSelectedDocId(null);
        setSourceViewerOpen(false);
    }, []);

    const openSource = useCallback(() => setSourceViewerOpen(true), []);
    const closeSource = useCallback(() => setSourceViewerOpen(false), []);

    const openChapter = useCallback((i) => {
        setChapterIdx(i);
        setContentModeState('summary');
        setChapterContent(null);
    }, []);

    const backToOverview = useCallback(() => {
        setChapterIdx(null);
        setContentModeState('summary');
    }, []);

    // Текст/таблицы главы грузятся лениво — только когда реально открыт режим «Весь текст».
    const setContentMode = useCallback((mode) => {
        setContentModeState(mode);
        if (mode !== 'full' || chapterContent || selectedDocId == null || chapterIdx == null) return;

        setChapterContentLoading(true);
        api.get(ENDPOINTS.KNOWLEDGE_DOCUMENT_CHAPTER(selectedDocId, chapterIdx))
            .then(setChapterContent)
            .catch((e) => showError(e.message))
            .finally(() => setChapterContentLoading(false));
    }, [api, showError, selectedDocId, chapterIdx, chapterContent]);

    const loadDocuments = useCallback(async () => {
        try {
            const data = await api.get(ENDPOINTS.KNOWLEDGE_DOCUMENTS);
            setDocuments(data.documents || []);
            setCollections(data.collections || []);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const patchStatus = useCallback(async (docId, status) => {
        try {
            const updated = await api.patch(ENDPOINTS.KNOWLEDGE_DOCUMENT_STATUS(docId), { status });
            setDocuments((prev) => prev.map((d) => (d.id === docId ? updated : d)));
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError]);

    const upload = useCallback(async (file) => {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const doc = await api.postForm(ENDPOINTS.KNOWLEDGE_DOCUMENTS, formData);
            setDocuments((prev) => [doc, ...prev]);
            setSelectedCollection('personal');
            setTimeout(() => patchStatus(doc.id, 'indexed'), 2600);
        } catch (e) {
            showError(e.message);
        }
    }, [api, showError, patchStatus]);

    const reindex = useCallback(async (docId) => {
        await patchStatus(docId, 'processing');
        setTimeout(() => patchStatus(docId, 'indexed'), 1800);
    }, [patchStatus]);

    return {
        documents,
        collections,
        selectedCollection,
        setSelectedCollection,
        query,
        setQuery,
        selectedDocId,
        setSelectedDocId,
        chapterIdx,
        contentMode,
        setContentMode,
        chapterContent,
        chapterContentLoading,
        sourceViewerOpen,
        openSource,
        closeSource,
        openDoc,
        closeDoc,
        openChapter,
        backToOverview,
        loadDocuments,
        upload,
        reindex,
    };
}
