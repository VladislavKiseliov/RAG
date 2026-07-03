import { useState, useCallback } from 'react';
import { ENDPOINTS } from '../config/api';

export function useKnowledgeBase(api, showError) {
    const [documents, setDocuments] = useState([]);
    const [collections, setCollections] = useState([]);
    const [selectedCollection, setSelectedCollection] = useState('all');
    const [query, setQuery] = useState('');
    const [selectedDocId, setSelectedDocId] = useState(null);

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
        loadDocuments,
        upload,
        reindex,
    };
}
