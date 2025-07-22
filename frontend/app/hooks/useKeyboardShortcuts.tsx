import { useHotkeys } from 'react-hotkeys-hook';
import { useState } from 'react';

export const useKeyboardShortcuts = (initialShortcuts = {}) => {
  const [shortcuts, setShortcuts] = useState(initialShortcuts);

  const addShortcut = (keys, callback) => {
    setShortcuts((prev) => ({ ...prev, [keys]: callback }));
  };

  const removeShortcut = (keys) => {
    setShortcuts((prev) => {
      const newShortcuts = { ...prev };
      delete newShortcuts[keys];
      return newShortcuts;
    });
  };

  Object.entries(shortcuts).forEach(([keys, callback]) => {
    useHotkeys(keys, callback);
  });

  return { addShortcut, removeShortcut, shortcuts };
};