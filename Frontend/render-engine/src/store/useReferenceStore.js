import { create } from 'zustand';

const useReferenceStore = create((set) => ({
  activeReference: null,
  setActiveReference: (refId) => set({ activeReference: refId }),
}));

export default useReferenceStore;
