import { createContext, useContext } from 'react';

export const ApiContext = createContext(null);

export function useApi() {
    return useContext(ApiContext)?.api;
}

export function useShowError() {
    return useContext(ApiContext)?.showError;
}